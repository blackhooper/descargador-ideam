import io
import math
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
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
ZOOM_HORIZONTE = 10    # ~150 m por pixel: basta para ver si hay montanas a varios km (16 veces menos imagenes)
EXAGERACION = 2.0      # el relieve se ve el doble de alto para notar los desniveles
ZOOM_MAX_TILES = 15    # nivel mas fino que publica Terrarium (~5 m por pixel de textura)
# Si la altitud del catalogo se aleja mas que esto del terreno real en ese punto,
# probablemente esta mal digitada (p. ej. 1.900 m en plena sabana de Bogota)
ALTITUD_DUDOSA_M = 200

# Orbita de la camara alrededor de la estacion elegida
ALTO_PIN_SEL = 260          # m reales del pin de la seleccionada (en la escena x EXAGERACION)
DISTANCIA_ORBITA = 4000     # m de la camara a la estacion
ALTO_VISOR = 650            # px, alto del mapa 3D en la app (para convertir distancia en zoom)
# inclinacion de la camara: 35 = casi cenital, 60 = de lado (mas inclinada pide relieve hasta el
# horizonte y llena la memoria grafica)
PITCH_MIN, PITCH_MAX = 35, 60
MARGEN_VISTA = 6            # grados de holgura sobre el horizonte de montanas
DISTANCIAS_HORIZONTE = (100, 200, 350, 550, 800, 1100, 1500, 2000, 2600, 3300, 4000)


def _num(n):
    return f"{n:,.0f}".replace(",", ".")


# Cache propia de imagenes de relieve, compartida por todas las sesiones y segura entre
# hilos (asi se pueden descargar varias a la vez). Guarda las ultimas MAX_TILES_MEMORIA.
MAX_TILES_MEMORIA = 400
_TILES = OrderedDict()
_TILES_CANDADO = threading.Lock()


def _tile(z, x, y):
    clave = (z, x, y)
    with _TILES_CANDADO:
        if clave in _TILES:
            _TILES.move_to_end(clave)
            return _TILES[clave]
    respuesta = requests.get(URL_ELEVACION.format(z=z, x=x, y=y), timeout=30)
    respuesta.raise_for_status()
    imagen = Image.open(io.BytesIO(respuesta.content)).convert("RGB")
    with _TILES_CANDADO:
        _TILES[clave] = imagen
        while len(_TILES) > MAX_TILES_MEMORIA:
            _TILES.popitem(last=False)
    return imagen


def _indice_tile(lon, lat, z):
    n = 2 ** z
    xf = (lon + 180) / 360 * n
    yf = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return xf, yf


def precargar(puntos, z=ZOOM_DEM):
    """Descarga en paralelo (8 a la vez) las imagenes de relieve que cubren esos puntos
    (lon, lat) y aun no estan en memoria. Antes se bajaban de a una: ~1 s cada una."""
    claves = set()
    for lon, lat in puntos:
        xf, yf = _indice_tile(lon, lat, z)
        claves.add((z, int(xf), int(yf)))
    with _TILES_CANDADO:
        faltan = [c for c in claves if c not in _TILES]
    if not faltan:
        return

    def bajar(clave):
        try:
            _tile(*clave)
        except Exception:
            pass  # sin red o tile inexistente: altura_terreno devolvera None en ese punto

    with ThreadPoolExecutor(max_workers=8) as grupo:
        list(grupo.map(bajar, faltan))


