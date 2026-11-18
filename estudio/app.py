"""Estudio hidrológico express. Etapa 1: delimitar la cuenca.

Se ejecuta con:  streamlit run estudio/app.py   (desde la raíz del repositorio)

Orden de la página: Ajustes (arriba a la derecha) · cabecera con las etapas · datos de entrada y mapa · resultados
· fuentes. El modelo de elevación se lee y se acondiciona en segundo plano apenas hay área; un punto junto a la
etiqueta se enciende cuando está listo (sin pantallas de carga).
"""
from __future__ import annotations

import hashlib
import math
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:   # Streamlit pone en la ruta la carpeta del guion, no la raíz del repositorio
    sys.path.insert(0, str(RAIZ))
os.chdir(RAIZ)   # los módulos del descargador leen data/ con rutas relativas a la raíz

import folium  # noqa: E402
import geopandas as gpd  # noqa: E402
import streamlit as st  # noqa: E402
from folium.plugins import Draw  # noqa: E402
from shapely.geometry import box  # noqa: E402
from streamlit_folium import st_folium  # noqa: E402

st.set_page_config(page_title="Estudio hidrológico", page_icon="💧", layout="wide", initial_sidebar_state="collapsed")

from estudio import almacen, core, fuentes, terreno, trabajos, ui  # noqa: E402
from modules import acceso, estilo, geo_input, ideam_catalog  # noqa: E402

ETAPAS = ["Terreno", "Morfometría", "Datos", "Clima", "Suelos", "Lluvia de diseño", "Caudales", "Informe"]
RADIO_DEFECTO_M = 300
UMBRAL_DEFECTO_KM2 = 1.0

ss = st.session_state
_q = st.query_params
for clave, valor in {"tema": _q.get("tema") if _q.get("tema") in estilo.TEMAS else "sistema",
                     "contraste": _q.get("contraste") if _q.get("contraste") in estilo.CONTRASTES else "sistema",
                     "lite": _q.get("lite") == "1", "idioma": "es",
                     "estudio": None, "bbox": None, "modo_area": "Dibujar", "fuente_dem": "Copernicus",
                     "modo_punto": "Mapa", "punto": None, "radio": RADIO_DEFECTO_M,
                     "umbral": UMBRAL_DEFECTO_KM2, "resultado": None, "aviso": None, "vista": None,
                     "dem_subido": None, "auto_delinear": False, "version_mapa": 0}.items():
    ss.setdefault(clave, valor)
if ss.estudio is None:
    ss.estudio = core.Estudio(nombre="Estudio sin nombre")

# Cada control guarda su valor en una clave propia ("<nombre>_control") y aquí se copia a la clave que usa la página.
# Dos razones: (1) Streamlit no muestra en un control el valor que se puso antes en session_state si el control
# aparece en una corrida posterior (pasa con la pantalla de la clave o con los resultados, que salen después), así
# que el valor inicial se le pasa con `default`/`value`; (2) la copia va al principio porque partes de arriba de la
# página (el modelo en preparación, el mapa) necesitan ya el valor nuevo.
CONTROLES = ("modo_area", "fuente_dem", "modo_punto", "radio", "umbral")
for _c in CONTROLES:
    if f"{_c}_control" in ss and ss[f"{_c}_control"] is not None:
        ss[_c] = ss[f"{_c}_control"]


@st.cache_resource
def _trabajos() -> trabajos.Trabajos:
    return trabajos.Trabajos()


@st.cache_resource
def _almacen():
    return almacen.almacen_configurado()


# Estaciones donde se mide el nivel del río (limnimétricas LM y limnigráficas LG): son las que sirven de punto de
# cierre. Se usa el mismo catálogo del descargador, ya limpio (sin estaciones de prueba ni duplicadas).
CATEGORIAS_HIDROLOGICAS = ("LM", "LG")


