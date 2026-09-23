import streamlit as st
import geopandas as gpd
import tempfile
import os
import zipfile

# Formatos que acepta el cargador de la barra lateral
EXTENSIONES_ACEPTADAS = ["zip", "shp", "shx", "dbf", "prj", "cpg", "geojson", "json", "kml", "kmz", "gpkg"]
PARTES_SHAPEFILE = {".shp", ".shx", ".dbf", ".prj", ".cpg", ".qix", ".sbn", ".sbx"}


def _buscar_archivos(carpeta, extension):
    """Busca archivos con esa extension en la carpeta y sus subcarpetas."""
    encontrados = []
    for raiz, _, archivos in os.walk(carpeta):
        for nombre in archivos:
            if nombre.lower().endswith(extension) and not nombre.startswith("._"):  # "._" = basura de Mac
                encontrados.append(os.path.join(raiz, nombre))
    return sorted(encontrados)


def _leer_shapefile(carpeta):
    shp_files = _buscar_archivos(carpeta, ".shp")
    if not shp_files:
        st.error("No se encontró ningún archivo .shp (ni en subcarpetas).")
        return None
    # Un shapefile necesita al menos sus archivos .shx y .dbf al lado
    for ruta in shp_files:
        base = os.path.splitext(ruta)[0]
        faltan = [ext for ext in (".shx", ".dbf")
                  if not (os.path.exists(base + ext) or os.path.exists(base + ext.upper()))]
        if faltan:
            st.error(f"Al shapefile **{os.path.basename(ruta)}** le falta: {', '.join(faltan)}. "
                     f"Súbelo junto con sus archivos .shx, .dbf y .prj (o todo en un ZIP).")
            return None

    # Si hay varios, se prefiere el primero que tenga poligonos (la cuenca)
    elegido = None
    for ruta in shp_files:
        capa = gpd.read_file(ruta)
        if elegido is None:
            elegido = (ruta, capa)
        if capa.geom_type.isin(["Polygon", "MultiPolygon"]).any():
            elegido = (ruta, capa)
            break
    if len(shp_files) > 1:
        st.info(f"Había {len(shp_files)} shapefiles; se usó **{os.path.basename(elegido[0])}**.")
    return elegido[1]


def load_vector_file(uploaded_files) -> gpd.GeoDataFrame:
    """
    Recibe uno o varios archivos subidos y devuelve un GeoDataFrame.
    - ZIP con un shapefile adentro (tambien en subcarpetas)
    - Las partes sueltas del shapefile (.shp + .shx + .dbf + .prj) subidas juntas
    - GeoJSON / JSON, KML, KMZ, GeoPackage
    """
    if not isinstance(uploaded_files, list):
        uploaded_files = [uploaded_files]
    extensiones = {os.path.splitext(f.name)[1].lower() for f in uploaded_files}

    with tempfile.TemporaryDirectory() as tmp_dir:
        rutas = []
        for archivo in uploaded_files:
            ruta = os.path.join(tmp_dir, os.path.basename(archivo.name))
            with open(ruta, "wb") as f:
                f.write(archivo.getbuffer())
            rutas.append(ruta)

        try:
            # Partes sueltas de un shapefile
            if extensiones & PARTES_SHAPEFILE:
                if ".shp" not in extensiones:
                    st.error("Para un shapefile suelto sube juntos el .shp, .shx, .dbf y .prj (o todo en un ZIP).")
                    return None
                return _leer_shapefile(tmp_dir)

            if len(rutas) > 1:
                st.error("Sube un solo archivo (o las partes de un mismo shapefile).")
                return None

            ruta = rutas[0]
            ext = os.path.splitext(ruta)[1].lower()

            if ext == ".zip":
                carpeta = os.path.join(tmp_dir, "zip")
                with zipfile.ZipFile(ruta) as zf:
                    zf.extractall(carpeta)
                if _buscar_archivos(carpeta, ".shp"):
                    return _leer_shapefile(carpeta)
                # ZIP sin shapefile: se intenta con otros formatos que traiga
                for otra_ext in (".gpkg", ".geojson", ".json", ".kml"):
                    otros = _buscar_archivos(carpeta, otra_ext)
                    if otros:
                        return gpd.read_file(otros[0])
                st.error("El ZIP no trae ningún .shp, .gpkg, .geojson ni .kml.")
                return None

            if ext == ".kmz":
                # Un KMZ es un ZIP con un archivo .kml adentro
                carpeta = os.path.join(tmp_dir, "kmz")
                with zipfile.ZipFile(ruta) as zf:
                    zf.extractall(carpeta)
                kmls = _buscar_archivos(carpeta, ".kml")
                if not kmls:
                    st.error("El KMZ no trae ningún archivo .kml adentro.")
                    return None
                return gpd.read_file(kmls[0])

            if ext in (".geojson", ".json", ".kml", ".gpkg"):
                return gpd.read_file(ruta)

            st.error("Formato de archivo no soportado.")
            return None

        except zipfile.BadZipFile:
            st.error("El archivo comprimido está dañado o no es un ZIP válido.")
            return None
        except Exception as e:
            st.error(f"No se pudo leer el archivo: {e}")
            return None
