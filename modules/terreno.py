import io
import math
import requests
import pydeck as pdk
import streamlit as st
from PIL import Image

# ===========================================================================
# VISTA 3D CON RELIEVE REAL
# ---------------------------------------------------------------------------
# El terreno sale del modelo de elevacion abierto "Terrarium" (AWS / Mapzen):
# tiles PNG donde cada pixel guarda la altura en metros. El mismo modelo se
# usa para dibujar el relieve y para apoyar cada estacion en el terreno, asi
# ningun pin flota ni queda enterrado. La etiqueta muestra la altitud del
# catalogo del IDEAM (que casi siempre coincide con el terreno a pocos metros).
# ===========================================================================

URL_ELEVACION = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TEXTURAS = {
    "Satélite": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    "Topográfico": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
}
ZOOM_DEM = 12          # ~35 m por pixel en Colombia
EXAGERACION = 2.0      # el relieve se ve el doble de alto para notar los desniveles
ZOOM_MAX_TILES = 15    # nivel mas fino que publica Terrarium (~5 m por pixel de textura)
# Si la altitud del catalogo se aleja mas que esto del terreno real en ese punto,
# probablemente esta mal digitada (p. ej. 1.900 m en plena sabana de Bogota)
ALTITUD_DUDOSA_M = 200

# Orbita de la camara alrededor de la estacion elegida
ALTO_PIN_SEL = 260          # m reales del pin de la seleccionada (en la escena x EXAGERACION)
DISTANCIA_ORBITA = 4000     # m de la camara a la estacion
ALTO_VISOR = 650            # px, alto del mapa 3D en la app (para convertir distancia en zoom)
PITCH_MIN, PITCH_MAX = 35, 68   # inclinacion de la camara: 35 = casi cenital, 68 = casi a ras
MARGEN_VISTA = 6            # grados de holgura sobre el horizonte de montanas
DISTANCIAS_HORIZONTE = (100, 200, 350, 550, 800, 1100, 1500, 2000, 2600, 3300, 4000)


def _num(n):
    return f"{n:,.0f}".replace(",", ".")


# cache_resource devuelve la misma imagen sin copiarla (cache_data la copiaria en cada
# consulta, y se consultan cientos de puntos por dibujo)
@st.cache_resource(show_spinner=False, max_entries=400)
def _tile(z, x, y):
    respuesta = requests.get(URL_ELEVACION.format(z=z, x=x, y=y), timeout=30)
    respuesta.raise_for_status()
    return Image.open(io.BytesIO(respuesta.content)).convert("RGB")


def altura_terreno(lon, lat, z=ZOOM_DEM):
    """Altura del terreno en metros (modelo Terrarium) en un punto. None si falla."""
    n = 2 ** z
    xf = (lon + 180) / 360 * n
    yf = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    x, y = int(xf), int(yf)
    try:
        imagen = _tile(z, x, y)
    except Exception:
        return None
    r, g, b = imagen.getpixel((min(255, int((xf - x) * 256)), min(255, int((yf - y) * 256))))
    return r * 256 + g + b / 256 - 32768