@st.cache_data(show_spinner=False)
def _estaciones_hidrologicas():
    g = ideam_catalog.load_ideam_catalog()
    g = g[g["idcategoria"].isin(CATEGORIAS_HIDROLOGICAS)][["idestacion", "nombre", "idcategoria", "geometry"]].copy()
    g["idestacion"] = g["idestacion"].astype(str)
    return g


TR = _trabajos()
ALM = _almacen()
E: core.Estudio = ss.estudio


# ---------------------------------------------------------------------------------------------------------------
# Trabajos de fondo: leer el modelo y acondicionarlo
# ---------------------------------------------------------------------------------------------------------------
def _bbox_txt(b):
    return ",".join(f"{v:.4f}" for v in b)


def _clave_flujo(papel: str) -> str | None:
    """Clave del trabajo de flujo. `papel`: "principal" o "comparacion"."""
    if not ss.bbox:
        return None
    if papel == "principal":
        origen = ss.fuente_dem if ss.fuente_dem == "Copernicus" else f"propio-{ss.dem_subido['hash'] if ss.dem_subido else ''}"
        if origen == "propio-":
            return None
    else:
        origen = "SRTM" if ss.fuente_dem == "Copernicus" else "Copernicus"
    return f"{E.id}|{papel}|{origen}|{_bbox_txt(ss.bbox)}"


def _mensaje(e: Exception) -> str:
    if isinstance(e, terreno.ErrorTerreno):
        return str(e)
    return "No se pudo preparar el modelo de elevación. Revisa la conexión e inténtalo de nuevo."


def _iniciar_flujos():
    bbox = tuple(ss.bbox)
    for papel in ("principal", "comparacion"):
        clave = _clave_flujo(papel)
        if not clave:
            continue
        nombre = f"terreno/dem_{papel}.tif"
        destino = ALM.ruta_local(E.id, nombre)
        origen = clave.split("|")[2]
        subido = ss.dem_subido

        def tarea(origen=origen, destino=destino):
            if origen == "Copernicus":
                dem = terreno.leer_copernicus(bbox, destino)
            elif origen == "SRTM":
                dem = terreno.leer_terrarium(bbox, destino)
            else:
                tmp = destino.with_suffix(".subido.tif")
                tmp.write_bytes(subido["datos"])
                dem = terreno.preparar_dem_propio(tmp, destino, bbox, subido["nombre"])
                tmp.unlink(missing_ok=True)
            return dem, terreno.acondicionar(dem.ruta)

        TR.iniciar(clave, tarea, _mensaje)


def _estado(papel: str):
    clave = _clave_flujo(papel)
    t = TR.obtener(clave) if clave else None
    return t


# ---------------------------------------------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------------------------------------------
def _poner_bbox(b, como: str):
    b = tuple(round(float(v), 5) for v in b)
    if ss.bbox and tuple(ss.bbox) == b:
        return
    ss.bbox = b
    ss.resultado = None
    E.decidir("terreno.area", "rectangulo_wgs84", list(b), ["herramienta_control_borde"],
              nota=f"Área marcada: {como}.", por="hidrologo")
    ss.vista = _encuadre(b)
    ss.version_mapa += 1


def _encuadre(b, alto_px: int = 600):
    """Centro y zoom para que el rectángulo `b` (grados) quepa en el mapa: a zoom z, 256 px cubren 360/2^z grados."""
    o, s, e, n = b
    extension = max(e - o, (n - s) * 1.1, 1e-3)
    zoom = int(math.floor(math.log2(alto_px / 256 * 360 / extension)))
    return {"center": [(s + n) / 2, (o + e) / 2], "zoom": max(5, min(15, zoom))}


