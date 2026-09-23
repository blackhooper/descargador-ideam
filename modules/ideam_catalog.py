import os
import requests
import geopandas as gpd
import streamlit as st

@st.cache_data(show_spinner=False)
def load_ideam_catalog() -> gpd.GeoDataFrame:
    # Nuevo nombre de archivo para ignorar el viejo de 49 estaciones
    cache_path = os.path.join("data", "ideam_catalogo_completo.geojson")
    
    if os.path.exists(cache_path):
        try:
            return gpd.read_file(cache_path)
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
    
    os.makedirs("data", exist_ok=True)
    gdf.to_file(cache_path, driver="GeoJSON")
    
    return gdf