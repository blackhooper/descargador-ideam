import json
import re
import threading
import time
import unicodedata
from datetime import date

import pandas as pd
import shapely
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from modules import (escaner, estilo, geo_input, geo_utils, map_view, ideam_catalog, ideam_parameters,
                     ideam_downloader, panel_estadisticas, terreno)
from modules.calidad import CLASES_CALIDAD, filtrar_descargables, clasificar_calidad

st.set_page_config(page_title="Descargador IDEAM", page_icon="🌧️", layout="wide", initial_sidebar_state="collapsed")

# ===========================================================================
# TRES PANTALLAS SOBRE UN MISMO MAPA
#   parametros -> mapa -> descarga ("Exportacion")
# El mapa 2D va siempre en el mismo lugar del arbol de Streamlit (el escenario), asi no se vuelve a cargar al
# cambiar de pantalla: en Parametros se carga por detras mientras la persona elige que descargar.
# ===========================================================================
ss = st.session_state
# Preferencias de apariencia y rendimiento: viajan en la direccion (?tema=, ?contraste=, ?lite=) para que sobrevivan
# a una recarga. Sin parametro = lo que pida el equipo (tema y contraste) y calidad completa.
_q = st.query_params
for clave, valor in {"paso": "parametros", "vista": "2D", "cuenca": None, "version_mapa": 0, "version_subida": 0,
                     "estacion_sel": None, "_prev_sel": {}, "consulta": None, "descarga": None, "resultado": None,
                     "estado_descarga": None, "excluidas": set(), "version_lista": 0, "subida_abierta": False,
                     "saltos": 0,
                     "tema": _q.get("tema") if _q.get("tema") in estilo.TEMAS else "sistema",
                     "contraste": _q.get("contraste") if _q.get("contraste") in estilo.CONTRASTES else "sistema",
                     "lite": _q.get("lite") == "1"}.items():
    ss.setdefault(clave, valor)
if (ss.paso not in ("parametros", "mapa", "descarga") or (ss.paso == "mapa" and not ss.consulta)
        or (ss.paso == "descarga" and not ss.descarga)):
    ss.paso = "parametros"
PANTALLA = {"parametros": "parametros", "mapa": "mapa", "descarga": "exportar"}[ss.paso]

# Para saber si el mapa 2D sigue montado en el navegador: si la corrida anterior lo dibujo, es el mismo
ss._mapa_en_run_anterior = ss.get("_mapa_en_esta_run", False)
ss._mapa_en_esta_run = False

estilo.aplicar(ss.tema, ss.contraste, ss.lite)
estilo.guiones_globales(PANTALLA)
# Guion que colorea el relieve en la textura "Altura": se instala desde el arranque de la pagina (no cuesta nada
# si no se usa) para que ya este puesto antes de que el visor 3D pida sus imagenes
with st.container(key="y2k_hipso"):
    components.html(terreno.HIPSOMETRICO, height=0)
# Aqui (arriba, sin alto) se pone despues el CSS que tapa el visor 3D mientras arranca la secuencia de entrada
velo_3d = st.container(key="y2k_velo")
PALETA = estilo.paleta(ss.tema)
# Ajustes (arriba a la derecha, en todas las pantallas). Durante una descarga se bloquean: cambiar algo recargaria
# la pagina y la detendria
estilo.ajustes(bloqueado=ss.paso == "descarga" and ss.estado_descarga in ("pendiente", "en_curso"))

if not all(ideam_downloader.credenciales_ideam()):
    st.error("Faltan el usuario y la clave del portal DHIME del IDEAM. En tu computador van en "
             "`.streamlit/secrets.toml`; en Streamlit Cloud, en Settings → Secrets de la app, así:\n\n"
             "```toml\n[ideam]\nusuario = \"...\"\nclave = \"...\"\n```")
    st.stop()

catalogo = ideam_catalog.load_ideam_catalog()
# El mapa vive aqui, en la misma posicion en las tres pantallas (no mover esta linea por debajo de nada condicional)
escenario = st.container(key="y2k_escenario")
# Los huecos de las tres pantallas van siempre, en este orden (vacios los de las otras pantallas). Asi cada uno
# conserva su lugar en la pagina: al cambiar de pantalla, lo de la anterior no aparece dentro de la nueva mientras
# Streamlit termina la corrida (y el CSS lo oculta enseguida por su clave). Lo condicional va despues de todos.
hueco_inicio = st.container(key="y2k_inicio")
hueco_panel = st.container(key="y2k_panel")
hueco_abrir = st.container(key="y2k_abrir")
hueco_herr = st.container(key="y2k_herr")
hueco_dock = st.container(key="y2k_dock", horizontal=True, gap=None)
hueco_ficha = st.container(key="y2k_ficha")
hueco_exportar = st.container(key="y2k_exportar")
hueco_ocultos = st.container(key="y2k_ocultos")


# ===========================================================================
# Cargas por detras: lista de parametros (al arrancar el servidor) y series de cada parametro (al elegirlo)
# ===========================================================================
@st.cache_resource(show_spinner=False)
def _iniciar_precarga_servidor():
    """La lista de parametros del IDEAM tarda unos segundos (decenas de consultas). Se pide por detras apenas arranca
    el servidor; mientras tanto la pantalla de Parametros muestra su desplegable en gris.
    Devuelve el estado compartido: {"listo": bool, "error": str | None}."""
    estado = {"listo": False, "error": None}

    def trabajo():
        try:
            ideam_parameters.obtener_catalogo_parametros()
        except Exception as e:  # sin red o IDEAM caido: se ofrece reintentar
            estado["error"] = str(e)
        finally:
            estado["listo"] = True

    threading.Thread(target=trabajo, daemon=True, name="precarga-ideam").start()
    return estado


@st.cache_resource(show_spinner=False)
def _registro_series():
    return {"candado": threading.Lock(), "estado": {}}


def _precargar_series(etiqueta):
    """Pide por detras que estaciones tienen la serie `etiqueta` (lo que necesita el mapa para evaluar). Compartido
    entre sesiones; si fallo, se reintenta a los 30 s. Devuelve {"listo": bool, "error": str | None}."""
    reg = _registro_series()
    with reg["candado"]:
        e = reg["estado"].get(etiqueta)
        vigente = e and (not e["listo"] or (e["error"] is None and time.time() - e["t"] < 6 * 3600 - 120)
                         or (e["error"] and time.time() - e["t"] < 30))
        if vigente:
            return e
        e = {"listo": False, "error": None, "t": time.time()}
        reg["estado"][etiqueta] = e

    def trabajo():
        try:
            ideam_downloader.obtener_series_disponibles(etiqueta)
        except Exception as ex:
            e["error"] = str(ex)
        finally:
            e["listo"] = True

    threading.Thread(target=trabajo, daemon=True, name=f"series-{etiqueta}").start()
    return e