# Vuelta de camara alrededor de la estacion elegida. Streamlit no deja animar la vista
# desde Python, asi que este guion busca el visor deck.gl ya dibujado en la pagina (por
# dentro de React) y le cambia la vista cuadro a cuadro. Si el usuario toca el mapa, para.
# La camara de deck.gl gira alrededor del punto al que mira; "position" sube ese punto a la
# mitad del pin de la estacion, asi la estacion queda en el centro y la camara la rodea.
_ORBITA = """
<script>
(async () => {
  const w = window.parent, d = w.document;
  const O = __ORBITA__;
  const esperar = ms => new Promise(r => setTimeout(r, ms));
  function buscarDeck() {
    const lienzo = d.querySelector('[data-testid="stDeckGlJsonChart"] canvas');
    if (!lienzo) return null;
    const clave = Object.keys(lienzo).find(k => k.startsWith("__reactFiber$"));
    let fibra = clave && lienzo[clave];
    for (let i = 0; fibra && i < 40; i++, fibra = fibra.return) {
      let gancho = fibra.memoizedState;
      for (let j = 0; gancho && typeof gancho === "object" && j < 60; j++, gancho = gancho.next) {
        const v = gancho.memoizedState;
        if (v && v.current && v.current.deck && typeof v.current.deck.setProps === "function") return v.current.deck;
      }
    }
    return null;
  }
  let deck = null;
  for (let i = 0; i < 80 && !deck; i++) { deck = buscarDeck(); if (!deck) await esperar(150); }
  if (!deck) return;
  await esperar(300);
  let parar = false;
  const detener = () => { parar = true; };
  const zona = d.querySelector('[data-testid="stDeckGlJsonChart"]');
  ["pointerdown", "wheel", "touchstart", "keydown"].forEach(e => zona.addEventListener(e, detener, {once: true, capture: true}));
  // Una vuelta lenta (60 s) que arranca y frena suave; los primeros 5 s la camara baja hacia la estacion
  const ACERCAMIENTO = 5000, VUELTA = 60000, RAMPA = 7000;
  const vel = 360 / (VUELTA - RAMPA);
  const giro = t => t <= 0 ? 0 : t < RAMPA ? vel * t * t / (2 * RAMPA)
    : t < VUELTA - RAMPA ? vel * (t - RAMPA / 2)
    : t < VUELTA ? 360 - vel * Math.pow(VUELTA - t, 2) / (2 * RAMPA) : 360;
  const suave = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
  const normal = b => ((b % 360) + 540) % 360 - 180;
  // Inclinacion segun donde queda la camara (del lado opuesto hacia donde mira): sube
  // al pasar detras de una montana para no perder la estacion, baja donde esta despejado
  const inclinacion = rumbo => {
    const az = ((((rumbo + 180) % 360) + 360) % 360) / 10;
    const i0 = Math.floor(az) % 36, i1 = (i0 + 1) % 36, f = az - Math.floor(az);
    return O.pitch[i0] * (1 - f) + O.pitch[i1] * f;
  };
  const inicio = w.performance.now();
  // Streamlit maneja la vista como estado de React (viewState + onViewStateChange): se le
  // avisa cada cuadro por ese mismo canal, igual que cuando el usuario arrastra el mapa
  const mover = cambios => {
    const actual = deck.props.viewState || {};
    const nueva = {...actual, ...cambios};
    if (typeof deck.props.onViewStateChange === "function") {
      deck.props.onViewStateChange({viewState: nueva, oldViewState: actual, interactionState: {}, viewId: "default-view"});
    } else {
      deck.setProps({viewState: nueva});
    }
  };
  const cuadro = ahora => {
    if (parar) return;
    const t = Math.min(ahora - inicio, VUELTA);
    const a = suave(Math.min(1, t / ACERCAMIENTO));
    const rumbo = O.inicio.bearing + (O.rumbo + giro(t) - O.inicio.bearing) * a;
    mover({
      longitude: O.lon, latitude: O.lat, position: [0, 0, O.pivote], maxPitch: 85,
      zoom: O.inicio.zoom + (O.zoom - O.inicio.zoom) * a,
      pitch: O.inicio.pitch + (inclinacion(rumbo) - O.inicio.pitch) * a,
      bearing: normal(rumbo),
    });
    if (t < VUELTA) w.requestAnimationFrame(cuadro);
  };
  w.requestAnimationFrame(cuadro);
})();
</script>
"""