def _es(valor: float, decimales: int = 2) -> str:
    """Número con la convención colombiana: punto para miles y coma decimal."""
    return f"{valor:,.{decimales}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _delinear():
    ss.aviso = None
    t = _estado("principal")
    if not ss.bbox:
        ss.aviso = ("Falta el área de trabajo: dibuja un rectángulo, sube un archivo o escribe sus coordenadas.", "")
        return
    if t is None or t.estado == "cargando":
        ss.auto_delinear = True    # se delimita sola apenas el modelo esté listo
        return
    if t.estado == "error":
        ss.aviso = (t.error, "")
        return
    if not ss.punto:
        ss.aviso = ("Falta el punto de cierre: haz clic en el río, elige una estación o escribe sus coordenadas.", "")
        return
    dem, flujo = t.resultado
    lon, lat = ss.punto["lon"], ss.punto["lat"]
    try:
        punto = terreno.ubicar_punto_cierre(flujo, lon, lat, radio_m=ss.radio)
        cuenca = terreno.delinear(flujo, punto)
    except terreno.ErrorTerreno as e:
        ss.aviso = (str(e), "")
        ss.resultado = None
        return
    ss.resultado = {"clave": _clave_flujo("principal"), "cuenca": cuenca, "dem": dem}
    g = gpd.GeoSeries([cuenca.poligono], crs=terreno.CRS_TRABAJO).to_crs(terreno.CRS_GEOGRAFICO)
    ss.vista = _encuadre(tuple(g.total_bounds))    # el mapa se acerca a la cuenca
    ss.version_mapa += 1
    E.decidir("terreno.dem", "modelo", dem.descripcion, [dem.fuente, "minambiente_res940_2026", "igac_res471_2020"],
              por="hidrologo" if dem.fuente == "dem_propio" else "herramienta")
    E.decidir("terreno.punto", "punto_cierre_wgs84", [lon, lat], ["ideam_era_2013", "esri_snap_pour_point"],
              nota=f"Origen: {ss.punto['origen']}.", por="hidrologo")
    E.decidir("terreno.punto", "radio_ajuste_m", ss.radio, ["esri_snap_pour_point"],
              por="hidrologo" if ss.radio != RADIO_DEFECTO_M else "herramienta")
    E.resultados["terreno"] = {"area_km2": round(cuenca.area_km2, 4), "elev_min_m": round(cuenca.elev_min, 1),
                               "elev_max_m": round(cuenca.elev_max, 1), "cortada": cuenca.cortada,
                               "ajuste_punto_m": round(punto.distancia_m, 1)}


def _ampliar():
    cuenca = ss.resultado["cuenca"]
    _poner_bbox(terreno.ampliar_bbox(ss.bbox, cuenca.lados_borde), "ampliado por la prueba de borde")
    ss.auto_delinear = True


def _red_y_comparacion(t_principal, t_comparacion):
    """Red de drenaje y cuenca con el segundo modelo. Se calculan antes de dibujar la página porque el mapa (arriba)
    y las cifras (abajo) muestran lo mismo; se guardan para no repetirlas en cada recarga."""
    res = ss.resultado
    cuenca, flujo = res["cuenca"], t_principal.resultado[1]
    if res.get("umbral_red") != ss.umbral:
        res["red"], res["umbral_red"] = terreno.red_drenaje(flujo, cuenca, ss.umbral), ss.umbral
    if "comparacion" not in res and t_comparacion is not None and t_comparacion.estado == "listo":
        flujo2 = t_comparacion.resultado[1]
        try:
            # en el segundo modelo el punto se busca por área parecida (Lehner, 2011), con un radio de al menos 1 km
            p2 = terreno.ubicar_punto_cierre(flujo2, ss.punto["lon"], ss.punto["lat"], radio_m=max(ss.radio, 1000),
                                             area_objetivo_km2=cuenca.area_km2)
            c2 = terreno.delinear(flujo2, p2)
            res["comparacion"] = {"cuenca": c2, "cifras": terreno.comparar_cuencas(cuenca, c2), "error": ""}
            E.resultados["terreno_comparacion"] = {k: round(v, 3) for k, v in res["comparacion"]["cifras"].items()}
        except terreno.ErrorTerreno as e:
            res["comparacion"] = {"cuenca": None, "cifras": None, "error": str(e)}


