import folium
import pandas as pd
from folium.plugins import Draw, FastMarkerCluster
from shapely.geometry import shape
import geopandas as gpd
from modules.calidad import clasificar_calidad
from modules.ideam_downloader import codigo_de_estacion

# ===========================================================================
# MAPA 2D (Leaflet)
# ---------------------------------------------------------------------------
# El mapa "base" (capas de fondo + herramientas de dibujo + la cuenca como
# figura EDITABLE) solo cambia cuando cambia la cuenca, asi Streamlit no lo
# redibuja en cada clic. Estaciones y buffer van en una capa dinamica que se
# actualiza sin recargar el mapa (feature_group_to_add de st_folium).
# ===========================================================================

AZUL = "#1C6FD8"
NARANJA = "#FAB219"
GRIS = "#7C87A3"


def mapa_base(cuenca_gdf=None, tema="claro"):
    if cuenca_gdf is not None and not cuenca_gdf.empty:
        minx, miny, maxx, maxy = cuenca_gdf.total_bounds
        centro, zoom = [(miny + maxy) / 2, (minx + maxx) / 2], 11
    else:
        centro, zoom = [4.6, -74.1], 6

    m = folium.Map(location=centro, zoom_start=zoom, tiles=None, control_scale=True, prefer_canvas=True)
    # Mapas base sin clave (CARTO ahora exige API key y muestra una marca de agua)
    esri = "https://server.arcgisonline.com/ArcGIS/rest/services/{}/MapServer/tile/{{z}}/{{y}}/{{x}}"
    # Satelite arranca visible; los demas se eligen en el boton de capas (arriba a la derecha)
    folium.TileLayer(tiles=esri.format("World_Imagery"), attr="Esri, Maxar", name="Satélite").add_to(m)
    folium.TileLayer(tiles=esri.format("World_Topo_Map"), attr="Esri", name="Relieve", show=False).add_to(m)
    folium.TileLayer("OpenStreetMap", name="Calles", show=False).add_to(m)
    # Luces nocturnas de la NASA (VIIRS Black Marble 2016): solo trae detalle hasta el nivel 8,
    # de cerca se ve borroso pero muestra bien los pueblos y ciudades iluminados
    folium.TileLayer(
        tiles="https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_Black_Marble/default/2016-01-01/"
              "GoogleMapsCompatible_Level8/{z}/{y}/{x}.png",
        attr="NASA EOSDIS GIBS", name="Satélite de noche", show=False, max_native_zoom=8, max_zoom=19,
    ).add_to(m)

    # La cuenca va dentro del grupo de dibujo: asi se pueden mover sus
    # esquinas (lapiz) o borrarla (basurita) con las herramientas del mapa
    editables = folium.FeatureGroup(name="Cuenca")
    if cuenca_gdf is not None:
        for geom in cuenca_gdf.geometry:
            for parte in getattr(geom, "geoms", [geom]):
                if parte.geom_type == "Polygon":
                    folium.Polygon(
                        locations=[(lat, lon) for lon, lat in parte.exterior.coords],
                        color=AZUL, weight=3, fill=True, fill_color=AZUL, fill_opacity=0.12,
                    ).add_to(editables)
    editables.add_to(m)

    estilo = {"color": AZUL, "weight": 3, "fillColor": AZUL, "fillOpacity": 0.12}
    Draw(
        feature_group=editables,
        position="topleft",
        draw_options={
            "polyline": False, "circle": False, "circlemarker": False, "marker": False,
            "polygon": {"allowIntersection": False, "showArea": True, "shapeOptions": estilo},
            "rectangle": {"shapeOptions": estilo},
        },
        edit_options={"edit": True, "remove": True},
    ).add_to(m)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)
    if cuenca_gdf is not None and not cuenca_gdf.empty:
        minx, miny, maxx, maxy = cuenca_gdf.total_bounds
        m.fit_bounds([[miny, minx], [maxy, maxx]], padding=(30, 30))
    return m


def cuenca_desde_dibujos(dibujos):
    """GeoDataFrame con los poligonos dibujados en el mapa (None si no hay)."""
    geoms = []
    for feature in dibujos or []:
        try:
            geom = shape(feature["geometry"])
        except Exception:
            continue
        if geom.geom_type in ("Polygon", "MultiPolygon") and not geom.is_empty:
            geoms.append(geom if geom.is_valid else geom.buffer(0))
    if not geoms:
        return None
    return gpd.GeoDataFrame(geometry=geoms, crs="EPSG:4326")