def _reintentar_catalogo():
    _iniciar_precarga_servidor.clear()
    limpiar = getattr(ideam_parameters.obtener_catalogo_parametros, "clear", None)
    if limpiar:
        limpiar()


_precarga = _iniciar_precarga_servidor()

# Condiciones de uso de los datos (terminos del portal DHIME)
TEXTO_LEGAL = ("Los datos provienen del IDEAM y su descarga está autorizada para uso personal, privado y no "
               "comercial. No pueden comercializarse ni venderse. Todo trabajo que los utilice debe citar la "
               "fuente (el ZIP incluye la cita en CITACION.txt). El IDEAM no se hace responsable del uso de los "
               "datos ni de las interpretaciones o inferencias derivadas de ellos. Esta es una herramienta "
               "independiente, no oficial del IDEAM.")


# ===========================================================================
# Utilidades
# ===========================================================================
def _num(n):
    return f"{n:,.0f}".replace(",", ".")


def _firma(gdf):
    """Huella de una geometria para saber si la cuenca cambio de verdad."""
    if gdf is None or gdf.empty:
        return None
    return shapely.normalize(shapely.set_precision(gdf.union_all(), 1e-5)).wkt


def _area_km2(gdf):
    """Area de la cuenca en km² (en la proyeccion de Colombia que usa tambien el buffer)."""
    try:
        return float(gdf[["geometry"]].to_crs(epsg=3116).area.sum()) / 1e6
    except Exception:
        return None


def _periodo(ini, fin):
    """Periodo corto para los textos: "2000–2020" si son anos completos; si no, las fechas."""
    if (ini.month, ini.day, fin.month, fin.day) == (1, 1, 12, 31):
        return f"{ini.year}–{fin.year}" if ini.year != fin.year else str(ini.year)
    return f"{ini:%d/%m/%Y} – {fin:%d/%m/%Y}"


def _frecuencia_txt(frecuencia):
    """Frecuencia para una frase ("frecuencia diaria", "frecuencia cada 10 minutos")."""
    f = re.sub(r"^0(\d)", r"\1", frecuencia.lower())
    return {"diario": "diaria", "horario": "horaria"}.get(f, f)


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")


def _parametros_de(catalogo_param, frecuencia):
    """{etiqueta: parametro} de todas las variables con esa frecuencia, con un nombre legible en "nombre": la
    descripcion y la unidad, con la variable delante si la descripcion no la nombra. Sin codigos (salvo que dos
    parametros se llamen igual)."""
    params = [p for p in catalogo_param if p["frecuencia"] == frecuencia]
    nombres = {}
    for p in params:
        var = p["variable_nombre"]
        desc = p["descripcion"]
        nombre = desc if _sin_tildes(var.split()[0]) in _sin_tildes(desc) else f"{var} · {desc[:1].lower()}{desc[1:]}"
        nombres[p["etiqueta"]] = f"{nombre} ({p['unidad']})" if p["unidad"] else nombre
    repetidos = {n for n in nombres.values() if list(nombres.values()).count(n) > 1}
    ordenados = sorted(params, key=lambda p: (_sin_tildes(p["variable_nombre"]), _sin_tildes(nombres[p["etiqueta"]])))
    return {p["etiqueta"]: {**p, "nombre": nombres[p["etiqueta"]] + (f" · {p['etiqueta']}" if nombres[p["etiqueta"]] in repetidos else "")}
            for p in ordenados}


def _param_de(etiqueta):
    """Parametro del catalogo por su etiqueta (None si la lista no esta o ya no lo trae)."""
    try:
        catalogo_param = ideam_parameters.obtener_catalogo_parametros()
    except Exception:
        return None
    return next((p for p in catalogo_param if p["etiqueta"] == etiqueta), None)


def _sincronizar(fuente, valor, a_codigo):
    """Marca como seleccionada la estacion que se eligio en `fuente` (si esa fuente cambio)."""
    firma = json.dumps(valor, sort_keys=True, default=str)
    if ss._prev_sel.get(fuente) == firma:
        return False
    ss._prev_sel[fuente] = firma
    codigo = a_codigo(valor)
    if codigo:
        ss.estacion_sel = str(codigo)
        return True
    return False


def _estacion_cercana(zona, clic):
    if zona is None or zona.empty or not clic:
        return None
    d = (zona.geometry.x - clic["lng"]) ** 2 + (zona.geometry.y - clic["lat"]) ** 2
    idx = d.idxmin()
    return ideam_downloader.codigo_de_estacion(zona.loc[idx], idx) if d.min() < 1e-6 else None


def _nombre_archivo(texto, respaldo):
    """Nombre de archivo valido en Windows a partir de lo que escribio el usuario."""
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (texto or "").strip())
    limpio = re.sub(r"\.zip$", "", limpio, flags=re.IGNORECASE).strip(" .")
    return limpio or respaldo


def _es_celular():
    """True si la pagina se abrio desde un celular o tablet (segun el navegador)."""
    try:
        agente = st.context.headers.get("User-Agent", "")
    except Exception:
        return False
    return any(marca in agente for marca in ("Mobi", "Android", "iPhone", "iPad"))


def _hex_a_rgb(color):
    color = color.lstrip("#")
    return [int(color[i:i + 2], 16) for i in (0, 2, 4)]


def _revisar_altitudes(zona):
    """Compara la altitud del catalogo con el terreno real (columnas 'terreno' y 'altitud_dudosa')."""
    terreno.precargar(list(zip(zona.geometry.x, zona.geometry.y)))
    revision = [terreno.revisar_altitud(r.get("altitud"), r.geometry.x, r.geometry.y) for _, r in zona.iterrows()]
    zona["terreno"] = [t for t, _ in revision]
    zona["altitud_dudosa"] = [d for _, d in revision]


def _estaciones_3d(zona, excluidas):
    salida = []
    for idx, r in zona.iterrows():
        codigo = ideam_downloader.codigo_de_estacion(r, idx)
        # En 3D solo las que tienen serie en DHIME (salvo la seleccionada): las demas no se
        # pueden descargar y llenan el relieve de pines
        if r.get("Serie DHIME") == "No" and codigo != ss.estacion_sel:
            continue
        pct = r.get("Porcentaje (%)")
        evaluada = pct is not None and pd.notna(pct)
        tiene = bool(evaluada and r.get("Serie DHIME") == "Sí" and r.get("Cantidad Probable", 0) > 0)
        ok = tiene and codigo not in excluidas
        try:
            altitud = float(r.get("altitud"))
        except (TypeError, ValueError):
            altitud = None
        dudosa = bool(r.get("altitud_dudosa")) and r.get("terreno") is not None
        salida.append({
            "codigo": codigo,
            "nombre": str(r.get("nombre", "")),
            "lon": float(r.geometry.x), "lat": float(r.geometry.y),
            "altitud": altitud,
            "altitud_txt": f"{_num(altitud)} m" if altitud else "altitud sin dato",
            "pct_txt": (f"{pct:.0f} %" + (" · excluida" if tiene and not ok else "")) if evaluada else "sin evaluar",
            "color": _hex_a_rgb(clasificar_calidad(pct)["color"]) if ok else [150, 160, 180],
            "ok": ok,
            "zona": "En el área" if r.get("zona") == "cuenca" else "En el buffer",
            "alerta": f"⚠ Altitud dudosa: el relieve marca {_num(r['terreno'])} m" if dudosa else "",
            "terreno": r.get("terreno"),
            "dudosa": dudosa,
        })
    return salida


