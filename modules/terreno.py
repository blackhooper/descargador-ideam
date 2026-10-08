import io
import json
from functools import lru_cache
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


# ---- Textura "Altura": el relieve se pinta segun su altitud (hipsometrico) con sombreado de ladera ----
# Colombia: del nivel del mar al Pico Cristobal Colon (Sierra Nevada de Santa Marta, ~5.730 m)
ALTURA_COLOMBIA = (0, 5730)
# Verdes abajo, amarillos y naranjas en medio, rojos terracota y vino arriba, con un blanco rosado en las cumbres
RAMPA_ALTURA = [(0.00, "#1F7A4D"), (0.10, "#4E9A55"), (0.22, "#8DB45A"), (0.34, "#CFCB6B"), (0.46, "#E8B75B"),
                (0.58, "#DB8A4B"), (0.70, "#C0603F"), (0.82, "#94403A"), (0.93, "#6B2E35"), (1.00, "#EFE8E4")]
# La marca "y2k_hipso" en la direccion la reconoce el guion de abajo; S3 ignora lo que va despues del "?"
URL_ALTURA = URL_ELEVACION + "?y2k_hipso=1&px=__PX__&min=__MIN__&max=__MAX__"

# deck.gl pide las imagenes con fetch. Este guion (se instala una sola vez en la pagina) intercepta
# las que llevan la marca, baja el mismo tile de elevacion y devuelve una imagen coloreada por altura con
# sombreado de ladera. La imagen sale a 128 px (la mitad): un poco pixelada, pero un cuarto de memoria.
_HIPSOMETRICO = """
<script>
(() => {
  const w = window.parent;
  if (w.__y2kHipso) return;
  const original = w.fetch.bind(w);
  const pasos = __RAMPA__.map(p => [p[0], [parseInt(p[1].slice(1, 3), 16), parseInt(p[1].slice(3, 5), 16), parseInt(p[1].slice(5, 7), 16)]]);
  const color = t => {
    let k = 0;
    while (k < pasos.length - 2 && t > pasos[k + 1][0]) k++;
    const a = pasos[k], b = pasos[k + 1], f = Math.min(1, Math.max(0, (t - a[0]) / (b[0] - a[0])));
    return [a[1][0] + (b[1][0] - a[1][0]) * f, a[1][1] + (b[1][1] - a[1][1]) * f, a[1][2] + (b[1][2] - a[1][2]) * f];
  };
  const N = 256, EXAG = 2;
  const LX = -0.55, LY = -0.55, LZ = 0.63;
  async function colorear(url, opciones) {
    const partes = url.split("?"), base = partes[0], q = new URLSearchParams(partes[1] || "");
    const trozos = base.split("/");
    const y = parseInt(trozos[trozos.length - 1]), x = parseInt(trozos[trozos.length - 2]), z = parseInt(trozos[trozos.length - 3]);
    const mn = parseFloat(q.get("min")), mx = parseFloat(q.get("max"));
    const SALIDA = parseInt(q.get("px")) || N, PASO = N / SALIDA;
    const resp = await original(base, {mode: "cors", signal: opciones && opciones.signal});
    if (!resp.ok) return resp;
    const bmp = await w.createImageBitmap(await resp.blob(), {colorSpaceConversion: "none", premultiplyAlpha: "none"});
    const origen = w.document.createElement("canvas");
    origen.width = origen.height = N;
    const oc = origen.getContext("2d", {willReadFrequently: true});
    oc.drawImage(bmp, 0, 0, N, N);
    bmp.close();
    const px = oc.getImageData(0, 0, N, N).data, H = new Float32Array(N * N);
    for (let i = 0; i < N * N; i++) H[i] = Math.max(0, px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768);
    const lat = Math.atan(Math.sinh(Math.PI * (1 - 2 * (y + 0.5) / Math.pow(2, z))));
    const mpp = 156543.03392 * Math.cos(lat) / Math.pow(2, z);
    const salida = w.document.createElement("canvas");
    salida.width = salida.height = SALIDA;
    const sc = salida.getContext("2d", {willReadFrequently: true}), img = sc.createImageData(SALIDA, SALIDA), d = img.data;
    const s = PASO, esc = 2 * s * mpp;
    for (let j = 0; j < SALIDA; j++) {
      for (let i = 0; i < SALIDA; i++) {
        const ix = i * PASO, iy = j * PASO, c = iy * N + ix;
        const h = H[c];
        const dx = (H[iy * N + Math.min(N - 1, ix + s)] - H[iy * N + Math.max(0, ix - s)]) * EXAG / esc;
        const dy = (H[Math.min(N - 1, iy + s) * N + ix] - H[Math.max(0, iy - s) * N + ix]) * EXAG / esc;
        const luz = (-dx * LX - dy * LY + LZ) / Math.sqrt(dx * dx + dy * dy + 1) / LZ;
        const lit = Math.min(1.3, Math.max(0.35, 0.3 + 0.7 * luz));
        const col = color(Math.min(1, Math.max(0, (h - mn) / (mx - mn))));
        const o = (j * SALIDA + i) * 4;
        d[o] = Math.min(255, col[0] * lit); d[o + 1] = Math.min(255, col[1] * lit); d[o + 2] = Math.min(255, col[2] * lit); d[o + 3] = 255;
      }
    }
    sc.putImageData(img, 0, 0);
    const blob = await new Promise(r => salida.toBlob(r, "image/png"));
    // los lienzos no quedan esperando al recolector de basura (en la tarjeta grafica pesan)
    origen.width = origen.height = 0; salida.width = salida.height = 0;
    return new Response(blob, {status: 200, headers: {"Content-Type": "image/png"}});
  }
  w.fetch = (entrada, opciones) => {
    const url = typeof entrada === "string" ? entrada : entrada ? (entrada.url || entrada.href || String(entrada)) : "";
    if (url.indexOf("y2k_hipso=") < 0) return original(entrada, opciones);
    // si algo falla, queda el error en la consola del navegador (F12) y en window.__y2kHipsoError
    return colorear(url, opciones).catch(e => { console.error("y2k_hipso", e); w.__y2kHipsoError = String((e && e.message) || e); return original(entrada, opciones); });
  };
  w.__y2kHipso = true;
  w.__y2kHipsoHora = w.performance.now();
})();
</script>
"""
HIPSOMETRICO = _HIPSOMETRICO.replace("__RAMPA__", json.dumps(RAMPA_ALTURA))