# ---------------------------------------------------------------------------------------------------------------
# Página
# ---------------------------------------------------------------------------------------------------------------
estilo.aplicar(ss.tema, ss.contraste, ss.lite, sello=False)
ui.aplicar_css()
ui.guiones("estudio")
# misma puerta y mismas claves que el descargador (secreto [acceso]); se detiene aquí hasta acertar la clave
acceso.puerta(titulo="Estudio hidrológico")
estilo.ajustes()

if ss.bbox:
    _iniciar_flujos()
t_principal, t_comparacion = _estado("principal"), _estado("comparacion")
if ss.auto_delinear and t_principal is not None and t_principal.estado != "cargando":
    ss.auto_delinear = False
    if ss.punto:
        _delinear()
# un resultado de otro modelo o de otra área ya no vale
if ss.resultado and (ss.resultado["clave"] != _clave_flujo("principal") or t_principal is None
                     or t_principal.estado != "listo"):
    ss.resultado = None
if ss.resultado:
    _red_y_comparacion(t_principal, t_comparacion)

ui.cabecera("Estudio hidrológico", "Delimitar la cuenca",
            "Del modelo de elevación a la cuenca y su red de drenaje, en Magna-Sirgas origen nacional. Cada resultado "
            "muestra su fuente; el botón «i» de cada paso explica qué hace y por qué.", ETAPAS, 0)

col_izq, col_der = st.columns([0.42, 0.58], gap="medium")

