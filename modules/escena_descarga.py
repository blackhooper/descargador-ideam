import json
import streamlit.components.v1 as components

# ===========================================================================
# ESCENA PIXEL ART DE LA DESCARGA: el tornado
# ---------------------------------------------------------------------------
# Un tornado va al archivo del IDEAM, lo sacude, se lleva los documentos y
# los suelta en nuestro escritorio (un computador de los 2000). Cada estacion
# guardada cae como una carpeta del color de su calidad.
#
# El avance real lo lee de un elemento oculto de la pagina (.ideam-estado)
# que actualiza procesar_descargas: "p=0.42;c=#0ca30c,#fab219;f=0".
# Si no lo encuentra (por ejemplo en otro navegador), avanza por tiempo.
# ===========================================================================

_HTML = r"""
<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Silkscreen&display=swap">
<style>
html,body{margin:0;height:100%;background:#1a2440;overflow:hidden}
canvas{width:100%;height:100%;display:block;image-rendering:pixelated;object-fit:contain;border-radius:12px}
#banner{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none}
#banner div{font-family:"Silkscreen",monospace;color:#FFF6C8;font-size:clamp(18px,4.5vw,38px);text-shadow:3px 3px 0 #7A2E8F,-1px -1px 0 #16213A;text-align:center;line-height:1.15;background:rgba(22,33,58,.4);padding:10px 18px;border-radius:6px}
#banner small{display:block;font-size:.45em;color:#DDF7FF;margin-top:6px}
[hidden]{display:none!important}
</style></head><body>
<canvas id="scene" width="256" height="144"></canvas>
<div id="banner" hidden><div>¡BOTÍN ASEGURADO!<small id="sub"></small></div></div>
<script>
(() => {
const MODO = __MODO__, TOTAL = __TOTAL__, EST_SEG = __SEG__, COLORES_FIN = __COLORES__, SUB = __SUB__;
const sc = document.getElementById("scene"), s = sc.getContext("2d");
const PW = 256, PH = 144, SUELO = 122, EDIF_X = 46, MESA_X = 212, VIAJE = 2900;
const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
let p = 0, colores = [], fin = MODO === "final", tFin = fin ? -1e9 : 0, xFin = MESA_X, vistoEstado = false;
let volando = [], llevados = [], cayendo = [], carpetas = [];
const t0 = performance.now();
if (fin) { colores = COLORES_FIN.slice(); p = 1; }

function rect(x, y, w, h, c){ s.fillStyle = c; s.fillRect(Math.round(x), Math.round(y), w, h); }
const ease = q => q < .5 ? 2 * q * q : 1 - (-2 * q + 2) ** 2 / 2;
const lerp = (a, b, q) => a + (b - a) * q;

function leerEstado(t){
  if (fin) return;
  try {
    const el = window.parent.document.querySelector(".ideam-estado");
    if (el) {
      vistoEstado = true;
      const d = Object.fromEntries(el.textContent.trim().split(";").map(x => x.split("=")));
      p = Math.max(0, Math.min(1, parseFloat(d.p) || 0));
      colores = d.c ? d.c.split(",").filter(Boolean) : [];
      if (d.f === "1") { fin = true; tFin = t; xFin = tornadoEn(t).x; }
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
function tornadoEn(t){
  if (fin) return {x: lerp(xFin, 300, Math.min(1, (t - tFin) / 1400)), fase: "sale"};
  const k = Math.floor(t / VIAJE), q = (t % VIAJE) / VIAJE, desde = k === 0 ? 290 : MESA_X;
  if (q < .32) return {x: lerp(desde, EDIF_X + 4, ease(q / .32)), fase: "va"};
  if (q < .52) return {x: EDIF_X + 4 + Math.sin(t / 120) * 7, fase: "arrasa"};
  if (q < .82) return {x: lerp(EDIF_X + 4, MESA_X, ease((q - .52) / .30)), fase: "trae"};
  return {x: MESA_X + Math.sin(t / 150) * 4, fase: "suelta"};
}
function cielo(tormenta){
  const b = tormenta ? ["#141229","#221D45","#322A5F","#473B7A","#5E4E92"] : ["#2B2F77","#4B3D9A","#7A55B8","#C77DC7","#F2A7B8"];
  b.forEach((c, i) => rect(0, i * 18, PW, 18, c));
  for (let i = 1; i < b.length; i++) for (let x = 0; x < PW; x += 2) rect(x + (i % 2), i * 18 - 1, 1, 1, b[i]);
}
function paisaje(tormenta){
  for (let x = 0; x < PW; x++){
    const y1 = 70 + Math.round(10 * Math.sin(x * .045) + 6 * Math.sin(x * .13 + 1)); rect(x, y1, 1, PH - y1, tormenta ? "#2A2758" : "#3D3A7E");
    const y2 = 88 + Math.round(8 * Math.sin(x * .03 + 2) + 4 * Math.sin(x * .09)); rect(x, y2, 1, PH - y2, tormenta ? "#1D2346" : "#27305E");
  }
  rect(0, SUELO, PW, PH - SUELO, "#1A2140");
  for (let x = 0; x < PW; x += 4) rect(x, SUELO, 2, 1, "#2E3A6B");
}
function edificio(t, sacudida){
  const dx = sacudida ? Math.round(Math.sin(t / 23) * 1.6) : 0, tilt = sacudida ? Math.round(Math.sin(t / 37) * 2) : 0, x0 = 14 + dx;
  rect(x0, 70, 62, 52, "#D9DFEF"); rect(x0, 70, 62, 4, "#9AA6C9"); rect(x0 - 4, 66, 70, 5, "#6E7BA8");
  rect(x0 + 12, 56 + tilt, 38, 11, "#FAB219"); rect(x0 + 12, 66 + tilt, 38, 1, "#C98A00");
  s.fillStyle = "#16213A"; s.font = "8px Silkscreen, monospace"; s.textBaseline = "top"; s.fillText("IDEAM", x0 + 17, 57 + tilt);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++){
    const x = x0 + 6 + c * 13, y = 78 + r * 14, abierta = sacudida && ((Math.floor(t / 140) + r + c * 2) % 3 === 0);
    rect(x, y, 10, 10, "#8A6A3E"); rect(x + 1, y + 1, 8, 8, abierta ? "#2B1D10" : "#B08850"); rect(x + 4, y + 4, 2, 1, "#E8D3A8");
    if (abierta) rect(x + 1 + (Math.floor(t / 90) % 3), y - 2, 6, 4, ["#FAB219","#5AA2F5","#0CA30C","#EC835A"][(r + c) % 4]);
  }
  rect(x0 + 26, 110, 10, 12, "#4A3A28");
}
function escritorio(){
  rect(184, 103, 66, 4, "#A06A3A"); rect(184, 103, 66, 1, "#C98F58"); rect(188, 107, 3, 15, "#6B4424"); rect(243, 107, 3, 15, "#6B4424");
  rect(188, 80, 30, 22, "#D8D0B8"); rect(188, 80, 30, 1, "#EFE9D6"); rect(191, 83, 24, 15, "#0E1A12");
  s.fillStyle = "#8CFF9E"; s.font = "8px Silkscreen, monospace"; s.textBaseline = "top";
  const txt = Math.round(p * 100) + "%"; s.fillText(txt, 203 - s.measureText(txt).width / 2, 86);
  rect(199, 102, 8, 1, "#B9B09A"); rect(190, 101, 26, 2, "#C7BEA5");
  while (carpetas.length < colores.length) carpetas.push({c: colores[carpetas.length], y: fin && MODO === "final" ? 999 : 60});
  const visibles = carpetas.slice(-20);
  visibles.forEach((cp, i) => {
    const col = Math.floor(i / 10), fila = i % 10, x = 222 + col * 13, y = 99 - fila * 4;
    cp.y = (reduce || cp.y === 999) ? y : Math.min(y, cp.y + 5);
    rect(x, cp.y, 11, 3, cp.c); rect(x, cp.y, 4, 1, "#FFFFFF"); rect(x, cp.y + 3, 11, 1, "rgba(0,0,0,.35)");
  });
}
function embudo(cx, t, fuerza){
  const tope = 16, alto = SUELO - tope;
  for (let r = 0; r < alto; r += 2){
    const f = r / alto, w = Math.max(2, (5 + Math.pow(1 - f, 1.6) * 40) * fuerza);
    const off = Math.sin(t / 130 + r * .19) * (2 + f * 5) + f * Math.sin(t / 380) * 6;
    rect(cx + off - w / 2, tope + r, w, 2, ["#D6D1F0","#A9A2D4","#7C75B0"][(Math.floor(r / 2) + Math.floor(t / 80)) % 3]);
    if (r % 4 === 0) rect(cx + off - w / 2 - 1, tope + r + 1, 1, 1, "#A9A2D4");
  }
  for (let k = 0; k < 7; k++){ const a = t / 160 + k * .9; rect(cx + Math.cos(a) * (8 + k), SUELO - 2 - (k % 3), 2, 1, "#8A7A62"); }
}
function papel(x, y, c){ rect(x, y, 3, 4, "#FFFFFF"); rect(x, y, 3, 1, c); }
function escena(t){
  const tor = (!fin || t - tFin < 1400) ? tornadoEn(t) : null, tormenta = tor !== null;
  cielo(tormenta);
  if (!tormenta){
    for (let k = 0; k < 18; k++){ const x = (k * 53) % PW, y = (k * 29) % 34; if ((Math.floor(t / 400) + k) % 5) rect(x, y, 1, 1, "#FFF6C8"); }
    for (let k = 0; k < 8; k++){ const a = k / 8 * 6.283 + t / 900; rect(236 + Math.cos(a) * 11, 22 + Math.sin(a) * 11, 2, 2, "#FFE27A"); }
    rect(230, 16, 12, 12, "#FFD23F"); rect(232, 14, 8, 16, "#FFD23F"); rect(228, 18, 16, 8, "#FFD23F");
  }
  paisaje(tormenta);
  edificio(t, tor && tor.fase === "arrasa");
  escritorio();
  if (tor && tor.fase === "arrasa" && !reduce)
    for (let k = 0; k < 3; k++) volando.push({x: 22 + Math.random() * 50, y: 78 + Math.random() * 36, q: 0, c: ["#FAB219","#5AA2F5","#0CA30C","#EC835A"][Math.floor(Math.random() * 4)]});
  const fuerza = !tor ? 0 : tor.fase === "sale" ? Math.max(.1, 1 - (t - tFin) / 1400) : 1;
  llevados.forEach(q => { q.a += .22; });
  const orbita = (q, cx) => [cx + Math.cos(q.a) * (6 + (SUELO - q.y) * .28), q.y + Math.sin(q.a * 2) * 2];
  if (tor) llevados.filter(q => Math.sin(q.a) < 0).forEach(q => { const [x, y] = orbita(q, tor.x); papel(x, y, q.c); });
  if (tor) embudo(tor.x, t, fuerza);
  if (tor) llevados.filter(q => Math.sin(q.a) >= 0).forEach(q => { const [x, y] = orbita(q, tor.x); papel(x, y, q.c); });
  volando.forEach(v => { v.q += .09; const x = lerp(v.x, tor ? tor.x : v.x, v.q), y = lerp(v.y, v.y - 30, v.q) - Math.sin(v.q * 3.14) * 10; papel(x, y, v.c); if (v.q >= 1 && llevados.length < 46) llevados.push({a: Math.random() * 6.28, y: 30 + Math.random() * 70, c: v.c}); });
  volando = volando.filter(v => v.q < 1);
  if (tor && (tor.fase === "suelta" || tor.fase === "sale") && llevados.length)
    llevados.splice(0, 3).forEach(q => { const [x, y] = orbita(q, tor.x); cayendo.push({x, y, c: q.c, f: Math.random() * 6}); });
  cayendo.forEach(q => { q.y += 1.6; q.f += .3; q.x += Math.sin(q.f) * .9 + (220 - q.x) * .03; papel(q.x, q.y, q.c); });
  cayendo = cayendo.filter(q => q.y < 100);
  if (fin && (MODO === "final" || t - tFin > 1500)) {
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
if (reduce) { setInterval(() => { const t = performance.now() - t0; leerEstado(t); escena(fin ? t + 99999 : 700); }, 500); }
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
