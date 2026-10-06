import json
import time
from pathlib import Path

import streamlit.components.v1 as components

# ===========================================================================
# ESCANER DEL MAPA 2D
# ---------------------------------------------------------------------------
# Al dibujar (o editar) el rectangulo de la cuenca, un escaner se superpone al rectangulo mientras
# el servidor calcula las estaciones; al terminar se desvanece y las estaciones aparecen en orden,
# de arriba hacia abajo. El dibujo del escaner (canvas) viene del handoff de diseno:
# modules/scan_overlay.js (ScanOverlay.drawFrame / ScanOverlay.leaflet).
#
# Como funciona:
#  - El mapa 2D (streamlit-folium) vive en un iframe del mismo origen que expone `map`, `L` y
#    `drawnItems`. El controlador se inyecta en la pagina principal (asi sobrevive a las recargas
#    de los components.html) y engancha los eventos draw:created / edited / deleted de ese mapa.
#  - El escaner arranca en el instante en que se suelta el rectangulo, sin esperar al servidor; el
#    mapa queda quieto (sin arrastrar ni zoom; la barra de dibujo sigue activa) hasta que termina, o a los 30 s.
#  - Python avisa que termino con `listo(...)` (al final del calculo, despues del mapa). El
#    controlador espera a que lleguen los marcadores de estaciones y los revela de a uno.
#  - Los marcadores de estaciones llevan la opcion y2k="pin" (ver map_view.capa_dinamica): el
#    escaner los esconde con estilo (radio y opacidad) mientras corre y los revela de a uno. Van en el
#    mismo canvas que el rectangulo: un panel propio intercepta los clics del lapiz y la basurita.
#  - El rectangulo nuevo reemplaza al anterior: el controlador quita las demas figuras ANTES de que
#    streamlit-folium lea `drawnItems` (su listener corre despues del nuestro).
# ===========================================================================

_SCAN_SRC = (Path(__file__).with_name("scan_overlay.js")).read_text(encoding="utf-8")