with col_izq, st.container(key="est_entrada"):
    # 1. Área de trabajo
    ui.seccion("terreno.area", 1)
    st.segmented_control("Cómo marcar el área", ["Dibujar", "Archivo", "Coordenadas"], default=ss.modo_area,
                         key="modo_area_control", required=True, label_visibility="collapsed", width="stretch")
    if ss.modo_area == "Dibujar":
        estilo.md('<p class="y2k-hint">Usa la herramienta de rectángulo del mapa y encierra toda la cuenca con margen.</p>')
    elif ss.modo_area == "Archivo":
        archivos = st.file_uploader("Contorno aproximado de la cuenca (shapefile en ZIP, GeoJSON, KML/KMZ o GeoPackage)",
                                    type=geo_input.EXTENSIONES_ACEPTADAS, accept_multiple_files=True, key="area_archivo")
        if archivos:
            gdf = geo_input.load_vector_file(archivos)
            if gdf is not None and len(gdf):
                o, s, e, n = gdf.to_crs(terreno.CRS_GEOGRAFICO).total_bounds
                margen = 0.03   # ~3 km alrededor del contorno subido
                _poner_bbox((o - margen, s - margen, e + margen, n + margen), "contorno subido con 3 km de margen")
    else:
        b = ss.bbox or (-74.12, 4.52, -73.80, 5.00)
        # dos filas (oeste-este, sur-norte): en el celular las columnas se apilan en ese mismo orden
        c1, c2 = st.columns(2)
        oeste = c1.number_input("Oeste (longitud)", value=float(b[0]), format="%.4f", step=0.01)
        este = c2.number_input("Este (longitud)", value=float(b[2]), format="%.4f", step=0.01)
        c1, c2 = st.columns(2)
        sur = c1.number_input("Sur (latitud)", value=float(b[1]), format="%.4f", step=0.01)
        norte = c2.number_input("Norte (latitud)", value=float(b[3]), format="%.4f", step=0.01)
        if st.button("Usar estas coordenadas", key="usar_coord", width="stretch"):
            try:
                terreno._validar_bbox((oeste, sur, este, norte))
                _poner_bbox((oeste, sur, este, norte), "coordenadas escritas")
                ss.version_mapa += 1
            except terreno.ErrorTerreno as e:
                ss.aviso = (str(e), "")

    # 2. Modelo de elevación
    ui.seccion("terreno.dem", 2, estado=t_principal.estado if t_principal else None)
    st.segmented_control("Fuente del modelo", ["Copernicus", "Archivo propio"], default=ss.fuente_dem,
                         key="fuente_dem_control", required=True,
                         label_visibility="collapsed", width="stretch")
    if ss.fuente_dem == "Archivo propio":
        tif = st.file_uploader("Modelo de elevación (GeoTIFF)", type=["tif", "tiff"], key="dem_archivo")
        if tif is not None:
            datos = tif.getvalue()
            ss.dem_subido = {"nombre": tif.name, "datos": datos, "hash": hashlib.sha1(datos).hexdigest()[:10]}
    if t_principal is not None and t_principal.estado == "listo":
        dem, flujo = t_principal.resultado
        ui.linea_fuentes([dem.fuente], f"{dem.descripcion} ·")
        for nota in dem.notas:
            estilo.aviso(nota, tono="info")
    elif t_principal is not None and t_principal.estado == "error":
        estilo.aviso(t_principal.error, tono="error")

    # 3. Punto de cierre
    ui.seccion("terreno.punto", 3)
    st.segmented_control("Cómo elegir el punto", ["Mapa", "Estación", "Coordenadas"], default=ss.modo_punto,
                         key="modo_punto_control", required=True, label_visibility="collapsed", width="stretch")
    if ss.modo_punto == "Estación":
        if ss.bbox:
            est = _estaciones_hidrologicas()
            est = est[est.intersects(box(*ss.bbox))]
            if len(est):
                opciones = {" ".join(str(r.nombre).split()): (r.geometry.x, r.geometry.y) for r in est.itertuples()}
                elegida = st.selectbox("Estación hidrológica del área", list(opciones), index=None,
                                       placeholder="Elige una estación", key="estacion_cierre")
                if elegida:
                    lon, lat = opciones[elegida]
                    if not ss.punto or ss.punto.get("origen") != f"estación {elegida}":
                        ss.punto = {"lon": lon, "lat": lat, "origen": f"estación {elegida}"}
            else:
                estilo.aviso("No hay estaciones hidrológicas del IDEAM dentro del área.", tono="info")
        else:
            estilo.md('<p class="y2k-hint">Primero marca el área de trabajo.</p>')
    elif ss.modo_punto == "Coordenadas":
        c1, c2 = st.columns(2)
        lon = c1.number_input("Longitud", value=float(ss.punto["lon"]) if ss.punto else -73.9987, format="%.5f", step=0.001)
        lat = c2.number_input("Latitud", value=float(ss.punto["lat"]) if ss.punto else 4.9429, format="%.5f", step=0.001)
        if st.button("Usar este punto", key="usar_punto", width="stretch"):
            ss.punto = {"lon": lon, "lat": lat, "origen": "coordenadas escritas"}
    else:
        estilo.md('<p class="y2k-hint">Haz clic sobre el río, en el sitio donde termina la cuenca.</p>')
    st.number_input("Radio de ajuste al cauce (m)", min_value=30, max_value=2000, step=30, value=int(ss.radio),
                    key="radio_control",
                    help="La página mueve el punto a la celda del cauce con más acumulación dentro de este radio. "
                         "Si el punto salta a otro río, redúcelo.")

    if ss.aviso:
        estilo.aviso(ss.aviso[0], ss.aviso[1], tono="alerta")
    st.button("Delimitar la cuenca", key="delinear", type="primary", width="stretch", on_click=_delinear)