def leyenda_altura(minimo, maximo, escala):
    """Barra de colores con la escala de altitudes (HTML para st.markdown)."""
    gradiente = ", ".join(f"{c} {t * 100:.0f}%" for t, c in RAMPA_ALTURA)
    marcas = "".join(f"<span>{_num(minimo + (maximo - minimo) * f)}</span>" for f in (0, 0.25, 0.5, 0.75, 1))
    return (f'<p class="tit">Altitud (m) · {escala}</p>'
            f'<div class="rampa" style="background:linear-gradient(90deg,{gradiente})"></div>'
            f'<div class="marcas">{marcas}</div>')


# ---- Intro satelital: del mapa 2D al despliegue 3D (cubre la carga del relieve) ----
# Los archivos estan en static/intro_satelital/ (escena Three.js + reproductor). El guion de abajo los carga en la
# pagina, tapa el visor 3D con la animacion y, al "encender la pantalla", avisa al guion de la secuencia de entrada
# (_ORBITA) para que empiecen los lasers sobre el relieve real.
SATELITE_ACTIVO = True
PANEL_SATELITE = False   # panel de ajustes de camara y tiempos dentro de la intro (solo para afinarla)


def _version_satelite():
    """Cambia cuando se edita algun archivo de la intro: asi el navegador no usa copias viejas."""
    import os
    carpeta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "intro_satelital")
    try:
        return max(int(os.path.getmtime(os.path.join(carpeta, f))) for f in os.listdir(carpeta))
    except OSError:
        return 1


_INTRO_SATELITAL = """
<script>
(async () => {
  const w = window.parent, d = w.document;
  const P = __PARAMS__;
  const visor = d.querySelector(".st-key-y2k_visor3d");
  const fin = () => { w.__y2kIntroSatFin = P.turno; };
  // con movimiento reducido no se reproduce sola; si la persona la pide ("Repetir animacion"), si
  const menos = w.matchMedia && w.matchMedia("(prefers-reduced-motion: reduce)").matches && !P.forzar;
  w.__y2kIntroSatTurno = P.turno;
  if (!visor || menos) { fin(); return; }
  // Si la animacion ya arranco en el clic (sobre el mapa 2D), se adopta en vez de empezar otra
  if (w.__y2kSatTemprano && w.__y2kSatTemprano.adoptar) { try { w.__y2kSatTemprano.adoptar(visor, P); return; } catch (e) { console.error(e); } }
  // capa negra inmediata (sobre toda la ventana): el reproductor tarda un momento en cargar (la primera vez, bastante)
  d.querySelectorAll(".y2k-sat").forEach(e => e.remove());
  const previo = d.createElement("div");
  previo.className = "y2k-sat";
  previo.style.cssText = "position:fixed;inset:0;z-index:60;background:#000";
  d.body.appendChild(previo);
  try {
    if (!w.__y2kSat || w.__y2kSatV !== P.version) {
      await new Promise((ok, no) => {
        const s = d.createElement("script");
        s.type = "module";
        s.src = new URL("app/static/intro_satelital/player.js?v=" + P.version, w.location.href).href;
        s.onload = ok; s.onerror = () => no(new Error("no se pudo cargar el reproductor"));
        d.head.appendChild(s);
      });
      w.__y2kSatV = P.version;
    }
    await w.__y2kSat.reproducir({visor: visor, clave: P.clave, lon: P.lon, lat: P.lat, bbox: P.bbox, estaciones: P.estaciones, n: P.n, buffer: P.buffer, turno: P.turno, panel: P.panel, version: P.version});
  } catch (e) {
    console.error("intro satelital", e);
    fin(); previo.remove();
  }
})();
</script>
"""


def _datos_satelite(bbox, estaciones, buffer=True):
    """Lo que necesita la intro de la cuenca: caja envolvente y estaciones ([lon, lat, 1 si cumple]) para dibujarlas,
    el total real de estaciones (se dibujan hasta 250, pero el contador usa el total) y si el buffer esta activo."""
    x0, y0, x1, y1 = (float(v) for v in bbox)
    return {"clave": f"{x0:.5f},{y0:.5f},{x1:.5f},{y1:.5f}", "lon": round((x0 + x1) / 2, 4), "lat": round((y0 + y1) / 2, 4),
            "bbox": [round(x0, 5), round(y0, 5), round(x1, 5), round(y1, 5)],
            "estaciones": [[round(float(e["lon"]), 4), round(float(e["lat"]), 4), 1 if e.get("ok") else 0] for e in estaciones[:250]],
            "n": len(estaciones), "buffer": bool(buffer),
            "panel": bool(PANEL_SATELITE), "version": _version_satelite()}


def intro_satelital(turno, bbox, estaciones, buffer=True, forzar=False):
    """Guion (para components.html) que reproduce la intro satelital del visor 3D de este turno. `forzar`: la pidio
    la persona ("Repetir animacion"), asi que se reproduce aunque su equipo pida reducir el movimiento."""
    datos = {"turno": turno, "forzar": bool(forzar), **_datos_satelite(bbox, estaciones, buffer)}
    return _INTRO_SATELITAL.replace("__PARAMS__", json.dumps(datos)) + f"<!-- turno {turno} -->"