# Algunos navegadores (Safari en modo privado o con proteccion avanzada contra rastreo, Brave,
# Firefox "resistFingerprinting") meten ruido a proposito en los pixeles que lee una pagina.
# Las alturas del relieve vienen en los pixeles, asi que ese ruido se ve como miles de puas.
# Esto no se puede apagar desde la pagina: se detecta (una imagen de prueba que no vuelve
# identica) y se avisa encima del mapa 3D.
AVISO_NAVEGADOR = """
<script>
(async () => {
  const c = document.createElement("canvas"); c.width = c.height = 16;
  const g = c.getContext("2d", {willReadFrequently: true});
  const img = g.createImageData(16, 16);
  for (let i = 0; i < img.data.length; i += 4) {
    img.data[i] = (i * 7) % 256; img.data[i + 1] = (i * 13) % 256; img.data[i + 2] = (i * 29) % 256; img.data[i + 3] = 255;
  }
  g.putImageData(img, 0, 0);
  const leido = g.getImageData(0, 0, 16, 16).data;
  let distintos = 0;
  for (let i = 0; i < leido.length; i++) if (leido[i] !== img.data[i]) distintos++;
  if (!distintos) return;
  const d = window.parent.document;
  for (let i = 0; i < 50; i++) {
    const mapa = d.querySelector('[data-testid="stDeckGlJsonChart"]');
    if (mapa) {
      if (mapa.querySelector(".y2k-aviso3d")) return;
      const aviso = d.createElement("div");
      aviso.className = "y2k-aviso3d";
      aviso.textContent = "⚠ Tu navegador altera las imágenes por privacidad (Safari en modo privado o con " +
        "protección contra rastreo, Brave…). Por eso el relieve puede verse con púas. Ábrelo en una pestaña " +
        "normal, desactiva esa protección para este sitio o usa Chrome.";
      aviso.style.cssText = "position:absolute;left:10px;right:10px;bottom:10px;z-index:5;padding:8px 12px;" +
        "border-radius:10px;background:rgba(255,243,236,.95);color:#16213A;border:1px solid #EC835A;" +
        "font:13px Figtree,system-ui,sans-serif;pointer-events:none";
      mapa.style.position = "relative";
      mapa.appendChild(aviso);
      return;
    }
    await new Promise(r => setTimeout(r, 200));
  }
})();
</script>
"""


def orbitar(orbita, turno):
    """Guion que acerca la camara a la estacion y da una vuelta lenta a su alrededor. `turno`
    cambia en cada seleccion nueva, asi el guion solo corre una vez por estacion elegida."""
    import json
    return _ORBITA.replace("__ORBITA__", json.dumps(orbita)) + f"<!-- turno {turno} -->"


def _destino(lon, lat, azimut, distancia):
    """Punto a `distancia` metros de (lon, lat) en la direccion `azimut` (0 = norte, 90 = este)."""
    rad = math.radians(azimut)
    return (lon + distancia * math.sin(rad) / (111320 * math.cos(math.radians(lat))),
            lat + distancia * math.cos(rad) / 111320)


def _zoom_para_distancia(distancia, lat):
    """Zoom de deck.gl con el que la camara queda a `distancia` metros del punto que mira
    (la camara esta a 1,5 altos de pantalla; el mundo mide 512 px en el zoom 0)."""
    metros_por_px_z0 = 40075016.686 * math.cos(math.radians(lat)) / 512
    return math.log2(1.5 * ALTO_VISOR * metros_por_px_z0 / distancia)


def _orbita(e, base):
    """Vuelta de camara alrededor de la estacion `e` (la seleccionada)."""
    lon, lat = e["lon"], e["lat"]
    t0 = altura_terreno(lon, lat)
    if t0 is None:
        t0 = e["altitud"] if e.get("altitud") is not None else base
    z_suelo = (t0 - base) * EXAGERACION
    z_min, z_max = z_suelo, z_suelo + ALTO_PIN_SEL * EXAGERACION
    if e.get("dudosa") and e.get("altitud") is not None:
        # que tambien quepa el fantasma naranja (la altura que dice el catalogo)
        z_fantasma = (e["altitud"] - base) * EXAGERACION
        z_min, z_max = min(z_min, z_fantasma), max(z_max, z_fantasma)
    return _parametros_orbita(lon, lat, t0, z_min, z_max, alcance=0)