# ===========================================================================
# Acciones (callbacks: corren antes del guion, asi la pantalla nueva aparece en la misma recarga)
# ===========================================================================
def _ir_mapa(clave_param):
    nueva = {"etiqueta": ss.get(clave_param), "ini": ss.get("f_ini"), "fin": ss.get("f_fin")}
    if nueva != ss.consulta:
        ss.excluidas = set()   # otro parametro u otro periodo: las estaciones quitadas antes no aplican
    ss.consulta = nueva
    ss.paso = "mapa"


def _volver_parametros():
    ss.paso = "parametros"


def _borrar_cuenca():
    ss.cuenca = None
    ss.version_mapa += 1
    ss.estacion_sel = None
    ss.excluidas = set()


def _abrir_subida():
    ss.subida_abierta = True


def _cerrar_subida():
    ss.subida_abierta = False


def _recargar_3d():
    """«Seguir intentando» tras un fallo del 3D: visor nuevo en el mismo modo (la camara la repone el navegador)."""
    ss.version_3d = ss.get("version_3d", 0) + 1


def _lite_reintentar():
    """«Activar Lite y reintentar»: solo cuando el usuario lo elige en un aviso de fallo."""
    estilo.poner_lite(True)
    ss.version_3d = ss.get("version_3d", 0) + 1


def _pasar_a_2d():
    ss.vista = "2D"


def _repetir_intro():
    ss._repetir_intro = True


def _preparar(datos):
    ss.descarga = datos
    ss.resultado = None
    ss.estado_descarga = "pendiente"
    ss.pop("nombre_zip", None)  # cada descarga nueva arranca con su nombre sugerido
    ss.paso = "descarga"


def _detener():
    ss.estado_descarga = "detenida"


def _reintentar_descarga():
    ss.resultado = None
    ss.estado_descarga = "pendiente"


def _volver_mapa():
    ss.paso = "mapa"


def _nueva_consulta():
    _borrar_cuenca()
    ss.descarga = None
    ss.resultado = None
    ss.estado_descarga = None
    ss.paso = "parametros"


def _vigia(pendiente):
    """Mientras algo carga por detras, este fragmento revisa cada segundo y, al terminar, recarga la pagina una vez."""
    @st.fragment(run_every=1.0)
    def _vigilar():
        if not pendiente():
            st.rerun()
    _vigilar()


# ===========================================================================
# Mapa 2D (escenario): el mismo en las tres pantallas
# ===========================================================================
def _capa_catalogo():
    """Capa del catalogo nacional agrupado (sin area marcada). Se arma de nuevo en cada corrida: folium no deja
    volver a dibujar el mismo objeto (el agrupador quedaria sin definir)."""
    return map_view.capa_dinamica(catalogo=catalogo)


def mapa_2d(capa, centro=None, zoom=None):
    """Mapa base de Leaflet a pantalla completa. El mapa base solo lleva la cuenca cuando se monta de cero (archivo,
    vuelta del 3D, "Borrar"). Un rectangulo recien dibujado ya vive en el navegador: meterlo al mapa base cambiaria
    el componente y Streamlit lo reconstruiria (pantalla en blanco y salto de zoom). Estaciones y buffer van aparte."""
    viva = ss._mapa_en_run_anterior and ss.get("_mapa_version") == ss.version_mapa
    if not viva:
        ss._base_cuenca = ss.cuenca
        ss._mapa_version = ss.version_mapa
    base = map_view.mapa_base(ss.get("_base_cuenca"), ss.tema)
    # El alto real lo pone el CSS (llena la ventana); 650 es solo el valor inicial del componente
    with st.container(key="y2k_mapa2d"):
        retorno = st_folium(base, key=f"mapa2d_{ss.version_mapa}", height=650, use_container_width=True,
                            feature_group_to_add=capa, center=centro, zoom=zoom,
                            returned_objects=["all_drawings", "last_object_clicked"])
    ss._mapa_en_esta_run = True
    return retorno


def mapa_de_fondo(nuevo_permitido=True):
    """Mapa detras de Parametros y Exportacion: el de la pantalla del mapa, quieto y velado. Si no estaba montado y
    `nuevo_permitido` es False (durante una descarga), no se monta: al cargar podria recargar la pagina."""
    if not nuevo_permitido and not (ss._mapa_en_run_anterior and ss.get("_mapa_version") == ss.version_mapa):
        return
    args = ss.get("_capa_args")
    capa = map_view.capa_dinamica(*args) if ss.cuenca is not None and args is not None else _capa_catalogo()
    with escenario:
        mapa_2d(capa)