# Se manda en cuanto se confirma la cuenca (ya no se va a mover): baja en silencio lo que pesa de la intro y arma el
# mosaico de satelite de la zona, para que al pasar a 3D no haya que esperar. No crea nada en la tarjeta grafica.
_PRECALENTAR_SATELITE = """
<script>
(async () => {
  const w = window.parent, d = w.document;
  const P = __PARAMS__;
  try {
    if (!w.__y2kSat || w.__y2kSatV !== P.version) {
      if (!w.__y2kSatCargando || w.__y2kSatCargandoV !== P.version) {
        w.__y2kSatCargandoV = P.version;
        w.__y2kSatCargando = new Promise((ok, no) => {
          const s = d.createElement("script");
          s.type = "module";
          s.src = new URL("app/static/intro_satelital/player.js?v=" + P.version, w.location.href).href;
          s.onload = ok; s.onerror = () => no(new Error("no se pudo cargar el reproductor"));
          d.head.appendChild(s);
        });
      }
      await w.__y2kSatCargando;
      w.__y2kSatV = P.version;
    }
    await w.__y2kSat.precalentar(P);
  } catch (e) { console.warn("precalentamiento de la intro", e); }
  // el boton 3D se habilita (ver CSS que manda app.py) cuando ya esta todo precalentado
  d.documentElement.dataset.y2kListo = P.clave;
})();
</script>
"""


def precalentar_satelite(bbox, estaciones, buffer=True):
    """Guion (para components.html) que precalienta la intro satelital de esta cuenca."""
    return _PRECALENTAR_SATELITE.replace("__PARAMS__", json.dumps(_datos_satelite(bbox, estaciones, buffer)))


def css_boton_3d_espera(bbox, estaciones):
    """CSS que deja el boton 3D gris y sin respuesta hasta que el precalentamiento de esta cuenca termina."""
    clave = _datos_satelite(bbox, estaciones)["clave"]
    return ('<style>html:not([data-y2k-listo="' + clave + '"]) .st-key-vista button[role="radio"]:last-of-type'
            '{opacity:.4 !important;filter:grayscale(1);pointer-events:none !important;cursor:progress}</style>')


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


# Capas que la secuencia de entrada esconde y va mostrando (mismos ids que ID_SECUENCIA del guion)
CAPAS_SECUENCIA = ("cuenca", "buffer", "tallos", "estaciones", "saltos", "fantasmas", "fantasmas_texto")