def altura_terreno(lon, lat, z=ZOOM_DEM):
    """Altura del terreno en metros (modelo Terrarium) en un punto. None si falla."""
    xf, yf = _indice_tile(lon, lat, z)
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
    const lienzo = d.querySelector('[data-testid="stDeckGlJsonChart"] canvas:not(.y2k-avion)');
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
  const w = window.parent, d = w.document;
  // Si el usuario ya lo cerro, no vuelve a salir en esta sesion
  try { if (w.sessionStorage.getItem("y2k_aviso3d_cerrado")) return; } catch (e) {}
  if (w.__y2kAviso3dCerrado) return;
  for (let i = 0; i < 50; i++) {
    const mapa = d.querySelector('[data-testid="stDeckGlJsonChart"]');
    if (mapa) {
      if (mapa.querySelector(".y2k-aviso3d")) return;
      const aviso = d.createElement("div");
      aviso.className = "y2k-aviso3d";
      aviso.style.cssText = "position:absolute;left:10px;bottom:10px;z-index:5;max-width:min(420px,calc(100% - 20px));" +
        "display:flex;align-items:flex-start;gap:8px;padding:5px 6px 5px 10px;border-radius:8px;" +
        "background:rgba(255,243,236,.92);color:#16213A;border:1px solid #EC835A;" +
        "font:12px/1.35 Figtree,system-ui,sans-serif";
      const texto = d.createElement("span");
      texto.textContent = "⚠ Tu navegador altera las imágenes por privacidad y el relieve puede verse con púas. " +
        "Prueba en una pestaña normal o con Chrome.";
      const cerrar = d.createElement("button");
      cerrar.type = "button"; cerrar.textContent = "×"; cerrar.setAttribute("aria-label", "Cerrar aviso");
      cerrar.style.cssText = "all:unset;cursor:pointer;font:600 16px/1 Figtree,system-ui,sans-serif;padding:0 6px;color:#16213A";
      cerrar.onclick = () => {
        w.__y2kAviso3dCerrado = true;
        try { w.sessionStorage.setItem("y2k_aviso3d_cerrado", "1"); } catch (e) {}
        aviso.remove();
      };
      aviso.append(texto, cerrar);
      mapa.style.position = "relative";
      mapa.appendChild(aviso);
      return;
    }
    await new Promise(r => setTimeout(r, 200));
  }
})();
</script>
"""


# Vigia del 3D, activo mientras la vista 3D esta abierta:
#  1. Pixeles: en pantallas de alta densidad (celulares) el visor dibuja hasta 9 veces mas
#     pixeles de los que se notan; se limita a 1,5x.
#  2. Memoria: si el navegador se queda sin memoria grafica (el 3D queda en blanco), avisa
#     con botones para recargar la vista 3D (en version liviana) o pasar al 2D. Los botones
#     pulsan botones ocultos de Streamlit, asi Python se entera.
#  3. Detalle escondido (desactivado, ver AVION_ACTIVO): un avion pixel art vuela entre
#     estaciones y vuelve. Se dibuja en un lienzo transparente encima del mapa, proyectando
#     su posicion 3D con la camara actual (no toca el visor). Ctrl + A lo lanza a mano.
# Avion desactivado en la version que se presenta al IDEAM (True para volver a activarlo)
AVION_ACTIVO = False
_EXTRAS_3D = """
<script>
(() => {
  const w = window.parent, d = w.document;
  const AVION_ACTIVO = __AVION__;
  if (w.__y2k3d && w.__y2k3d.parar) w.__y2k3d.parar();
  const estado = {vivo: true, volando: false, temporizador: null, ciclo: null};

  const contenedor = () => d.querySelector('[data-testid="stDeckGlJsonChart"]');
  function buscarDeck() {
    const lienzo = d.querySelector('[data-testid="stDeckGlJsonChart"] canvas:not(.y2k-avion)');
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

  // 1. Pixeles
  function limitarPixeles(deck) {
    const tope = Math.min(w.devicePixelRatio || 1, 1.5);
    if (deck && deck.props.useDevicePixels !== tope) deck.setProps({useDevicePixels: tope});
  }

  // 2. Memoria grafica
  function avisarSinMemoria(caja) {
    if (caja.querySelector(".y2k-sin-memoria")) return;
    const aviso = d.createElement("div");
    aviso.className = "y2k-sin-memoria";
    aviso.innerHTML = "<b>El navegador se quedó sin memoria gráfica</b>" +
      "<span>La vista 3D se detuvo. Al recargarla se usa una versión más liviana.</span>" +
      "<div><button data-accion='y2k_recargar3d'>Recargar vista 3D</button>" +
      "<button data-accion='y2k_pasar2d'>Ver en 2D</button></div>";
    aviso.addEventListener("click", ev => {
      const accion = ev.target && ev.target.dataset && ev.target.dataset.accion;
      const boton = accion && d.querySelector(".st-key-" + accion + " button");
      if (boton) boton.click();
    });
    caja.style.position = "relative";
    caja.appendChild(aviso);
  }
  function vigilar() {
    const caja = contenedor();
    const lienzo = caja && caja.querySelector("canvas:not(.y2k-avion)");
    if (!lienzo) return;
    if (!lienzo.dataset.y2kVigia) {
      lienzo.dataset.y2kVigia = "1";
      lienzo.addEventListener("webglcontextlost", () => avisarSinMemoria(caja));
    }
    try { const gl = lienzo.getContext("webgl2"); if (gl && gl.isContextLost()) avisarSinMemoria(caja); } catch (e) {}
  }

  // 3. El avion
  const AVION = ["....BB......", "....BWB.....", "B....BWB....", "BB...BWWB...", "BWWWWWWWWWWD",
                 "BB...BWWB...", "B....BWB....", "....BWB.....", "....BB......"];
  const COLOR = {B: "#1C6FD8", W: "#FFFFFF", D: "#16213A"};
  function pintarAvion(ctx, x, y, angulo, px) {
    ctx.save(); ctx.translate(x, y); ctx.rotate(angulo);
    ctx.translate(-AVION[0].length * px / 2, -AVION.length * px / 2);
    AVION.forEach((fila, f) => [...fila].forEach((c, k) => {
      if (COLOR[c]) { ctx.fillStyle = COLOR[c]; ctx.fillRect(k * px, f * px, px, px); }
    }));
    ctx.restore();
  }
  const suave = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

  function volar() {
    if (estado.volando) return;
    const caja = contenedor(), deck = buscarDeck();
    if (!caja || !deck) return;
    const capa = (deck.props.layers || []).find(l => l && l.id === "estaciones");
    const datos = capa && capa.props && Array.isArray(capa.props.data) ? capa.props.data : [];
    const puntos = datos.map(e => e.pos).filter(p => Array.isArray(p) && p.length >= 2);
    if (puntos.length < 2) return;
    estado.volando = true;
    // ruta al azar: 3 a 5 estaciones y de vuelta a la primera
    const mezcla = puntos.map(p => [Math.random(), p]).sort((a, b) => a[0] - b[0]).map(v => v[1]);
    const paradas = mezcla.slice(0, Math.min(mezcla.length, 3 + Math.floor(Math.random() * 3)));
    const ruta = [...paradas, paradas[0]];
    const techo = Math.max(...ruta.map(p => p[2] || 0)) + 700;
    const lienzo = d.createElement("canvas");
    lienzo.className = "y2k-avion";
    lienzo.style.cssText = "position:absolute;pointer-events:none;z-index:4;image-rendering:pixelated";
    caja.style.position = "relative";
    caja.appendChild(lienzo);
    const ctx = lienzo.getContext("2d");
    const TRAMO = 1700, total = TRAMO * (ruta.length - 1), estela = [];
    const inicio = w.performance.now();
    const enRuta = t => {
      const i = Math.min(ruta.length - 2, Math.floor(t / TRAMO));
      const f = suave(Math.min(1, (t - i * TRAMO) / TRAMO));
      const a = ruta[i], b = ruta[i + 1];
      return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f, techo + Math.sin(Math.PI * f) * 250];
    };
    const terminar = () => { lienzo.remove(); estado.volando = false; };
    const cuadro = ahora => {
      const deckAhora = buscarDeck();
      const vp = deckAhora && deckAhora.viewManager && deckAhora.viewManager.getViewports()[0];
      const base = caja.querySelector("canvas:not(.y2k-avion)");
      if (!estado.vivo || !vp || !base || !caja.isConnected) return terminar();
      const t = ahora - inicio;
      if (t >= total) return terminar();
      // el lienzo del avion calza exacto sobre el del mapa
      const rc = caja.getBoundingClientRect(), rb = base.getBoundingClientRect();
      Object.assign(lienzo.style, {left: (rb.left - rc.left) + "px", top: (rb.top - rc.top) + "px",
                                   width: rb.width + "px", height: rb.height + "px"});
      if (lienzo.width !== Math.round(rb.width)) lienzo.width = Math.round(rb.width);
      if (lienzo.height !== Math.round(rb.height)) lienzo.height = Math.round(rb.height);
      ctx.clearRect(0, 0, lienzo.width, lienzo.height);
      const aqui = enRuta(t);
      estela.push(aqui); if (estela.length > 40) estela.shift();
      const opacidad = Math.min(1, t / 300, (total - t) / 300);
      // estela blanca que se desvanece
      const proyectada = estela.map(p => vp.project(p));
      for (let k = 1; k < proyectada.length; k++) {
        ctx.strokeStyle = "rgba(255,255,255," + (0.55 * k / proyectada.length * opacidad) + ")";
        ctx.lineWidth = 3;
        ctx.beginPath(); ctx.moveTo(proyectada[k - 1][0], proyectada[k - 1][1]);
        ctx.lineTo(proyectada[k][0], proyectada[k][1]); ctx.stroke();
      }
      const [x, y] = vp.project(aqui);
      const [x2, y2] = vp.project(enRuta(Math.min(total - 1, t + 40)));
      ctx.globalAlpha = opacidad;
      pintarAvion(ctx, x, y, Math.atan2(y2 - y, x2 - x), 4);
      ctx.globalAlpha = 1;
      w.requestAnimationFrame(cuadro);
    };
    w.requestAnimationFrame(cuadro);
  }

  // cada uno o dos minutos, al azar, si la pestana esta a la vista
  function programar() {
    clearTimeout(estado.temporizador);
    estado.temporizador = setTimeout(() => {
      if (estado.vivo && d.visibilityState === "visible" && contenedor()) volar();
      if (estado.vivo) programar();
    }, 55000 + Math.random() * 65000);
  }
  // Ctrl + A (o Cmd + A) lo lanza a mano, salvo si se esta escribiendo en un campo
  const tecla = ev => {
    if (!(ev.ctrlKey || ev.metaKey) || (ev.key || "").toLowerCase() !== "a") return;
    const t = ev.target;
    if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
    if (!contenedor()) return;
    ev.preventDefault();
    volar();
  };
  if (AVION_ACTIVO) d.addEventListener("keydown", tecla, true);

  estado.ciclo = setInterval(() => { limitarPixeles(buscarDeck()); vigilar(); }, 1500);
  if (AVION_ACTIVO) programar();
  w.__y2k3d = {
    volar,
    parar: () => {
      estado.vivo = false;
      clearInterval(estado.ciclo); clearTimeout(estado.temporizador);
      d.removeEventListener("keydown", tecla, true);
    },
  };
})();
</script>
"""
EXTRAS_3D = _EXTRAS_3D.replace("__AVION__", "true" if AVION_ACTIVO else "false")



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
    # vista de conjunto: la camara mas alta (inclinacion max. 55) para ver todas las estaciones
    return _parametros_orbita(lon, lat, t0, z_min, z_max, alcance, pitch_max=55)


def _parametros_orbita(lon, lat, t0, z_min, z_max, alcance, pitch_max=PITCH_MAX):
    """Punto de giro (entre z_min y z_max), zoom, rumbo inicial e inclinacion por direccion segun
    el relieve de alrededor. `alcance`: radio horizontal (m) que debe quedar a la vista."""
    # lo vertical (pin, fantasma) ocupa como mucho ~2/3 del alto de pantalla y lo horizontal
    # (el grupo de estaciones) cabe a lo ancho; nunca mas cerca de DISTANCIA_ORBITA
    distancia = max(DISTANCIA_ORBITA, 2.4 * (z_max - z_min) * 0.9, 2.6 * alcance)
    escala = distancia / DISTANCIA_ORBITA

    # Horizonte de montanas visto desde el centro, cada 10 grados: la camara debe ir por
    # encima de el para no chocar con el relieve ni perder la estacion detras de un cerro.
    # Hasta 2 km se mira con el relieve fino; mas lejos basta el de baja resolucion.
    muestras = [(i, d * escala) for i in range(36) for d in DISTANCIAS_HORIZONTE]
    zoom_de = {d: (ZOOM_DEM if d <= 2000 else ZOOM_HORIZONTE) for _, d in muestras}
    puntos = {(i, d): _destino(lon, lat, i * 10, d) for i, d in muestras}
    for z in (ZOOM_DEM, ZOOM_HORIZONTE):
        precargar([puntos[m] for m in muestras if zoom_de[m[1]] == z], z)
    inclinaciones = []
    for i in range(36):
        horizonte = 0.0
        for d in DISTANCIAS_HORIZONTE:
            d *= escala
            x, y = puntos[(i, d)]
            altura = altura_terreno(x, y, zoom_de[d])
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
    muestra = list(zip(xs.ravel()[dentro], ys.ravel()[dentro]))
    precargar(muestra)
    alturas = [altura_terreno(x, y) for x, y in muestra]
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
    ligero: celulares, o despues de que el navegador se quedo sin memoria grafica: menos detalle.
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
    # Todas las alturas que se van a consultar (centro, estaciones, contornos) se bajan juntas
    anillos_area = _anillos(area_gdf) if area_gdf is not None else []
    anillos_cuenca = _anillos(cuenca_gdf) if cuenca_gdf is not None else []
    precargar([(lon_c, lat_c)] + [(e["lon"], e["lat"]) for e in estaciones]
              + [p for a in anillos_area + anillos_cuenca for p in a])
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

    # Calidad segun la distancia. La memoria grafica se va en tiles de relieve: cada uno es
    # una malla de triangulos mas una foto. Cerca de una estacion vale la pena el detalle doble;
    # en la vista de conjunto no se nota y cuesta ~4 veces mas tiles.
    #   cerca:    tiles de 256 (foto nitida), malla fina, dibuja 3 veces mas lejos
    #   conjunto: tiles de 512, malla simple, dibuja 2 veces mas lejos
    #   ligero:   celular o despues de que el navegador se quedo sin memoria
    cerca = elegida is not None and not ligero
    detalle = {"tiles": 256 if cerca else 512, "malla": 4 if cerca else (10 if ligero else 8),
               "guardados": 50 if ligero else (100 if cerca else 80), "lejos": 1.8 if ligero else (3 if cerca else 2)}

    capas = [pdk.Layer(
        "TerrainLayer",
        id="terreno",
        elevation_decoder={"rScaler": 256 * EXAGERACION, "gScaler": EXAGERACION,
                           "bScaler": EXAGERACION / 256, "offset": (-32768 - base) * EXAGERACION},
        elevation_data=URL_ELEVACION,
        texture=TEXTURAS.get(textura, TEXTURAS["Satélite"]),
        # Los tiles miden 256 px: con tile_size=256 cada pixel de la foto se ve a su tamano real
        # (con 512, el valor normal, se estira al doble); cuesta ~4 veces mas tiles
        tile_size=detalle["tiles"],
        max_zoom=ZOOM_MAX_TILES,
        # Error de la malla en metros (mas alto = menos triangulos) y tope de tiles guardados:
        # sin tope, al girar la camara el navegador se queda sin memoria y el 3D se borra
        mesh_max_error=detalle["malla"],
        max_cache_size=detalle["guardados"],
        # mientras llega el detalle, no dibujar a la vez la version gruesa y la fina de una zona
        refinement_strategy="'no-overlap'",
        # Las alturas vienen codificadas en los colores del PNG: el navegador no debe "corregir"
        # esos colores (perfil de color / alfa), porque un cambio minimo en el rojo son 256 m
        # y el relieve se llena de puas
        load_options={"imagebitmap": {"colorSpaceConversion": "none", "premultiplyAlpha": "none"}},
        wireframe=False,
    )]

    if area_gdf is not None:
        capas.append(pdk.Layer("PathLayer", id="buffer", data=[{"path": _camino_3d(a, base)} for a in anillos_area],
                               get_path="path", get_color=[250, 178, 25, 230], width_min_pixels=2, get_width=20))
    if cuenca_gdf is not None:
        capas.append(pdk.Layer("PathLayer", id="cuenca", data=[{"path": _camino_3d(a, base)} for a in anillos_cuenca],
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
        views=[pdk.View(type="MapView", controller=True, far_z_multiplier=detalle["lejos"],
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