# ===========================================================================
# PANTALLA 1: PARAMETROS
# ===========================================================================
def pantalla_parametros():
    mapa_de_fondo()
    pendientes = []
    with hueco_inicio:
        estilo.cabecera_inicio()
        avanzado = bool(ss.get("avanzado", False))
        frecuencias = ideam_parameters.FRECUENCIAS_AVANZADAS if avanzado else ideam_parameters.FRECUENCIAS_NORMALES
        estilo.etiqueta("Frecuencia")
        frecuencia = st.selectbox("Frecuencia", frecuencias, key=f"frec_{int(avanzado)}", label_visibility="collapsed",
                                  persist_state="session")

        # Lista de parametros del IDEAM: el desplegable queda en gris hasta que carga (el punto se enciende)
        estado_cat = "cargando" if not _precarga["listo"] else ("error" if _precarga["error"] else "listo")
        opciones = {}
        if estado_cat == "listo":
            try:
                opciones = _parametros_de(ideam_parameters.obtener_catalogo_parametros(), frecuencia)
            except Exception as e:
                estado_cat, _precarga["error"] = "error", str(e)
        if estado_cat == "cargando":
            pendientes.append(lambda: not _precarga["listo"])
        estilo.etiqueta("Parámetro", punto=estado_cat)
        etiquetas = list(opciones)
        clave_param = f"par_{frecuencia}"
        if etiquetas:
            # se puede escribir para buscar; por defecto, el primero de precipitacion
            defecto = next((i for i, e in enumerate(etiquetas) if opciones[e]["variable"] == "PRECIPITACION"), 0)
            etiqueta = st.selectbox("Parámetro", etiquetas, index=defecto, key=clave_param, label_visibility="collapsed",
                                    format_func=lambda e: opciones[e]["nombre"] if e in opciones else e,
                                    placeholder="Escribe para buscar", persist_state="session")
        else:
            # mientras carga (o si fallo), un desplegable gris que no se puede abrir; otra clave, para que el de
            # verdad nazca con su valor por defecto
            etiqueta = st.selectbox("Parámetro", [], index=None, key="par_espera", label_visibility="collapsed",
                                    disabled=True, placeholder=("Cargando la lista del IDEAM…" if estado_cat == "cargando"
                                                                else "No se pudo cargar la lista" if estado_cat == "error"
                                                                else "No hay parámetros con esta frecuencia"))
        param = opciones.get(etiqueta) if etiqueta else None
        if estado_cat == "error":
            st.error(f"No se pudo cargar la lista de parámetros del IDEAM. {_precarga['error'] or ''}".strip(),
                     icon=":material/cloud_off:")
            st.button("Reintentar", key="reintentar_catalogo", icon=":material/replay:", on_click=_reintentar_catalogo)

        c1, c2 = st.container(key="y2k_fechas").columns(2, gap="small")   # en una fila tambien en el celular
        with c1:
            estilo.etiqueta("Desde")
            fecha_ini = st.date_input("Desde", date(2000, 1, 1), min_value=date(1920, 1, 1), max_value=date.today(),
                                      key="f_ini", format="DD/MM/YYYY", label_visibility="collapsed", persist_state="session")
        with c2:
            estilo.etiqueta("Hasta")
            fecha_fin = st.date_input("Hasta", date(2020, 12, 31), min_value=date(1920, 1, 1), max_value=date.today(),
                                      key="f_fin", format="DD/MM/YYYY", label_visibility="collapsed", persist_state="session")
        fechas_ok = fecha_ini < fecha_fin
        if not fechas_ok:
            st.error("La fecha inicial debe ser anterior a la final.", icon=":material/event_busy:")
        filas = ideam_parameters.filas_estimadas(param, fecha_ini, fecha_fin) if param and fechas_ok else 0
        excede = filas > ideam_parameters.MAX_FILAS_EXCEL
        if excede:
            st.warning(f"Con frecuencia {_frecuencia_txt(param['frecuencia'])}, este periodo daría hasta {_num(filas)} filas por "
                       "estación y Excel admite alrededor de un millón por hoja. Acorta el periodo.",
                       icon=":material/table_rows:")

        with st.expander("Ajustes avanzados", icon=":material/tune:"):
            st.toggle("Series cada 2, 5 o 10 minutos", key="avanzado", persist_state="session",
                      help="Descarga avanzada: series con muchísimos datos. El IDEAM entrega solo un mes por consulta.")
            if avanzado:
                st.warning("El IDEAM entrega estos datos de **un mes por consulta** (10 años = 120 consultas por estación). "
                           "Usa periodos cortos y pocas estaciones.", icon=":material/hourglass_top:")
            st.checkbox("Separar el ZIP en carpetas por cobertura", value=True, key="carpetas", persist_state="session",
                        help="Alta (70–100 %), media (50–70 %), baja (25–50 %) y crítica (0–25 %) del periodo consultado.")

        # Series del parametro elegido: se piden por detras mientras la persona termina de elegir
        series = _precargar_series(param["etiqueta"]) if param else None
        if series and not series["listo"]:
            pendientes.append(lambda s=series: not s["listo"])
        if estado_cat == "cargando":
            texto, estado = "Cargando la lista de parámetros del IDEAM…", "cargando"
        elif estado_cat == "error":
            texto, estado = "Sin la lista de parámetros no se puede continuar.", "error"
        elif param is None:
            texto, estado = "Elige un parámetro para continuar.", "pendiente"
        elif not fechas_ok or excede:
            texto, estado = "Revisa las fechas para continuar.", "error"
        elif not series["listo"]:
            texto, estado = "Consultando qué estaciones tienen este parámetro…", "cargando"
        elif series["error"]:
            texto, estado = "El IDEAM no respondió; se volverá a intentar en el mapa.", "listo"
        else:
            texto, estado = "Todo listo: el mapa y los datos ya cargaron.", "listo"
        st.button("Seleccionar área en el mapa", type="primary", key="ir_mapa", icon=":material/arrow_forward:",
                  icon_position="right", width="stretch", disabled=estado != "listo", on_click=_ir_mapa,
                  args=(clave_param,))
        estilo.espera(texto, estado)
        estilo.como_funciona()
        estilo.toggle_lite("lite_inicio", "Modo Lite",
                           "Para equipos con poca memoria gráfica: sin desenfoque ni animaciones y con un 3D más "
                           "liviano. Los datos y las funciones son los mismos. Puedes cambiarlo luego en Ajustes.")
        estilo.pie_inicio(TEXTO_LEGAL)
    with hueco_ocultos:
        if pendientes:
            _vigia(lambda: any(p() for p in pendientes))


# ===========================================================================
# PANTALLA 2: MAPA
# ===========================================================================
@st.dialog("Subir el contorno del área", width="medium", on_dismiss=_cerrar_subida)
def dialogo_subida():
    st.html('<p class="y2k-hint">SHP (en ZIP o suelto), GeoJSON, KML, KMZ o GPKG. Si el archivo no trae sistema de '
            'coordenadas, te avisaremos.</p>')
    # la clave cambia al usar el archivo: asi el cargador queda vacio para la siguiente vez
    archivos = st.file_uploader("Archivo del área", type=geo_input.EXTENSIONES_ACEPTADAS, accept_multiple_files=True,
                                label_visibility="collapsed", key=f"subida_{ss.version_subida}")
    if not archivos:
        return
    gdf_raw = geo_input.load_vector_file(archivos)
    if gdf_raw is None:
        return
    valido, mensaje = geo_utils.validate_geometry(gdf_raw)
    if not valido:
        st.error(mensaje)
        return
    try:
        gdf = geo_utils.reproject_to_epsg4326(gdf_raw)
    except ValueError as e:
        st.error(str(e))
        return
    poligonos = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
    if poligonos.empty:
        st.error("El archivo solo tiene puntos o líneas. Sube el contorno (polígono) del área.")
        return
    if mensaje != "Geometría válida.":
        st.warning(mensaje)
    st.success(f"Archivo válido: {len(poligonos)} {'polígonos' if len(poligonos) != 1 else 'polígono'}.")
    if st.button("Usar esta área", type="primary", width="stretch", key="usar_subida", icon=":material/check:"):
        ss.cuenca = poligonos[["geometry"]].reset_index(drop=True)
        ss.version_mapa += 1
        ss.version_subida += 1
        ss.estacion_sel = None
        ss.excluidas = set()
        ss.subida_abierta = False
        st.rerun()


