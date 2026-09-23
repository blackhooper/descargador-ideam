import geopandas as gpd
from typing import Tuple

def validate_geometry(gdf: gpd.GeoDataFrame) -> Tuple[bool, str]:
    if gdf is None or gdf.empty:
        return False, "El archivo o conjunto de datos está vacío."

    gdf.drop(gdf.index[gdf.geometry.isna() | gdf.geometry.is_empty], inplace=True)
    if gdf.empty:
        return False, "El archivo no trae ninguna geometría."

    # Geometrias invalidas (ej. poligonos que se cruzan a si mismos): se reparan
    if not gdf.is_valid.all():
        gdf["geometry"] = gdf.geometry.make_valid()
        if not gdf.is_valid.all():
            return False, "El archivo contiene geometrías inválidas que no se pudieron reparar."
        return True, "Había geometrías inválidas y se repararon automáticamente."

    return True, "Geometría válida."

def reproject_to_epsg4326(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Pasa la geometria a coordenadas geograficas (EPSG:4326).
    Si el archivo no trae sistema de coordenadas (.prj) solo se asume 4326
    cuando los valores parecen grados; si parecen metros se lanza un error.
    """
    if gdf.crs is None:
        minx, miny, maxx, maxy = gdf.total_bounds
        if -180 <= minx <= maxx <= 180 and -90 <= miny <= maxy <= 90:
            return gdf.set_crs(epsg=4326)
        raise ValueError(
            "El archivo no trae sistema de coordenadas (falta el .prj) y sus valores están en metros. "
            "Súbelo con su archivo .prj para poder ubicarlo."
        )
    if gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    return gdf

def create_buffer(gdf: gpd.GeoDataFrame, radius_km: float) -> gpd.GeoDataFrame:
    """Crea un área de influencia (buffer) en kilómetros alrededor de la cuenca."""
    # Convertir a zona local Colombia (EPSG:3116) para poder medir en metros exactos
    gdf_utm = gdf[["geometry"]].to_crs(epsg=3116)
    # Crear el buffer (multiplicamos km por 1000 para pasar a metros)
    gdf_utm['geometry'] = gdf_utm.geometry.buffer(radius_km * 1000)
    # Se une todo en un solo poligono: si el archivo trae varios poligonos que
    # se tocan, una estacion no debe aparecer repetida
    area = gdf_utm.dissolve()
    # Devolver a coordenadas de internet (WGS84)
    return area.to_crs(epsg=4326)

def filter_stations(catalog_gdf: gpd.GeoDataFrame, buffer_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Recorta la base de datos nacional dejando solo las que tocan el buffer."""
    # Solo se usa la geometria del area, asi las columnas del archivo del
    # usuario (ej. "nombre") no se mezclan con las de las estaciones
    area = buffer_gdf[["geometry"]]
    filtered = gpd.sjoin(catalog_gdf, area, how="inner", predicate="intersects")
    filtered = filtered.drop(columns=["index_right"], errors="ignore")
    return filtered[~filtered.index.duplicated()].copy()
