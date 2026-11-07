import os
import re
import requests
import geopandas as gpd
import streamlit as st

# Nombres que delatan una estacion de prueba metida en el catalogo oficial
# (p. ej. "MONDONEDO_TEST [21208080]", con coordenadas 4.0/-74.0 de relleno).
# No son estaciones reales y ensucian cualquier filtro por cercania o mapa.
_PATRON_PRUEBA = re.compile(r"(?:^|[^A-ZÁÉÍÓÚÑ])(?:TEST|PRUEBA)(?:[^A-ZÁÉÍÓÚÑ]|$)", re.IGNORECASE)


def _quitar_estaciones_de_prueba(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Elimina filas cuyo nombre indica que es una estacion de prueba, no una real."""
    if "nombre" not in gdf.columns:
        return gdf
    es_prueba = gdf["nombre"].astype(str).str.contains(_PATRON_PRUEBA, regex=True, na=False)
    return gdf.loc[~es_prueba].copy()


def _marcar_coordenada_compartida(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Agrega "coordenada_compartida": True si la estacion comparte sus coordenadas
    exactas con otras 2 o mas estaciones. Suele pasar cuando a la estacion le
    pusieron el centro del municipio en vez de su ubicacion real: para Thiessen o
    relleno ponderado por distancia, dos estaciones "en el mismo punto" dan pesos
    invalidos, asi que conviene poder filtrarlas o revisarlas antes de usarlas."""
    if "latitud" not in gdf.columns or "longitud" not in gdf.columns:
        return gdf
    clave = gdf["latitud"].round(5).astype(str) + "," + gdf["longitud"].round(5).astype(str)
    conteo = clave.value_counts()
    gdf["coordenada_compartida"] = clave.map(conteo).fillna(0) >= 3
    return gdf


@st.cache_data(show_spinner=False)
def load_ideam_catalog() -> gpd.GeoDataFrame:
    # Nuevo nombre de archivo para ignorar el viejo de 49 estaciones
    cache_path = os.path.join("data", "ideam_catalogo_completo.geojson")

    if os.path.exists(cache_path):
        try:
            gdf = gpd.read_file(cache_path)
            gdf = _quitar_estaciones_de_prueba(gdf)
            gdf = _marcar_coordenada_compartida(gdf)
            return gdf
        except Exception:
            pass

    url = "https://dhime.ideam.gov.co/server/rest/services/CNE/Estaciones/MapServer/0/query"
    
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    all_features = []
    offset = 0
    batch_size = 1000 # Pedimos en bloques de 1000 para no hacer saltar la alarma del servidor
    
    # Ciclo infinito que pide datos hasta que el servidor diga "ya no hay más"
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "f": "geojson",
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": batch_size
        }
        try:
            response = requests.get(url, params=params, timeout=40, verify=False)
            response.raise_for_status()
            data = response.json()
            
            features = data.get("features", [])
            if not features:
                break # Rompemos el ciclo si ya no hay datos
                
            all_features.extend(features)
            
            # Si nos devolvió menos de lo que pedimos, significa que llegamos al final
            if len(features) < batch_size:
                break
                
            offset += batch_size
        except Exception as e:
            st.error(f"❌ Error durante la descarga fragmentada: {e}")
            break
            
    if not all_features:
        return None
        
    gdf = gpd.GeoDataFrame.from_features(all_features)
    gdf = gdf.set_crs(epsg=4326)
    gdf = _quitar_estaciones_de_prueba(gdf)

    os.makedirs("data", exist_ok=True)
    gdf.to_file(cache_path, driver="GeoJSON")

    return _marcar_coordenada_compartida(gdf)