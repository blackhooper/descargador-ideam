"""Pruebas de las correcciones de la auditoria: bloques, nombres de Excel, catalogo sin duplicados y relieve."""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from modules import ideam_catalog, ideam_downloader as dl, terreno


def test_bloques_alineados_no_pasan_del_limite():
    ini, fin, dias = date(1990, 1, 15), date(2020, 12, 31), 3650
    bloques = dl.calcular_bloques(ini, fin, dias_por_bloque=dias, alinear_mes=True)
    assert bloques[0][0] == ini and bloques[-1][1] == fin
    for (_, b), (c, _) in zip(bloques, bloques[1:]):
        assert (c - b).days == 1                      # sin huecos ni solapes
    for a, b in bloques:
        assert a <= b <= fin
        assert (b - a).days + 1 <= dias               # nunca mas largo que el limite
    for _, b in bloques[:-1]:
        assert (b + timedelta(days=1)).day == 1       # los cortes caen en fin de mes


def test_nombre_excel_lleva_codigo_y_no_se_repite():
    param, usados = {"etiqueta": "PTPM_CON"}, set()
    a = dl.nombre_excel("PAEZ", "35087020", param, usados)
    b = dl.nombre_excel("PAEZ", "21057060", param, usados)
    c = dl.nombre_excel("PAEZ", "35087020", param, usados)
    d = dl.nombre_excel("PAEZ [35087020]", "35087020", param)
    assert a == "PAEZ_[35087020]_PTPM_CON.xlsx"
    assert len({a, b, c}) == 3
    assert "[35087020]" in c and c.endswith(".xlsx")
    assert d.count("35087020") == 1                   # el codigo no se repite si el nombre ya lo trae


def test_catalogo_una_fila_por_estacion():
    df = pd.DataFrame({
        "idestacion": ["1", "1", "2"],
        "nombre": ["VIEJA", "NUEVA", "OTRA"],
        "fechaultimamodificacion": ["2019-01-01", "2023-05-01", "2020-01-01"],
    })
    limpio = ideam_catalog._quitar_duplicados(df)
    assert sorted(limpio["idestacion"]) == ["1", "2"]
    assert limpio.loc[limpio["idestacion"] == "1", "nombre"].iloc[0] == "NUEVA"


def _malla(lon0, lat0, lon1, lat1, n=40):
    return [(lon0 + (lon1 - lon0) * i / n, lat0 + (lat1 - lat0) * j / n) for i in range(n + 1) for j in range(n + 1)]


def test_zoom_para_respeta_el_tope():
    chico = _malla(-75.60, 6.20, -75.55, 6.25)
    grande = _malla(-77.2, 5.4, -73.8, 8.9)           # un departamento entero
    assert terreno.zoom_para(chico, 150, z_min=10) == terreno.ZOOM_DEM
    z = terreno.zoom_para(grande, 64)
    assert z < terreno.ZOOM_DEM
    tiles = {tuple(int(v) for v in terreno._indice_tile(lon, lat, z)) for lon, lat in grande}
    assert len(tiles) <= 64


def test_tile_fallido_no_se_reintenta_enseguida(monkeypatch):
    llamadas = []

    def falla(*a, **k):
        llamadas.append(1)
        raise OSError("sin red")

    monkeypatch.setattr(terreno.requests, "get", falla)
    terreno._TILES.pop((9, 1, 1), None)
    terreno._TILES_FALLIDOS.pop((9, 1, 1), None)
    for _ in range(3):
        try:
            terreno._tile(9, 1, 1)
            raise AssertionError("debia fallar")
        except (OSError, RuntimeError):
            pass
    assert len(llamadas) == 1                          # solo el primer intento sale a la red
    terreno._TILES_FALLIDOS.pop((9, 1, 1), None)