_CONTROLADOR = r"""
(function () {
  if (window.__y2kScan) return;
  var SRC = __SCAN_SRC__;
  var MIN_MS = 1200, TOPE_MS = 30000, ESPERA_MARCAS = 6000;
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var COLORES = {satelite: {color: "#5fe0ff", halo: "rgba(4,10,16,.6)"}, mapa: {color: "#1a63d8", halo: "rgba(255,255,255,.85)"}};
  var S = {activo: null, n: 0};
  var pausa = function (ms) { return new Promise(function (r) { setTimeout(r, ms); }); };

  function marco() {
    var fs = document.querySelectorAll("iframe");
    for (var i = 0; i < fs.length; i++) if ((fs[i].title || "").indexOf("folium") >= 0) return fs[i];
    return null;
  }
  function esPin(l) { return l && l.options && l.options.y2k === "pin" && l.setRadius; }
  function marcas(map) {
    var r = [];
    map.eachLayer(function (l) { if (esPin(l)) r.push(l); });
    return r;
  }
  // Los pines comparten canvas con el rectangulo (un panel propio se comeria los clics del lapiz y la
  // basurita), asi que se esconden con estilo y guardan sus valores originales para revelarlos despues
  function ocultar(l) {
    if (!l.__y2k) l.__y2k = {r: l.options.radius, o: l.options.opacity, f: l.options.fillOpacity};
    l.setRadius(0.01); l.setStyle({opacity: 0, fillOpacity: 0});
  }
  function restaurar(l) {
    var g = l.__y2k; if (!g) return;
    l.setRadius(g.r); l.setStyle({opacity: g.o, fillOpacity: g.f}); delete l.__y2k;
  }
  function preparar(win) {
    if (win.ScanOverlay) return true;
    try {
      var s = win.document.createElement("script"); s.textContent = SRC; win.document.head.appendChild(s);
      var l = win.document.createElement("link"); l.rel = "stylesheet";
      l.href = "https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@500&display=swap";
      win.document.head.appendChild(l);
    } catch (e) {}
    return !!win.ScanOverlay;
  }
  // Mientras corre el escaner el mapa no se mueve ni hace zoom
  function bloquear(map, win, si) {
    ["dragging", "touchZoom", "doubleClickZoom", "scrollWheelZoom", "boxZoom", "keyboard"].forEach(function (k) {
      if (map[k]) { if (si) map[k].disable(); else map[k].enable(); }
    });
    // La barra de dibujo queda activa: dibujar o editar de nuevo cancela este escaner y arranca otro
    win.document.querySelectorAll(".leaflet-control-zoom").forEach(function (b) {
      b.style.pointerEvents = si ? "none" : ""; b.style.opacity = si ? ".45" : "";
    });
  }

  function iniciar(map, win, limites) {
    cancelar(false);
    if (!preparar(win)) return;
    var c = (map.__y2kBase === "Calles" || map.__y2kBase === "Relieve") ? COLORES.mapa : COLORES.satelite;
    var scan = win.ScanOverlay.leaflet(win.L, limites, {cycle: 1.8, color: c.color, halo: c.halo, label: "Buscando estaciones"});
    scan.addTo(map);
    marcas(map).forEach(ocultar);
    bloquear(map, win, true);
    var a = S.activo = {map: map, win: win, scan: scan, t0: performance.now(), info: null, id: ++S.n};
    a.tope = setTimeout(function () { if (S.activo === a) terminar(a); }, TOPE_MS);
  }

  function cancelar(devolverPines) {
    var a = S.activo; if (!a) return;
    S.activo = null; clearTimeout(a.tope);
    try { a.map.removeLayer(a.scan); } catch (e) {}
    bloquear(a.map, a.win, false);
    if (devolverPines) marcas(a.map).forEach(restaurar);
  }

  async function terminar(a) {
    if (a.terminando) return;
    a.terminando = true;
    var falta = MIN_MS - (performance.now() - a.t0);
    if (falta > 0) await pausa(falta);
    // esperar a que el componente dibuje los marcadores de las estaciones
    var t1 = performance.now(), antes = -1, estable = 0;
    while (S.activo === a && a.info && a.info.n > 0 && performance.now() - t1 < ESPERA_MARCAS) {
      var k = marcas(a.map).length;
      estable = k > 0 && k === antes ? estable + 1 : 0; antes = k;
      if (estable >= 2) break;
      await pausa(100);
    }
    if (S.activo !== a) return;
    if (a.info && a.info.texto) { a.scan.setOptions({label: a.info.texto}); await pausa(800); }   // que se alcance a leer
    if (S.activo !== a) return;
    await a.scan.finish();
    if (S.activo !== a) return;
    S.activo = null; clearTimeout(a.tope);
    bloquear(a.map, a.win, false);
    revelar(a.map);
  }

  // Las estaciones aparecen de norte a sur (como el barrido), cada una crece y asienta un poco
  function revelar(map) {
    var lista = marcas(map).filter(function (l) { return l.__y2k; });
    if (!lista.length) return;
    lista.sort(function (x, y) { return y.getLatLng().lat - x.getLatLng().lat; });
    var info = lista.map(function (m) { return {m: m, r: m.__y2k.r, o: m.__y2k.o, f: m.__y2k.f}; });
    var N = info.length, t0 = performance.now(), DUR = 420, ESC = 520;
    var atras = function (t) { var c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
    (function cuadro() {
      var ahora = performance.now() - t0, vivos = 0;
      info.forEach(function (i, k) {
        var u = (ahora - (N > 1 ? k / (N - 1) : 0) * ESC) / DUR;
        if (u >= 1) {
          if (!i.fin) { i.fin = true; restaurar(i.m); }
          return;
        }
        vivos++;
        if (u <= 0) return;
        i.m.setRadius(Math.max(0.01, i.r * atras(u)));
        var al = Math.min(1, u * 2.5);
        i.m.setStyle({opacity: i.o * al, fillOpacity: i.f * al});
      });
      if (vivos) requestAnimationFrame(cuadro);
    })();
  }

  function primero(map, tipo, fn) {
    map.on(tipo, fn);
    var cola = map._events && map._events[tipo];
    if (cola && cola.length > 1) cola.unshift(cola.pop());   // que corra antes que el de streamlit-folium
  }

  function enganchar() {
    var f = marco(), win;
    try { win = f && f.contentWindow; } catch (e) { return; }
    var map = win && win.map;
    if (!map || !win.L || map.__y2kEnganchado) return;
    map.__y2kEnganchado = true;
    map.on("baselayerchange", function (e) { map.__y2kBase = e.name; });
    // pines que llegan mientras corre el escaner (la respuesta del servidor): nacen escondidos
    map.on("layeradd", function (e) { if (S.activo && S.activo.map === map && esPin(e.layer)) ocultar(e.layer); });
    primero(map, "draw:created", function (e) {
      var items = win.drawnItems;
      if (items) items.eachLayer(function (l) { if (l !== e.layer) items.removeLayer(l); });
      if (!reduce && e.layer && e.layer.getBounds) iniciar(map, win, e.layer.getBounds());
    });
    map.on("draw:edited", function (e) {
      var b = null;
      e.layers.eachLayer(function (l) { if (!b && l.getBounds) b = l.getBounds(); });
      if (b && !reduce) iniciar(map, win, b);
    });
    map.on("draw:deleted", function () { cancelar(true); });
    // Leaflet.draw vuelve a habilitar el arrastre del mapa al cerrar la herramienta (justo despues de
    // draw:created): si el escaner sigue corriendo, se reaplica el bloqueo
    map.on("draw:drawstop draw:editstop", function () {
      var a = S.activo;
      if (a && a.map === map) setTimeout(function () { if (S.activo === a) bloquear(map, a.win, true); }, 0);
    });
  }
  setInterval(enganchar, 400);

  window.__y2kScan = {
    // Python avisa que termino de calcular: {n: estaciones, texto: mensaje final}
    listo: function (info) {
      var a = S.activo;
      if (!a || a.info) return;
      a.info = info || {};
      terminar(a);
    },
  };
})();
"""


def instalar():
    """Inyecta el controlador en la pagina principal (una sola vez) para que sobreviva a las recargas."""
    codigo = _CONTROLADOR.replace("__SCAN_SRC__", json.dumps(_SCAN_SRC))
    cuerpo = ("(function(){var w=window.parent;if(w.__y2kScan)return;var s=w.document.createElement('script');"
              f"s.textContent={json.dumps(codigo)};w.document.head.appendChild(s);}})();")
    components.html("<script>" + cuerpo.replace("</", "<\\/") + "</script>", height=0)


def listo(n, texto):
    """Avisa al navegador que las estaciones ya estan calculadas (cierra el escaner si hay uno corriendo)."""
    aviso = json.dumps({"n": int(n), "texto": texto})
    components.html(f"<script>try{{window.parent.__y2kScan.listo({aviso})}}catch(e){{}}</script><!--{time.time()}-->",
                    height=0)
