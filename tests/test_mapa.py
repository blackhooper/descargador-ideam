"""Capa de estaciones del mapa 2D (`modules/map_view.py`)."""
import geopandas as gpd
from folium.plugins import MarkerCluster
from shapely.geometry import Point

from modules import map_view


def _estaciones(n):
    return gpd.GeoDataFrame({"codigo": [str(1000 + i) for i in range(n)], "nombre": [f"E{i}" for i in range(n)],
                             "altitud": [100] * n, "altitud_dudosa": [i == 1 for i in range(n)]},
                            geometry=[Point(-74 + i / 1000, 4.5) for i in range(n)], crs="EPSG:4326")


def _grupos(capa):
    return [h for h in capa._children.values() if isinstance(h, MarkerCluster)]


def test_pocas_estaciones_van_sueltas():
    capa = map_view.capa_dinamica(estaciones=_estaciones(map_view.AGRUPAR_DESDE - 1))
    assert not _grupos(capa)
    assert len(capa._children) == map_view.AGRUPAR_DESDE     # un pin por estacion y el halo de la dudosa


def test_muchas_estaciones_se_agrupan_y_la_elegida_queda_fuera():
    n = map_view.AGRUPAR_DESDE
    capa = map_view.capa_dinamica(estaciones=_estaciones(n), seleccionada="1000")
    (grupo,) = _grupos(capa)
    assert len(grupo._children) == n - 1                     # sin halos: contarian como otra estacion
    assert len(capa._children) == 3                          # el agrupador, el aro de la elegida y su pin
    assert grupo.options["disable_clustering_at_zoom" if "disable_clustering_at_zoom" in grupo.options
                         else "disableClusteringAtZoom"] == map_view.ZOOM_SIN_GRUPOS