def pantalla_mapa():
    consulta = ss.consulta
    param = _param_de(consulta["etiqueta"])
    if param is None:   # la lista del IDEAM no esta (servidor reiniciado o sin red): de vuelta a Parametros
        ss.paso = "parametros"
        st.rerun()
    fecha_ini, fecha_fin = consulta["ini"], consulta["fin"]
    cuenca = ss.cuenca
    vista = ss.get("vista") or "2D"   # el selector 2D/3D se dibuja abajo, en las pildoras
    excluidas = set(ss.excluidas)

    # Disposicion: el mapa ocupa la ventana (escenario). Encima flotan, en vidrio: el panel (area, buffer y calidad),
    # la capsula de herramientas, las pildoras de abajo y la ficha de la estacion elegida
    with hueco_panel:
        with st.container(key="y2k_panel_cab"):
            estilo.asa_hoja()
            with st.container(key="y2k_panel_fila", horizontal=True, gap=None, vertical_alignment="center"):
                st.button(f"{param['descripcion']} · {_periodo(fecha_ini, fecha_fin)}", key="chip_param",
                          icon=":material/arrow_back:", width="stretch", on_click=_volver_parametros,
                          help="Volver a Parámetros para cambiar el parámetro o las fechas")
                estilo.controles_panel()
        cuerpo = st.container(key="y2k_cuerpo")
    with hueco_abrir:
        estilo.boton_abrir_panel()

    # ---------------- area y buffer ----------------
    with cuerpo:
        area_km2 = _area_km2(cuenca) if cuenca is not None else None
        estilo.seccion("Área de estudio", f"≈ {_num(area_km2)} km²" if area_km2 else "")
        estilo.acciones_area(cuenca is not None, vista)
        buffer_on = st.toggle("Incluir estaciones cercanas (buffer)", value=True, key="buf_on", persist_state="session",
                              help="Agrega una franja alrededor del área para tener en cuenta las estaciones cercanas.")
        buffer_km = st.slider("Ancho del buffer", 0.5, 15.0, 2.0, 0.5, key="buf_km", format="%.1f km",
                              disabled=not buffer_on, persist_state="session")
        estilo.seccion("Calidad de los datos")
        caja_calidad = st.container()
        estilo.pie()

    # ---------------- estaciones del area + evaluacion ----------------
    zona = area = None
    descargables = seleccion = None
    evaluada = False
    error_ideam = None
    if cuenca is not None and catalogo is not None:
        area = geo_utils.create_buffer(cuenca, buffer_km if buffer_on else 0)
        zona = geo_utils.filter_stations(catalogo, area)
        union = cuenca.union_all()
        zona["zona"] = ["cuenca" if union.covers(g) else "buffer" for g in zona.geometry]
        if not zona.empty:
            with caja_calidad, st.spinner("Comparando la altitud de las estaciones con el relieve…"):
                _revisar_altitudes(zona)
            try:
                with caja_calidad, st.spinner("Consultando en el IDEAM qué datos tiene cada estación…"):
                    calidad = ideam_parameters.get_metadata_availability(zona, param, fecha_ini, fecha_fin)
                for columna in ["Cantidad Probable", "Esperados", "Porcentaje (%)", "Clase calidad",
                                "Serie DHIME", "Inicio serie", "Fin serie"]:
                    zona[columna] = calidad[columna].values
                evaluada = True
            except ideam_downloader.ErrorAccesoIDEAM as e:
                error_ideam = str(e)
            except Exception as e:
                error_ideam = f"No se pudo consultar el IDEAM: {e}"
        if evaluada:
            descargables = filtrar_descargables(zona, 0)
            codigos = [ideam_downloader.codigo_de_estacion(r, i) for i, r in descargables.iterrows()]
            seleccion = descargables[[c not in excluidas for c in codigos]]
    codigos_desc = (set(ideam_downloader.codigo_de_estacion(r, i) for i, r in descargables.iterrows())
                    if descargables is not None else set())

    # ---------------- estacion seleccionada (mapa 2D, 3D o lista) ----------------
    v = ss.get(f"mapa3d_{ss.get('version_3d', 0)}") or {}
    objetos = ((v.get("selection") or {}).get("objects") or {}).get("estaciones", [])
    cambio_sel = _sincronizar("3d", objetos, lambda o: o[0].get("codigo") if o else None)
    cambio_sel |= bool(ss.pop("_centrar", False))   # elegida en la lista del panel: el mapa va a ella
    dudosas = panel_estadisticas.tabla_dudosas(zona)
    v = ss.get("tabla_dudosas") or {}
    filas = (v.get("selection") or {}).get("rows", [])
    cambio_sel |= _sincronizar("dudosas", filas, lambda f: dudosas.iloc[f[0]]["Código"] if f and f[0] < len(dudosas) else None)
    rango = terreno.rango_terreno(area) if zona is not None and not zona.empty else None
    # Intro satelital: con el area ya confirmada (no se va a mover) se precalienta por detras, asi al pasar a 3D no hay
    # espera. No en celulares; en modo Lite tampoco se precalienta ni se reproduce (es lo mas costoso para la tarjeta
    # grafica), pero `usar_intro` no depende de Lite para que activarlo no cambie el guion de la camara
    bbox_intro, est_intro, usar_intro = None, [], False
    if zona is not None and not zona.empty and terreno.SATELITE_ACTIVO and not _es_celular():
        usar_intro = True
        bbox_intro = list((cuenca if cuenca is not None else area).total_bounds)
        est_intro = _estaciones_3d(zona, excluidas)

    # ---------------- mapa (escenario a pantalla completa) ----------------
    textura = ss.get("textura") or "Satélite"
    escala_alt = ss.get("escala_altura") or "Rango de la zona"
    repetir = False
    with escenario:
        if vista == "3D":
            if zona is None or zona.empty:
                estilo.sobre_mapa("Marca tu área en la vista 2D para verla en relieve." if cuenca is None else
                                  "No hay estaciones en esta zona. Activa o amplía el buffer.", "y2k-vacio")
            else:
                altura = None
                if textura == "Altura":
                    altura = (rango if (escala_alt == "Rango de la zona" and rango and rango[1] > rango[0])
                              else terreno.ALTURA_COLOMBIA)
                ligero = _es_celular() or ss.lite
                with st.container(key="y2k_visor3d"):
                    deck, orbita = terreno.construir_deck(cuenca, area if buffer_on else None,
                                                          _estaciones_3d(zona, excluidas), ss.estacion_sel, textura,
                                                          PALETA, ligero=ligero, altura=altura)
                    # Vuelta de camara: alrededor de la estacion recien elegida o, sin seleccion, alrededor
                    # del centro de las estaciones (al abrir el 3D, al cambiar las estaciones o al quitar la seleccion)
                    pedida = ss.pop("_orbitar", False)
                    repetir = ss.pop("_repetir_intro", False)   # boton temporal "Repetir animacion"
                    entro_3d = ss.get("_vista_prev") != "3D"
                    if ss.estacion_sel:
                        disparar = cambio_sel or pedida or entro_3d
                    else:
                        firma = json.dumps([orbita["lon"], orbita["lat"], orbita["zoom"], orbita["pivote"]])
                        disparar = entro_3d or firma != ss.get("_orbita_firma") or ss.get("_sel_prev") is not None
                        ss._orbita_firma = firma
                    ss._sel_prev = ss.estacion_sel
                    disparar = disparar or repetir
                    if disparar:
                        ss.saltos += 1
                        ss.orbita = ss.saltos
                    # Secuencia de entrada (lasers, caida de pines, alertas): una sola vez por area/buffer (o al
                    # pulsar "Repetir animacion"). Se ata al turno de la vuelta para que el guion no cambie entre una
                    # recarga y otra. En modo Lite el guion no la corre (se muestra el resultado final de una vez)
                    firma_intro = json.dumps([[round(float(c), 5) for c in area.total_bounds], bool(buffer_on)])
                    if disparar and (ss.get("_intro_firma") != firma_intro or repetir):
                        ss._intro_firma = firma_intro
                        ss._intro_turno = ss.orbita
                        ss._intro_forzada = repetir
                    intro = ss.get("_intro_turno") == ss.get("orbita")
                    forzar = bool(intro and ss.get("_intro_forzada"))
                    # Mientras corre la secuencia el visor se tapa (CSS) hasta que el guion de terreno.py esconde las capas
                    # y lo marca con este turno. Se manda en todas las corridas del turno (no solo la primera): si Streamlit
                    # repite el script al entrar al 3D, el velo no puede desaparecer. Si algo falla, se destapa solo a los 12 s
                    if intro and not ss.lite:
                        with velo_3d:
                            st.html('<style>.st-key-y2k_visor3d:not([data-mostrar="' + str(ss.orbita) + '"]) '
                                    '[data-testid="stDeckGlJsonChart"]{visibility:hidden;animation:y2k-mostrar 0s linear 12s forwards}'
                                    '@keyframes y2k-mostrar{to{visibility:visible}}</style>')
                    # La clave cambia con "Seguir intentando" / "Activar Lite y reintentar": visor nuevo desde cero
                    st.pydeck_chart(deck, height=terreno.ALTO_VISOR, on_select="rerun", selection_mode="single-object",
                                    key=f"mapa3d_{ss.get('version_3d', 0)}")
                # Intro satelital (del mapa 2D al 3D): no en celulares ni en modo Lite
                satelite = bool(intro and usar_intro)
                with st.container(key="y2k_orbita"):
                    components.html(terreno.orbitar(orbita, ss.get("orbita", 0), intro, satelite, 1.7, forzar), height=0)
                    if satelite and not ss.lite:
                        components.html(terreno.intro_satelital(ss.get("orbita", 0), bbox_intro, est_intro, buffer_on,
                                                                forzar), height=0)
                    components.html(terreno.AVISO_NAVEGADOR, height=0)
                    components.html(terreno.EXTRAS_3D, height=0)
                if altura:
                    estilo.leyenda_altura(terreno.leyenda_altura(
                        altura[0], altura[1], "escala de Colombia" if altura == terreno.ALTURA_COLOMBIA else "escala de la zona"))
                else:
                    estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD], en3d=True,
                                              hay_excluidas=bool(excluidas & codigos_desc))
                estilo.sobre_mapa(estilo.ATRIB_RELIEVE_3D_CORTO, "y2k-atrib3d", "lg-claro")
                if intro and not forzar and not ss.lite and usar_intro:
                    estilo.sobre_mapa("Tu equipo pide reducir el movimiento, así que la animación de entrada no se "
                                      "reproduce sola. Puedes verla con el botón ↻ de abajo.", "y2k-nota-mov")
        else:
            if cuenca is None:
                capa = _capa_catalogo()
            else:
                ss._capa_args = (area if buffer_on else None, zona, ss.estacion_sel, None, excluidas & codigos_desc)
                capa = map_view.capa_dinamica(*ss._capa_args)
            centro = zoom = None
            if cambio_sel and zona is not None and ss.estacion_sel:
                elegida = zona[[ideam_downloader.codigo_de_estacion(r, i) == ss.estacion_sel for i, r in zona.iterrows()]]
                if not elegida.empty:
                    # El mapa solo se mueve si centro/zoom cambian respecto a la vez anterior: un
                    # desfase minusculo (invisible) garantiza que vuelva aunque se elija la misma estacion
                    ss.saltos += 1
                    centro = (elegida.geometry.iloc[0].y + ss.saltos * 1e-9, elegida.geometry.iloc[0].x)
                    zoom = 14 + (ss.saltos % 2) * 1e-4
            retorno = mapa_2d(capa, centro, zoom)
            if retorno and retorno.get("all_drawings") is not None:
                nueva = map_view.cuenca_desde_dibujos(retorno["all_drawings"])
                if _firma(nueva) != _firma(cuenca):
                    ss.cuenca = nueva
                    ss.estacion_sel = None
                    ss.excluidas = set()
                    st.rerun()
            # Escaner del mapa: el controlador se instala una vez y, al terminar el calculo, se le avisa
            with st.container(key="y2k_escaner"):
                escaner.instalar()
                if cuenca is not None and zona is not None:
                    hay = len(descargables) if evaluada and descargables is not None else len(zona)
                    if hay:
                        texto = f"{hay} {'estaciones con datos' if hay != 1 else 'estación con datos'}"
                    elif zona.empty:
                        texto = "No hay estaciones aquí · amplía el buffer"
                    else:
                        texto = "Ninguna estación tiene datos en el periodo"
                    escaner.listo(hay, texto)
            clic = (retorno or {}).get("last_object_clicked")
            if _sincronizar("mapa2d", clic, lambda c: _estacion_cercana(zona, c)):
                st.rerun()
            if cuenca is not None:
                estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD],
                                          hay_excluidas=bool(excluidas & codigos_desc))
        ss._vista_prev = vista

    # ---------------- tablero de calidad ----------------
    n_sel = len(seleccion) if seleccion is not None else 0
    cifras = panel_estadisticas.cifras_seleccion(seleccion, param, fecha_ini, fecha_fin) if evaluada else None
    filas_estacion = ideam_parameters.filas_estimadas(param, fecha_ini, fecha_fin)
    excede = filas_estacion > ideam_parameters.MAX_FILAS_EXCEL
    with caja_calidad:
        if error_ideam:
            st.error(error_ideam, icon=":material/cloud_off:")
        elif cuenca is None:
            st.html('<p class="y2k-hint">Marca el área para ver qué estaciones hay y cuántos datos tiene cada una.</p>')
        elif zona is not None and zona.empty:
            st.warning("No hay estaciones del IDEAM en esta zona. Activa o amplía el buffer.", icon=":material/location_off:")
        elif excede:
            st.warning(f"Con frecuencia {_frecuencia_txt(param['frecuencia'])}, el periodo daría hasta {_num(filas_estacion)} filas "
                       "por estación y Excel admite alrededor de un millón por hoja. Acorta el periodo en Parámetros.",
                       icon=":material/table_rows:")
        elif evaluada and descargables.empty:
            st.warning("Ninguna estación de esta zona tiene datos de este parámetro en el periodo. Cambia las fechas o el "
                       "parámetro (botón de arriba) o amplía el buffer.", icon=":material/search_off:")
        elif evaluada:
            panel_estadisticas.tablero(zona, descargables, seleccion, param, cifras, dudosas, rango)

    # ---------------- capsula de herramientas (derecha) ----------------
    with hueco_herr:
        if vista == "3D":
            if zona is not None and not zona.empty:
                estilo.controles_camara()
        else:
            estilo.herramientas_2d(cuenca is not None)

    # ---------------- pildoras de abajo: 2D/3D y "Preparar descarga" ----------------
    listo = evaluada and n_sel > 0 and not excede
    if listo:
        razon = f"{n_sel} {'estaciones' if n_sel != 1 else 'estación'} · {panel_estadisticas.duracion_aprox(cifras['segundos'])}"
    elif cuenca is None:
        razon = "Primero marca el área en el mapa"
    elif error_ideam:
        razon = "No se pudo consultar el IDEAM"
    elif excede:
        razon = "El periodo es demasiado largo para Excel"
    elif evaluada and descargables is not None and not descargables.empty:
        razon = "Marca al menos una estación en la lista"
    else:
        razon = "No hay estaciones con datos en esta zona"
    with hueco_dock:
        with st.container(key="y2k_dock_izq", horizontal=True, gap=None, vertical_alignment="center"):
            st.segmented_control("Vista del mapa", ["2D", "3D"], key="vista", required=True,
                                 label_visibility="collapsed", persist_state="session")
            if vista == "3D" and zona is not None and not zona.empty:
                with st.popover(f"Textura: {textura}", icon=":material/layers:"):
                    st.segmented_control("Textura del relieve", ["Satélite", "Topográfico", "Altura"], default="Satélite",
                                         key="textura", required=True, persist_state="session")
                    if textura == "Altura":
                        st.segmented_control("Escala de colores", ["Rango de la zona", "Rango de Colombia"],
                                             default="Rango de la zona", key="escala_altura", required=True,
                                             format_func=lambda e: e.replace("Rango", "Escala"), persist_state="session")
                # TEMPORAL: para ver la animacion de entrada otra vez mientras se ajusta
                if usar_intro:
                    st.button("Repetir animación", key="y2k_repetir_intro", icon=":material/replay:", on_click=_repetir_intro,
                              disabled=ss.lite,
                              help="En modo Lite no hay animación de entrada. Desactívalo en Ajustes para verla." if ss.lite
                              else "Repetir la animación de entrada al 3D")
        with st.container(key="y2k_dock_der"):
            datos = ({"estaciones": seleccion.copy(), "param": param, "ini": fecha_ini, "fin": fecha_fin,
                      "carpetas": bool(ss.get("carpetas", True))} if listo else None)
            st.button("Preparar descarga", type="primary", key="preparar", icon=":material/arrow_forward:",
                      icon_position="right", disabled=not listo, help=razon, on_click=_preparar, args=(datos,))

    # ---------------- ficha de la estacion elegida (flotante) ----------------
    with hueco_ficha:
        if ss.estacion_sel and zona is not None and not zona.empty:
            fila = zona[[ideam_downloader.codigo_de_estacion(r, i) == ss.estacion_sel for i, r in zona.iterrows()]]
            if not fila.empty:
                panel_estadisticas.tarjeta_seleccionada(fila.iloc[0], rango, vista,
                                                        descargable=ss.estacion_sel in codigos_desc)

    # Botones ocultos: los pulsan los menus y los avisos de fallo del navegador (siempre por eleccion del usuario)
    with hueco_ocultos:
        st.button("Activar Lite y reintentar", key="y2k_lite_reintentar", on_click=_lite_reintentar)
        st.button("Seguir intentando", key="y2k_reintentar3d", on_click=_recargar_3d)
        st.button("Ver en 2D", key="y2k_pasar2d", on_click=_pasar_a_2d)
        st.button("Borrar el área", key="y2k_borrar", on_click=_borrar_cuenca)
        st.button("Subir un archivo", key="y2k_subir", on_click=_abrir_subida)

    # Lo condicional va al final, para no mover de lugar (y rehacer) lo de arriba
    if usar_intro and not ss.lite:
        with st.container(key="y2k_precal"):
            components.html(terreno.precalentar_satelite(bbox_intro, est_intro, buffer_on), height=0)
            st.html(terreno.css_boton_3d_espera(bbox_intro, est_intro))   # el boton 3D espera a que todo este listo
    if ss.subida_abierta:
        if vista == "2D":
            dialogo_subida()
        else:
            ss.subida_abierta = False


