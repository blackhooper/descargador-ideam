import os
import re
import shutil
import requests
import geopandas as gpd
import streamlit as st

from modules.idioma import tr

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


def _quitar_duplicados(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Deja una sola fila por codigo de estacion (idestacion). El catalogo oficial trae unos pocos codigos repetidos
    (la misma estacion con dos estados): en la app salian dos veces en la lista y se descargaban dos veces. Se
    conserva la fila modificada mas recientemente, en su lugar original."""
    if "idestacion" not in gdf.columns:
        return gdf
    orden = gdf
    if "fechaultimamodificacion" in gdf.columns:
        orden = gdf.sort_values("fechaultimamodificacion", ascending=False, na_position="last", kind="stable")
    codigo = orden["idestacion"].astype(str).str.strip()
    conservar = orden.index[~codigo.duplicated() | codigo.isin(["", "None", "nan"])]
    return gdf.loc[gdf.index.isin(conservar)].copy()


def _limpiar(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return _marcar_coordenada_compartida(_quitar_duplicados(_quitar_estaciones_de_prueba(gdf)))


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
            return _limpiar(gdf)
        except Exception:
            pass

    url = "https://dhime.ideam.gov.co/server/rest/services/CNE/Estaciones/MapServer/0/query"
    
    all_features = []
    offset = 0
    batch_size = 1000 # Pedimos en bloques de 1000 para no hacer saltar la alarma del servidor
    # Solo queda en True si el servidor dijo "ya no hay mas". Si el ciclo se corta por una
    # excepcion (red, timeout, HTTP de error), queda en False: lo que se alcanzo a bajar es
    # un catalogo PARCIAL y no debe guardarse como si fuera el oficial completo (si se hiciera,
    # la proxima sesion lo cargaria del disco tal cual, sin volver a intentar completarlo).
    descarga_completa = False

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
            response = requests.get(url, params=params, timeout=40)
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            if not features:
                descarga_completa = True
                break # Rompemos el ciclo si ya no hay datos

            all_features.extend(features)

            # Si nos devolvió menos de lo que pedimos, significa que llegamos al final
            if len(features) < batch_size:
                descarga_completa = True
                break

            offset += batch_size
        except Exception as e:
            st.error(tr("No se pudo descargar el catálogo de estaciones del IDEAM: {e}", e=e))
            break

    if not all_features:
        return None

    gdf = gpd.GeoDataFrame.from_features(all_features)
    gdf = gdf.set_crs(epsg=4326)
    gdf = _quitar_duplicados(_quitar_estaciones_de_prueba(gdf))

    if not descarga_completa:
        # Se cortó a medias: se muestra lo que llegó, pero NO se guarda en disco como
        # catalogo completo (no se toca cache_path, así que si ya había uno bueno sigue ahí).
        st.warning(tr("El catálogo de estaciones del IDEAM se descargó incompleto (se cortó la conexión a medio "
                      "camino). Se muestran solo las estaciones que llegaron a tiempo. Vuelve a intentarlo más "
                      "tarde."))
        return _marcar_coordenada_compartida(gdf)

    os.makedirs("data", exist_ok=True)
    if os.path.exists(cache_path):
        # Antes de sobrescribir, dejamos una copia del catalogo anterior (data/*.bak). Si esta
        # descarga nueva completa resultara tener algun problema que no detectamos aqui, siempre
        # queda a mano la ultima version buena conocida.
        try:
            shutil.copy2(cache_path, cache_path + ".bak")
        except OSError:
            pass
    gdf.to_file(cache_path, driver="GeoJSON")

    return _marcar_coordenada_compartida(gdf)


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def load_ideam_catalog_enriquecido() -> gpd.GeoDataFrame:
    """El catalogo con lo que mide cada estacion, su subred y sus codigos homologados (ver dhime_enriquecimiento).
    Si el IDEAM no responde, es el catalogo de siempre."""
    from modules import dhime_enriquecimiento
    catalogo = load_ideam_catalog()
    try:
        return dhime_enriquecimiento.enriquecer_catalogo(catalogo, dhime_enriquecimiento.cargar_tablas())
    except Exception:
        return catalogo