def _tarjeta(row, codigo):
    nombre = str(row.get("nombre", codigo))
    partes = [f"<b style='font-size:13px'>{nombre}</b>",
              f"<span style='color:#7C87A3'>{codigo} · {_altitud_txt(row)}</span>"]
    if "Porcentaje (%)" in row and pd.notna(row["Porcentaje (%)"]):
        if row.get("Serie DHIME") == "No":
            partes.append("<span style='color:#D03B3B'>Sin serie en DHIME</span>")
        else:
            partes.append(f"Cantidad probable <b>{row['Porcentaje (%)']:.0f} %</b> · {row.get('Clase calidad', '')}")
            if row.get("Inicio serie"):
                partes.append(f"<span style='color:#7C87A3'>Serie {str(row['Inicio serie'])[:4]}–{str(row['Fin serie'])[:4]}</span>")
    if row.get("zona"):
        partes.append(f"<span style='color:#7C87A3'>{'En la cuenca' if row['zona'] == 'cuenca' else 'En el buffer'}</span>")
    if row.get("altitud_dudosa") and row.get("terreno") is not None:
        partes.append(f"<span style='color:#D0602F'>⚠ Altitud inconsistente: el terreno mide"
                      f"{row['terreno']:,.0f} m</span>".replace(",", "."))
    return "<div style='font-family:Figtree,sans-serif;font-size:12px;line-height:1.45'>" + "<br>".join(partes) + "</div>"


def _altitud_txt(row):
    try:
        return f"{float(row.get('altitud')):,.0f} m".replace(",", ".")
    except (TypeError, ValueError):
        return "altitud sin dato"


def capa_dinamica(area_gdf=None, estaciones=None, umbral=0, seleccionada=None, catalogo=None):
    """Capa que cambia sin recargar el mapa: buffer, estaciones y la seleccionada."""
    fg = folium.FeatureGroup(name="Estaciones")
    if area_gdf is not None:
        folium.GeoJson(
            area_gdf.__geo_interface__,
            style_function=lambda _: {"color": NARANJA, "weight": 2, "dashArray": "6 5",
                                      "fillColor": NARANJA, "fillOpacity": 0.10},
            interactive=False,
        ).add_to(fg)

    if estaciones is not None and not estaciones.empty:
        evaluadas = "Porcentaje (%)" in estaciones.columns
        for idx, row in estaciones.iterrows():
            codigo = codigo_de_estacion(row, idx)
            pct = row["Porcentaje (%)"] if evaluadas else None
            ok = evaluadas and row.get("Serie DHIME") == "Sí" and row.get("Cantidad Probable", 0) > 0 and pct >= umbral
            color = clasificar_calidad(pct)["color"] if ok else GRIS
            es_sel = codigo == seleccionada
            # Con un minimo de cantidad probable, las descartadas (puntos grises) se quitan del mapa
            if evaluadas and umbral > 0 and not ok and not es_sel:
                continue
            if es_sel:
                folium.CircleMarker(location=[row.geometry.y, row.geometry.x], radius=16, color=AZUL, weight=3,
                                    fill=True, fill_color="#FFFFFF", fill_opacity=0.35).add_to(fg)
            folium.CircleMarker(
                location=[row.geometry.y, row.geometry.x],
                radius=9 if es_sel else 7 if ok else 5,
                # borde naranja = altitud dudosa
                color="#D0602F" if row.get("altitud_dudosa") else "#16213A" if ok or es_sel else GRIS,
                weight=2.5 if es_sel or row.get("altitud_dudosa") else 1.2,
                fill=ok or es_sel, fill_color=color, fill_opacity=0.95 if ok else 0.4,
                tooltip=folium.Tooltip(_tarjeta(row, codigo), sticky=True),
            ).add_to(fg)
    elif catalogo is not None and not catalogo.empty:
        # Sin cuenca todavia: el catalogo nacional agrupado, para ubicarse
        FastMarkerCluster(data=list(zip(catalogo.geometry.y, catalogo.geometry.x)), name="Catálogo nacional").add_to(fg)
    return fg
