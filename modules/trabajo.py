"""La descarga como trabajo del servidor: corre en su propio hilo, no dentro de la corrida de Streamlit.

Antes la descarga vivia en la corrida que dibuja la pantalla: cualquier recarga la cortaba y habia que rescatar lo
guardado con cuidado. Ahora la pantalla solo mira el trabajo (avance, fila, resultado) y puede recargarse, cambiar
de idioma o perder la conexion un rato sin que la descarga se entere.

- La sesion guarda su `Trabajo`; ademas queda en un registro del servidor por su `id`, que viaja en la direccion
  (`?descarga=`): una pestaña recargada (sesion nueva) lo vuelve a encontrar con `buscar`.
- La pantalla llama a `latido()` cada segundo. Si pasan `GRACIA` segundos sin latidos (pestaña cerrada), el trabajo
  se detiene solo, para no seguir pidiendole datos al IDEAM ni ocupar un cupo sin que nadie mire.
- Los trabajos terminados salen del registro a los `CADUCIDAD` segundos sin latidos (un ZIP pesa decenas de MB).
"""
import secrets
import threading
import time
import traceback

from modules import ideam_downloader

GRACIA = 120       # segundos sin que nadie mire antes de detener una descarga en curso
CADUCIDAD = 900    # segundos sin que nadie mire antes de olvidar un trabajo terminado

_registro = {}
_candado = threading.Lock()


class Trabajo:
    """Una descarga. `estado`: "en_curso", "lista", "error" o "detenida"."""

    def __init__(self, datos, sesion=None):
        self.id = secrets.token_urlsafe(12)
        self.datos = datos              # lo que se pidio (estaciones, periodo, parametro…)
        self.sesion = sesion or {}      # lo que la pantalla necesita para volver al mapa tras una recarga
        self.estado = "en_curso"
        self.avance = None              # cifras del avance (ideam_downloader.html_avance); None mientras prepara
        self.espera = None              # {"puesto", "falta", "desde"} mientras espera cupo; None si ya descarga
        self.resultado = None           # el de procesar_descargas, o {"error": ...}
        self.parcial = {}               # ZIP de lo ya guardado, si se corto
        self.detener = threading.Event()
        self.visto = time.time()

    def latido(self):
        self.visto = time.time()

    def abandonado(self):
        return time.time() - self.visto > GRACIA

    def iniciar(self):
        with _candado:
            _limpiar()
            _registro[self.id] = self
        threading.Thread(target=self._correr, name=f"descarga-{self.id}", daemon=True).start()
        return self

    def _vigilar(self, avance=None):
        """Guarda el avance y, si ya nadie mira la descarga, pide detenerla."""
        if avance is not None:
            self.avance = avance
        if self.abandonado():
            self.detener.set()

    def _correr(self):
        d = self.datos
        # Turno: como mucho MAX_DESCARGAS_SIMULTANEAS descargas a la vez en el servidor (entre todos los usuarios),
        # para no saturar al IDEAM. Si no hay cupo, se espera en fila
        cupos = ideam_downloader.cupos_descarga()
        turnos = ideam_downloader.turnos_descarga()
        turno = object()
        tomado = False
        try:
            _, _, segundos = ideam_downloader.plan_descarga(d["estaciones"], d["ini"], d["fin"], d["param"])
            tomado = cupos.acquire(blocking=False)
            if not tomado:
                with turnos["candado"]:
                    turnos["fila"].append(turno)
                desde = time.time()
                while not tomado:
                    puesto, falta = ideam_downloader.espera_estimada(turno)
                    self.espera = {"puesto": puesto, "falta": falta, "desde": desde}
                    self._vigilar()
                    if self.detener.is_set():
                        raise ideam_downloader.DescargaDetenida()
                    tomado = cupos.acquire(timeout=1)
            with turnos["candado"]:
                if turno in turnos["fila"]:
                    turnos["fila"].remove(turno)
                turnos["en_curso"][turno] = (time.time(), segundos)
            self.espera = None
            # el ZIP sale plano: las carpetas por completitud se eligen al final, antes de descargarlo
            resultado = ideam_downloader.procesar_descargas(
                d["estaciones"], False, d["ini"], d["fin"], d["param"],
                {"avance": self._vigilar, "parcial": self.parcial, "detener": self.detener})
            self.resultado = resultado or {"error": "No se pudo completar la descarga."}
            self.estado = "error" if "error" in self.resultado else "lista"
        except ideam_downloader.DescargaDetenida:
            self.estado = "detenida"
        except Exception:
            traceback.print_exc()
            self.resultado = {"error": "No se pudo completar la descarga."}
            self.estado = "error"
        finally:
            # El cupo se devuelve siempre: al terminar, al detener o si algo falla (tambien mientras espera turno)
            self.espera = None
            with turnos["candado"]:
                if turno in turnos["fila"]:
                    turnos["fila"].remove(turno)
                turnos["en_curso"].pop(turno, None)
            if tomado:
                cupos.release()


def _limpiar():
    """Saca del registro los trabajos terminados que nadie mira hace rato (con el candado tomado)."""
    ahora = time.time()
    for clave in [k for k, t in _registro.items() if t.estado != "en_curso" and ahora - t.visto > CADUCIDAD]:
        del _registro[clave]


def buscar(clave):
    """El trabajo con ese id, si sigue en el servidor (None si no existe o ya caduco)."""
    with _candado:
        _limpiar()
        return _registro.get(clave) if clave else None


def olvidar(trabajo):
    """Detiene el trabajo (si corria) y lo saca del registro: la persona empezo otra consulta."""
    if trabajo is None:
        return
    trabajo.detener.set()
    with _candado:
        _registro.pop(trabajo.id, None)