# Vuelta de camara alrededor de la estacion elegida. Streamlit no deja animar la vista
# desde Python, asi que este guion busca el visor deck.gl ya dibujado en la pagina (por
# dentro de React) y le cambia la vista cuadro a cuadro. Si el usuario toca el mapa, para.
# La camara de deck.gl gira alrededor del punto al que mira; "position" sube ese punto a la
# mitad del pin de la estacion, asi la estacion queda en el centro y la camara la rodea.
# Al abrir el 3D (O.intro) antes de la vuelta corre la secuencia de entrada: mientras llega el relieve
# se ve la cubierta "Alistando..."; luego las lineas se dibujan como lasers, caen los pines y suben los
# haces naranjas de las altitudes dudosas. Las capas se esconden/animan con layer.clone() sobre las que
# mando Python y al final se devuelven tal cual.
_ORBITA = """
<script>
(async () => {
  const w = window.parent, d = w.document;
  const O = __ORBITA__;
  const esperar = ms => new Promise(r => setTimeout(r, ms));
  // Cada ejecucion del guion tiene su numero: si arranca otra, la anterior se detiene
  const miId = w.__y2kOrbitaId = (w.__y2kOrbitaId || 0) + 1;
  const vigente = () => miId === w.__y2kOrbitaId;
  const visor = d.querySelector(".st-key-y2k_visor3d");
  const levantarCubierta = () => { if (visor) visor.dataset.listo = "1"; };
  // Al arrancar la secuencia, Python tapa el visor (CSS) hasta que este guion haya escondido las capas: asi no se alcanza
  // a ver el resultado final antes de los lasers. Se destapa marcando el visor con el numero de turno
  const mostrar = () => { if (visor) visor.dataset.mostrar = String(O.turno); };
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
  if (!deck) { levantarCubierta(); mostrar(); return; }

  // Las capas "originales" son las que mando Python; las que pone este guion llevan una marca
  const puestas = deck.props.layers;
  const originales = (puestas && puestas.__y2k ? deck.__y2kOriginales : puestas) || [];
  deck.__y2kOriginales = originales;
  const poner = lista => { lista.__y2k = true; deck.setProps({layers: lista}); };
  if (puestas && puestas.__y2k) poner(originales.slice());
  // Modo "Altura": si el guion que colorea el relieve se instalo tarde, las primeras imagenes llegaron sin colorear;
  // se vuelve a pedir el relieve una sola vez
  const terr = originales.find(l => l && l.id === "terreno");
  const esAltura = !!(terr && typeof terr.props.texture === "string" && terr.props.texture.indexOf("y2k_hipso") >= 0);
  if (esAltura && w.__y2kHipsoHora && !w.__y2kHipsoRecargado && w.performance.now() - w.__y2kHipsoHora < 20000) {
    w.__y2kHipsoRecargado = true;
    const i = originales.findIndex(l => l && l.id === "terreno");
    if (i >= 0 && typeof originales[i].props.texture === "string") {
      originales[i] = originales[i].clone({texture: originales[i].props.texture + "&v=2"});
      poner(originales.slice());
    }
  }

  // ---- 1. Secuencia de entrada: lineas como lasers, caen los pines, suben las alertas ----
  const quiereMenosMovimiento = w.matchMedia && w.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Modo Lite (lo marca el CSS de la pagina): sin secuencia ni vuelta animada. Se lee aqui, no desde Python, para que
  // activarlo o quitarlo no vuelva a ejecutar este guion (moveria la camara o repetiria la animacion)
  const lite = w.getComputedStyle(d.documentElement).getPropertyValue("--y2k-lite").trim() === "1";
  const conIntro = O.intro && (!quiereMenosMovimiento || O.forzar) && !lite && originales.length > 0;
  let enIntro = conIntro, vueltaIniciada = false;
  w.__y2kEnIntro = enIntro;
  // Tamano de los efectos segun lo lejos que mira la camara (E = 1 a 4 km)
  const DIST = O.distancia || 4000, E = DIST / 4000;
  const capa = id => originales.find(l => l && l.id === id);
  const ID_SECUENCIA = ["cuenca", "buffer", "tallos", "estaciones", "saltos", "fantasmas", "fantasmas_texto"];
  const reemplazos = {};
  const refrescar = extra => poner(originales.map(l => reemplazos[l.id] || l).concat(extra || []));
  if (conIntro) {
    ID_SECUENCIA.forEach(id => { const l = capa(id); if (l) reemplazos[id] = l.clone({visible: false}); });
    refrescar();
    // Si Streamlit vuelve a mandar sus capas (todas visibles) mientras corre la secuencia, se vuelven a esconder
    const guardia = setInterval(() => {
      if (!vigente() || !enIntro) { clearInterval(guardia); return; }
      if (deck.props.layers && !deck.props.layers.__y2k) refrescar();
    }, 60);
  }
  // Con la intro satelital el visor se destapa cuando ya esta la capa de la intro encima
  if (conIntro && O.satelite) { for (let i = 0; i < 60 && w.__y2kIntroSatTurno !== O.turno && vigente(); i++) await esperar(50); }
  mostrar();
  // Lite o movimiento reducido: no hay nada que animar, asi que la camara se ubica ya (sin esperar al relieve) y no
  // pisa lo que el usuario haga despues
  const tInicio = w.performance.now();
  let tocado = false;
  const zonaDeck = d.querySelector('[data-testid="stDeckGlJsonChart"]');
  if (zonaDeck) ["pointerdown", "wheel", "touchstart", "keydown"].forEach(e => zonaDeck.addEventListener(e, () => { tocado = true; }, {once: true, capture: true}));
  if (!conIntro && (lite || (quiereMenosMovimiento && !O.forzar))) vuelta();

  // ---- 2. Esperar a que el relieve este dibujado (la cubierta "Alistando..." sigue encima) ----
  if (!visor || visor.dataset.listo !== "1") {
    const t0 = w.performance.now();
    let seguidas = 0;
    while (vigente() && w.performance.now() - t0 < 15000) {
      const l = deck.layerManager && deck.layerManager.getLayers().find(x => x.id === "terreno");
      seguidas = l && l.isLoaded ? seguidas + 1 : 0;
      if (seguidas >= 3 && w.performance.now() - t0 > 1200) break;
      await esperar(150);
    }
  }
  if (!vigente()) return;
  levantarCubierta();

  if (conIntro) {
    await esperar(500);
    try {
      const ease = t => t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      const cuadro = () => new Promise(r => w.requestAnimationFrame(r));
      // Las capas de efectos se rehacen en cada cuadro (datos nuevos = buffers nuevos en la tarjeta grafica): se limita
      // a ~30 cuadros por segundo para no generar tanta basura de memoria. La camara usa intervalo 0 (cada cuadro)
      const durante = async (ms, f, intervalo = 33) => {
        const t0 = w.performance.now();
        let t, ultimo = -1e9;
        do {
          await cuadro();
          const ahora = w.performance.now();
          t = Math.min(1, (ahora - t0) / ms);
          if (t >= 1 || ahora - ultimo >= intervalo) { ultimo = ahora; f(t); }
        } while (t < 1 && vigente());
      };
      // Antes de los lasers la camara sube suave a la posicion inicial (al repetir la animacion puede estar en cualquier lado)
      {
        const I = O.inicio, v = deck.props.viewState || (deck.viewManager && deck.viewManager.getViewState && deck.viewManager.getViewState("default-view")) || {};
        const nz = (x, def) => (x === undefined || x === null ? def : x);
        const a = {lon: nz(v.longitude, O.lon), lat: nz(v.latitude, O.lat), zoom: nz(v.zoom, I.zoom), pitch: nz(v.pitch, I.pitch), bearing: nz(v.bearing, I.bearing)};
        const dB = ((I.bearing - a.bearing + 540) % 360) - 180;
        const lejos = Math.abs(a.zoom - I.zoom) > 0.05 || Math.abs(dB) > 2 || Math.abs(a.pitch - I.pitch) > 1
          || Math.abs(a.lon - O.lon) > 1e-4 || Math.abs(a.lat - O.lat) > 1e-4;
        if (lejos && vigente()) {
          await durante(1700, t => {
            const k = ease(t), mezcla = (p, q) => p + (q - p) * k;
            deck.setProps({viewState: {...(deck.props.viewState || {}), longitude: mezcla(a.lon, O.lon), latitude: mezcla(a.lat, O.lat),
              zoom: mezcla(a.zoom, I.zoom), pitch: mezcla(a.pitch, I.pitch), bearing: a.bearing + dB * k, position: [0, 0, O.pivote], maxPitch: 85}});
          }, 0);
          await esperar(200);
        }
      }
      // Con la intro satelital el relieve se prepara por detras; los lasers empiezan cuando la intro enciende la pantalla
      if (O.satelite) {
        const t0 = w.performance.now();
        while (vigente() && w.__y2kIntroSatFin !== O.turno && w.performance.now() - t0 < 90000) await esperar(50);
      }
      const Punto = (capa("estaciones") || capa("fantasmas") || {}).constructor;
      const Linea = (capa("tallos") || capa("saltos") || {}).constructor;
      const Trazo = (capa("cuenca") || capa("buffer") || {}).constructor;
      const encima = {depthCompare: "always"};
      const lim = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
      const seno = x => -(Math.cos(Math.PI * x) - 1) / 2;
      const salida = x => 1 - Math.pow(1 - x, 3);
      const conAlfa = (c, a) => [c[0], c[1], c[2], Math.round(lim(a, 0, 255))];

      // Haz vertical con degradado: segmentos apilados que se desvanecen hacia arriba
      const haz = (base, alto, color, alfa, partes = 8) => {
        const r = [];
        for (let k = 0; k < partes; k++) {
          r.push({a: [base[0], base[1], base[2] + alto * k / partes], b: [base[0], base[1], base[2] + alto * (k + 1) / partes],
                  c: conAlfa(color, alfa * Math.pow(1 - k / partes, 1.6))});
        }
        return r;
      };
      // Haz oblicuo desde `base` hacia `ap` (el satelite, sobre el centro del rectangulo), con degradado; `frac` = cuanto del camino cubre
      const mezcla3 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
      const hazA = (base, ap, color, alfa, partes = 8, frac = 1) => {
        const r = [];
        for (let k = 0; k < partes; k++) {
          r.push({a: mezcla3(base, ap, frac * k / partes), b: mezcla3(base, ap, frac * (k + 1) / partes),
                  c: conAlfa(color, alfa * Math.pow(1 - k / partes, 1.6))});
        }
        return r;
      };
      const dibujaHaz = (id, datos, ancho, minPx) => new Linea({id, data: datos, getSourcePosition: d => d.a,
        getTargetPosition: d => d.b, getColor: d => d.c, getWidth: ancho, widthMinPixels: minPx, parameters: encima});
      // Circulo plano sobre el terreno: solo contorno (onda) o relleno (destello)
      const anillo = (id, datos, px) => new Punto({id, data: datos, getPosition: d => d.p, getRadius: d => d.r, filled: false,
        stroked: true, getLineColor: d => d.c, getLineWidth: px, lineWidthUnits: "pixels", billboard: false, parameters: encima});
      const disco = (id, datos) => new Punto({id, data: datos, getPosition: d => d.p, getRadius: d => d.r, getFillColor: d => d.c,
        filled: true, stroked: false, billboard: false, parameters: encima});

      // Largo acumulado de un camino (en grados, corregido por la latitud) y recorte hasta una fraccion
      const largo = (a, b) => Math.hypot((b[0] - a[0]) * Math.cos(a[1] * Math.PI / 180), b[1] - a[1]);
      const medir = camino => { const ac = [0]; for (let i = 1; i < camino.length; i++) ac.push(ac[i - 1] + largo(camino[i - 1], camino[i])); return ac; };
      const recortar = (camino, ac, f) => {
        const n = camino.length, L = ac[n - 1] * f;
        let i = 1; while (i < n - 1 && ac[i] < L) i++;
        const s = lim((L - ac[i - 1]) / ((ac[i] - ac[i - 1]) || 1)), a = camino[i - 1], b = camino[i];
        const punta = [a[0] + (b[0] - a[0]) * s, a[1] + (b[1] - a[1]) * s, (a[2] || 0) + ((b[2] || 0) - (a[2] || 0)) * s];
        return [camino.slice(0, i).concat([punta]), punta];
      };

      // ---- Fase 1: dos lasers (cuenca azul, buffer amarillo) bajan del cielo y dibujan su perimetro ----
      // Punto del que "vienen" los dos lasers y las estaciones: el satelite, sobre el centro del rectangulo. APEX_ALTO = altura (ajustable)
      const APEX_ALTO = (O.apex || 1.7) * DIST;
      const base0 = capa("cuenca") || capa("buffer");
      let apex = [O.lon, O.lat, APEX_ALTO];
      if (base0) {
        let x0 = 1e9, x1 = -1e9, y0 = 1e9, y1 = -1e9, zs = 0, nz = 0;
        base0.props.data.forEach(r => r.path.forEach(q => { x0 = Math.min(x0, q[0]); x1 = Math.max(x1, q[0]); y0 = Math.min(y0, q[1]); y1 = Math.max(y1, q[1]); zs += q[2] || 0; nz++; }));
        if (nz) apex = [(x0 + x1) / 2, (y0 + y1) / 2, zs / nz + APEX_ALTO];
      }
      const LASERES = [{id: "cuenca", color: [53, 240, 255], ini: 0, dur: 1900},
                       {id: "buffer", color: [255, 122, 26], ini: 350, dur: 1900}]
        .map(d => ({...d, capa: capa(d.id)})).filter(d => d.capa);
      if (LASERES.length && Punto && Linea && Trazo && vigente()) {
        LASERES.forEach(L => { L.medidas = L.capa.props.data.map(r => medir(r.path)); });
        const COLA = 700, TOTAL_L = Math.max(...LASERES.map(L => L.ini + L.dur)) + COLA;
        await durante(TOTAL_L, t => {
          const ms = t * TOTAL_L, extra = [];
          LASERES.forEach(L => {
            const lt = (ms - L.ini) / L.dur, dt = ms - (L.ini + L.dur);
            if (lt <= 0) { reemplazos[L.id] = L.capa.clone({visible: false}); return; }
            const f = lt >= 1 ? 1 : seno(lt), puntas = [];
            const datos = L.capa.props.data.map((r, i) => { const [tramo, punta] = recortar(r.path, L.medidas[i], f); puntas.push(punta); return {...r, path: tramo}; });
            reemplazos[L.id] = L.capa.clone({visible: true, data: datos});
            // resplandor del trazo: constante mientras dibuja; al cerrarse destella y se apaga en 0,6 s
            const brillo = lt < 1 ? 1 : lim(1 - dt / 600), pulso = lt < 1 ? 1 : 1 + 0.9 * Math.exp(-dt / 140);
            if (brillo > 0.001) {
              extra.push(new Trazo({id: "glow_" + L.id, data: datos, getPath: r => r.path, getColor: conAlfa(L.color, 70 * brillo * pulso),
                getWidth: 140 * pulso, widthMinPixels: 12 * pulso, capRounded: true, jointRounded: true, parameters: encima}));
            }
            // haz de luz desde el cielo hasta la punta; al cerrar la figura se eleva y se desvanece
            const subida = lt < 1 ? 0 : lim(dt / 300), alfaH = lt < 1 ? lim(lt / 0.08) : 1 - subida;
            if (alfaH > 0.001) {
              const alzar = subida * subida, ps = puntas.slice(0, 4), fl = 1 + 0.12 * Math.sin(ms / 25);
              const nucleo = [], aura = [];
              // al cerrar la figura el haz se recoge hacia el satelite
              ps.forEach(p => { const b = mezcla3(p, apex, alzar); nucleo.push(...hazA(b, apex, [255, 255, 255], 255 * alfaH)); aura.push(...hazA(b, apex, L.color, 150 * alfaH)); });
              extra.push(dibujaHaz("haz_g_" + L.id, aura, 14, 8), dibujaHaz("haz_n_" + L.id, nucleo, 3, 2));
              const pts = ps.map(p => ({p}));
              extra.push(new Punto({id: "flare_" + L.id, data: pts, getPosition: d => d.p, getFillColor: conAlfa(L.color, 120 * alfaH), getRadius: 90,
                              radiusMinPixels: 14 * fl, radiusMaxPixels: (30 + 20 * subida) * fl, billboard: true, parameters: encima}),
                         new Punto({id: "punta_" + L.id, data: pts, getPosition: d => d.p, getFillColor: conAlfa([255, 255, 255], 255 * alfaH), getRadius: 40,
                              radiusMinPixels: 5, radiusMaxPixels: 10, billboard: true, parameters: encima}));
            }
          });
          refrescar(extra);
        });
        LASERES.forEach(L => { reemplazos[L.id] = L.capa.clone({visible: true}); });
        refrescar();
      } else {
        ["cuenca", "buffer"].forEach(id => { const l = capa(id); if (l) reemplazos[id] = l.clone({visible: true}); });
        refrescar();
      }
      await esperar(150);
      vuelta();   // la camara empieza a moverse justo antes de que caigan los pines

      // ---- Fase 2: las estaciones caen una tras otra (el ultimo aterriza siempre al mismo tiempo, sea cual sea N) ----
      const cab = capa("estaciones"), tal = capa("tallos");
      if (cab && Punto && Linea && vigente()) {
        const datosC = cab.props.data, datosT = tal ? tal.props.data : [];
        const n = datosC.length, CAIDA = 1500, REPARTO = 3800, COLA_D = 850;
        const paso = n > 1 ? (REPARTO - CAIDA) / (n - 1) : 0;
        // orden aleatorio, pero siempre el mismo para un mismo conjunto
        let sem = 12345; const azar = () => { sem = (Math.imul(sem, 1664525) + 1013904223) >>> 0; return sem / 4294967296; };
        const orden = datosC.map((_, i) => i);
        for (let i = n - 1; i > 0; i--) { const j = Math.floor(azar() * (i + 1)); [orden[i], orden[j]] = [orden[j], orden[i]]; }
        const inicio = new Array(n);
        orden.forEach((si, k) => { inicio[si] = k * paso; });
        const total = (n > 1 ? REPARTO : CAIDA) + COLA_D;
        await durante(total, t => {
          const ms = t * total, idx = [], desp = [], esc = [], opaco = [], estelas = [], sombras = [], ondas = [];
          for (let i = 0; i < n; i++) {
            const u = (ms - inicio[i]) / CAIDA;
            if (u <= 0) continue;
            const q = lim(u), dt = ms - inicio[i] - CAIDA, c = datosC[i], tl = datosT[i];
            // falta recorrer esta fraccion del camino desde el satelite: arranca rapido, como un disparo
            const fr = q < 1 ? 1 - (0.35 * q + 0.65 * q * q) : 0;
            const off = [(apex[0] - c.pos[0]) * fr, (apex[1] - c.pos[1]) * fr, (apex[2] - c.pos[2]) * fr];
            let e = 1;
            if (dt >= 0) {
              if (dt < 320) off[2] += 90 * E * Math.sin(Math.PI * dt / 320) * (1 - dt / 320);   // rebote
              e = 1 + 0.35 * (1 - lim(dt / 180));                                         // golpe al aterrizar
            }
            idx.push(i); desp.push(off); esc.push(e); opaco.push(255 * lim(q * 6));
            const suelo = tl ? tl.desde : c.pos, col = c.rgb || [255, 255, 255];
            if (q < 1) estelas.push(...hazA([c.pos[0] + off[0], c.pos[1] + off[1], c.pos[2] + off[2]], apex, col, 200 * q, 5, 0.04 + 0.16 * q));
            const so = q < 1 ? 0.45 * q * q : 0.45 * lim(1 - dt / 400);
            if (so > 0.005) sombras.push({p: suelo, r: 140 * E * (2.4 - 1.4 * q), c: [0, 0, 0, Math.round(255 * so)]});
            if (dt >= 0 && dt < 700) { const k = dt / 700; ondas.push({p: suelo, r: (40 + 340 * salida(k)) * E, c: conAlfa(col, 120 * (1 - k) * (1 - k))}); }
          }
          reemplazos.estaciones = cab.clone({visible: true, data: idx.map(i => datosC[i]),
            getPosition: (x, o) => { const d = desp[o.index]; return [x.pos[0] + d[0], x.pos[1] + d[1], x.pos[2] + d[2]]; },
            getRadius: (x, o) => x.radio * esc[o.index],
            getFillColor: (x, o) => [...x.rgb, opaco[o.index]],
            updateTriggers: {getPosition: [ms], getRadius: [ms], getFillColor: [ms]}});
          if (tal && datosT.length === n) reemplazos.tallos = tal.clone({visible: true, data: idx.map(i => datosT[i]),
            getSourcePosition: (x, o) => { const d = desp[o.index]; return [x.desde[0] + d[0], x.desde[1] + d[1], x.desde[2] + d[2]]; },
            getTargetPosition: (x, o) => { const d = desp[o.index]; return [x.hasta[0] + d[0], x.hasta[1] + d[1], x.hasta[2] + d[2]]; },
            updateTriggers: {getSourcePosition: [ms], getTargetPosition: [ms]}});
          refrescar([disco("sombras", sombras), dibujaHaz("estelas", estelas, 3, 2), anillo("ondas_pin", ondas, 2)]);
        });
        reemplazos.estaciones = cab.clone({visible: true});
        if (tal) reemplazos.tallos = tal.clone({visible: true});
        refrescar();
      }

      // ---- Fase 3: las altitudes dudosas salen del suelo a la vez como haces naranjas, con doble onda y destello ----
      const sal = capa("saltos"), fan = capa("fantasmas");
      if (sal && Linea && Punto && vigente()) {
        const datosS = sal.props.data, SUBIDA = 1300, TOTAL_A = 2000;
        await durante(TOTAL_A, t => {
          const ms = t * TOTAL_A, k = salida(lim(ms / SUBIDA));
          const nucleo = [], aura = [], bases = [], ondas = [], destellos = [];
          datosS.forEach(s => {
            const d = s.desde, h = s.hasta, tope = [d[0], d[1], d[2] + (h[2] - d[2]) * k];
            nucleo.push({a: d, b: tope, c: [255, 205, 150, 255]});
            aura.push({a: d, b: tope, c: [255, 122, 26, 90]});
            bases.push({p: d, r: 80 * E, c: [255, 122, 26, Math.round(110 + 50 * Math.sin(ms / 160))]});
            const k1 = lim(ms / 1100), k2 = lim((ms - 220) / 1250);
            if (k1 < 1) ondas.push({p: d, r: (60 + 520 * salida(k1)) * E, c: [255, 122, 26, Math.round(150 * (1 - k1) * (1 - k1))]});
            if (k2 > 0 && k2 < 1) ondas.push({p: d, r: (60 + 750 * salida(k2)) * E, c: [255, 150, 70, Math.round(130 * (1 - k2) * (1 - k2))]});
            const fk = ms / 500;
            if (fk < 1) destellos.push({p: d, r: (100 + 250 * fk) * E, c: [255, 170, 90, Math.round(130 * (1 - fk))]});
          });
          // el fantasma (altitud del catalogo) aparece con un pequeno "pop" cuando el haz llega arriba
          if (fan && ms > SUBIDA * 0.75) {
            const h = lim((ms - SUBIDA * 0.75) / 500), pop = 1 + 0.6 * Math.sin(Math.PI * h) * (1 - 0.4 * h);
            reemplazos.fantasmas = fan.clone({visible: true, radiusMinPixels: 6 * pop, radiusMaxPixels: 14 * pop});
          }
          refrescar([disco("alerta_destello", destellos), anillo("alerta_ondas", ondas, 2), anillo("alerta_base", bases, 2),
                     dibujaHaz("haces_aura", aura, 12, 8), dibujaHaz("haces", nucleo, 4, 3)]);
        });
        ["saltos", "fantasmas", "fantasmas_texto"].forEach(id => { const l = capa(id); if (l) reemplazos[id] = l.clone({visible: true}); });
        refrescar();
        await esperar(600);
      }
    } catch (e) { /* si algo falla, se muestra todo de una vez */ }
    if (vigente()) poner(originales.slice());
  }
  if (!vigente()) return;
  enIntro = false;
  w.__y2kEnIntro = false;
  vuelta();   // si ya arranco durante la intro, no hace nada

  // ---- 3. Vuelta de camara ----
  function vuelta() {
  if (vueltaIniciada) return;
  vueltaIniciada = true;
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
    if (enIntro) {
      // durante la intro Streamlit no debe re-dibujar (borraria las capas animadas): se mueve la vista directo
      deck.setProps({viewState: nueva});
    } else if (typeof deck.props.onViewStateChange === "function") {
      deck.props.onViewStateChange({viewState: nueva, oldViewState: actual, interactionState: {}, viewId: "default-view"});
    } else {
      deck.setProps({viewState: nueva});
    }
  };
  const cuadro = ahora => {
    // tambien se detiene si el usuario usa los botones de camara (w.__y2kParaVuelta)
    if (parar || !vigente() || (w.__y2kParaVuelta || 0) > inicio) return;
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
  // Modo Lite o movimiento reducido: sin acercamiento animado ni vuelta continua; la camara queda de una vez en el
  // encuadre final (misma estacion, mismo zoom). Son ajustes independientes: cualquiera de los dos basta.
  if (lite || quiereMenosMovimiento) {
    if (!tocado && !((w.__y2kParaVuelta || 0) > tInicio))
      mover({longitude: O.lon, latitude: O.lat, position: [0, 0, O.pivote], maxPitch: 85, zoom: O.zoom,
             pitch: inclinacion(O.rumbo), bearing: normal(O.rumbo)});
    return;
  }
  w.requestAnimationFrame(cuadro);
  }
})();
</script>
"""