def _orbita_grupo(estaciones, zona_gdf, base):
    """Vuelta de camara alrededor del centro de las estaciones seleccionadas para descargar
    (o de todas las del mapa, o de la zona si no hay ninguna), lo bastante lejos para verlas todas."""
    grupo = [e for e in estaciones if e.get("ok")] or list(estaciones)
    if grupo:
        lon = sum(e["lon"] for e in grupo) / len(grupo)
        lat = sum(e["lat"] for e in grupo) / len(grupo)
        puntos = [(e["lon"], e["lat"]) for e in grupo]
    else:
        minx, miny, maxx, maxy = zona_gdf.total_bounds
        lon, lat = (minx + maxx) / 2, (miny + maxy) / 2
        puntos = [(minx, miny), (maxx, maxy)]
    # radio horizontal (m) que ocupan las estaciones alrededor del centro
    alcance = max(math.hypot((x - lon) * 111320 * math.cos(math.radians(lat)), (y - lat) * 111320) for x, y in puntos)
    t0 = altura_terreno(lon, lat)
    if t0 is None:
        t0 = base
    alturas = [((altura_terreno(e["lon"], e["lat"]) or t0) - base) * EXAGERACION for e in grupo] or [(t0 - base) * EXAGERACION]
    z_min, z_max = min(alturas), max(alturas) + 170 * EXAGERACION
    # vista de conjunto: la camara mas alta (inclinacion max. 58) para ver todas las estaciones
    return _parametros_orbita(lon, lat, t0, z_min, z_max, alcance, pitch_max=58)


def _parametros_orbita(lon, lat, t0, z_min, z_max, alcance, pitch_max=PITCH_MAX):
    """Punto de giro (entre z_min y z_max), zoom, rumbo inicial e inclinacion por direccion segun
    el relieve de alrededor. `alcance`: radio horizontal (m) que debe quedar a la vista."""
    # lo vertical (pin, fantasma) ocupa como mucho ~2/3 del alto de pantalla y lo horizontal
    # (el grupo de estaciones) cabe a lo ancho; nunca mas cerca de DISTANCIA_ORBITA
    distancia = max(DISTANCIA_ORBITA, 2.4 * (z_max - z_min) * 0.9, 2.6 * alcance)
    escala = distancia / DISTANCIA_ORBITA

    # Horizonte de montanas visto desde el centro, cada 10 grados: la camara debe ir por
    # encima de el para no chocar con el relieve ni perder la estacion detras de un cerro
    inclinaciones = []
    for i in range(36):
        horizonte = 0.0
        for d in DISTANCIAS_HORIZONTE:
            d *= escala
            x, y = _destino(lon, lat, i * 10, d)
            altura = altura_terreno(x, y)
            if altura is not None:
                horizonte = max(horizonte, math.degrees(math.atan2((altura - t0) * EXAGERACION, d)))
        inclinaciones.append(min(pitch_max, max(PITCH_MIN, 90 - horizonte - MARGEN_VISTA)))
    # Suavizado circular: primero lo mas prudente en +-20 grados, luego promedio (sin tirones)
    n = len(inclinaciones)
    prudentes = [min(inclinaciones[(i + k) % n] for k in range(-2, 3)) for i in range(n)]
    suaves = [sum(prudentes[(i + k) % n] for k in range(-2, 3)) / 5 for i in range(n)]
    zoom = _zoom_para_distancia(distancia, lat)
    abierto = max(range(n), key=lambda i: suaves[i])   # arranca por el lado mas despejado
    rumbo = ((abierto * 10 + 180) + 180) % 360 - 180    # la camara mira hacia el lado opuesto
    return {
        "lon": lon, "lat": lat, "zoom": round(zoom, 3), "pivote": round((z_min + z_max) / 2, 1),
        "rumbo": rumbo, "pitch": [round(p, 1) for p in suaves],
        "inicio": {"zoom": round(zoom - 1.2, 3), "pitch": round(max(25.0, suaves[abierto] - 20), 1),
                   "bearing": rumbo - 35},
    }


def revisar_altitud(altitud_catalogo, lon, lat):
    """(altura del terreno, es_dudosa). La altitud es dudosa si falta, es 0 o se
    aleja mas de ALTITUD_DUDOSA_M del terreno real en ese punto."""
    terreno = altura_terreno(lon, lat)
    if terreno is None:
        return None, False
    terreno = max(0.0, terreno)  # un pixel de mar (batimetria) cuenta como nivel del mar
    try:
        altitud = float(altitud_catalogo)
    except (TypeError, ValueError):
        return terreno, False
    if altitud != altitud:  # NaN: sin dato, no es una alerta
        return terreno, False
    return terreno, abs(altitud - terreno) > ALTITUD_DUDOSA_M