# ===========================================================================
# PANTALLA 3: EXPORTACION
# ===========================================================================
def _recibo(d):
    n = len(d["estaciones"])
    en_area = int((d["estaciones"]["zona"] == "cuenca").sum()) if "zona" in d["estaciones"].columns else n
    p = d["param"]
    unidad = f" ({p['unidad']})" if p.get("unidad") else ""
    estilo.recibo([
        ("Parámetro", p["descripcion"] + unidad, f"Frecuencia {_frecuencia_txt(p['frecuencia'])}"),
        ("Periodo", f"{d['ini']:%d/%m/%Y} – {d['fin']:%d/%m/%Y}", ""),
        ("Estaciones", f"{n}", f"{en_area} en el área" + (f" · {n - en_area} en el buffer" if n - en_area else "")),
        ("Archivo", "Un Excel por estación",
         ("En carpetas por cobertura · " if d.get("carpetas") else "") + "con resumen_descarga.csv y CITACION.txt"),
        ("Fuente", "IDEAM · DHIME", ""),
    ])


@st.fragment
def _entrega(resultado):
    """Nombre del ZIP y boton de descarga (en un fragmento: escribir el nombre no recarga la tarjeta entera)."""
    ini, fin = resultado["rango"]
    predeterminado = f"IDEAM_{resultado['etiqueta']}_{ini:%Y%m%d}-{fin:%Y%m%d}"
    nombre = st.text_input("Nombre del archivo ZIP", value=predeterminado, key="nombre_zip", max_chars=120, live=True,
                           help="Por ejemplo: descarga 1. La extensión .zip se añade sola.")
    st.download_button("Descargar el ZIP", data=resultado["zip"], type="primary", width="stretch",
                       file_name=f"{_nombre_archivo(nombre, predeterminado)}.zip", icon=":material/download:",
                       mime="application/zip", key="bajar_zip")