# --------------------------------------------- Mapa ---------------------------------------------
with col_der, st.container(key="est_mapa"):
    centro = ss.vista["center"] if ss.vista else [4.6, -74.1]
    zoom = ss.vista["zoom"] if ss.vista else 6
    m = folium.Map(location=centro, zoom_start=zoom, tiles=None, control_scale=True)
    folium.TileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
                     attr=estilo.ATRIB_ESRI_RELIEVE, name="Relieve").add_to(m)
    # créditos del mapa en una línea discreta (en el celular, a todo lo ancho, no tapan la escala)
    m.get_root().header.add_child(folium.Element(
        "<style>.leaflet-control-attribution{font:11px/1.5 Figtree,system-ui,sans-serif !important;"
        "background:rgba(255,255,255,.8) !important;border-radius:999px 0 0 0;padding:1px 8px !important;"
        "max-width:calc(100vw - 90px);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}</style>"))
    Draw(draw_options={"polyline": False, "polygon": False, "circle": False, "marker": False, "circlemarker": False,
                       "rectangle": {"shapeOptions": {"color": "#1258D6", "weight": 2, "fillOpacity": 0.04}}},
         edit_options={"edit": False}).add_to(m)

    capa = folium.FeatureGroup(name="estudio")
    if ss.bbox:
        o, s, e, n = ss.bbox
        folium.Rectangle([[s, o], [n, e]], color="#1258D6", weight=1.5, fill=False, dash_array="6 4",
                         tooltip="Área de trabajo").add_to(capa)
    res = ss.resultado
    if res:
        cuenca = res["cuenca"]
        g = gpd.GeoSeries([cuenca.poligono], crs=terreno.CRS_TRABAJO).to_crs(terreno.CRS_GEOGRAFICO)
        folium.GeoJson(g.__geo_interface__, style_function=lambda _: {"color": "#0E6B36", "weight": 2.5,
                                                                      "fillColor": "#22C55E", "fillOpacity": 0.12},
                       tooltip="Cuenca").add_to(capa)
        if len(res["red"]):
            folium.GeoJson(res["red"].to_crs(terreno.CRS_GEOGRAFICO).__geo_interface__,
                           style_function=lambda f: {"color": "#0891B2", "weight": 0.8 + 0.6 * f["properties"]["orden"]},
                           tooltip=folium.GeoJsonTooltip(["orden", "longitud_km"], ["Orden", "Longitud (km)"])
                           ).add_to(capa)
        if res.get("comparacion") and res["comparacion"]["cuenca"] is not None:
            g2 = gpd.GeoSeries([res["comparacion"]["cuenca"].poligono], crs=terreno.CRS_TRABAJO).to_crs(terreno.CRS_GEOGRAFICO)
            folium.GeoJson(g2.__geo_interface__, style_function=lambda _: {"color": "#B27DFF", "weight": 1.5,
                                                                           "dashArray": "5 4", "fillOpacity": 0},
                           tooltip="Cuenca con el segundo modelo").add_to(capa)
        p = cuenca.punto
        lonp, latp = gpd.GeoSeries.from_xy([p.x], [p.y], crs=terreno.CRS_TRABAJO).to_crs(terreno.CRS_GEOGRAFICO).iloc[0].coords[0]
        folium.CircleMarker([latp, lonp], radius=6, color="#FFFFFF", weight=2, fill=True, fill_color="#A8201A",
                            fill_opacity=1, tooltip="Punto de cierre ajustado al cauce").add_to(capa)
    if ss.punto:
        folium.CircleMarker([ss.punto["lat"], ss.punto["lon"]], radius=4, color="#A8201A", weight=1.5, fill=False,
                            tooltip="Punto elegido").add_to(capa)

    salida = st_folium(m, height=620, use_container_width=True, feature_group_to_add=capa,
                       returned_objects=["all_drawings", "last_clicked"], key=f"mapa_{ss.version_mapa}")
    if salida:
        dibujos = salida.get("all_drawings") or []
        if ss.modo_area == "Dibujar" and dibujos:
            coords = dibujos[-1]["geometry"]["coordinates"][0]
            xs, ys = [c[0] for c in coords], [c[1] for c in coords]
            nuevo = (min(xs), min(ys), max(xs), max(ys))
            if not ss.bbox or tuple(round(v, 5) for v in nuevo) != tuple(ss.bbox):
                try:
                    terreno._validar_bbox(nuevo)
                    _poner_bbox(nuevo, "rectángulo dibujado en el mapa")
                    st.rerun()
                except terreno.ErrorTerreno as e:
                    ss.aviso = (str(e), "")
        clic = salida.get("last_clicked")
        if ss.modo_punto == "Mapa" and clic and not dibujos[len(dibujos):]:
            nuevo = {"lon": clic["lng"], "lat": clic["lat"], "origen": "clic en el mapa"}
            if ss.punto != nuevo and (ss.get("_ultimo_clic") != (clic["lng"], clic["lat"])):
                ss._ultimo_clic = (clic["lng"], clic["lat"])
                ss.punto = nuevo
                st.rerun()

