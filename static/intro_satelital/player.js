// Reproductor de la intro satelital (del mapa 2D al despliegue 3D).
// Se carga como modulo en la pagina de Streamlit (ver terreno.INTRO_SATELITAL) y deja window.__y2kSat.reproducir().
// Dibuja la escena 3D (satellite-scene.js) y encima la interfaz (HUD), todo en una capa que tapa el visor 3D mientras
// el relieve real se carga por detras. Al terminar hace el "encendido" tipo monitor y libera la memoria grafica.
import { satelliteImage } from './satimg.js';
import { crearMosaico, cajaDe } from './mosaico.js';

const CY = '#35f0ff', DIM = '#7fb3c4', WH = '#eafcff', OR = '#ff8a2a';
const mono = "ui-monospace, 'Cascadia Mono', Consolas, monospace";
const sans = "Figtree, system-ui, 'Segoe UI', sans-serif";

const cl = v => Math.min(1, Math.max(0, v));
const seg = (t, a, b) => cl((t - a) / (b - a));
const o3 = t => 1 - Math.pow(1 - t, 3);
const ease = v => (v < 0.5 ? 4 * v * v * v : 1 - Math.pow(-2 * v + 2, 3) / 2);

// ---- almacenamiento de los ajustes temporales ----
const guardado = {
  leer(k, def) { try { const v = localStorage.getItem('y2k_sat_' + k); return v == null ? def : JSON.parse(v); } catch (e) { return def; } },
  poner(k, v) { try { localStorage.setItem('y2k_sat_' + k, JSON.stringify(v)); } catch (e) { /* sin almacenamiento */ } },
};