def pantalla_descarga():
    d = ss.descarga
    if ss.estado_descarga == "en_curso":
        # La corrida anterior se corto a mitad de la descarga ("Detener" u otra recarga): no se puede retomar
        ss.estado_descarga = "detenida"
    estado = ss.estado_descarga
    if estado not in ("pendiente", "detenida", "error", "lista") or (estado == "lista" and not ss.resultado):
        estado = ss.estado_descarga = "detenida"
    # el mapa queda detras (velado); no se monta de cero si se va a descargar: al cargar podria recargar la pagina
    mapa_de_fondo(nuevo_permitido=estado not in ("pendiente",))
    n = len(d["estaciones"])
    resultado = ss.resultado
    # Tarjeta de vidrio: a la izquierda el avance y lo que se hace con la descarga; a la derecha el recibo y las
    # condiciones de uso (en el celular, una debajo de la otra)
    with hueco_exportar:
        if estado == "pendiente":
            titulo, tono = "Descargando datos del IDEAM", "vivo"
        elif estado == "lista":
            titulo, tono = "Descarga lista", "hecho"
        else:
            titulo, tono = ("No se pudo descargar" if (resultado or {}).get("error") else "Descarga detenida"), "alto"
        estilo.cabecera_exportar(titulo, tono)
        izq, der = st.columns([1.12, 1], gap="large")
        with der:
            _recibo(d)
            estilo.legal_exportar(TEXTO_LEGAL)

        if estado == "pendiente":
            with izq:
                progreso = st.empty()
                progreso.markdown(estilo.progreso(0, "Preparando…", f"<span>Estaciones <b>0 de {n}</b></span>"),
                                  unsafe_allow_html=True)
                aviso = st.empty()
                st.html('<p class="y2k-hint">Puedes seguir mirando esta pantalla; si cierras la pestaña, la descarga '
                        'se detiene.</p>')
                st.button("Detener la descarga", key="detener", icon=":material/stop_circle:", width="stretch",
                          on_click=_detener)
            _descargar(d, progreso, aviso)
            st.rerun()

        if estado in ("detenida", "error"):
            error = (resultado or {}).get("error")
            with izq:
                st.markdown(estilo.progreso(0, "Sin terminar", "<span>No se guardó nada</span>", "alto"),
                            unsafe_allow_html=True)
                if error:
                    st.error(error, icon=":material/cloud_off:")
                else:
                    st.html('<p class="y2k-hint">Puedes reintentarla o volver al mapa para cambiar la selección.</p>')
                with st.container(horizontal=True, gap="small"):
                    st.button("Reintentar", type="primary", width="stretch", icon=":material/replay:", key="reintentar",
                              on_click=_reintentar_descarga)
                    st.button("Volver al mapa", width="stretch", icon=":material/arrow_back:", key="volver_mapa",
                              on_click=_volver_mapa)
            return

        # Descarga lista
        guardadas, omitidas = resultado["guardadas"], resultado["omitidas"]
        with izq:
            st.markdown(estilo.progreso(1.0, f"Completada en {resultado['duracion']}",
                                        f"<span>Guardadas <b>{guardadas}</b></span><span>Omitidas <b>{omitidas}</b></span>",
                                        "fin"), unsafe_allow_html=True)
            frase = (f"Se {'guardaron' if guardadas != 1 else 'guardó'} <b>{guardadas}</b> de {guardadas + omitidas} "
                     f"{'estaciones' if guardadas + omitidas != 1 else 'estación'}."
                     + (f" {'Una' if omitidas == 1 else omitidas} no {'tenía' if omitidas == 1 else 'tenían'} datos en el "
                        "periodo o el IDEAM no respondió; el detalle está en resumen_descarga.csv, dentro del ZIP."
                        if omitidas else ""))
            estilo.resumen_final(frase, panel_estadisticas.reparto_cobertura(resultado["colores"]))
            _entrega(resultado)
            with st.container(horizontal=True, gap="small"):
                st.button("Volver al mapa", width="stretch", icon=":material/arrow_back:", key="volver_mapa",
                          on_click=_volver_mapa)
                st.button("Nueva consulta", width="stretch", icon=":material/add_location_alt:", key="nueva_consulta",
                          on_click=_nueva_consulta)