# --------------------------------------------- Resultados ---------------------------------------------
if ss.resultado:
    cuenca = ss.resultado["cuenca"]
    flujo = t_principal.resultado[1]
    with st.container(key="est_resultado"):
        ui.seccion("terreno.cuenca", 4, "Cuenca delimitada")
        p = cuenca.punto
        ui.kpis([(f"{cuenca.area_km2:,.2f} km²".replace(",", "X").replace(".", ",").replace("X", "."),
                  "Área", f"{cuenca.area_km2 * 100:,.2f} ha".replace(",", "X").replace(".", ",").replace("X", ".")),
                 (f"{cuenca.elev_min:,.0f} – {cuenca.elev_max:,.0f} m".replace(",", "."), "Elevación",
                  "Mínima y máxima del modelo"),
                 (f"{p.distancia_m:,.0f} m".replace(",", "."), "Ajuste del punto",
                  f"Movido al cauce; radio {ss.radio} m")])
        ui.linea_fuentes(["ideam_era_2013", "barnes_2014_priority_flood", "ocallaghan_mark_1984"],
                         "Procedimiento:")
        if cuenca.cortada:
            estilo.aviso(f"La cuenca toca el borde del área ({', '.join(cuenca.lados_borde)}): puede faltar terreno "
                         "aguas arriba.", "Amplía el área hacia ese lado y se vuelve a delimitar con el mismo punto.",
                         tono="alerta")
            st.button("Ampliar el área y delimitar de nuevo", key="ampliar", on_click=_ampliar)
        else:
            estilo.aviso("La cuenca no toca el borde del área: está completa dentro del modelo.", tono="info")

        # Red de drenaje
        ui.seccion("terreno.red", 5)
        st.slider("Umbral de área para formar cauce (km²)", 0.05, 5.0, value=float(ss.umbral), step=0.05,
                  key="umbral_control", format="%.2f",
                  help="Más bajo: red más densa. Queda declarado en el informe, porque la densidad de drenaje depende "
                       "de este valor.")
        red = ss.resultado["red"]
        E.decidir("terreno.red", "umbral_km2", ss.umbral, ["mads_rondas_2018"],
                  por="hidrologo" if ss.umbral != UMBRAL_DEFECTO_KM2 else "herramienta")
        largo = float(red["longitud_km"].sum()) if len(red) else 0.0
        ui.kpis([(f"{largo:,.1f} km".replace(",", "X").replace(".", ",").replace("X", "."), "Longitud de cauces",
                  f"{len(red)} tramos"),
                 (f"{int(red['orden'].max()) if len(red) else 0}", "Orden máximo", "Strahler (1957)"),
                 (f"{largo / cuenca.area_km2:.2f}".replace(".", ","), "Densidad de drenaje", "km/km² con este umbral")])
        ui.linea_fuentes(["mads_rondas_2018", "strahler_1957"])

        # Comparación con el segundo modelo
        ui.seccion("terreno.comparacion", 6)
        otro = "SRTM (NASA)" if ss.fuente_dem == "Copernicus" else "Copernicus GLO-30"
        comp = ss.resultado.get("comparacion")
        if comp is None and (t_comparacion is None or t_comparacion.estado == "cargando"):
            ui.etiqueta(f"Delimitando con {otro}", "cargando", "Segundo modelo")
        elif comp is None:
            estilo.aviso(f"No se pudo leer {otro}: la comparación queda pendiente.", t_comparacion.error, tono="alerta")
        elif comp["error"]:
            estilo.aviso(f"Con {otro} no se pudo delimitar la cuenca.", comp["error"], tono="alerta")
        else:
            c2, cifras = comp["cuenca"], comp["cifras"]
            ui.kpis([(f"{_es(c2.area_km2)} km²", f"Área con {otro}",
                      f"Punto ajustado {_es(c2.punto.distancia_m, 0)} m"),
                     (f"{cifras['diferencia_pct']:+.1f} %".replace(".", ","), "Diferencia de área",
                      "Frente al modelo principal"),
                     (f"{_es(cifras['coincidencia_pct'], 1)} %", "Coincidencia", "Intersección sobre unión")])
            ui.linea_fuentes(["ideam_protocolo_2018", "herramienta_comparar_dem", "lehner_2011_snapping"])

        # Exportar
        ui.seccion("terreno.exportar", 7)
        capas = terreno.capas(cuenca, red, ss.resultado["dem"].fuente, ss.umbral)
        gpkg = terreno.exportar_gpkg(capas, ALM.ruta_local(E.id, "terreno/cuenca.gpkg"))
        kml = terreno.exportar_kml(capas, ALM.ruta_local(E.id, "terreno/cuenca.kml"))
        c1, c2, c3 = st.columns(3)
        c1.download_button("GeoPackage (QGIS)", gpkg.read_bytes(), "cuenca.gpkg", "application/geopackage+sqlite3",
                           width="stretch", icon=":material/layers:")
        c2.download_button("KML (Google Earth)", kml.read_bytes(), "cuenca.kml",
                           "application/vnd.google-earth.kml+xml", width="stretch", icon=":material/public:")
        c3.download_button("Estudio completo (ZIP)", almacen.exportar_zip(ALM, E), f"{E.nombre}.zip",
                           "application/zip", width="stretch", icon=":material/folder_zip:",
                           help="Guarda el estudio para seguirlo otro día: sube este ZIP y queda como lo dejaste.")
        ui.linea_fuentes(["minambiente_res940_2026", "igac_res471_2020"], "Formato y sistema:")