@st.cache_data(show_spinner=False, max_entries=50)
def _rango_terreno(wkt):
    from shapely import wkt as shp_wkt, contains_xy
    import numpy as np
    zona = shp_wkt.loads(wkt)
    minx, miny, maxx, maxy = zona.bounds
    xs, ys = np.meshgrid(np.linspace(minx, maxx, 30), np.linspace(miny, maxy, 30))
    dentro = contains_xy(zona, xs.ravel(), ys.ravel())
    alturas = [altura_terreno(x, y) for x, y in zip(xs.ravel()[dentro], ys.ravel()[dentro])]
    alturas = [max(0.0, a) for a in alturas if a is not None]
    return (min(alturas), max(alturas)) if alturas else None


def rango_terreno(area_gdf):
    """(minimo, maximo) del relieve real dentro de la zona (cuenca + buffer), muestreado en una malla 30x30."""
    if area_gdf is None or area_gdf.empty:
        return None
    return _rango_terreno(area_gdf.union_all().wkt)


def _anillos(gdf):
    """Contornos exteriores de los poligonos de un GeoDataFrame, densificados."""
    anillos = []
    for geom in gdf.geometry:
        partes = getattr(geom, "geoms", [geom])
        for parte in partes:
            if parte.geom_type != "Polygon":
                continue
            borde = parte.exterior
            n = max(40, min(160, int(borde.length / 0.002)))
            anillos.append([borde.interpolate(i / n, normalized=True).coords[0] for i in range(n + 1)])
    return anillos


def _camino_3d(anillo, base):
    puntos = []
    for lon, lat in anillo:
        z = altura_terreno(lon, lat)
        puntos.append([lon, lat, ((z if z is not None else base) - base) * EXAGERACION + 25])
    return puntos