def _descargar(d, progreso, aviso):
    """Corre la descarga en esta misma corrida (la barra se actualiza en vivo) y deja el resultado en la sesion."""
    # Turno: como mucho MAX_DESCARGAS_SIMULTANEAS descargas a la vez en el servidor (entre todos los usuarios), para
    # no saturar al IDEAM. Si no hay cupo, se espera con aviso
    cupos = ideam_downloader.cupos_descarga()
    turnos = ideam_downloader.turnos_descarga()
    _, _, segundos = ideam_downloader.plan_descarga(d["estaciones"], d["ini"], d["fin"], d["param"])
    turno = object()
    ss.estado_descarga = "en_curso"
    if not cupos.acquire(blocking=False):
        with turnos["candado"]:
            turnos["fila"].append(turno)
        try:
            inicio_espera = time.time()
            while not cupos.acquire(timeout=2):
                puesto, falta = ideam_downloader.espera_estimada(turno)
                cuando = (f"en ≈ {ideam_downloader.duracion_texto(falta)}" if falta >= 5 else "en cualquier momento")
                aviso.info(f"El servidor está ocupado: hay {ideam_downloader.MAX_DESCARGAS_SIMULTANEAS} descargas en curso. "
                           f"Eres el número {puesto} en la fila y la tuya empezará sola {cuando} "
                           f"(llevas {ideam_downloader.duracion_texto(time.time() - inicio_espera)}).",
                           icon=":material/hourglass_top:")
        finally:
            with turnos["candado"]:
                if turno in turnos["fila"]:
                    turnos["fila"].remove(turno)
    aviso.empty()
    with turnos["candado"]:
        turnos["en_curso"][turno] = (time.time(), segundos)
    try:
        resultado = ideam_downloader.procesar_descargas(d["estaciones"], d["carpetas"], d["ini"], d["fin"],
                                                        d["param"], {"progreso": progreso})
        ss.resultado = resultado or {"error": "No se pudo completar la descarga."}
        ss.estado_descarga = "error" if "error" in ss.resultado else "lista"
    finally:
        # Se libera el turno siempre: al terminar, al pulsar "Detener" o si se cierra la pestaña
        with turnos["candado"]:
            turnos["en_curso"].pop(turno, None)
        cupos.release()


# ===========================================================================
if ss.paso == "descarga":
    pantalla_descarga()
elif ss.paso == "mapa":
    pantalla_mapa()
else:
    pantalla_parametros()
