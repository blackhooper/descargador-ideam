import json
import streamlit.components.v1 as components

# ===========================================================================
# ESCENA PIXEL ART DE LA DESCARGA
# ---------------------------------------------------------------------------
# El edificio del IDEAM, con su estacion meteorologica al lado, envia los
# documentos en arco hasta el escritorio del usuario (un computador de los 2000).
# Cada estacion guardada llega como una carpeta del color de su clase de cobertura.
#
# El avance real lo lee de un elemento oculto de la pagina (.ideam-estado)
# que actualiza procesar_descargas: "p=0.42;c=#0ca30c,#fab219;f=0".
# Si no lo encuentra (por ejemplo en otro navegador), avanza por tiempo.
# ===========================================================================

_HTML = r"""
<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Silkscreen&display=swap">
<style>
html,body{margin:0;height:100%;background:#3E6FC4;overflow:hidden}
canvas{width:100%;height:100%;display:block;image-rendering:pixelated;object-fit:contain;border-radius:12px}
#banner{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none}
#banner div{font-family:"Silkscreen",monospace;color:#FFF6C8;font-size:clamp(18px,4.5vw,38px);text-shadow:3px 3px 0 #7A2E8F,-1px -1px 0 #16213A;text-align:center;line-height:1.15;background:rgba(22,33,58,.4);padding:10px 18px;border-radius:6px}
#banner small{display:block;font-size:.45em;color:#DDF7FF;margin-top:6px}
[hidden]{display:none!important}
</style></head><body>
<canvas id="scene" width="256" height="144"></canvas>
<div id="banner" hidden><div>¡DESCARGA COMPLETA!<small id="sub"></small></div></div>
<script>
(() => {
const MODO = __MODO__, TOTAL = __TOTAL__, EST_SEG = __SEG__, COLORES_FIN = __COLORES__, SUB = __SUB__;
const sc = document.getElementById("scene"), s = sc.getContext("2d");
const PW = 256, PH = 144, SUELO = 122, VUELO = 1700;
const ORIGEN = {x: 46, y: 60}, DESTINO = {x: 203, y: 93};
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
let p = 0, colores = [], fin = MODO === "final", tFin = fin ? -1e9 : 0, vistoEstado = false;
let hojas = [], ultimaHoja = -1e9, carpetas = [];
const t0 = performance.now();
if (fin) { colores = COLORES_FIN.slice(); p = 1; }

function rect(x, y, w, h, c){ s.fillStyle = c; s.fillRect(Math.round(x), Math.round(y), w, h); }
const lerp = (a, b, q) => a + (b - a) * q;
const PAPELES = ["#FAB219", "#5AA2F5", "#0CA30C", "#EC835A"];

function leerEstado(t){
  if (fin) return;
  try {
    const el = window.parent.document.querySelector(".ideam-estado");
    if (el) {
      vistoEstado = true;
      const d = Object.fromEntries(el.textContent.trim().split(";").map(x => x.split("=")));
      p = Math.max(0, Math.min(1, parseFloat(d.p) || 0));
      colores = d.c ? d.c.split(",").filter(Boolean) : [];
      if (d.f === "1") { fin = true; tFin = t; }
      return;
    }
  } catch (e) {}
  if (!vistoEstado && t > 2500) {
    // sin acceso a la pagina: avance aproximado por tiempo
    p = Math.min(.97, t / 1000 / Math.max(5, EST_SEG));
    const n = Math.floor(p * TOTAL);
    while (colores.length < n) colores.push("#5AA2F5");
  }
}
function cielo(){
  const b = ["#3E6FC4", "#5A86D0", "#7AA0DB", "#9DBAE6", "#C3D6F0"];
  b.forEach((c, i) => rect(0, i * 18, PW, 18, c));
  for (let i = 1; i < b.length; i++) for (let x = 0; x < PW; x += 2) rect(x + (i % 2), i * 18 - 1, 1, 1, b[i]);
}
function sol(t){
  for (let k = 0; k < 8; k++){ const a = k / 8 * 6.283 + t / 2400; rect(236 + Math.cos(a) * 11, 22 + Math.sin(a) * 11, 2, 2, "#FFE27A"); }
  rect(230, 16, 12, 12, "#FFD23F"); rect(232, 14, 8, 16, "#FFD23F"); rect(228, 18, 16, 8, "#FFD23F");
}
function nube(x, y){
  rect(x + 4, y, 14, 4, "#FFFFFF"); rect(x, y + 3, 26, 5, "#FFFFFF"); rect(x + 2, y + 8, 22, 2, "#E4ECF8");
}
function paisaje(){
  for (let x = 0; x < PW; x++){
    const y1 = 72 + Math.round(10 * Math.sin(x * .045) + 6 * Math.sin(x * .13 + 1)); rect(x, y1, 1, PH - y1, "#4F8A6A");
    const y2 = 90 + Math.round(8 * Math.sin(x * .03 + 2) + 4 * Math.sin(x * .09)); rect(x, y2, 1, PH - y2, "#3B7053");
  }
  rect(0, SUELO, PW, PH - SUELO, "#2E5A43");
  for (let x = 0; x < PW; x += 4) rect(x, SUELO, 2, 1, "#46785B");
}
function edificio(t){
  const x0 = 14;
  rect(x0, 70, 62, 52, "#E4E8F2"); rect(x0, 70, 62, 4, "#9AA6C9"); rect(x0 - 4, 66, 70, 5, "#6E7BA8");
  rect(x0 + 12, 56, 38, 11, "#FAB219"); rect(x0 + 12, 66, 38, 1, "#C98A00");
  s.fillStyle = "#16213A"; s.font = "8px Silkscreen, monospace"; s.textBaseline = "top"; s.fillText("IDEAM", x0 + 17, 57);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++){
    const x = x0 + 6 + c * 13, y = 78 + r * 14, encendida = (Math.floor(t / 1800) + r * 3 + c) % 4 !== 0;
    rect(x, y, 10, 10, "#6E7BA8"); rect(x + 1, y + 1, 8, 8, encendida ? "#FFF1B8" : "#9FB3D9");
  }
  rect(x0 + 26, 110, 10, 12, "#4A5673");
}
function estacion(t){
  // estacion meteorologica: pluviometro y anemometro girando
  const x = 92;
  rect(x, 96, 2, 26, "#C9D2E6");
  rect(x - 5, 108, 12, 2, "#C9D2E6"); rect(x - 4, 102, 6, 6, "#F3F6FB"); rect(x - 4, 102, 6, 1, "#9AA6C9");
  const a = t / 160;
  for (let k = 0; k < 3; k++){ const b = a + k * 2.094; rect(x + 1 + Math.cos(b) * 6, 94 + Math.sin(b) * 2, 3, 2, "#FFFFFF"); }
  rect(x, 93, 2, 3, "#9AA6C9");
}
function escritorio(){
  rect(184, 103, 66, 4, "#A06A3A"); rect(184, 103, 66, 1, "#C98F58"); rect(188, 107, 3, 15, "#6B4424"); rect(243, 107, 3, 15, "#6B4424");
  rect(188, 80, 30, 22, "#D8D0B8"); rect(188, 80, 30, 1, "#EFE9D6"); rect(191, 83, 24, 15, "#0E1A12");
  s.fillStyle = "#8CFF9E"; s.font = "8px Silkscreen, monospace"; s.textBaseline = "top";
  const txt = Math.round(p * 100) + "%"; s.fillText(txt, 203 - s.measureText(txt).width / 2, 86);
  rect(199, 102, 8, 1, "#B9B09A"); rect(190, 101, 26, 2, "#C7BEA5");
  while (carpetas.length < colores.length) carpetas.push({c: colores[carpetas.length], y: fin && MODO === "final" ? 999 : 60});
  carpetas.slice(-20).forEach((cp, i) => {
    const col = Math.floor(i / 10), fila = i % 10, x = 222 + col * 13, y = 99 - fila * 4;
    cp.y = (reduce || cp.y === 999) ? y : Math.min(y, cp.y + 5);
    rect(x, cp.y, 11, 3, cp.c); rect(x, cp.y, 4, 1, "#FFFFFF"); rect(x, cp.y + 3, 11, 1, "rgba(0,0,0,.35)");
  });
}
function papel(x, y, c){ rect(x, y, 4, 5, "#FFFFFF"); rect(x, y, 4, 1, c); rect(x + 1, y + 2, 2, 1, "#C9D2E6"); }
function escena(t){
  cielo(); sol(t);
  nube(((t / 90) % (PW + 60)) - 40, 20); nube(((t / 140 + 150) % (PW + 60)) - 40, 36);
  paisaje(); edificio(t); estacion(t); escritorio();
  // el IDEAM envia los documentos en arco hasta el escritorio, al ritmo del avance
  if (!fin && !reduce && t - ultimaHoja > 380) { ultimaHoja = t; hojas.push({t0: t, c: PAPELES[Math.floor(Math.random() * 4)]}); }
  hojas.forEach(h => {
    const q = Math.min(1, (t - h.t0) / VUELO);
    papel(lerp(ORIGEN.x, DESTINO.x, q), lerp(ORIGEN.y, DESTINO.y, q) - Math.sin(Math.PI * q) * 40, h.c);
  });
  hojas = hojas.filter(h => t - h.t0 < VUELO);
  if (fin && (MODO === "final" || t - tFin > 1200)) {
    document.getElementById("sub").textContent = SUB;
    document.getElementById("banner").hidden = false;
  }
}
let ultimo = 0;
function paso(now){
  requestAnimationFrame(paso);
  if (now - ultimo < 66) return; ultimo = now;
  const t = now - t0;
  leerEstado(t);
  escena(t);
}
if (reduce) { setInterval(() => { const t = performance.now() - t0; leerEstado(t); escena(t); }, 500); }
else requestAnimationFrame(paso);
})();
</script></body></html>
"""


def mostrar(modo="vivo", total=0, segundos_estimados=60, colores_finales=None, subtitulo="", alto=400):
    html = (_HTML.replace("__MODO__", json.dumps(modo))
                 .replace("__TOTAL__", str(int(total)))
                 .replace("__SEG__", str(float(segundos_estimados)))
                 .replace("__COLORES__", json.dumps(colores_finales or []))
                 .replace("__SUB__", json.dumps(subtitulo)))
    components.html(html, height=alto)


def estado_oculto(fraccion, colores, terminado=False):
    """Texto oculto que la escena lee desde la pagina para sincronizarse."""
    return (f'<div class="ideam-estado">p={fraccion:.3f};c={",".join(colores)};f={1 if terminado else 0}</div>')
