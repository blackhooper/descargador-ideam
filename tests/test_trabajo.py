"""La descarga como trabajo en su hilo (`modules/trabajo.py`): termina, se detiene, falla y cede el cupo."""
import threading
import time

import pytest

from modules import ideam_downloader, trabajo

DATOS = {"estaciones": [], "ini": None, "fin": None, "param": {}}


@pytest.fixture
def servidor(monkeypatch):
    """Cupos y turnos propios de la prueba (los de verdad son recursos de Streamlit)."""
    cupos = threading.BoundedSemaphore(1)
    turnos = {"candado": threading.Lock(), "en_curso": {}, "fila": []}
    monkeypatch.setattr(ideam_downloader, "cupos_descarga", lambda: cupos)
    monkeypatch.setattr(ideam_downloader, "turnos_descarga", lambda: turnos)
    monkeypatch.setattr(ideam_downloader, "plan_descarga", lambda *a: ([], 0, 1))
    monkeypatch.setattr(trabajo, "_registro", {})
    return cupos, turnos


def _esperar(condicion, segundos=5):
    fin = time.time() + segundos
    while not condicion() and time.time() < fin:
        time.sleep(.02)
    assert condicion()


def _descarga_lenta(*a):
    """Imita a procesar_descargas: avisa el avance hasta que le piden parar."""
    ui = a[-1]
    while not ui["detener"].is_set():
        ui["avance"]({"fraccion": .5})
        time.sleep(.02)
    ui["parcial"].update(parcial=True, guardadas=1)
    raise ideam_downloader.DescargaDetenida()


def test_termina_y_devuelve_el_cupo(servidor, monkeypatch):
    cupos, turnos = servidor
    monkeypatch.setattr(ideam_downloader, "procesar_descargas", lambda *a: {"zip": b"x", "guardadas": 1})
    t = trabajo.Trabajo(DATOS).iniciar()
    _esperar(lambda: t.estado == "lista")
    assert t.resultado["guardadas"] == 1
    assert trabajo.buscar(t.id) is t
    assert cupos.acquire(blocking=False) and not turnos["en_curso"]


def test_detener_deja_lo_parcial(servidor, monkeypatch):
    cupos, _ = servidor
    monkeypatch.setattr(ideam_downloader, "procesar_descargas", _descarga_lenta)
    t = trabajo.Trabajo(DATOS).iniciar()
    _esperar(lambda: t.avance is not None)
    t.detener.set()
    _esperar(lambda: t.estado == "detenida")
    assert t.parcial["parcial"] and cupos.acquire(blocking=False)


def test_error_inesperado_no_deja_el_cupo_tomado(servidor, monkeypatch):
    cupos, _ = servidor
    monkeypatch.setattr(ideam_downloader, "procesar_descargas", lambda *a: 1 / 0)
    t = trabajo.Trabajo(DATOS).iniciar()
    _esperar(lambda: t.estado == "error")
    assert "error" in t.resultado and cupos.acquire(blocking=False)


def test_espera_turno_y_empieza_solo(servidor, monkeypatch):
    cupos, turnos = servidor
    monkeypatch.setattr(ideam_downloader, "procesar_descargas", lambda *a: {"zip": b"x"})
    cupos.acquire()                         # otra descarga ocupa el unico cupo
    t = trabajo.Trabajo(DATOS).iniciar()
    _esperar(lambda: t.espera is not None)
    assert t.espera["puesto"] == 1 and t.estado == "en_curso"
    cupos.release()
    _esperar(lambda: t.estado == "lista")
    assert not turnos["fila"]


def test_se_detiene_si_nadie_la_mira(servidor, monkeypatch):
    monkeypatch.setattr(ideam_downloader, "procesar_descargas", _descarga_lenta)
    monkeypatch.setattr(trabajo, "GRACIA", .1)
    t = trabajo.Trabajo(DATOS).iniciar()
    _esperar(lambda: t.estado == "detenida")


def test_olvidar_y_caducidad(servidor, monkeypatch):
    monkeypatch.setattr(ideam_downloader, "procesar_descargas", lambda *a: {"zip": b"x"})
    a = trabajo.Trabajo(DATOS).iniciar()
    b = trabajo.Trabajo(DATOS).iniciar()
    _esperar(lambda: a.estado == b.estado == "lista")
    trabajo.olvidar(a)
    assert trabajo.buscar(a.id) is None and trabajo.buscar(b.id) is b
    b.visto -= trabajo.CADUCIDAD + 1
    assert trabajo.buscar(b.id) is None
    assert trabajo.buscar(None) is None