def construir_deck(cuenca_gdf, area_gdf, estaciones, seleccionada=None, textura="Satélite", paleta=None,
                   ligero=False):
    """
    ligero: para celulares (menos memoria grafica): tiles de 512, menos tiles guardados y menos distancia.
    estaciones: lista de dicts con codigo, nombre, lon, lat, altitud, pct, color [r,g,b], ok (bool), zona, alerta.
    Devuelve (deck, orbita). `orbita` trae los parametros de la vuelta de camara (ver `orbitar`):
    alrededor de la estacion seleccionada o, si no hay, del centro de las estaciones.
    """
    paleta = paleta or {"tinta": "#16213A", "superficie": "#FBFCFE", "borde": "#B8C4D8"}
    minx, miny, maxx, maxy = (area_gdf if area_gdf is not None else cuenca_gdf).total_bounds
    lon_c, lat_c = (minx + maxx) / 2, (miny + maxy) / 2
    # Toda la escena se baja la altura del terreno en el centro de la cuenca: la camara
    # de deck.gl apunta al nivel 0, y con el relieve a ~5 km (Bogota x2) al acercarse
    # quedaba debajo del terreno y no se veia nada. Asi el suelo de la cuenca queda en 0.
    base = altura_terreno(lon_c, lat_c) or 0
    elegida = next((e for e in estaciones if e["codigo"] == seleccionada), None)
    # Vuelta de camara: alrededor de la estacion elegida o, si no hay, del centro de las estaciones
    orbita = _orbita(elegida, base) if elegida else _orbita_grupo(
        estaciones, area_gdf if area_gdf is not None else cuenca_gdf, base)
    # La vista arranca donde empieza la vuelta de camara (si el guion no corre, igual se ve bien).
    # "position" sube el punto de giro a la altura de la estacion o del grupo; max_pitch 85 deja
    # inclinar mas que el tope de 60 que trae deck.gl al arrastrar
    vista = pdk.ViewState(latitude=orbita["lat"], longitude=orbita["lon"], zoom=orbita["inicio"]["zoom"],
                          pitch=orbita["inicio"]["pitch"], bearing=orbita["inicio"]["bearing"],
                          position=[0, 0, orbita["pivote"]], max_pitch=85)

    capas = [pdk.Layer(
        "TerrainLayer",
        id="terreno",
        elevation_decoder={"rScaler": 256 * EXAGERACION, "gScaler": EXAGERACION,
                           "bScaler": EXAGERACION / 256, "offset": (-32768 - base) * EXAGERACION},
        elevation_data=URL_ELEVACION,
        texture=TEXTURAS.get(textura, TEXTURAS["Satélite"]),
        # Los tiles miden 256 px: con tile_size=256 cada pixel de la foto se ve a
        # su tamano real (el valor por defecto, 512, la estira al doble y se ve pixelada)
        tile_size=512 if ligero else 256,
        max_zoom=ZOOM_MAX_TILES,
        # Memoria de la tarjeta grafica: al girar la camara se cargan muchos tiles nuevos y sin
        # limite el navegador se queda sin memoria y el 3D se borra (GL_OUT_OF_MEMORY). Malla con
        # error de 4 m (el valor normal) y como mucho 120 tiles guardados a la vez (60 en celular).
        mesh_max_error=4,
        max_cache_size=60 if ligero else 120,
        # Las alturas vienen codificadas en los colores del PNG: el navegador no debe "corregir"
        # esos colores (perfil de color / alfa), porque un cambio minimo en el rojo son 256 m
        # y el relieve se llena de puas
        load_options={"imagebitmap": {"colorSpaceConversion": "none", "premultiplyAlpha": "none"}},
        wireframe=False,
    )]

    if area_gdf is not None:
        capas.append(pdk.Layer("PathLayer", id="buffer", data=[{"path": _camino_3d(a, base)} for a in _anillos(area_gdf)],
                               get_path="path", get_color=[250, 178, 25, 230], width_min_pixels=2, get_width=20))
    if cuenca_gdf is not None:
        capas.append(pdk.Layer("PathLayer", id="cuenca", data=[{"path": _camino_3d(a, base)} for a in _anillos(cuenca_gdf)],
                               get_path="path", get_color=[90, 162, 245, 255], width_min_pixels=3, get_width=30))

    # Pines: tallo desde el terreno y cabeza redonda arriba
    tallos, cabezas = [], []
    for e in estaciones:
        z = altura_terreno(e["lon"], e["lat"])
        z = ((z if z is not None else e["altitud"] or base) - base) * EXAGERACION
        es_sel = e["codigo"] == seleccionada
        alto = ALTO_PIN_SEL if es_sel else 170 if e["ok"] else 90
        color = [255, 255, 255] if es_sel else e["color"] if e["ok"] else [150, 160, 180]
        tallos.append({"desde": [e["lon"], e["lat"], z], "hasta": [e["lon"], e["lat"], z + alto * EXAGERACION]})
        cabezas.append({**e, "pos": [e["lon"], e["lat"], z + alto * EXAGERACION], "rgb": color,
                        "radio": 90 if es_sel else 60 if e["ok"] else 35,
                        "borde": [22, 33, 58] if not es_sel else [28, 111, 216]})
    capas.append(pdk.Layer("LineLayer", id="tallos", data=tallos, get_source_position="desde",
                           get_target_position="hasta", get_color=[255, 255, 255, 220], get_width=2))

    # Altitud dudosa: un "fantasma" naranja donde quedaria la estacion con la altitud del
    # catalogo, unido al punto real del terreno. Se dibuja por encima de todo (depthCompare
    # "always") para que se vea aunque quede enterrado bajo el relieve.
    encima = {"depthCompare": "always"}
    saltos, fantasmas = [], []
    for e in estaciones:
        if not (e.get("dudosa") and e.get("altitud") is not None and e.get("terreno") is not None):
            continue
        z_terreno = (e["terreno"] - base) * EXAGERACION
        z_catalogo = (e["altitud"] - base) * EXAGERACION
        saltos.append({"desde": [e["lon"], e["lat"], z_terreno], "hasta": [e["lon"], e["lat"], z_catalogo]})
        diferencia = e["altitud"] - e["terreno"]
        fantasmas.append({**e, "pos": [e["lon"], e["lat"], z_catalogo],
                          # bajo tierra la etiqueta se ve diminuta: ahi va junto al punto real del terreno
                          "pos_texto": [e["lon"], e["lat"], max(z_catalogo, z_terreno)],
                          "etiqueta": f"catálogo {_num(e['altitud'])} m · terreno {_num(e['terreno'])} m\n"
                                      f"{_num(abs(diferencia))} m más {'arriba' if diferencia > 0 else 'abajo'}"})
    if fantasmas:
        capas.append(pdk.Layer("LineLayer", id="saltos", data=saltos, get_source_position="desde",
                               get_target_position="hasta", get_color=[236, 131, 90, 240], get_width=3,
                               parameters=encima))
        capas.append(pdk.Layer("ScatterplotLayer", id="fantasmas", data=fantasmas, get_position="pos",
                               get_fill_color=[236, 131, 90, 110], get_line_color=[236, 131, 90, 255],
                               stroked=True, line_width_min_pixels=2, get_radius=70, radius_min_pixels=6,
                               radius_max_pixels=14, billboard=True, pickable=True, parameters=encima))
        # Etiqueta solo en la seleccionada (con todas a la vez el relieve se llena de texto);
        # las demas muestran su ficha al pasar el cursor por el fantasma
        capas.append(pdk.Layer("TextLayer", id="fantasmas_texto",
                               data=[f for f in fantasmas if f["codigo"] == seleccionada], get_position="pos_texto",
                               size_min_pixels=13, size_max_pixels=16,
                               # pydeck convierte los textos sin comillas en expresiones: "'auto'" llega como "auto"
                               get_text="etiqueta", character_set="'auto'", get_size=15, get_color=[22, 33, 58, 255],
                               get_pixel_offset=[22, 0], get_text_anchor="'start'", get_alignment_baseline="'center'",
                               background=True, get_background_color=[255, 243, 236, 235],
                               background_padding=[6, 4], font_family="'Figtree, sans-serif'", parameters=encima))
    capas.append(pdk.Layer("ScatterplotLayer", id="estaciones", data=cabezas, get_position="pos",
                           get_fill_color="rgb", get_line_color="borde", stroked=True, line_width_min_pixels=2,
                           get_radius="radio", radius_min_pixels=5, radius_max_pixels=16,
                           billboard=True, pickable=True, auto_highlight=True))

    deck = pdk.Deck(
        layers=capas,
        initial_view_state=vista,
        # deck.gl deja de dibujar a la distancia en que un suelo plano llegaria al horizonte; con
        # montanas por encima de ese suelo, el relieve lejano se cortaba en linea recta al inclinar.
        # far_z_multiplier=3 dibuja 3 veces mas lejos (mas seria pedirle demasiada memoria a la
        # tarjeta grafica); near bajo evita recortes pegados a la camara.
        views=[pdk.View(type="MapView", controller=True, far_z_multiplier=2 if ligero else 3,
                        near_z_multiplier=0.05)],
        map_provider=None,
        # "__MAP_STYLE__" le dice a Streamlit que no ponga su mapa plano de fondo: ese mapa
        # queda a nivel 0 y tapaba (de negro) los valles mas bajos que el suelo de la cuenca
        map_style="__MAP_STYLE__",
        tooltip={
            # Streamlit escapa el HTML que viene en los datos: el estilo va en la plantilla
            "html": "<b>{nombre}</b><br/>{codigo} · {altitud_txt}<br/>Cantidad probable: <b>{pct_txt}</b><br/>{zona}"
                    "<div style='color:#EC835A'>{alerta}</div>",
            "style": {"backgroundColor": paleta["superficie"], "color": paleta["tinta"], "fontFamily": "Figtree, sans-serif",
                      "fontSize": "12px", "border": f"1px solid {paleta['borde']}", "borderRadius": "10px"},
        },
    )
    return deck, orbita