// ---- constructor minimo de SVG en texto (reemplaza React.createElement del prototipo) ----
class Raw { constructor(s) { this.s = s; } }
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const ATTR = {
  strokeWidth: 'stroke-width', strokeOpacity: 'stroke-opacity', fillOpacity: 'fill-opacity', fontFamily: 'font-family',
  fontSize: 'font-size', fontWeight: 'font-weight', letterSpacing: 'letter-spacing', textAnchor: 'text-anchor',
  strokeDasharray: 'stroke-dasharray',
};
function h(tag, props, ...kids) {
  let a = '';
  for (const k in (props || {})) {
    const v = props[k];
    if (v == null || v === false || k === 'key') continue;
    a += ' ' + (ATTR[k] || k) + '="' + esc(v).replace(/"/g, '&quot;') + '"';
  }
  const inner = kids.flat(Infinity).map(x => (x == null || x === false ? '' : x instanceof Raw ? x.s : esc(x))).join('');
  return new Raw('<' + tag + a + '>' + inner + '</' + tag + '>');
}

// ---- interfaz (HUD) en coordenadas de 1920x1080 ----
function hudSvg(H, T, caja, dots) {
  const cx = 960, cy = 540;
  const tx = (x, y, s, p) => h('text', Object.assign({ x, y, fill: CY, fontFamily: mono, fontSize: 20, letterSpacing: 1.5 }, p), s);
  const ln = (x1, y1, x2, y2, p) => h('line', Object.assign({ x1, y1, x2, y2, stroke: CY, strokeWidth: 1.5 }, p));
  const corners = (x, y, w, hh, L, p) => h('path', Object.assign({ d: `M${x} ${y + L}V${y}H${x + L}M${x + w - L} ${y}H${x + w}V${y + L}M${x + w} ${y + hh - L}V${y + hh}H${x + w - L}M${x + L} ${y + hh}H${x}V${y + hh - L}`, fill: 'none', stroke: CY, strokeWidth: 2 }, p));
  const kids = [], intro = [];

  if (H.tz < 0.35) {
    const fade = cl(H.tl / 0.45), k = ease(cl((H.tl - 0.25) / 0.6)), out = 1 - cl(H.tz / 0.3);
    const bx = 960 + (H.box.x - 960) * k, by = 540 + (H.box.y - 540) * k, bw = caja.bw + (36 - caja.bw) * k, bh = caja.bh + (24 - caja.bh) * k;
    const glow = fade, stroke = glow > 0.5 ? CY : '#f6d84a';
    // las estaciones desaparecen en cuanto se resalta el cuadro (despues las dispara el satelite)
    const dotsOp = 1 - cl(H.tl / 0.3);
    intro.push(h('g', { opacity: out },
      h('rect', { x: bx - bw / 2, y: by - bh / 2, width: bw, height: bh, fill: 'none', stroke: CY, strokeOpacity: 0.35 * glow, strokeWidth: 10 }),
      h('rect', { x: bx - bw / 2, y: by - bh / 2, width: bw, height: bh, fill: glow > 0.5 ? 'rgba(53,240,255,0.08)' : 'rgba(246,216,74,0.06)', stroke, strokeWidth: 2.5, strokeDasharray: k > 0.7 ? '4 3' : '12 8' }),
      dotsOp > 0.01 ? h('g', { opacity: dotsOp },
        dots.map(d => h('circle', { cx: bx - bw / 2 + d[0] * bw, cy: by - bh / 2 + d[1] * bh, r: Math.max(1.6, (dots.length > 60 ? 4 : 7) * (1 - k)), fill: d[2] ? '#3fbf62' : '#f6a33b', stroke: '#0a1a10', strokeWidth: 1.5 * (1 - k) }))) : null
    ));
    if (H.head) {
      intro.push(h('g', null,
        h('line', { x1: H.box.x, y1: H.box.y, x2: H.head.x, y2: H.head.y, stroke: CY, strokeWidth: 9, strokeOpacity: 0.3 }),
        h('line', { x1: H.box.x, y1: H.box.y, x2: H.head.x, y2: H.head.y, stroke: '#f2feff', strokeWidth: 2.4 }),
        h('circle', { cx: H.head.x, cy: H.head.y, r: 14, fill: CY, fillOpacity: 0.35 }),
        h('circle', { cx: H.head.x, cy: H.head.y, r: 5, fill: '#ffffff' }),
        h('circle', { cx: H.box.x, cy: H.box.y, r: 9, fill: CY, fillOpacity: 0.5 })
      ));
    }
  }

  if (H.map > 0.001) {
    const sc = Math.max(40, Math.min(600, 500 / H.kmPerPx));
    kids.push(h('g', { opacity: H.map },
      h('rect', { x: 28, y: 28, width: 1864, height: 1024, fill: 'none', stroke: CY, strokeOpacity: 0.22 }),
      corners(28, 28, 1864, 1024, 36, { strokeOpacity: 0.7 }),
      tx(72, 98, 'MAPA OPERATIVO', { fontFamily: sans, fontWeight: 600, fontSize: 30, fill: WH, letterSpacing: 4 }),
      tx(72, 132, 'COLOMBIA · CAPA DE LÍMITES', { fill: DIM, fontSize: 18, letterSpacing: 2 }),
      tx(1848, 98, 'WGS84 · EPSG:4326', { textAnchor: 'end', fill: DIM, fontSize: 18 }),
      tx(1848, 132, 'NIVEL 6', { textAnchor: 'end', fill: DIM, fontSize: 18 }),
      h('rect', { x: 1800, y: 470, width: 48, height: 48, rx: 8, fill: 'rgba(4,14,26,0.75)', stroke: CY, strokeOpacity: 0.4 }),
      h('rect', { x: 1800, y: 526, width: 48, height: 48, rx: 8, fill: 'rgba(4,14,26,0.75)', stroke: CY, strokeOpacity: 0.4 }),
      tx(1824, 503, '+', { textAnchor: 'middle', fontSize: 26, fill: WH }),
      tx(1824, 559, '−', { textAnchor: 'middle', fontSize: 26, fill: WH }),
      h('g', { opacity: Math.min(1, Math.max(0, (H.tr + 0.2) / 0.6)) },
        ln(1848 - sc, 1004, 1848, 1004, { strokeWidth: 2 }), ln(1848 - sc, 994, 1848 - sc, 1010, { strokeWidth: 2 }), ln(1848, 994, 1848, 1010, { strokeWidth: 2 }),
        tx(1848, 982, '500 km', { textAnchor: 'end', fontSize: 18, fill: '#bfefff' }))
    ));
  }

  if (H.colTag > 0.001 && H.g.vis) {
    const g = H.g, w = 180 * Math.min(1, H.colTag * 1.6);
    kids.push(h('g', { opacity: H.colTag },
      h('circle', { cx: g.x, cy: g.y, r: 6, fill: CY }),
      h('path', { d: `M${g.x} ${g.y}L${g.x + 80} ${g.y - 80}H${g.x + 80 + w}`, fill: 'none', stroke: CY, strokeWidth: 1.5 }),
      tx(g.x + 92, g.y - 94, 'COLOMBIA', { fontFamily: sans, fontWeight: 600, fontSize: 28, fill: WH, letterSpacing: 4 }),
      tx(g.x + 92, g.y - 52, 'ENLACE ASCENDENTE', { fontSize: 17, fill: CY, letterSpacing: 2 })
    ));
  }

  if (H.satTag > 0.001 && H.s.vis) {
    const s = H.s, L = 34;
    kids.push(h('g', { opacity: H.satTag },
      corners(s.x - L, s.y - L, L * 2, L * 2, 10, { strokeOpacity: 0.9 }),
      tx(s.x + L + 12, s.y - L + 14, 'SAT-07', { fontFamily: sans, fontWeight: 600, fontSize: 20, fill: WH, letterSpacing: 3 }),
      tx(s.x + L + 12, s.y - L + 40, 'ÓRBITA MEO', { fontSize: 16, fill: DIM, letterSpacing: 2 })
    ));
  }
  if (H.satInfo > 0.001) {
    kids.push(h('g', { opacity: H.satInfo },
      tx(72, 98, 'SAT-07 · ÓRBITA MEO', { fontFamily: sans, fontWeight: 600, fontSize: 26, fill: WH, letterSpacing: 3 }),
      tx(72, 134, 'DATOS RECIBIDOS DESDE COLOMBIA', { fontSize: 18, fill: CY, letterSpacing: 2 })
    ));
  }

  if (H.can > 0.001) {
    const names = ['COMPUERTAS', 'BRAZOS', 'CAÑONES', 'DISIPADORES'], pct = Math.round(H.charge * 100);
    kids.push(h('g', { opacity: H.can },
      tx(72, 98, 'SECUENCIA DE DESPLIEGUE', { fontFamily: sans, fontWeight: 600, fontSize: 26, fill: WH, letterSpacing: 3 }),
      names.map((n, i) => {
        const v = H.steps[i], ok = v >= 1;
        return h('g', null,
          tx(72, 146 + i * 36, n, { fontSize: 19, fill: ok ? '#bfefff' : DIM }),
          tx(380, 146 + i * 36, ok ? 'OK' : v > 0 ? '···' : '—', { textAnchor: 'end', fontSize: 19, fill: ok ? CY : DIM })
        );
      }),
      tx(72, 902, 'CARGA DE ENERGÍA', { fontSize: 18, fill: DIM, letterSpacing: 2 }),
      tx(72, 950, 'ÁREA', { fontSize: 19, fill: WH }),
      h('rect', { x: 196, y: 936, width: 360, height: 14, fill: 'none', stroke: CY, strokeOpacity: 0.45 }),
      h('rect', { x: 196, y: 936, width: 360 * H.charge, height: 14, fill: CY }),
      tx(640, 950, pct + '%', { textAnchor: 'end', fontSize: 19, fill: CY }),
      tx(72, 994, 'BUFFER', { fontSize: 19, fill: WH }),
      h('rect', { x: 196, y: 980, width: 360, height: 14, fill: 'none', stroke: OR, strokeOpacity: 0.5 }),
      h('rect', { x: 196, y: 980, width: 360 * H.charge, height: 14, fill: OR }),
      tx(640, 994, pct + '%', { textAnchor: 'end', fontSize: 19, fill: OR })
    ));
  }

  if (H.pov > 0.001) {
    const b = H.boot, lk = H.lock, L = 600 - 290 * (1 - Math.pow(1 - lk, 3));
    const sc = 1 + 0.08 * H.dive * H.speed, blink = lk < 1 && Math.floor(T * 14) % 2 === 0;
    const alt = Math.round(H.altKm).toLocaleString('es-CO');
    const rot = (T * 28) % 360, ladder = [];
    const off = (Math.log(H.altKm) * 120) % 40;
    for (let i = 0; i < 13; i++) { const y = 300 + i * 40 + off; ladder.push(ln(1830, y, i % 2 ? 1846 : 1856, y, { strokeOpacity: 0.6 })); }
    const tape = [];
    const toff = (T * 22) % 30;
    for (let i = 0; i < 21; i++) { const x = 660 + i * 30 - toff; tape.push(ln(x, 128, x, i % 3 ? 138 : 146, { strokeOpacity: 0.55 })); }
    kids.push(h('g', { opacity: H.pov * (1 - 0.3 * H.speed), transform: `translate(${cx} ${cy}) scale(${sc}) translate(${-cx} ${-cy})` },
      corners(90, 90, 1740, 900, 70, { strokeWidth: 2.5, opacity: b }),
      h('g', { opacity: Math.min(1, b * 1.4) },
        tape, h('path', { d: 'M954 156L960 148L966 156', fill: CY }),
        tx(cx, 112, 'NADIR · RUMBO 000°', { textAnchor: 'middle', fontSize: 17, fill: DIM, letterSpacing: 3 })
      ),
      h('g', { transform: `translate(${cx} ${cy}) scale(${0.6 + 0.4 * b})`, opacity: b },
        h('circle', { r: 46, fill: 'none', stroke: CY, strokeWidth: 1.5 }),
        h('circle', { r: 2.5, fill: WH }),
        ln(-130, 0, -62, 0), ln(62, 0, 130, 0), ln(0, -130, 0, -62), ln(0, 62, 0, 130),
        h('circle', { r: 150, fill: 'none', stroke: CY, strokeOpacity: 0.55, strokeDasharray: '3 11', transform: `rotate(${rot})` }),
        h('path', { d: 'M -198 -40 A 202 202 0 0 1 -150 -136 M 198 40 A 202 202 0 0 1 150 136', fill: 'none', stroke: CY, strokeWidth: 2.5, transform: `rotate(${-rot * 0.6})` })
      ),
      lk > 0 ? corners(cx - L / 2, cy - L / 2, L, L, 34, { stroke: lk >= 1 ? OR : CY, strokeWidth: 3, opacity: blink ? 0.35 : 1 }) : null,
      lk >= 1 ? h('g', null,
        tx(cx + L / 2 + 24, cy - L / 2 + 22, 'OBJETIVO FIJADO', { fontSize: 20, fill: OR, letterSpacing: 3 }),
        tx(cx + L / 2 + 24, cy - L / 2 + 54, 'COLOMBIA', { fontFamily: sans, fontWeight: 600, fontSize: 22, fill: WH, letterSpacing: 2 })
      ) : null,
      h('g', { opacity: b },
        tx(130, 470, H.dive > 0 ? 'VELOCIDAD' : 'ZOOM ÓPTICO', { fontSize: 18, fill: DIM, letterSpacing: 2 }),
        tx(130, 530, H.dive > 0 ? Math.round(H.vKmS).toLocaleString('es-CO') : '×' + H.zoomX.toFixed(1), { fontFamily: sans, fontWeight: 600, fontSize: 56, fill: H.dive > 0 ? OR : CY }),
        tx(130, 566, H.dive > 0 ? 'KM/S' : 'FOV ' + H.fov.toFixed(2) + '°', { fontSize: 18, fill: DIM }),
        tx(1800, 470, 'ALTITUD', { textAnchor: 'end', fontSize: 18, fill: DIM, letterSpacing: 2 }),
        tx(1800, 530, alt, { textAnchor: 'end', fontFamily: sans, fontWeight: 600, fontSize: 56, fill: H.dive > 0 ? OR : CY }),
        tx(1800, 566, 'KM', { textAnchor: 'end', fontSize: 18, fill: DIM }),
        ladder,
        tx(130, 150, '● ENLACE ACTIVO', { fontSize: 18, fill: Math.floor(T * 3) % 2 ? CY : WH, letterSpacing: 2 }),
        tx(130, 182, 'ÁREA + BUFFER · 100%', { fontSize: 18, fill: OR, letterSpacing: 2 }),
        H.capOut > 0 ? tx(130, 214, 'ESTACIONES LANZADAS ' + H.capOut + '/' + H.capN, { fontSize: 18, fill: '#3fff7a', letterSpacing: 2 }) : null,
        tx(1790, 150, 'SAT-07 · ÓPTICA PRINCIPAL', { textAnchor: 'end', fontSize: 18, fill: DIM, letterSpacing: 2 })
      ),
      H.dive > 0 ? h('g', { opacity: H.dive * (Math.floor(T * 10) % 2 ? 1 : 0.55) },
        tx(cx, 900, 'DESCENSO', { textAnchor: 'middle', fontFamily: sans, fontWeight: 600, fontSize: 34, fill: OR, letterSpacing: 10 })
      ) : null
    ));
  }
  return h('g', null, intro, kids).s;
}

// ---- panel temporal de ajustes ----
const AJUSTES = [
  ['panAmt', 'Giro de mirada hacia tu cuadro (0 = nada)', 0, 1.5, 0.05],
  ['panStart', 'Giro: inicio (s dentro del zoom óptico)', 0, 1.2, 0.05],
  ['panEnd', 'Giro: fin (s dentro del zoom óptico)', 0.1, 1.2, 0.05],
  ['diveShift', 'Traslado de cámara sobre el cuadro (s)', 0.1, 1.5, 0.05],
  ['descenso', 'Duración del descenso (s)', 0.3, 2.0, 0.05],
  ['preDark', 'Oscuridad durante el zoom óptico', 0, 1, 0.05],
  ['fadeStart', 'Negro final: inicio (s del descenso)', 0, 1.5, 0.05],
  ['fadeDur', 'Negro final: duración (s)', 0.05, 1.2, 0.05],
  ['blackMax', 'Negro máximo antes del encendido', 0, 1, 0.05],
  ['reveal', 'Encendido tipo monitor (s)', 0.2, 2, 0.05],
  ['resScale', 'Resolución interna (aplica en la próxima repetición)', 0.4, 1, 0.05],
];

function armarPanel(R, S, TUNE, mod) {
  const caja = document.createElement('div');
  caja.style.cssText = 'position:absolute;top:8px;left:8px;z-index:40;font:12px/1.3 ' + sans + ';color:#d8f6ff;max-width:300px;pointer-events:auto';
  const filas = AJUSTES.map(([k, et, mn, mx, st]) =>
    `<label style="display:block;margin:5px 0">${et}: <b data-v="${k}"></b><input type="range" data-k="${k}" min="${mn}" max="${mx}" step="${st}" style="width:100%"></label>`).join('');
  caja.innerHTML =
    '<button data-a="abrir" style="all:unset;cursor:pointer;background:rgba(4,14,26,.82);border:1px solid #35f0ff66;border-radius:8px;padding:5px 10px;font-weight:600">⚙ Ajustes (temporal)</button>' +
    '<div data-panel style="display:none;margin-top:6px;background:rgba(4,14,26,.92);border:1px solid #35f0ff55;border-radius:10px;padding:10px;max-height:70vh;overflow:auto">' +
    '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px">' +
    '<button data-a="play">⏸ Pausa</button><button data-a="saltar">⏭ Saltar</button>' +
    '<button data-a="v025">0,25×</button><button data-a="v05">0,5×</button><button data-a="v1">1×</button></div>' +
    '<label style="display:block">Tiempo: <b data-t></b><input type="range" data-a="scrub" min="0" max="20" step="0.01" style="width:100%"></label>' +
    '<label style="display:block;margin:6px 0"><input type="checkbox" data-c="holdEnd"> Detenerse al final (antes del encendido)</label>' +
    '<label style="display:block;margin:6px 0"><input type="checkbox" data-c="liviana"> Calidad liviana (sin brillo; próxima repetición)</label>' +
    filas +
    '<div style="margin:6px 0">Cuadro de prueba (lon, lat): <input data-l="lon" type="number" step="0.1" style="width:70px"> <input data-l="lat" type="number" step="0.1" style="width:70px"> <button data-a="caja">Aplicar</button></div>' +
    '<div style="display:flex;gap:6px;flex-wrap:wrap"><button data-a="copiar">📋 Copiar valores</button><button data-a="reset">Restablecer</button></div>' +
    '<pre data-out style="white-space:pre-wrap;margin:6px 0 0;font:11px ' + mono + ';display:none"></pre></div>';
  caja.querySelectorAll('button:not([data-a="abrir"])').forEach(b => { b.style.cssText = 'all:unset;cursor:pointer;background:#10304a;border:1px solid #35f0ff55;border-radius:6px;padding:3px 8px'; });
  const panel = caja.querySelector('[data-panel]');
  const refrescar = () => {
    AJUSTES.forEach(([k]) => { caja.querySelector(`[data-k="${k}"]`).value = TUNE[k]; caja.querySelector(`[data-v="${k}"]`).textContent = Number(TUNE[k]).toFixed(2); });
    caja.querySelector('[data-c="holdEnd"]').checked = !!S.holdEnd;
    caja.querySelector('[data-c="liviana"]').checked = !!S.liviana;
    caja.querySelector('[data-l="lon"]').value = S.lon; caja.querySelector('[data-l="lat"]').value = S.lat;
  };
  refrescar();
  const valores = () => JSON.stringify(Object.assign({}, Object.fromEntries(AJUSTES.map(([k]) => [k, +Number(TUNE[k]).toFixed(3)])), { holdEnd: !!S.holdEnd, liviana: !!S.liviana }), null, 1);
  caja.addEventListener('input', ev => {
    const e = ev.target;
    if (e.dataset.k) { TUNE[e.dataset.k] = parseFloat(e.value); guardado.poner('tune', Object.fromEntries(AJUSTES.map(([k]) => [k, TUNE[k]]))); caja.querySelector(`[data-v="${e.dataset.k}"]`).textContent = Number(e.value).toFixed(2); }
    else if (e.dataset.a === 'scrub') { S.T = parseFloat(e.value); S.playing = false; caja.querySelector('[data-a="play"]').textContent = '▶ Seguir'; }
    else if (e.dataset.c) { S[e.dataset.c] = e.checked; guardado.poner(e.dataset.c, e.checked); }
  });
  caja.addEventListener('click', ev => {
    const a = ev.target && ev.target.dataset && ev.target.dataset.a;
    if (!a) return;
    if (a === 'abrir') panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    else if (a === 'play') { if (S.fase === 'play' && S.T >= S.Tend && S.holdEnd) S.holdEnd = false; S.playing = !S.playing; ev.target.textContent = S.playing ? '⏸ Pausa' : '▶ Seguir'; }
    else if (a === 'saltar') S.saltar = true;
    else if (a === 'v025') S.speed = 0.25; else if (a === 'v05') S.speed = 0.5; else if (a === 'v1') S.speed = 1;
    else if (a === 'caja') { S.lon = parseFloat(caja.querySelector('[data-l="lon"]').value); S.lat = parseFloat(caja.querySelector('[data-l="lat"]').value); S.api && S.api.setBox(S.lon, S.lat); }
    else if (a === 'reset') { Object.assign(TUNE, S.defaults); guardado.poner('tune', null); refrescar(); }
    else if (a === 'copiar') { const t = valores(), o = caja.querySelector('[data-out]'); o.style.display = 'block'; o.textContent = t; try { navigator.clipboard.writeText(t); } catch (e) { /* se puede copiar a mano */ } }
  });
  R.ov.appendChild(caja);
  return { actualizar(T, Tend) { const t = caja.querySelector('[data-t]'); if (t) t.textContent = T.toFixed(2) + ' / ' + Tend.toFixed(2) + ' s'; const sc = caja.querySelector('[data-a="scrub"]'); if (sc && document.activeElement !== sc) { sc.max = Tend; sc.value = T; } } };
}

// ---- capa que tapa el visor 3D ----
function armarCapa(visor, geom) {
  const ov = document.createElement('div');
  ov.className = 'y2k-sat';
  ov.style.cssText = (geom ? 'position:absolute;left:0;width:100%;top:' + geom.top + 'px;height:' + geom.height + 'px;' : 'position:absolute;inset:0;') + 'z-index:30;background:#000;overflow:hidden;border-radius:12px;display:flex;align-items:center;justify-content:center;pointer-events:auto';
  const stage = document.createElement('div');
  stage.style.cssText = 'position:relative;width:100%;aspect-ratio:16/9;background:#000;overflow:hidden';
  const host = document.createElement('div'); host.style.cssText = 'position:absolute;inset:0';
  const img = document.createElement('img'); img.alt = '';
  img.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;object-fit:cover;display:none;pointer-events:none';
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 1920 1080'); svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  svg.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none';
  const capa = css => { const d = document.createElement('div'); d.style.cssText = 'position:absolute;inset:0;pointer-events:none;' + css; return d; };
  const scan = capa('opacity:0;background:repeating-linear-gradient(0deg,rgba(53,240,255,0.06) 0px,rgba(53,240,255,0.06) 1px,transparent 1px,transparent 4px)');
  const vig = capa('background:radial-gradient(ellipse at center,rgba(0,0,0,0) 55%,rgba(0,0,0,0.55) 100%)');
  const white = capa('background:#e9fdff;opacity:0');
  const black = capa('background:#000;opacity:1');
  const msg = document.createElement('div');
  msg.style.cssText = 'position:absolute;left:0;right:0;bottom:8%;text-align:center;color:#6f9fb0;font:500 14px ' + mono + ';letter-spacing:2px;pointer-events:none;z-index:2';
  stage.append(host, img, svg, scan, vig, white, black, msg);
  ov.appendChild(stage);
  // encendido tipo monitor (barras que se abren) y boton de saltar
  const barra = (pos) => { const d = document.createElement('div'); d.style.cssText = 'position:absolute;left:0;right:0;background:#000;display:none;' + pos + ':0;height:50%;z-index:10;pointer-events:none'; return d; };
  const arriba = barra('top'), abajo = barra('bottom');
  const linea = document.createElement('div');
  linea.style.cssText = 'position:absolute;top:calc(50% - 2px);height:4px;background:#effeff;box-shadow:0 0 18px 6px rgba(53,240,255,.8);display:none;z-index:11;pointer-events:none';
  const saltar = document.createElement('button');
  saltar.textContent = 'Saltar ⏭';
  saltar.style.cssText = 'all:unset;cursor:pointer;position:absolute;right:10px;bottom:10px;z-index:41;background:rgba(4,14,26,.7);color:#d8f6ff;border:1px solid #35f0ff55;border-radius:8px;padding:5px 12px;font:600 12px ' + sans;
  ov.append(arriba, abajo, linea, saltar);
  visor.appendChild(ov);
  const ajustar = () => {
    const w = ov.clientWidth, hh = ov.clientHeight, ancho = Math.min(w, hh * 16 / 9);
    stage.style.width = ancho + 'px'; stage.style.height = (ancho * 9 / 16) + 'px';
  };
  ajustar();
  const ro = new ResizeObserver(ajustar); ro.observe(ov);
  return { ov, stage, host, img, svg, scan, white, black, msg, arriba, abajo, linea, saltar,
    mover(v) { v.appendChild(ov); ov.style.top = ''; ov.style.left = ''; ov.style.width = ''; ov.style.height = ''; ov.style.inset = '0'; },
    cerrar() { ro.disconnect(); ov.remove(); } };
}

// ---- precalentamiento: se hace al confirmar la cuenca, antes de que el usuario pase a 3D ----
const cache = {};
function precache(o) {
  const k = (o.bbox || []).join(',');
  if (!cache[k]) {
    const claves = Object.keys(cache);
    if (claves.length > 3) delete cache[claves[0]];
    cache[k] = { mosaico: crearMosaico(o.bbox).catch(() => null) };
  }
  return cache[k];
}
const urlEscena = v => new URL('satellite-scene.js?v=' + (v || 1), import.meta.url).href;
let PRE = null;   // ultimos datos precalentados (cuenca confirmada)
async function precalentar(p) {
  if (!p || !p.bbox) return;
  PRE = p;
  const c = precache(p);
  const mod = await import(urlEscena(p.version));
  const espera = ms => new Promise(ok => setTimeout(ok, ms));
  // listo = mosaico armado (o fallido) y datos descargados; si algo tarda de mas, se da por listo igual (se reintenta al reproducir)
  await Promise.all([
    Promise.race([c.mosaico, espera(9000)]),
    Promise.race([mod.precargarDatos().catch(() => null), espera(15000)]),
  ]);
}

async function reproducir(o) {
  const w = window;
  if (w.__y2kSatActual) { try { w.__y2kSatActual.cancelar(); } catch (e) { /* ya terminada */ } }
  const visor = o.visor || o.host;
  if (o.clave) w.__y2kSatUltima = o.clave;   // el clic en 3D no vuelve a arrancar una intro temprana para esta cuenca
  visor.querySelectorAll('.y2k-sat').forEach(e => e.remove());
  const R = armarCapa(visor, o.geom);
  let vivo = true, raf = 0, api = null;
  const S = { T: 0, playing: true, speed: 1, fase: 'carga', saltar: false, Tend: 16.5, api: null,
    holdEnd: guardado.leer('holdEnd', false), liviana: guardado.leer('liviana', false), lon: o.lon, lat: o.lat, defaults: null };
  // la senal que espera el guion del visor 3D para empezar los lasers
  // Arranque temprano: la animacion empieza en el clic, sobre el mapa 2D, sin esperar al servidor (que tarda 2-3 s en
  // dibujar el visor 3D). Cuando el visor llega, el guion de esa corrida la "adopta": la mueve dentro del visor
  // y le pone el numero de turno. Si nadie la adopta en 20 s (el servidor decidio no hacer intro), se retira sola.
  const senal = () => { if (o.turno == null) { S.finPend = true; return; } w.__y2kIntroSatFin = o.turno; };
  const ctrl = {
    cancelar() { vivo = false; if (w.__y2kSatTemprano === ctrl) w.__y2kSatTemprano = null; limpiar(); },
    adoptar(v, P) {
      clearTimeout(S.reloj); o.turno = P.turno; R.mover(v);
      if (o.host && o.host.style) o.host.style.position = o.posPrevia || '';
      if (w.__y2kSatTemprano === ctrl) w.__y2kSatTemprano = null;
      if (S.finPend) senal();
    },
  };
  w.__y2kSatActual = ctrl;
  if (o.temprano) {
    w.__y2kSatTemprano = ctrl;
    S.reloj = setTimeout(() => { if (w.__y2kSatTemprano === ctrl) ctrl.cancelar(); }, 20000);
  }
  function limpiar() {
    cancelAnimationFrame(raf); clearTimeout(S.reloj);
    if (o.host && o.host.style && o.posPrevia != null) o.host.style.position = o.posPrevia;
    if (api) { try { api.destroy(); } catch (e) { /* ya liberada */ } api = null; S.api = null; }
    R.cerrar();
  }
  R.saltar.addEventListener('click', () => { S.saltar = true; });
  try {
    const mod = await import(urlEscena(o.version));
    const { TUNE, DUR } = mod;
    S.defaults = Object.assign({}, TUNE);
    const guardados = guardado.leer('tune', null);
    if (guardados) Object.assign(TUNE, guardados);
    mod.setLowPower(S.liviana);
    if (!vivo) return;
    // El cuadro se fija antes de crear la escena. La escena 3D se arma POR DETRAS mientras ya corre el primer plano
    // (imagen satelital + interfaz, que no necesitan WebGL): el usuario no ve ninguna pantalla de carga
    mod.setBoxLonLat(o.lon, o.lat);
    mod.getScene(R.host).then(a => { if (!vivo || S.fase === 'encendido') { a.destroy(); return; } api = a; S.api = a; })
      .catch(e => { console.error('escena', e); S.sinEscena = true; });
    const panel = o.panel ? armarPanel(R, S, TUNE, mod) : null;
    // cuadros clave (inicio de cada plano) y duracion total hasta el descenso
    const cue = {}; let acc = 0;
    for (const n of Object.keys(DUR)) { cue[n] = acc; acc += DUR[n]; }
    const KOVR = { 'Encendido': 1e4 };   // la animacion original seguia con una maqueta del 3D: aqui el 3D es el real
    const tick = () => { S.Tend = cue['Descenso'] + TUNE.descenso; };
    tick();
    // imagen del primer plano: mosaico real de la zona (ya precalentado) o, si no se pudo, un terreno distinto segun el lugar
    const b = o.bbox || [o.lon - 0.1, o.lat - 0.1, o.lon + 0.1, o.lat + 0.1];
    const caja = cajaDe(b);
    const dots = (o.estaciones || []).map(e => [(e[0] - b[0]) / (b[2] - b[0] || 1), (b[3] - e[1]) / (b[3] - b[1] || 1), e[2]])
      .filter(d => d[0] >= 0 && d[0] <= 1 && d[1] >= 0 && d[1] <= 1).slice(0, 250);
    let mos = null;
    try { mos = await Promise.race([precache({ bbox: b }).mosaico, new Promise(ok => setTimeout(() => ok(null), 3500))]); } catch (e) { mos = null; }
    if (!vivo) return;
    try { R.img.src = mos && mos.url ? mos.url : satelliteImage(960, Math.abs(Math.round(o.lon * 1000) * 31 + Math.round(o.lat * 1000) * 17) % 99991 + 7); } catch (e) { /* sin imagen de fondo */ }
    R.msg.style.display = 'none';
    // hasta que la escena este lista, el reloj se detiene justo antes de que empiece "Trazo laser" (ahi si hace falta WebGL)
    const TOPE = cue['Trazo láser'] - 0.001;
    S.fase = 'play';
    let ultimo = performance.now();
    let tr = 0;   // avance del encendido
    const dibujar = () => {
      const st = api ? api.render(S.T, KOVR) : mod.frame(S.T, KOVR);
      if (!st) return;
      const H = st.hud, t = st.t;
      const conImg = H.tl < 0.5;
      R.img.style.display = conImg ? 'block' : 'none';
      if (conImg) { R.img.style.opacity = 1 - cl(H.tl / 0.45); R.img.style.transform = 'scale(' + (1.25 - 0.05 * cl(H.tm / 1.2)) + ')'; }
      R.svg.innerHTML = hudSvg(H, S.T, caja, dots);
      R.scan.style.opacity = H.pov * 0.5;
      R.white.style.opacity = H.white;
      // oscuridad: entra desde negro al inicio y, al final, se hace de noche durante el descenso
      let fin = 0;
      if (t.tp >= 0) {
        if (t.td < 0) fin = TUNE.preDark * (t.to < 0 ? seg(t.tp, 1.05, 1.4) : 1);
        else fin = TUNE.preDark + (TUNE.blackMax - TUNE.preDark) * o3(seg(t.td, TUNE.fadeStart, TUNE.fadeStart + TUNE.fadeDur));
      }
      R.black.style.opacity = Math.max(1 - seg(t.tm, 0, 0.25), fin);
    };
    const empezarEncendido = () => {
      S.fase = 'encendido'; tr = 0;
      senal();
      // fuera la escena: libera la tarjeta grafica antes de que arranque el despliegue real
      if (api) { try { api.destroy(); } catch (e) { /* ya liberada */ } api = null; S.api = null; }
      R.stage.style.display = 'none'; R.ov.style.background = 'transparent';
      const q = [R.arriba, R.abajo]; q.forEach(b => { b.style.display = 'block'; });
      if (R.ov.querySelector('[data-panel]')) R.ov.querySelector('[data-panel]').style.display = 'none';
    };
    const bucle = now => {
      if (!vivo) return;
      if (!R.ov.isConnected) { vivo = false; senal(); limpiar(); return; }
      const dt = Math.min(0.05, (now - ultimo) / 1000); ultimo = now;
      if (S.fase === 'play') {
        tick();
        if (S.saltar) { S.saltar = false; empezarEncendido(); }
        else {
          if (S.playing) S.T += dt * S.speed;
          if (!api) { if (S.sinEscena) { S.saltar = true; } else if (S.T > TOPE) S.T = TOPE; }
          if (S.T >= S.Tend) { S.T = S.Tend; if (!S.holdEnd) empezarEncendido(); }
          if (S.fase === 'play') { if (api && api.lost) { /* se recupera solo */ } else dibujar(); panel && panel.actualizar(S.T, S.Tend); }
        }
      }
      if (S.fase === 'encendido') {
        tr += dt;
        const dur = Math.max(0.2, TUNE.reveal);
        const k = cl(tr / dur), linea = seg(k, 0, 0.25), abre = ease(seg(k, 0.2, 1));
        R.linea.style.display = k < 0.9 ? 'block' : 'none';
        R.linea.style.left = (50 * (1 - o3(linea))) + '%'; R.linea.style.width = (100 * o3(linea)) + '%';
        R.linea.style.opacity = 1 - seg(k, 0.5, 0.9);
        R.arriba.style.height = (50 * (1 - abre)) + '%'; R.abajo.style.height = (50 * (1 - abre)) + '%';
        if (k >= 1) { vivo = false; limpiar(); if (w.__y2kSatActual === ctrl) w.__y2kSatActual = null; return; }
      }
      raf = requestAnimationFrame(bucle);
    };
    raf = requestAnimationFrame(bucle);
  } catch (e) {
    console.error('intro satelital', e);
    vivo = false; senal(); limpiar();
  }
}

// Deteccion del clic en 3D (una sola vez en la pagina). Solo si el precalentamiento de esta cuenca termino y la intro
// no se reprodujo ya para ella (el servidor tambien la omite si es la misma cuenca y buffer).
function alClic(ev) {
  const w = window, d = document;
  if (!PRE || !PRE.clave) return;
  const b = ev.target && ev.target.closest ? ev.target.closest('.st-key-vista button[role="radio"]') : null;
  if (!b) return;
  const radios = b.parentElement.querySelectorAll('button[role="radio"]');
  if (b !== radios[radios.length - 1] || b.getAttribute('aria-checked') === 'true') return;
  if (d.documentElement.dataset.y2kListo !== PRE.clave || w.__y2kSatUltima === PRE.clave) return;
  if (w.matchMedia && w.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const fila = b.closest('[data-testid="stHorizontalBlock"]'), bloque = fila && fila.parentElement;
  if (!fila || !bloque) return;
  w.__y2kSatUltima = PRE.clave;
  const rf = fila.getBoundingClientRect(), rb = bloque.getBoundingClientRect();
  const posPrevia = bloque.style.position;
  bloque.style.position = 'relative';
  reproducir(Object.assign({}, PRE, { host: bloque, posPrevia, temprano: true, turno: null,
    geom: { top: Math.round(rf.bottom - rb.top + 16), height: 650 } }));
}
if (!window.__y2kSatClic) { window.__y2kSatClic = true; document.addEventListener('click', alClic, true); }

window.__y2kSat = { reproducir, precalentar };