# --------------------------------------------- Fuentes ---------------------------------------------
with st.container(key="est_fuentes"):
    estilo.md('<p class="est-sec" role="heading" aria-level="2">Fuentes de esta etapa</p>')
    estilo.md('<p class="y2k-hint">Cada fuente lleva su marca. Prioridad: entidades ambientales, luego otras '
              'entidades oficiales; lo que no tiene norma colombiana se declara.</p>')
    claves = sorted({c for p_ in ("terreno.area", "terreno.dem", "terreno.flujo", "terreno.punto", "terreno.cuenca",
                                  "terreno.red", "terreno.comparacion", "terreno.exportar")
                     for c in __import__("estudio.pasos", fromlist=["paso"]).paso(p_).fuentes})
    ui.bibliografia(claves)


# Vigía: mientras haya un modelo en preparación, revisa cada segundo y recarga una sola vez cuando termina
@st.fragment(run_every=1.0)
def _vigia():
    claves = [c for c in (_clave_flujo("principal"), _clave_flujo("comparacion")) if c]
    pendientes = TR.pendientes(claves)
    if ss.get("_habia_pendientes") and not pendientes:
        ss._habia_pendientes = False
        st.rerun(scope="app")
    ss._habia_pendientes = pendientes


with st.container(key="y2k_ocultos"):
    _vigia()