# Algunos navegadores (Safari en modo privado o con proteccion avanzada contra rastreo, Brave,
# Firefox "resistFingerprinting") meten ruido a proposito en los pixeles que lee una pagina.
# Las alturas del relieve vienen en los pixeles, asi que ese ruido se ve como miles de picos falsos.
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
      texto.textContent = "⚠ Tu navegador altera las imágenes por privacidad y el relieve puede verse con picos falsos. " +
        "Prueba en una ventana normal o en otro navegador.";
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
#     pixeles de los que se notan; se limita a 1,5x (1x en modo Lite).
#  2. (La perdida del contexto grafico y los fallos de carga los vigila estilo.instalar_ui, que
#     ofrece «Activar Lite y reintentar» o «Seguir intentando» sin cambiar de modo por su cuenta.)
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

  // 1. Pixeles (en modo Lite, 1 pixel de dibujo por pixel CSS: menos nitidez, mucha menos memoria)
  function limitarPixeles(deck) {
    const lite = w.getComputedStyle(d.documentElement).getPropertyValue("--y2k-lite").trim() === "1";
    const tope = Math.min(w.devicePixelRatio || 1, lite ? 1 : 1.5);
    if (deck && deck.props.useDevicePixels !== tope) deck.setProps({useDevicePixels: tope});
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

  estado.ciclo = setInterval(() => { limitarPixeles(buscarDeck()); }, 1500);
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



def orbitar(orbita, turno, intro=False, satelite=False, apex=1.7, forzar=False):
    """Guion que acerca la camara a la estacion y da una vuelta lenta a su alrededor. `turno`
    cambia en cada seleccion nueva, asi el guion solo corre una vez por estacion elegida.
    intro: antes de la vuelta, corre la secuencia de entrada (lasers, caida de pines, alertas).
    En modo Lite (lo lee el guion en el navegador) no hay secuencia ni vuelta: la camara salta al encuadre final.
    forzar: la persona pidio repetir la animacion; se hace aunque su equipo pida reducir el movimiento."""
    import json
    return _ORBITA.replace("__ORBITA__", json.dumps({**orbita, "intro": bool(intro), "turno": turno, "satelite": bool(satelite),
                                                     "apex": float(apex), "forzar": bool(forzar)})) + f"<!-- turno {turno} -->"


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
        "distancia": round(distancia), "lon": lon, "lat": lat, "zoom": round(zoom, 3), "pivote": round((z_min + z_max) / 2, 1),
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
            n = max(40, min(1600, int(borde.length / 0.0008)))
            anillos.append([borde.interpolate(i / n, normalized=True).coords[0] for i in range(n + 1)])
    return anillos


@lru_cache(maxsize=64)
def _camino_3d_cache(anillo, base):
    return _camino_3d_calcular(anillo, base)


def _camino_3d(anillo, base):
    """Igual que abajo, pero recuerda el resultado: Streamlit repite todo el script en cada clic y estos
    contornos (muchos miles de consultas de altura) no cambian mientras sea la misma zona."""
    return [list(p) for p in _camino_3d_cache(tuple(map(tuple, anillo)), base)]


def _camino_3d_calcular(anillo, base):
    """Contorno pegado al relieve. El relieve que dibuja el navegador es mas fino y distinto al que
    se consulta aqui (nivel 12), asi que se toma el punto mas alto de los alrededores y se sube un
    poco: de otro modo las lomas tapaban tramos de la linea."""
    puntos = []
    d = 0.0003  # ~33 m
    for lon, lat in anillo:
        alturas = [altura_terreno(lon + dx, lat + dy) for dx, dy in ((0, 0), (d, 0), (-d, 0), (0, d), (0, -d))]
        alturas = [a for a in alturas if a is not None]
        z = max(alturas) if alturas else None
        puntos.append([lon, lat, ((z if z is not None else base) - base) * EXAGERACION + 60])
    return puntos


def construir_deck(cuenca_gdf, area_gdf, estaciones, seleccionada=None, textura="Satélite", paleta=None,
                   ligero=False, altura=None):
    """
    ligero: celulares, o despues de que el navegador se quedo sin memoria grafica: menos detalle.
    altura: (minimo, maximo) en metros para la textura "Altura" (colores segun la altitud del relieve).
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
    # Modo "Altura": con la escala de Colombia (vista general) se pixela un poco: tiles de 512 (cuatro veces menos),
    # un nivel menos de detalle e imagen a 128 px. Con la escala de la zona se queda con todo el detalle
    por_altura = textura == "Altura" and altura is not None
    pixelado = por_altura and tuple(altura) == ALTURA_COLOMBIA
    detalle = {"tiles": 256 if (cerca and not pixelado) else 512, "malla": 4 if cerca else (10 if ligero else 8),
               "guardados": 50 if ligero else (100 if cerca else 80), "lejos": 1.8 if ligero else (3 if cerca else 2)}

    capas = [pdk.Layer(
        "TerrainLayer",
        id="terreno",
        elevation_decoder={"rScaler": 256 * EXAGERACION, "gScaler": EXAGERACION,
                           "bScaler": EXAGERACION / 256, "offset": (-32768 - base) * EXAGERACION},
        elevation_data=URL_ELEVACION,
        texture=(URL_ALTURA.replace("__MIN__", f"{altura[0]:.0f}").replace("__MAX__", f"{altura[1]:.0f}")
                 .replace("__PX__", "128" if pixelado else "256") if por_altura
                 else TEXTURAS.get(textura, TEXTURAS["Satélite"])),
        # Los tiles miden 256 px: con tile_size=256 cada pixel de la foto se ve a su tamano real
        # (con 512, el valor normal, se estira al doble); cuesta ~4 veces mas tiles
        tile_size=detalle["tiles"],
        max_zoom=ZOOM_MAX_TILES - 1 if pixelado else ZOOM_MAX_TILES,
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
                               get_path="path", get_color=[255, 122, 26, 235], width_min_pixels=2, get_width=20,
                               billboard=True))
    if cuenca_gdf is not None:
        capas.append(pdk.Layer("PathLayer", id="cuenca", data=[{"path": _camino_3d(a, base)} for a in anillos_cuenca],
                               get_path="path", get_color=[53, 240, 255, 255], width_min_pixels=3, get_width=30,
                               billboard=True))

    # Pines: tallo desde el terreno y cabeza redonda arriba
    tallos, cabezas = [], []
    for e in estaciones:
        z = altura_terreno(e["lon"], e["lat"])
        z = ((z if z is not None else e["altitud"] or base) - base) * EXAGERACION
        es_sel = e["codigo"] == seleccionada
        alto = ALTO_PIN_SEL if es_sel else 170 if e["ok"] else 90
        color = [255, 255, 255] if es_sel else e["color"] if e["ok"] else [150, 160, 180]
        # Si la altitud es dudosa, el pin marca el terreno real: sin tallo y casi al ras del suelo, para que
        # no parezca que la estacion esta elevada; lo unico vertical es el haz naranja hacia el catalogo
        con_fantasma = bool(e.get("dudosa") and e.get("altitud") is not None and e.get("terreno") is not None)
        alto_z = 35 if con_fantasma else alto * EXAGERACION
        # el tallo se queda en la lista (con largo cero) porque la animacion de entrada lo busca por posicion
        tallos.append({"desde": [e["lon"], e["lat"], z], "hasta": [e["lon"], e["lat"], z + (0 if con_fantasma else alto_z)]})
        cabezas.append({**e, "pos": [e["lon"], e["lat"], z + alto_z], "rgb": color,
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
                    f"<div style='color:{paleta.get('alerta', '#8A3208')}'>{{alerta}}</div>",
            "style": {"backgroundColor": paleta["superficie"], "color": paleta["tinta"], "fontFamily": "Figtree, sans-serif",
                      "fontSize": "12px", "border": f"1px solid {paleta['borde']}", "borderRadius": "10px"},
        },
    )
    return deck, orbita
