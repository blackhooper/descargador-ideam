"""Pruebas de la cobertura estimada (cantidad probable), la fusion de Excel y el catalogo recortado."""
import io
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import geopandas as gpd
import openpyxl
import pandas as pd
from shapely.geometry import Point

from modules import ideam_catalog, ideam_downloader as dl, ideam_parameters


def _estaciones():
    return pd.DataFrame({"idestacion": ["1", "2", "3"], "nombre": ["COMPLETA", "MEDIA", "SIN SERIE"]})


def test_cobertura_estimada(monkeypatch):
    series = {
        "1": {"InicioData": "1990-01-01T00:00:00", "FinData": "2025-01-01T00:00:00", "Periodo": 86400},
        "2": {"InicioData": "2010-07-02T00:00:00", "FinData": "2025-01-01T00:00:00", "Periodo": 86400},
    }
    monkeypatch.setattr(dl, "obtener_series_disponibles", lambda etiqueta: series)
    param = {"etiqueta": "PTPM_CON", "frecuencia": "Diario", "frecuencia_base": "Diario", "especial": False}
    t = ideam_parameters.get_metadata_availability(_estaciones(), param, date(2010, 1, 1), date(2010, 12, 31))
    pct = dict(zip(t["Código"], t["Porcentaje (%)"]))
    assert pct["1"] == 100.0                      # el registro cubre todo el periodo
    assert 49.0 <= pct["2"] <= 51.0               # empieza a mitad de año
    assert pct["3"] == 0.0                        # no tiene la serie
    assert dict(zip(t["Código"], t["Serie DHIME"])) == {"1": "Sí", "2": "Sí", "3": "No"}
    assert t["Esperados"].iloc[0] == 365


def _libro(filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(7):
        ws.append(["Meta", "x"])
    ws.append(["Fecha", "Valor"])
    for fila in filas:
        ws.append(fila)
    salida = io.BytesIO()
    wb.save(salida)
    return salida.getvalue()


def test_fusion_une_los_bloques_en_orden():
    a = _libro([["2020-01-01", 1.0], ["2020-01-02", 2.0]])
    b = _libro([["2020-01-03", 3.0], ["2020-01-04", 4.0], ["2020-01-05", 5.0]])
    unido, filas = dl.fusionar_excels_ideam([a, b])
    assert filas == [2, 3]
    hoja = openpyxl.load_workbook(io.BytesIO(unido)).active
    valores = [f[1] for f in hoja.iter_rows(min_row=9, values_only=True) if f[1] is not None]
    assert valores == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_catalogo_recortado_y_con_codigo():
    gdf = gpd.GeoDataFrame({
        "idestacion": ["21205710", "35087020"], "nombre": ["JARDIN BOTANICO", "PAEZ"], "altitud": [2552, 1300],
        "latitud": [4.67, 5.1], "longitud": [-74.1, -73.05], "usuario": ["alguien", "otro"],
        "observacion": ["nota interna", ""], "fechaultimamodificacion": ["2020-01-01", "2021-01-01"],
    }, geometry=[Point(-74.1, 4.67), Point(-73.05, 5.1)], crs="EPSG:4326")
    limpio = ideam_catalog._limpiar(gdf)
    assert "usuario" not in limpio.columns and "observacion" not in limpio.columns
    assert list(limpio["codigo"]) == ["21205710", "35087020"]
    assert dl.codigos_de(limpio) == ["21205710", "35087020"]
    assert dl.codigos_de(limpio.drop(columns=["codigo"])) == ["21205710", "35087020"]


def test_catalogo_del_repo_sin_columnas_internas():
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data",
                        "ideam_catalogo_completo.geojson")
    columnas = set(gpd.read_file(ruta, rows=1).columns)
    assert columnas <= set(ideam_catalog.COLUMNAS)
