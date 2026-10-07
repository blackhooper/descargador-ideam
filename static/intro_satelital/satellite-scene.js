import * as THREE from 'https://esm.sh/three@0.160.0';

const DEG = Math.PI / 180;
export const LON0 = -73.3, TLAT = 4.2;
const ALT = 1.6, KM = 6371, SS = 0.4, LENS_Z = 0.211 * SS;
export const DUR = { 'Satélite 2D': 1.2, 'Trazo láser': 1.9, 'Retícula': 0.9, 'Zoom out': 1.6, 'Haz de datos': 2.0, 'Impacto': 1.0, 'Cañones': 2.6, 'Apuntar': 1.8, 'POV': 1.4, 'Zoom óptico': 1.2, 'Descenso': 0.6, 'Encendido': 2.6 };
const W = 1920, H = 1080;
// Ajustes que se pueden mover desde el panel temporal del reproductor (player.js)
export const TUNE = {
  panAmt: 1,        // cuanto gira la mirada hacia el cuadro del usuario durante el zoom optico (0 = nada, 1 = todo)
  panStart: 0,      // segundo (dentro del zoom optico) en que empieza ese giro
  panEnd: 1,        // segundo en que termina
  diveShift: 0.8,   // duracion (s) del traslado de la camara hasta quedar sobre el cuadro, ya en el descenso
  descenso: 0.9,    // duracion total (s) del descenso, antes del encendido
  preDark: 0.25,    // oscuridad (0-1) durante el zoom optico
  blackMax: 1,      // oscuridad maxima justo antes del encendido
  fadeStart: 0.25,  // segundo del descenso en que empieza a oscurecer del todo
  fadeDur: 0.4,     // cuanto tarda en llegar a la oscuridad maxima
  reveal: 0.7,      // duracion (s) del encendido tipo monitor
  laserSep: 0.16,   // separacion lateral de los dos cañones al disparar (distancia desde el centro de la camara)
  laserDrop: 0.05, // cuanto salen por debajo del centro de la imagen
  laserT0: 0.05,    // segundos tras el primer disparo de cápsulas en que salen los lasers
  laserDur: 1.3,    // cuanto dura el disparo de los lasers
  laserW: 0.0012,   // grosor del nucleo del haz
  resScale: 0.7,    // resolucion interna de la escena (1 = 1920x1080); menos = menos memoria grafica
};
export function setTune(o) { Object.assign(TUNE, o); }
let LINE_RS = 1;

const V = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);
const PHI = TLAT * DEG;
const C = V(0, 0, -1);
const N = V(0, Math.sin(PHI), Math.cos(PHI));
const E = V(1, 0, 0);
const U = V(0, Math.cos(PHI), -Math.sin(PHI));
const Y = V(0, 1, 0);
const G = C.clone().add(N);
const S = C.clone().addScaledVector(N, 1 + ALT);
const LENS = S.clone().addScaledVector(N, -LENS_Z);
const ALT0 = ALT - LENS_Z;
const H0 = 2 * ALT0 * Math.tan(1 * DEG);
const HEND = 2 * 0.004 * Math.tan(31 * DEG);
const O1 = E.clone().multiplyScalar(0.86).addScaledVector(U, 0.34).addScaledVector(N, 0.16).multiplyScalar(SS);
const O2 = N.clone().multiplyScalar(-0.66).addScaledVector(E, 0.05).addScaledVector(U, 0.12).multiplyScalar(SS);
const LIGHT = N.clone().multiplyScalar(0.75).addScaledVector(E, -0.55).addScaledVector(U, 0.45).normalize();
const CYAN = new THREE.Color(0x35f0ff), ORANGE = new THREE.Color(0xff7a1a);

const clamp01 = x => (x < 0 ? 0 : x > 1 ? 1 : x);
const seg = (t, a, b) => clamp01((t - a) / (b - a));
const io2 = t => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
const io3 = t => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2);
const o3 = t => 1 - Math.pow(1 - t, 3);
const i2 = t => t * t;
const oBack = t => { const c1 = 1.4, c3 = c1 + 1; return t <= 0 ? 0 : 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); };
const lerp = (a, b, t) => a + (b - a) * t;
const elerp = (a, b, t) => a * Math.pow(b / a, t);
const hash = n => { const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); };
const noise1 = x => { const i = Math.floor(x), f = x - i, u = f * f * (3 - 2 * f); return lerp(hash(i), hash(i + 1), u) * 2 - 1; };
const wrap = lon => ((((lon - LON0) % 360) + 540) % 360) - 180;

function cuesOf(K) {
  const out = {}; let acc = 0;
  for (const n of Object.keys(DUR)) { const v = K && K[n]; out[n] = Number.isFinite(v) ? v : acc; acc = out[n] + DUR[n]; }
  return out;
}
function times(T, K) {
  return { tm: T - K['Satélite 2D'], tl: T - K['Trazo láser'], tr: T - K['Retícula'], tz: T - K['Zoom out'], tb: T - K['Haz de datos'], th: T - K['Impacto'], tc: T - K['Cañones'], ta: T - K['Apuntar'], tp: T - K['POV'], to: T - K['Zoom óptico'], td: T - K['Descenso'], te: T - K['Encendido'] };
}

function morphPoint(lam, phi, m, h = 0, out = V()) {
  const mm = Math.max(m, 1e-4), rho = 1 / mm, a = phi * mm, b = lam * mm;
  const ca = Math.cos(a), sa = Math.sin(a), cb = Math.cos(b), sb = Math.sin(b);
  const s1 = Math.sin(a / 2), s2 = Math.sin(b / 2);
  const omc = 2 * s1 * s1 + ca * 2 * s2 * s2;
  return out.set(rho * ca * sb + ca * sb * h, rho * sa + sa * h, -rho * omc + ca * cb * h);
}
const BOX = { lam: (-75.4 - LON0) * DEG, phi: 6.6 * DEG };
export function setBoxLonLat(lonDeg, latDeg) { BOX.lam = (lonDeg - LON0) * DEG; BOX.phi = latDeg * DEG; }
// direccion (unitaria, desde el centro del globo) a la que mira la camara al final: entre el punto fijo y el cuadro
const _bp = V();
function aimDir() {
  const P = morphPoint(BOX.lam, BOX.phi, 1, 0, _bp).sub(C).normalize();
  return N.clone().lerp(P, TUNE.panAmt).normalize();
}
function upAt(D) { return Y.clone().addScaledVector(D, -Y.dot(D)).normalize(); }
let COL = null;
function ringPoint(p) {
  const n = COL.cum.length - 1, target = clamp01(p) * COL.cum[n];
  let lo = 0, hi = n;
  while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (COL.cum[mid] <= target) lo = mid; else hi = mid; }
  const f = (target - COL.cum[lo]) / Math.max(1e-9, COL.cum[hi] - COL.cum[lo]);
  return [lerp(COL.pts[lo][0], COL.pts[hi][0], f), lerp(COL.pts[lo][1], COL.pts[hi][1], f)];
}
const NCAP = 28, CAP_FIRE = 0.45, CAP_SPAN = 0.5, CAP_FLY = 1.7;
const CAPS = Array.from({ length: NCAP }, (_, i) => ({ t0: CAP_FIRE + i * CAP_SPAN / NCAP + (hash(i * 3.1) - 0.5) * 0.012, ox: (hash(i * 7.3) - 0.5) * 0.06, oy: (hash(i * 11.9) - 0.5) * 0.06, sx: (hash(i * 5.7) - 0.5) * 0.008, sy: (hash(i * 2.3) - 0.5) * 0.008, yel: i % 3 === 1 }));
const CAP_START = LENS.clone().addScaledVector(N, -0.04).addScaledVector(E, -0.018).addScaledVector(U, -0.012);
function capPos(i, tp, out = V()) {
  const c = CAPS[i], s = (tp - c.t0) / CAP_FLY;
  if (s < 0 || s >= 1) return null;
  const e = 0.35 * s + 0.65 * s * s;
  const start = out.copy(CAP_START).addScaledVector(E, c.sx).addScaledVector(U, c.sy);
  const end = C.clone().add(aimDir()).addScaledVector(E, c.ox).addScaledVector(U, c.oy).addScaledVector(N, 0.002);
  return start.lerp(end, e);
}
const morphAt = tz => io2(seg(tz, 0.08, 1.4));

const _q = new THREE.Quaternion(), _qi = new THREE.Quaternion();
function slerpDir(a, b, t) { _q.setFromUnitVectors(a, b); _qi.identity().slerp(_q, t); return a.clone().applyQuaternion(_qi); }

// ── camera choreography (pure functions of authored time) ─────────────────
function camMap(tm, tz) {
  const m = morphAt(tz), s = seg(tz, 0, 1.6);
  const d = elerp(lerp(0.47, 0.43, o3(seg(tm, 0, 4.0))), 7.2, 1 - Math.pow(1 - s, 3.2));
  const w = io3(seg(tz, 0.45, 1.6));
  const look = morphPoint(0, PHI, m).lerp(C, w);
  const dir = V(0, 0, 1).lerp(N, w).normalize();
  const roll = -10 * DEG * Math.sin(Math.PI * s);
  return { pos: look.clone().addScaledVector(dir, d), look, up: V(Math.sin(roll), Math.cos(roll), 0), fov: 38 };
}
function camBeam(tb) {
  const s = io3(seg(tb, 0, 1.7)), a = 62 * DEG * s;
  const dir = N.clone().multiplyScalar(Math.cos(a)).addScaledVector(U, -Math.sin(a)).addScaledVector(E, 0.3 * Math.sin(a)).normalize();
  const look = C.clone().addScaledVector(N, 1.55 * io3(seg(tb, 0.3, 2.0)));
  return { pos: C.clone().addScaledVector(dir, lerp(7.2, 6.2, s)), look, up: Y.clone().lerp(N, s).normalize(), fov: 38 };
}
function camRush(T, K, t) {
  const B = camBeam(Math.min(t.tb, 2.0));
  const r = T - (K['Impacto'] - 0.7);
  const k = io3(seg(r, 0, 1.5));
  if (k <= 0) return B;
  const vB = B.pos.clone().sub(S), dB = vB.length(); vB.normalize();
  const vK = O1.clone().normalize(), dK = O1.length();
  const pos = S.clone().addScaledVector(slerpDir(vB, vK, k), elerp(dB, dK, k));
  const look = B.look.clone().lerp(S.clone().addScaledVector(N, -0.03 * SS), io3(seg(r, 0, 1.1)));
  return { pos, look, up: B.up.clone().lerp(N, k).normalize(), fov: lerp(38, 42, k) };
}
function canOffset(tc) {
  const ang = 24 * DEG * io2(seg(tc, 0, 2.6));
  return O1.clone().applyAxisAngle(N, ang).multiplyScalar(lerp(1, 0.86, io2(seg(tc, 0, 2.6))));
}
function camCan(tc) {
  return { pos: S.clone().add(canOffset(tc)), look: S.clone().addScaledVector(N, -0.03 * SS), up: N.clone(), fov: 42 };
}
function camAim(ta) {
  const offA = canOffset(2.6), k = io3(seg(ta, 0, 1.0));
  const dir = slerpDir(offA.clone().normalize(), O2.clone().normalize(), k);
  const pos0 = S.clone().addScaledVector(dir, elerp(offA.length(), O2.length(), k));
  const look0 = S.clone().addScaledVector(N, -0.03 * SS).lerp(LENS, k);
  const p = seg(ta, 1.0, 1.8), e = p * p * p;
  const target = LENS.clone().addScaledVector(N, -0.012 * SS);
  return { pos: pos0.lerp(target, e), look: look0, up: N.clone().lerp(E, k).normalize(), fov: lerp(lerp(42, 34, k), 26, e) };
}
function povFov(to) {
  const th = elerp(Math.tan(20 * DEG), Math.tan(1 * DEG), io3(seg(to, 0, 1.0)));
  return 2 * Math.atan(th) / DEG;
}
function diveAlt(td) {
  const s = seg(td, 0, 1.4);
  const fov = 2 + 60 * o3(seg(td, 0, 0.7));
  const e = 0.3 * o3(seg(s, 0, 0.5)) + 0.7 * Math.pow(s, 2.4);
  return { alt: elerp(H0, HEND, e) / (2 * Math.tan(fov / 2 * DEG)), fov };
}
function camAt(T, K, t) {
  if (t.tb < 0) return camMap(t.tm, t.tz);
  if (t.tc < 0) return camRush(T, K, t);
  if (t.ta < 0) return camCan(t.tc);
  if (t.tp < 0) return camAim(t.ta);
  const Dn = aimDir();
  if (t.td < 0) {
    const k = io3(seg(t.to, TUNE.panStart, Math.max(TUNE.panEnd, TUNE.panStart + 0.01)));
    return { pos: LENS.clone(), look: C.clone().add(N.clone().lerp(Dn, k).normalize()), up: U.clone().lerp(upAt(Dn), k).normalize(), fov: t.to < 0 ? 40 : povFov(t.to) };
  }
  // descenso: la mirada ya esta sobre el cuadro y la camara se desplaza hasta quedar justo encima
  const d = diveAlt(t.td), kd = io3(seg(t.td, 0, Math.max(TUNE.diveShift, 0.01)));
  const posDir = N.clone().lerp(Dn, kd).normalize();
  return { pos: C.clone().addScaledVector(posDir, 1 + d.alt), look: C.clone().add(Dn), up: upAt(Dn), fov: d.fov };
}

// ── whole-frame state ────────────────────────────────────────────────────
const _cam = new THREE.PerspectiveCamera(40, W / H, 0.0005, 500);
function project(cam, p) { const v = p.clone().project(cam); return { x: (v.x * 0.5 + 0.5) * W, y: (-v.y * 0.5 + 0.5) * H, vis: v.z < 1 && v.z > -1 }; }

export function frame(T, K0) {
  const K = cuesOf(K0), t = times(T, K);
  const cam = camAt(T, K, t);
  // shake
  const charge = Math.pow(seg(t.tc, 1.15, 2.6), 1.4);
  let shake = 0;
  if (t.tc >= 0 && t.ta < 0.9) shake = 0.006 * charge * charge;
  if (t.tp >= 0 && t.td < 0) shake = 0.0012 + (t.to >= 0 ? 0.004 * Math.exp(-Math.pow((t.to - 1.0) / 0.12, 2)) : 0);
  let diveSpeed = 0, travel = 0;
  if (t.td >= 0) {
    const a1 = diveAlt(t.td).alt, a0 = diveAlt(t.td - 1 / 60).alt;
    diveSpeed = Math.max(0, (Math.log(a0) - Math.log(a1)) * 60);
    travel = -Math.log(a1);
    shake = 0.002 + 0.0025 * Math.min(diveSpeed / 4, 1);
  }
  if (shake > 0) {
    const dist = cam.pos.distanceTo(cam.look);
    const side = V().subVectors(cam.look, cam.pos).normalize();
    const a = V().crossVectors(side, cam.up).normalize(), b = V().crossVectors(a, side);
    cam.look.addScaledVector(a, noise1(T * 23) * shake * dist).addScaledVector(b, noise1(T * 19 + 7) * shake * dist);
  }
  const m = t.tb >= 0 ? 1 : morphAt(t.tz);
  // satellite
  const theta = -0.75 * (1 - o3(seg(t.tb, 0, 2.0)));
  const radial = N.clone().multiplyScalar(Math.cos(theta)).addScaledVector(E, Math.sin(theta));
  const tangent = N.clone().multiplyScalar(-Math.sin(theta)).addScaledVector(E, Math.cos(theta));
  const satPos = C.clone().addScaledVector(radial, 1 + ALT);
  const st = {
    T, t, cam, m, charge, diveSpeed, travel,
    sat: {
      visible: t.tb >= 0 && t.tp < 0, pos: satPos, radial, tangent,
      pitch: io3(seg(t.ta, 0, 0.95)) + 0.05 * Math.sin(Math.PI * seg(t.ta, 0.8, 1.3)) * (1 - seg(t.ta, 0.8, 1.3)),
      roll: t.th < 0 ? 4 * DEG * Math.sin(T * 0.9) : 0,
      hatch: o3(seg(t.tc, 0, 0.35)), arm: oBack(seg(t.tc, 0.2, 0.75)), b1: oBack(seg(t.tc, 0.6, 0.95)), b2: oBack(seg(t.tc, 0.8, 1.15)), fins: o3(seg(t.tc, 0.95, 1.3)),
      power: t.th < 0 ? 0.35 : 0.35 + 0.65 * o3(seg(t.th, 0, 0.5)) * (t.th < 0.4 ? 0.6 + 0.4 * hash(Math.floor(T * 40)) : 1),
      lens: 0.6 + 0.9 * seg(t.ta, 1.0, 1.8),
    },
    hi: t.tb < 0 ? 0.55 + 0.25 * seg(t.tz, 1.0, 1.6) : 1 + 1.1 * Math.sin(Math.PI * seg(t.tb, 0, 0.7)),
    ripple: { r: 1.5 + 34 * o3(seg(t.tb, 0.05, 1.5)), a: t.tb < 0.05 ? 0 : 0.9 * (1 - seg(t.tb, 0.05, 1.5)) },
    beam: {
      on: t.tb >= 1.2 && t.ta < 0.2,
      head: lerp(1, 1 + ALT - 0.06 * SS, i2(seg(t.tb, 1.25, 2.0))),
      alpha: 1 - seg(t.tc, 0.4, 1.0),
      base: seg(t.tb, 1.1, 1.3) * (1 - seg(t.tc, 0.4, 1.0)),
      hit: t.th >= 0 ? 1 - seg(t.th, 0, 0.6) : 0,
      ring: t.th >= 0 ? seg(t.th, 0, 0.7) : -1,
    },
    orbit: seg(t.tb, 0.1, 0.8) * (1 - seg(t.tc, 0, 0.8)),
    stars: seg(m, 0.45, 1),
    caps: t.tp >= CAP_FIRE && t.te < 0 ? t.tp : null,
    reveal: t.tz >= 0 ? 1 : seg(t.tr, 0, 0.8),
    draw: io2(seg(t.tl, 0.5, 1.6)),
    pulse: Math.sin(Math.PI * seg(t.tl, 1.55, 2.2)),
    detail: { c2: t.tb < 0 ? 1 - seg(t.tz, 0.6, 1.6) : t.tp >= 0 ? 1 : 0, c3: t.to >= 0.3 ? 1 : 0, fine: t.tp >= 0 ? 1 : 0 },
    atmo: seg(m, 0.85, 1),
  };
  // HUD data
  _cam.fov = cam.fov; _cam.position.copy(cam.pos); _cam.up.copy(cam.up); _cam.lookAt(cam.look); _cam.updateMatrixWorld(); _cam.updateProjectionMatrix();
  const gNow = t.tb >= 0 ? G.clone() : morphPoint(0, PHI, m);
  const visW = 2 * cam.pos.distanceTo(cam.look) * Math.tan(cam.fov / 2 * DEG) * (W / H);
  const altSurf = t.td >= 0 ? diveAlt(t.td).alt : ALT0;
  st.hud = {
    black: t.te >= 0 ? (t.te < 0.25 ? 1 : 0) : Math.max(1 - seg(t.tm, 0, 0.25), t.tp < 0 ? 0 : t.to < 0 ? 0.35 * seg(t.tp, 1.05, 1.4) : 0.35 + 0.65 * o3(seg(t.to, 0, 0.5))),
    white: Math.max(t.tp < 0 ? Math.pow(seg(t.ta, 1.6, 1.8), 3) : 0, t.tp >= 0 && t.to < 0 ? 1 - seg(t.tp, 0, 0.35) : 0, st.beam.hit * st.beam.hit * 0.12),
    map: t.tb < 0 ? 1 - seg(t.tz, 0, 0.2) : 0,
    tm: t.tm, tl: t.tl, tr: t.tr, tz: t.tz,
    box: project(_cam, morphPoint(BOX.lam, BOX.phi, m)),
    head: COL && t.tl >= 0.5 && t.tl < 1.65 ? project(_cam, (() => { const q = ringPoint(io2(seg(t.tl, 0.5, 1.6))); return morphPoint(q[0], q[1], m, 0.0001); })()) : null,
    kmPerPx: visW * KM / W,
    g: project(_cam, gNow),
    s: project(_cam, satPos),
    colTag: seg(t.tb, 0.25, 0.65) * (1 - seg(t.tb, 1.5, 1.9)),
    satTag: seg(t.tb, 0.5, 0.9) * (1 - seg(t.th, -0.3, 0.1)),
    satInfo: seg(t.th, 0.3, 0.55) * (1 - seg(t.th, 0.8, 1.0)),
    can: seg(t.tc, 0.1, 0.4) * (1 - seg(t.ta, 0.4, 0.8)),
    steps: [seg(t.tc, 0, 0.35), seg(t.tc, 0.2, 0.75), seg(t.tc, 0.6, 1.15), seg(t.tc, 0.95, 1.3)],
    charge,
    pov: t.tp >= 0 && t.te < 0 ? seg(t.tp, 0.12, 0.5) : 0,
    boot: seg(t.tp, 0.12, 0.9),
    lock: seg(t.tp, 0.7, 1.1),
    zoomX: Math.tan(20 * DEG) / Math.tan(cam.fov / 2 * DEG),
    fov: cam.fov,
    altKm: altSurf * KM,
    dive: t.td >= 0 ? seg(t.td, 0, 0.3) : 0,
    speed: Math.min(diveSpeed / 4, 1),
    capN: NCAP, capOut: t.tp < 0 ? 0 : CAPS.filter(c => t.tp >= c.t0).length,
    inEnc: t.te >= 0, te: t.te,
    enc: t.te >= 0 ? {
      lineW: o3(seg(t.te, 0.25, 0.4)), line: seg(t.te, 0.25, 0.3) * (1 - seg(t.te, 0.5, 0.7)),
      open: io3(seg(t.te, 0.38, 0.75)), glow: t.te >= 0.38 ? 0.3 * (1 - seg(t.te, 0.4, 1.1)) : 0,
      flick: (t.te > 0.8 && t.te < 0.84) || (t.te > 0.9 && t.te < 0.93) ? 0.45 : 0, label: seg(t.te, 1.0, 1.4),
    } : null,
    vKmS: t.td >= 0 ? Math.max(0, (diveAlt(t.td - 1 / 60).alt - diveAlt(t.td).alt) * 60 * KM) : 0,
    T,
  };
  return st;
}

// ── shaders ──────────────────────────────────────────────────────────────
const MORPH_GLSL = /* glsl */`
uniform float uMorph;
vec3 s_morph(vec2 p, float h, out vec3 nrm) {
  float m = max(uMorph, 1e-4);
  float rho = 1.0 / m;
  float a = p.y * m, b = p.x * m;
  float ca = cos(a), sa = sin(a), cb = cos(b), sb = sin(b);
  float s1 = sin(a * 0.5), s2 = sin(b * 0.5);
  float omc = 2.0 * s1 * s1 + ca * 2.0 * s2 * s2;
  nrm = vec3(ca * sb, sa, ca * cb);
  return vec3(rho * ca * sb, rho * sa, -rho * omc) + nrm * h;
}`;

const GLOBE_VS = /* glsl */`
#include <common>
#include <logdepthbuf_pars_vertex>
${MORPH_GLSL}
varying vec2 vLL; varying vec3 vNrm; varying vec3 vW;
void main() {
  vec3 nrm; vec3 p = s_morph(position.xy, 0.0, nrm);
  vLL = position.xy; vNrm = nrm; vW = p;
  gl_Position = projectionMatrix * viewMatrix * vec4(p, 1.0);
  #include <logdepthbuf_vertex>
}`;

const GLOBE_FS = /* glsl */`
#include <common>
#include <logdepthbuf_pars_fragment>
uniform sampler2D tGlobal; uniform sampler2D tRegion; uniform vec4 uRegion;
uniform vec3 cOcean, cLand, cCol, cGrid, cRim;
uniform float uMorph, uHi, uTime, uRipple, uRippleA, uC2, uC3, uFine, uReveal;
uniform vec3 uCam, uLight; uniform float uTLat;
varying vec2 vLL; varying vec3 vNrm; varying vec3 vW;
float s_h(vec2 p) { vec3 p3 = fract(vec3(p.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float s_n(vec2 p) { vec2 i = floor(p), f = fract(p); vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(s_h(i), s_h(i + vec2(1.0, 0.0)), u.x), mix(s_h(i + vec2(0.0, 1.0)), s_h(i + vec2(1.0, 1.0)), u.x), u.y); }
float s_fbm(vec2 p) { float v = 0.0, a = 0.5; for (int i = 0; i < 3; i++) { v += a * s_n(p); p = p * 2.03 + 17.1; a *= 0.5; } return v; }
float s_line(float x, float px) { float fw = fwidth(x); float d = abs(fract(x + 0.5) - 0.5);
  return (1.0 - smoothstep(px * 0.5 * fw, px * 1.5 * fw, d)) * (1.0 - smoothstep(0.08, 0.3, fw)); }
float s_sharp(float v) { float w = max(fwidth(v) * 0.8, 0.003); return clamp((v - 0.5) / w * 0.5 + 0.5, 0.0, 1.0); }
void main() {
  vec2 d = vLL * 57.2957795;
  vec2 guv = vec2((d.x + 180.0) / 360.0, (d.y + 90.0) / 180.0);
  vec2 ruv = (d - uRegion.xy) / (uRegion.zw - uRegion.xy);
  vec4 g = texture2D(tGlobal, guv);
  vec4 r = texture2D(tRegion, clamp(ruv, 0.0, 1.0));
  float inR = step(0.002, ruv.x) * step(ruv.x, 0.998) * step(0.002, ruv.y) * step(ruv.y, 0.998);
  float landRaw = mix(g.r, r.r, inR);
  float land = s_sharp(landRaw);
  float col = s_sharp(r.g) * inR;
  vec3 c = mix(cOcean, cLand, land);
  float cont = 0.55 * s_line(s_fbm(d * 0.28) * 9.0, 1.0);
  if (uC2 > 0.0) cont += 0.45 * uC2 * s_line(s_fbm(d * 3.5 + 3.1) * 5.0, 1.0);
  if (uC3 > 0.0) cont += 0.4 * uC3 * s_line(s_fbm(d * 80.0 + 9.7) * 6.0, 1.0);
  c += cGrid * cont * land * (0.07 + 0.22 * col * min(uHi, 1.0));
  float pulse = 0.8 + 0.2 * sin(uTime * 5.0);
  c = mix(c, c + cCol * pulse, col * clamp(uHi, 0.0, 2.0) * 0.6);
  float g10 = max(s_line(d.x / 10.0, 1.0), s_line(d.y / 10.0, 1.0));
  float g1 = max(s_line(d.x, 1.0), s_line(d.y, 1.0));
  float gf = 0.0;
  if (uFine > 0.0) gf = 0.08 * max(s_line(d.x * 10.0, 1.0), s_line(d.y * 10.0, 1.0)) + 0.07 * max(s_line(d.x * 100.0, 1.0), s_line(d.y * 100.0, 1.0));
  c += cGrid * (0.16 * g10 + 0.09 * g1 + gf) * mix(1.0, 0.6, land);
  float dist = length(vec2(d.x * cos(radians(d.y)), d.y - uTLat));
  float rw = max(0.5, uRipple * 0.07);
  c += cRim * exp(-pow((dist - uRipple) / rw, 2.0)) * uRippleA;
  c += cRim * exp(-pow((dist - uRipple * 0.62) / rw, 2.0)) * uRippleA * 0.5;
  vec3 Nn = normalize(vNrm);
  float dif = clamp(dot(Nn, normalize(uLight)), 0.0, 1.0);
  float sm = smoothstep(0.6, 1.0, uMorph);
  c *= mix(1.0, 0.18 + 0.95 * dif, sm);
  vec3 Vv = normalize(uCam - vW);
  float fr = pow(1.0 - clamp(dot(Nn, Vv), 0.0, 1.0), 3.0);
  c += cRim * fr * 0.55 * sm * (0.35 + 0.65 * dif);
  gl_FragColor = vec4(c * uReveal, 1.0);
  #include <logdepthbuf_fragment>
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`;

const LINE_VS = /* glsl */`
#include <common>
#include <logdepthbuf_pars_vertex>
${MORPH_GLSL}
attribute vec2 aO; attribute float aSide; attribute float aDir; attribute float aT;
uniform float uWidth, uLift; uniform vec2 uHalf;
varying float vSide; varying float vT;
void main() {
  vT = aT;
  vec3 n1, n2;
  vec3 P = s_morph(position.xy, uLift, n1), Q = s_morph(aO, uLift, n2);
  mat4 vp = projectionMatrix * viewMatrix;
  vec4 a = vp * vec4(P, 1.0), b = vp * vec4(Q, 1.0);
  vSide = aSide;
  if (a.w < 1e-5 || b.w < 1e-5) { gl_Position = vec4(2.0, 2.0, 2.0, 1.0); return; }
  vec2 sa = a.xy / a.w * uHalf, sb = b.xy / b.w * uHalf;
  vec2 dir = (sb - sa) * aDir;
  float L = length(dir);
  dir = L > 1e-6 ? dir / L : vec2(1.0, 0.0);
  vec2 nrm = vec2(-dir.y, dir.x);
  a.xy += nrm * aSide * (uWidth * 0.5 + 0.75) / uHalf * a.w;
  gl_Position = a;
  #include <logdepthbuf_vertex>
}`;
const LINE_FS = /* glsl */`
#include <common>
#include <logdepthbuf_pars_fragment>
uniform vec3 uColor; uniform float uOpacity; uniform float uWidth; uniform float uDraw;
varying float vSide; varying float vT;
void main() {
  if (vT > uDraw) discard;
  float e = 1.0 - smoothstep(uWidth / (uWidth + 1.5), 1.0, abs(vSide));
  gl_FragColor = vec4(uColor * uOpacity * e, 1.0);
  #include <logdepthbuf_fragment>
}`;

const GLOW_VS = /* glsl */`
#include <common>
#include <logdepthbuf_pars_vertex>
varying vec3 vN; varying vec3 vV;
void main() {
  vec4 wp = modelMatrix * vec4(position, 1.0);
  vN = normalize(mat3(modelMatrix) * normal);
  vV = normalize(cameraPosition - wp.xyz);
  gl_Position = projectionMatrix * viewMatrix * wp;
  #include <logdepthbuf_vertex>
}`;
const GLOW_FS = /* glsl */`
#include <common>
#include <logdepthbuf_pars_fragment>
uniform vec3 uColor; uniform float uOpacity; uniform float uPow; uniform float uMode;
varying vec3 vN; varying vec3 vV;
void main() {
  float d = dot(normalize(vN), normalize(vV));
  float i = uMode < 0.5 ? pow(abs(d), uPow) : pow(clamp(-d * 2.4, 0.0, 1.0), uPow);
  gl_FragColor = vec4(uColor * i * uOpacity, 1.0);
  #include <logdepthbuf_fragment>
}`;

// ── geometry helpers ─────────────────────────────────────────────────────
function globeGeometry(nx = 360, ny = 180) {
  const pos = new Float32Array((nx + 1) * (ny + 1) * 3); let k = 0;
  for (let j = 0; j <= ny; j++) for (let i = 0; i <= nx; i++) { pos[k++] = -Math.PI + 2 * Math.PI * i / nx; pos[k++] = -Math.PI / 2 + Math.PI * j / ny; pos[k++] = 0; }
  const idx = [];
  for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) { const a = j * (nx + 1) + i, b = a + 1, c = a + nx + 1, d = c + 1; idx.push(a, b, d, a, d, c); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setIndex(idx); return g;
}
function segsFrom(lines, out = []) {
  for (const line of lines) for (let i = 1; i < line.length; i++) {
    const l1 = wrap(line[i - 1][0]), l2 = wrap(line[i][0]);
    if (Math.abs(l2 - l1) > 90) continue;
    out.push(l1 * DEG, line[i - 1][1] * DEG, l2 * DEG, line[i][1] * DEG);
  }
  return out;
}
function fatLineGeometry(segs, tv) {
  const n = segs.length / 4, AT = new Float32Array(n * 4);
  if (tv) for (let q = 0; q < n; q++) { AT[q * 4] = AT[q * 4 + 1] = tv[q * 2]; AT[q * 4 + 2] = AT[q * 4 + 3] = tv[q * 2 + 1]; }
  const P = new Float32Array(n * 12), O = new Float32Array(n * 8), SD = new Float32Array(n * 4), DR = new Float32Array(n * 4), I = new Uint32Array(n * 6);
  for (let s = 0; s < n; s++) {
    const ax = segs[4 * s], ay = segs[4 * s + 1], bx = segs[4 * s + 2], by = segs[4 * s + 3];
    const vs = [[ax, ay, bx, by, -1, 1], [ax, ay, bx, by, 1, 1], [bx, by, ax, ay, -1, -1], [bx, by, ax, ay, 1, -1]];
    for (let v = 0; v < 4; v++) { const q = s * 4 + v, x = vs[v]; P[q * 3] = x[0]; P[q * 3 + 1] = x[1]; O[q * 2] = x[2]; O[q * 2 + 1] = x[3]; SD[q] = x[4]; DR[q] = x[5]; }
    const b = s * 4; I.set([b, b + 2, b + 1, b + 1, b + 2, b + 3], s * 6);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(P, 3)); g.setAttribute('aO', new THREE.BufferAttribute(O, 2));
  g.setAttribute('aSide', new THREE.BufferAttribute(SD, 1)); g.setAttribute('aDir', new THREE.BufferAttribute(DR, 1)); g.setAttribute('aT', new THREE.BufferAttribute(AT, 1));
  g.setIndex(new THREE.BufferAttribute(I, 1)); return g;
}
function lineMaterial(color, width, opacity, lift = 0.00004) {
  return new THREE.ShaderMaterial({
    vertexShader: LINE_VS, fragmentShader: LINE_FS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide, toneMapped: false,
    uniforms: { uMorph: { value: 0 }, uDraw: { value: 2 }, uWidth: { value: width }, uLift: { value: lift }, uHalf: { value: new THREE.Vector2(W / 2 * LINE_RS, H / 2 * LINE_RS) }, uColor: { value: color.clone() }, uOpacity: { value: opacity } },
  });
}
function glowMaterial(color, pow = 2, mode = 0) {
  return new THREE.ShaderMaterial({
    vertexShader: GLOW_VS, fragmentShader: GLOW_FS, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false,
    side: mode > 0.5 ? THREE.BackSide : THREE.FrontSide,
    uniforms: { uColor: { value: color.clone() }, uOpacity: { value: 1 }, uPow: { value: pow }, uMode: { value: mode } },
  });
}
function radialTex(stops, size = 128) {
  const c = document.createElement('canvas'); c.width = c.height = size; const x = c.getContext('2d');
  const g = x.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  for (const [o, col] of stops) g.addColorStop(o, col);
  x.fillStyle = g; x.fillRect(0, 0, size, size);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
function sprite(tex, color, scale = 1) {
  const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, color, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, toneMapped: false }));
  s.scale.setScalar(scale); return s;
}
function rng(seed) { return () => { seed |= 0; seed = (seed + 0x6D2B79F5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }

// ── satellite ────────────────────────────────────────────────────────────
function buildSatellite(tex) {
  const root = new THREE.Group();
  const body = new THREE.Group(); root.add(body);
  const hullM = new THREE.MeshStandardMaterial({ color: 0x0e1118, roughness: 0.52, metalness: 0.6 });
  const darkM = new THREE.MeshStandardMaterial({ color: 0x07080c, roughness: 0.32, metalness: 0.85 });
  const glassM = new THREE.MeshStandardMaterial({ color: 0x02050a, roughness: 0.08, metalness: 1.0 });
  const neon = new THREE.MeshBasicMaterial({ color: CYAN.clone(), toneMapped: false });
  const lensM = new THREE.MeshBasicMaterial({ color: CYAN.clone(), toneMapped: false });
  const thrM = new THREE.MeshBasicMaterial({ color: ORANGE.clone(), toneMapped: false });
  const edgeM = new THREE.LineBasicMaterial({ color: CYAN.clone(), transparent: true, opacity: 0.5, toneMapped: false });
  const panelLineM = new THREE.LineBasicMaterial({ color: CYAN.clone(), transparent: true, opacity: 0.55, toneMapped: false });
  const box = (w, h, d, m, x, y, z, parent = body) => { const o = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m); o.position.set(x, y, z); parent.add(o); return o; };
  const edges = (o, m = edgeM) => o.add(new THREE.LineSegments(new THREE.EdgesGeometry(o.geometry, 20), m));
  const strip = (a, b, m = neon, parent = body, th = 0.0032) => {
    const d = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
    const o = box(Math.abs(d[0]) + th, Math.abs(d[1]) + th, Math.abs(d[2]) + th, m, (a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2, parent);
    return o;
  };
  edges(box(0.14, 0.10, 0.24, hullM, 0, 0, 0));
  edges(box(0.06, 0.022, 0.20, darkM, 0, 0.061, -0.01));
  const frG = new THREE.CylinderGeometry(0.06, 0.085, 0.06, 4, 1); frG.rotateY(Math.PI / 4); frG.rotateX(Math.PI / 2); frG.scale(1.15, 0.83, 1);
  const fr = new THREE.Mesh(frG, hullM); fr.position.z = 0.15; body.add(fr); edges(fr);
  const barrelG = new THREE.CylinderGeometry(0.036, 0.042, 0.032, 40); barrelG.rotateX(Math.PI / 2);
  const lb = new THREE.Mesh(barrelG, darkM); lb.position.z = 0.195; body.add(lb);
  const glass = new THREE.Mesh(new THREE.CircleGeometry(0.032, 48), glassM); glass.position.z = 0.2108; body.add(glass);
  const ring = (r, tube, m, z, parent = body) => { const o = new THREE.Mesh(new THREE.TorusGeometry(r, tube, 8, 64), m); o.position.z = z; parent.add(o); return o; };
  ring(0.035, 0.0026, neon, 0.2112);
  ring(0.022, 0.0011, lensM, 0.2114); ring(0.013, 0.0008, lensM, 0.2116); ring(0.006, 0.0006, lensM, 0.2117);
  const pupil = new THREE.Mesh(new THREE.CircleGeometry(0.0022, 24), lensM); pupil.position.z = 0.2118; body.add(pupil);
  const glint = sprite(tex.glow, CYAN.clone().multiplyScalar(0.6), 0.05); glint.position.z = 0.214; body.add(glint);
  edges(box(0.11, 0.085, 0.04, darkM, 0, 0, -0.14));
  ring(0.026, 0.003, thrM, -0.1605); ring(0.014, 0.002, thrM, -0.1605);
  // receiver on belly
  const dishG = new THREE.CylinderGeometry(0.03, 0.012, 0.012, 32, 1, true); const dish = new THREE.Mesh(dishG, darkM); dish.position.set(0, -0.058, -0.07); body.add(dish);
  const dishRing = new THREE.Mesh(new THREE.TorusGeometry(0.03, 0.0018, 8, 48), neon); dishRing.rotation.x = Math.PI / 2; dishRing.position.set(0, -0.064, -0.07); body.add(dishRing);
  // station launcher
  const greenM = new THREE.MeshBasicMaterial({ color: new THREE.Color(0x3fff7a).multiplyScalar(1.6), toneMapped: false });
  const yelM = new THREE.MeshBasicMaterial({ color: new THREE.Color(0xffd84a).multiplyScalar(1.6), toneMapped: false });
  edges(box(0.064, 0.026, 0.07, darkM, 0, -0.063, 0.105));
  [-0.02, 0, 0.02].forEach((x, i) => { const tb = new THREE.Mesh(new THREE.CylinderGeometry(0.0075, 0.0075, 0.02, 20).rotateX(Math.PI / 2), hullM); tb.position.set(x, -0.063, 0.145); body.add(tb); const rr = new THREE.Mesh(new THREE.TorusGeometry(0.0075, 0.0016, 8, 28), i === 1 ? yelM : greenM); rr.position.set(x, -0.063, 0.1552); body.add(rr); });
  // circuits
  for (const s of [-1, 1]) {
    const x = 0.0712 * s;
    strip([x, 0.026, -0.105], [x, 0.026, 0.05]); strip([x, 0.026, 0.05], [x, -0.018, 0.05]); strip([x, -0.018, 0.05], [x, -0.018, 0.115]);
    strip([x, -0.032, -0.11], [x, -0.032, -0.02]); strip([x, -0.032, -0.02], [x, 0.004, -0.02]);
    strip([0.045 * s, 0.0512, -0.11], [0.045 * s, 0.0512, 0.09]); strip([0.045 * s, 0.0512, 0.09], [0.02 * s, 0.0512, 0.115]);
    strip([0.04 * s, -0.0512, 0.0], [0.04 * s, -0.0512, 0.11]);
    // solar wing
    const rod = new THREE.Mesh(new THREE.CylinderGeometry(0.006, 0.006, 0.11, 12).rotateZ(Math.PI / 2), darkM); rod.position.set(0.125 * s, 0, -0.03); body.add(rod);
    const panel = box(0.30, 0.005, 0.12, darkM, 0.33 * s, 0, -0.03); edges(panel, panelLineM);
    const pts = [];
    for (let i = 1; i < 6; i++) { const px = -0.15 + 0.05 * i; pts.push(px, 0.0031, -0.06, px, 0.0031, 0.06, px, -0.0031, -0.06, px, -0.0031, 0.06); }
    for (let k = 1; k < 3; k++) { const pz = -0.06 + 0.04 * k; pts.push(-0.15, 0.0031, pz, 0.15, 0.0031, pz, -0.15, -0.0031, pz, 0.15, -0.0031, pz); }
    const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3));
    panel.add(new THREE.LineSegments(pg, panelLineM));
  }
  // hatches
  const hatches = [-1, 1].map(s => { const o = box(0.052, 0.004, 0.15, hullM, 0.026 * s, -0.052, 0.03); edges(o); return o; });
  // cannons
  const cannons = [0, 1].map(i => {
    const s = i === 0 ? -1 : 1, col = i === 0 ? CYAN : ORANGE;
    const ringM = new THREE.MeshBasicMaterial({ color: col.clone(), toneMapped: false });
    const mount = new THREE.Group(); mount.position.set(0.07 * s, -0.05, 0.02); body.add(mount);
    const joint = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.011, 0.07, 20).rotateX(Math.PI / 2), darkM); mount.add(joint);
    edges(box(0.016, 0.045, 0.05, hullM, 0, -0.0225, 0, mount));
    const gun = new THREE.Group(); gun.position.set(0, -0.045, 0.01); mount.add(gun);
    edges(box(0.044, 0.044, 0.15, hullM, 0, 0, 0, gun));
    edges(box(0.05, 0.05, 0.035, darkM, 0, 0, -0.06, gun));
    strip([0.0222, 0.0, -0.07], [0.0222, 0.0, 0.07], ringM, gun, 0.0028); strip([-0.0222, 0.0, -0.07], [-0.0222, 0.0, 0.07], ringM, gun, 0.0028);
    strip([0.0, 0.0222, -0.04], [0.0, 0.0222, 0.07], ringM, gun, 0.0028);
    const fins = [-1, 0, 1].map(k => { const f = box(0.006, 0.05, 0.03, darkM, 0, 0, -0.02 + k * 0.035, gun); edges(f, new THREE.LineBasicMaterial({ color: col.clone(), transparent: true, opacity: 0.6, toneMapped: false })); return f; });
    const b1 = new THREE.Group(); gun.add(b1);
    const b1m = new THREE.Mesh(new THREE.CylinderGeometry(0.015, 0.015, 0.10, 28).rotateX(Math.PI / 2), darkM); b1.add(b1m);
    const rings = [0, 0.02, 0.04].map(z => { const o = new THREE.Mesh(new THREE.TorusGeometry(0.019, 0.0028, 8, 40), ringM); o.position.z = z; b1.add(o); return o; });
    const b2 = new THREE.Group(); b1.add(b2);
    const b2m = new THREE.Mesh(new THREE.CylinderGeometry(0.011, 0.012, 0.08, 24).rotateX(Math.PI / 2), hullM); b2.add(b2m);
    const muzzle = new THREE.Mesh(new THREE.TorusGeometry(0.0135, 0.003, 8, 40), ringM); muzzle.position.z = 0.04; b2.add(muzzle);
    const tip = new THREE.Group(); tip.position.z = 0.05; b2.add(tip);
    const orb = sprite(tex.glow, col.clone(), 0.02); const core = sprite(tex.glow, new THREE.Color(1, 1, 1), 0.01); const halo = sprite(tex.ring, col.clone(), 0.05);
    tip.add(orb, core, halo);
    const NP = 48, pr = rng(91 + i * 17), dirs = [];
    for (let k = 0; k < NP; k++) { const u = pr() * 2 - 1, a = pr() * Math.PI * 2, rr = Math.sqrt(1 - u * u); dirs.push(V(rr * Math.cos(a), rr * Math.sin(a), u - 0.35).normalize(), pr()); }
    const pg = new THREE.BufferGeometry(); pg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(NP * 3), 3));
    const pm = new THREE.PointsMaterial({ color: col.clone().multiplyScalar(2.5), size: 3.2, sizeAttenuation: false, map: tex.dot, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false });
    const parts = new THREE.Points(pg, pm); parts.frustumCulled = false; tip.add(parts);
    const light = new THREE.PointLight(col.clone(), 0, 0, 2); tip.add(light);
    return { s, col, ringM, mount, gun, fins, b1, b2, rings, tip, orb, core, halo, parts, dirs, NP, light };
  });
  return { root, body, neon, lensM, thrM, edgeM, panelLineM, hatches, cannons, glint };
}

// ── scene ────────────────────────────────────────────────────────────────
let _inst = null, _degrade = false, _losses = 0;
// Descarga (y deja en cache) lo que pesa de la escena sin crear nada en la tarjeta grafica: se llama en cuanto se
// confirma la cuenca, para que cuando el usuario pase a 3D ya este todo en el navegador
let _datos = null;
export function precargarDatos() {
  if (!_datos) {
    _datos = Promise.all([
      import('https://esm.sh/d3-geo@3'), import('https://esm.sh/topojson-client@3'),
      fetch('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json').then(r => r.json()),
    ]).catch(e => { _datos = null; throw e; });
    ['EffectComposer', 'RenderPass', 'UnrealBloomPass', 'OutputPass'].forEach(n =>
      import('https://esm.sh/three@0.160.0/examples/jsm/postprocessing/' + n + '.js').catch(() => null));
  }
  return _datos;
}
export function setLowPower(v) { _degrade = !!v; }
// Sin buffer: el segundo cañon (naranja) se carga igual, pero al llegar el disparo se apaga y no sale su haz
let _buffer = true;
export function setBuffer(v) { _buffer = v !== false; }
let _renderer = null;   // se reutiliza entre repeticiones; solo se libera lo que pesa (geometrias, texturas, buffers)
export function getScene(host) {
  if (!_inst) { if (_losses > 1) return Promise.reject(new Error('webgl-blocked')); _inst = createScene().catch(e => { _inst = null; throw e; }); }
  return _inst.then(api => { api.attach(host); return api; });
}

async function createScene() {
  const renderer = _renderer || (_renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: false, powerPreference: 'high-performance' }));
  const gl = renderer.getContext(), dbg = gl.getExtension('WEBGL_debug_renderer_info');
  const gpu = String(dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER));
  const lowPower = _degrade || /swiftshader|llvmpipe|software/i.test(gpu);
  const RS = (lowPower ? 0.6 : 1) * TUNE.resScale; LINE_RS = RS;
  const listeners = new Set(), notify = () => listeners.forEach(f => { try { f(); } catch (e) { /* listener gone */ } });
  let lost = false, dead = false, lostTimer = 0;
  const onLost = e => {
    if (dead) return;
    e.preventDefault(); lost = true; _degrade = true; notify();
    clearTimeout(lostTimer);
    lostTimer = setTimeout(() => { if (!lost) return; dead = true; _inst = null; _renderer = null; _losses++; try { renderer.dispose(); } catch (err) { /* already gone */ } renderer.domElement.remove(); notify(); }, 6000);
  };
  const onRestored = () => { lost = false; clearTimeout(lostTimer); notify(); };
  renderer.domElement.addEventListener('webglcontextlost', onLost);
  renderer.domElement.addEventListener('webglcontextrestored', onRestored);
  renderer.setPixelRatio(1); renderer.setSize(W * RS, H * RS, false);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  Object.assign(renderer.domElement.style, { width: '100%', height: '100%', display: 'block' });

  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x010207);
  const camera = new THREE.PerspectiveCamera(40, W / H, 0.01, 20); scene.add(camera);

  const [d3, topo, world] = await precargarDatos();
  const land = topo.feature(world, world.objects.land);
  const countries = topo.feature(world, world.objects.countries);
  const colombia = countries.features.find(f => String(f.id) === '170');

  // textures (masks: R = land, G = Colombia)
  const gw = 2048, gh = 1024;
  const gc = document.createElement('canvas'); gc.width = gw; gc.height = gh;
  const gx = gc.getContext('2d'); gx.fillStyle = '#000'; gx.fillRect(0, 0, gw, gh);
  const gproj = d3.geoEquirectangular().rotate([-LON0, 0]).scale(gw / (2 * Math.PI)).translate([gw / 2, gh / 2]).precision(0.2);
  gx.fillStyle = '#f00'; gx.beginPath(); d3.geoPath(gproj, gx)(land); gx.fill();
  const RX0 = -26, RX1 = 26, RY0 = -22, RY1 = 28, rw = 2048, rh = Math.round(rw * (RY1 - RY0) / (RX1 - RX0));
  const rc = document.createElement('canvas'); rc.width = rw; rc.height = rh;
  const rx = rc.getContext('2d'); rx.fillStyle = '#000'; rx.fillRect(0, 0, rw, rh);
  const rk = rw / ((RX1 - RX0) * DEG);
  const rproj = d3.geoEquirectangular().rotate([-LON0, 0]).scale(rk).translate([-RX0 * DEG * rk, RY1 * DEG * rk]).precision(0.05);
  const rpath = d3.geoPath(rproj, rx);
  rx.fillStyle = '#f00'; rx.beginPath(); rpath(land); rx.fill();
  rx.globalCompositeOperation = 'lighter'; rx.fillStyle = '#0f0'; rx.beginPath(); rpath(colombia); rx.fill();
  const mkTex = (c, wrapS) => { const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.NoColorSpace; t.wrapS = wrapS; t.wrapT = THREE.ClampToEdgeWrapping; t.anisotropy = renderer.capabilities.getMaxAnisotropy(); t.minFilter = THREE.LinearMipmapLinearFilter; return t; };
  const tGlobal = mkTex(gc, THREE.RepeatWrapping), tRegion = mkTex(rc, THREE.ClampToEdgeWrapping);
  const freeAfterUpload = t => { t.onUpdate = () => { const c = t.image; t.image = { width: c.width, height: c.height }; c.width = c.height = 0; t.onUpdate = null; }; };
  freeAfterUpload(tGlobal); freeAfterUpload(tRegion);

  const lin = c => new THREE.Color(c);
  const globeMat = new THREE.ShaderMaterial({
    vertexShader: GLOBE_VS, fragmentShader: GLOBE_FS, side: THREE.DoubleSide, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 2,
    uniforms: {
      tGlobal: { value: tGlobal }, tRegion: { value: tRegion }, uRegion: { value: new THREE.Vector4(RX0, RY0, RX1, RY1) },
      cOcean: { value: lin(0x040a17) }, cLand: { value: lin(0x12304a) }, cCol: { value: lin(0x0b5e70) }, cGrid: { value: lin(0x4fe6ff) }, cRim: { value: lin(0x35d6ff) },
      uMorph: { value: 0 }, uReveal: { value: 1 }, uC2: { value: 1 }, uC3: { value: 0 }, uFine: { value: 0 }, uHi: { value: 0.6 }, uTime: { value: 0 }, uRipple: { value: 0 }, uRippleA: { value: 0 },
      uCam: { value: V() }, uLight: { value: LIGHT.clone() }, uTLat: { value: TLAT },
    },
  });
  const globe = new THREE.Mesh(globeGeometry(), globeMat); globe.frustumCulled = false; scene.add(globe);

  const coastSegs = segsFrom(topo.mesh(world, world.objects.countries, (a, b) => a === b).coordinates);
  const borderSegs = segsFrom(topo.mesh(world, world.objects.countries, (a, b) => a !== b).coordinates);
  const colLines = []; for (const poly of colombia.geometry.type === 'Polygon' ? [colombia.geometry.coordinates] : colombia.geometry.coordinates) for (const r of poly) colLines.push(r);
  colLines.sort((a, b) => b.length - a.length);
  const main = colLines[0].map(p => [wrap(p[0]) * DEG, p[1] * DEG]);
  // El contorno se dibuja desde el punto de la frontera mas cercano al cuadro: se puede rehacer si el cuadro cambia
  const buildCol = () => {
    let k0 = 0, best = 1e9;
    main.forEach((p, i) => { const dd = Math.hypot(p[0] - BOX.lam, p[1] - BOX.phi); if (dd < best) { best = dd; k0 = i; } });
    const ring = main.slice(k0).concat(main.slice(1, k0 + 1));
    const cum = [0]; for (let i = 1; i < ring.length; i++) cum.push(cum[i - 1] + Math.hypot(ring[i][0] - ring[i - 1][0], ring[i][1] - ring[i - 1][1]));
    COL = { pts: ring, cum };
    const colSegs = [], colT = [], L = cum[cum.length - 1];
    for (let i = 1; i < ring.length; i++) { colSegs.push(ring[i - 1][0], ring[i - 1][1], ring[i][0], ring[i][1]); colT.push(cum[i - 1] / L, cum[i] / L); }
    const rest = segsFrom(colLines.slice(1)); for (let i = 0; i < rest.length; i += 4) { colSegs.push(rest[i], rest[i + 1], rest[i + 2], rest[i + 3]); colT.push(1, 1); }
    return { colSegs, colT };
  };
  const colInit = buildCol();
  const coastM = lineMaterial(CYAN, 1.3, 0.55), borderM = lineMaterial(CYAN, 1.0, 0.28), colM = lineMaterial(CYAN.clone().multiplyScalar(1.6), 2.6, 1.0, 0.00006);
  const mkLines = (segs, m, order, tv) => { const o = new THREE.Mesh(fatLineGeometry(segs, tv), m); o.frustumCulled = false; o.renderOrder = order; scene.add(o); return o; };
  mkLines(coastSegs, coastM, 2); mkLines(borderSegs, borderM, 2); const colMesh = mkLines(colInit.colSegs, colM, 3, colInit.colT);

  // atmosphere
  const atmoM = glowMaterial(lin(0x2a9dff).multiplyScalar(1.2), 2.6, 1);
  const atmo = new THREE.Mesh(new THREE.SphereGeometry(1.09, 96, 64), atmoM); atmo.position.copy(C); atmo.renderOrder = 4; scene.add(atmo);

  // stars
  const sr = rng(7), NS = 3200, sp = new Float32Array(NS * 3), sc = new Float32Array(NS * 3);
  for (let i = 0; i < NS; i++) {
    const u = sr() * 2 - 1, a = sr() * Math.PI * 2, rr = Math.sqrt(1 - u * u), d = 180;
    sp.set([rr * Math.cos(a) * d, u * d, rr * Math.sin(a) * d], i * 3);
    const b = 0.25 + Math.pow(sr(), 3) * 1.3, tint = sr();
    sc.set([b * (0.8 + 0.2 * tint), b * 0.9, b], i * 3);
  }
  const sg = new THREE.BufferGeometry(); sg.setAttribute('position', new THREE.BufferAttribute(sp, 3)); sg.setAttribute('color', new THREE.BufferAttribute(sc, 3));
  const starM = new THREE.PointsMaterial({ size: 1.7, sizeAttenuation: false, vertexColors: true, transparent: true, depthWrite: false, toneMapped: false });
  const stars = new THREE.Points(sg, starM); stars.renderOrder = -1; stars.frustumCulled = false; scene.add(stars);

  // lights
  scene.add(new THREE.HemisphereLight(0x5f8fc0, 0x05070a, 0.55));
  const sun = new THREE.DirectionalLight(0xffffff, 2.6); sun.position.copy(C).addScaledVector(LIGHT, 10); sun.target.position.copy(C); scene.add(sun, sun.target);
  const rim = new THREE.DirectionalLight(0x35f0ff, 1.1); rim.position.copy(S).addScaledVector(E, -3).addScaledVector(N, 2); rim.target.position.copy(S); scene.add(rim, rim.target);

  const tex = {
    glow: radialTex([[0, 'rgba(255,255,255,1)'], [0.18, 'rgba(255,255,255,0.65)'], [0.45, 'rgba(255,255,255,0.12)'], [1, 'rgba(255,255,255,0)']]),
    dot: radialTex([[0, 'rgba(255,255,255,1)'], [0.5, 'rgba(255,255,255,0.6)'], [1, 'rgba(255,255,255,0)']], 32),
    ring: radialTex([[0, 'rgba(255,255,255,0)'], [0.72, 'rgba(255,255,255,0)'], [0.86, 'rgba(255,255,255,1)'], [0.93, 'rgba(255,255,255,0.25)'], [1, 'rgba(255,255,255,0)']]),
  };

  // beam
  const beam = new THREE.Group(); beam.position.copy(G); beam.quaternion.setFromUnitVectors(Y, N); scene.add(beam);
  const cyl = new THREE.CylinderGeometry(1, 1, 1, 24, 1, true); cyl.translate(0, 0.5, 0);
  const beamCoreM = new THREE.MeshBasicMaterial({ color: new THREE.Color(2.6, 3.2, 3.4), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
  const beamCore = new THREE.Mesh(cyl, beamCoreM); beam.add(beamCore);
  const beamGlowM = glowMaterial(CYAN.clone().multiplyScalar(1.2), 3.5, 0);
  const beamGlow = new THREE.Mesh(cyl, beamGlowM); beam.add(beamGlow);
  const beamTip = sprite(tex.glow, new THREE.Color(2.5, 3, 3.2), 0.08); beam.add(beamTip);
  const packets = Array.from({ length: 12 }, () => { const s = sprite(tex.glow, CYAN.clone().multiplyScalar(2.2), 0.025); beam.add(s); return s; });
  const baseFlare = sprite(tex.glow, CYAN.clone().multiplyScalar(2), 0.2); baseFlare.position.copy(G).addScaledVector(N, 0.004); scene.add(baseFlare);
  const hitFlash = sprite(tex.glow, new THREE.Color(1.8, 2.2, 2.3), 0.3); scene.add(hitFlash);
  const hitRing = sprite(tex.ring, CYAN.clone().multiplyScalar(2.4), 0.3); scene.add(hitRing);
  const orbitPts = []; for (let i = 0; i <= 256; i++) { const a = i / 256 * Math.PI * 2; orbitPts.push(C.clone().addScaledVector(N, Math.cos(a) * (1 + ALT)).addScaledVector(E, Math.sin(a) * (1 + ALT))); }
  const orbitM = new THREE.LineBasicMaterial({ color: CYAN.clone(), transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false });
  const orbit = new THREE.Line(new THREE.BufferGeometry().setFromPoints(orbitPts), orbitM); scene.add(orbit);

  const sat = buildSatellite(tex); scene.add(sat.root);
  const GREEN = new THREE.Color(0x3fff7a), YEL = new THREE.Color(0xffd84a);
  const capGroup = new THREE.Group(); scene.add(capGroup);
  const caps = CAPS.map(c => { const col = c.yel ? YEL : GREEN; const g = sprite(tex.glow, col.clone().multiplyScalar(2.4), 0.0012); const k = sprite(tex.glow, new THREE.Color(2.2, 2.2, 2.2), 0.0005); capGroup.add(g, k); return { g, k, col }; });
  const trailGeo = new THREE.BufferGeometry(), trailPos = new Float32Array(NCAP * 6), trailCol = new Float32Array(NCAP * 6);
  trailGeo.setAttribute('position', new THREE.BufferAttribute(trailPos, 3)); trailGeo.setAttribute('color', new THREE.BufferAttribute(trailCol, 3));
  const trails = new THREE.LineSegments(trailGeo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, toneMapped: false }));
  trails.frustumCulled = false; capGroup.add(trails);
  // Lasers de area (cian) y buffer (naranja): salen de los dos cañones al mismo tiempo que la rafaga de capsulas, hacia el cuadro
  const fireGroup = new THREE.Group(); fireGroup.frustumCulled = false; scene.add(fireGroup);
  const beamGeo = new THREE.CylinderGeometry(1, 1, 1, 10, 1, true);
  const mkBeam = (col, glow) => {
    const m = new THREE.MeshBasicMaterial({ color: col.clone().multiplyScalar(glow ? 1.1 : 1.8), transparent: true, opacity: 0, blending: THREE.AdditiveBlending, depthWrite: false, depthTest: false, toneMapped: false, side: THREE.DoubleSide });
    const o = new THREE.Mesh(beamGeo, m); o.frustumCulled = false; o.visible = false; o.renderOrder = 12; fireGroup.add(o); return o;
  };
  const lasers = [{ col: CYAN, side: -1, core: mkBeam(new THREE.Color(0.8, 1, 1), false), glow: mkBeam(CYAN, true) },
                  { col: ORANGE, side: 1, core: mkBeam(new THREE.Color(1, 0.9, 0.7), false), glow: mkBeam(ORANGE, true) }];
  const launchFlash = sprite(tex.glow, new THREE.Color(0.9, 1.4, 0.7), 0.007); launchFlash.position.copy(CAP_START); capGroup.add(launchFlash);

  // warp streaks (camera space)
  const NSTK = 420, stk = new THREE.BufferGeometry(), stkPos = new Float32Array(NSTK * 6), stkCol = new Float32Array(NSTK * 6), stkSeed = [];
  const kr = rng(33);
  for (let i = 0; i < NSTK; i++) { stkSeed.push({ a: kr() * Math.PI * 2, r: 0.18 + Math.pow(kr(), 0.7) * 1.2, z: kr(), c: kr() }); }
  stk.setAttribute('position', new THREE.BufferAttribute(stkPos, 3)); stk.setAttribute('color', new THREE.BufferAttribute(stkCol, 3));
  const stkM = new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, blending: THREE.AdditiveBlending, depthTest: false, depthWrite: false, toneMapped: false });
  const streaks = new THREE.LineSegments(stk, stkM); streaks.frustumCulled = false; streaks.renderOrder = 10; camera.add(streaks);

  // post
  let composer = null, bloom = null;
  if (!lowPower) try {
    const [{ EffectComposer }, { RenderPass }, { UnrealBloomPass }, { OutputPass }] = await Promise.all([
      import('https://esm.sh/three@0.160.0/examples/jsm/postprocessing/EffectComposer.js'),
      import('https://esm.sh/three@0.160.0/examples/jsm/postprocessing/RenderPass.js'),
      import('https://esm.sh/three@0.160.0/examples/jsm/postprocessing/UnrealBloomPass.js'),
      import('https://esm.sh/three@0.160.0/examples/jsm/postprocessing/OutputPass.js'),
    ]);
    composer = new EffectComposer(renderer); composer.setPixelRatio(1); composer.setSize(W * RS, H * RS);
    composer.addPass(new RenderPass(scene, camera));
    bloom = new UnrealBloomPass(new THREE.Vector2(W * RS / 2, H * RS / 2), 0.75, 0.42, 0.8); composer.addPass(bloom);
    composer.addPass(new OutputPass());
  } catch (e) { console.warn('bloom unavailable', e); }

  const qa = new THREE.Quaternion(), qp = new THREE.Quaternion(), qr = new THREE.Quaternion(), mtx = new THREE.Matrix4(), X = V(1, 0, 0), Z = V(0, 0, 1);

  function apply(st) {
    const { cam, t, T } = st;
    const dC = cam.pos.distanceTo(C), dS = Math.max(dC - 1, 1e-4);
    const dSat = st.sat.visible ? Math.max(cam.pos.distanceTo(st.sat.pos) - 0.2, 1e-4) : Infinity;
    camera.near = st.caps != null ? 0.003 : Math.min(0.6, Math.max(0.0004, 0.35 * Math.min(dS, dSat))); camera.far = dC + 7;
    camera.fov = cam.fov; camera.position.copy(cam.pos); camera.up.copy(cam.up); camera.lookAt(cam.look); camera.updateProjectionMatrix(); camera.updateMatrixWorld();
    stars.position.copy(cam.pos); stars.scale.setScalar((dC + 5.5) / 180);
    for (const m of [globeMat, coastM, borderM, colM]) m.uniforms.uMorph.value = st.m;
    globeMat.uniforms.uC2.value = st.detail.c2; globeMat.uniforms.uC3.value = st.detail.c3; globeMat.uniforms.uFine.value = st.detail.fine;
    globeMat.uniforms.uHi.value = st.hi; globeMat.uniforms.uTime.value = T;
    globeMat.uniforms.uRipple.value = st.ripple.r; globeMat.uniforms.uRippleA.value = st.ripple.a;
    globeMat.uniforms.uCam.value.copy(cam.pos);
    globeMat.uniforms.uReveal.value = st.reveal; colM.uniforms.uDraw.value = t.tz >= 0 ? 2 : st.draw;
    coastM.uniforms.uOpacity.value = 0.55 * st.reveal; borderM.uniforms.uOpacity.value = 0.28 * st.reveal;
    colM.uniforms.uOpacity.value = Math.min(1.4, 0.55 + 0.55 * st.hi) * (0.85 + 0.15 * Math.sin(T * 5)) * (t.tz >= 0 ? 1 : 1.25 + 1.6 * st.pulse);
    const close = t.td >= 0 ? seg(t.td, 0.6, 1.6) : 0;
    coastM.uniforms.uWidth.value = 1.3 + 1.2 * close; colM.uniforms.uWidth.value = 2.6 + 2.0 * close;
    starM.opacity = st.stars; stars.visible = st.stars > 0.001;
    atmoM.uniforms.uOpacity.value = st.atmo; atmo.visible = st.atmo > 0.001;
    // beam
    const b = st.beam;
    beam.visible = b.on;
    if (b.on) {
      const L = b.head - 1, wide = 1 + 0.6 * b.hit;
      beamCore.scale.set(0.0009 * wide, Math.max(L, 1e-4), 0.0009 * wide);
      beamGlow.scale.set(0.0045 * wide, Math.max(L, 1e-4), 0.0045 * wide);
      beamCoreM.opacity = b.alpha; beamGlowM.uniforms.uOpacity.value = b.alpha * (0.85 + 0.15 * Math.sin(T * 40));
      beamTip.position.set(0, L, 0); beamTip.visible = t.th < 0; beamTip.scale.setScalar(0.035);
      packets.forEach((p, i) => { const f = (i / packets.length + t.tb * 0.9) % 1; p.position.set(0, f * L, 0); p.visible = b.alpha > 0.02; p.material.opacity = b.alpha * Math.sin(Math.PI * f); });
    }
    baseFlare.visible = b.base > 0.001; baseFlare.material.opacity = b.base; baseFlare.scale.setScalar(0.16 + 0.05 * Math.sin(T * 30));
    hitFlash.visible = b.hit > 0.001; hitFlash.position.copy(S).addScaledVector(N, -0.05 * SS); hitFlash.material.opacity = b.hit * 0.8; hitFlash.scale.setScalar(0.08 + 0.32 * o3(1 - b.hit));
    hitRing.visible = b.ring >= 0 && b.ring < 1; hitRing.position.copy(S).addScaledVector(N, -0.05 * SS); hitRing.material.opacity = 1 - b.ring; hitRing.scale.setScalar(0.04 + 0.6 * o3(b.ring));
    orbit.visible = st.orbit > 0.001; orbitM.opacity = 0.32 * st.orbit;
    // satellite
    const s = st.sat;
    sat.root.visible = s.visible;
    if (s.visible) {
      const x = V().crossVectors(s.radial, s.tangent);
      mtx.makeBasis(x, s.radial, s.tangent); qa.setFromRotationMatrix(mtx);
      qp.setFromAxisAngle(X, 90 * DEG * s.pitch); qr.setFromAxisAngle(Z, s.roll);
      sat.root.scale.setScalar(SS); sat.root.position.copy(s.pos); sat.root.quaternion.copy(qa).multiply(qp).multiply(qr);
      if (t.tc >= 0 && t.ta < 0.9) { const j = 0.0012 * st.charge * st.charge; sat.body.position.set(noise1(T * 37) * j, noise1(T * 41 + 3) * j, 0); } else sat.body.position.set(0, 0, 0);
      sat.neon.color.copy(CYAN).multiplyScalar(0.2 + 1.25 * s.power);
      sat.edgeM.opacity = 0.15 + 0.45 * s.power; sat.panelLineM.opacity = 0.2 + 0.5 * s.power;
      sat.lensM.color.copy(CYAN).multiplyScalar(s.lens * (0.4 + 0.6 * s.power));
      sat.glint.material.opacity = 0.3 + 0.4 * s.power;
      sat.thrM.color.copy(ORANGE).multiplyScalar(0.6 + 1.6 * s.power);
      sat.hatches.forEach((hh, i) => { const sg = i ? 1 : -1; hh.position.set((0.026 + 0.03 * s.hatch) * sg, -0.052 + 0.006 * s.hatch, 0.03); });
      sat.cannons.forEach((c, i) => {
        c.mount.rotation.z = (c.s > 0 ? 1 : -1) * lerp(-90, 85, s.arm) * DEG;
        c.b1.position.z = lerp(0.02, 0.11, s.b1);
        c.b2.position.z = lerp(0.005, 0.07, s.b2);
        c.fins.forEach(f => { f.position.x = c.s * (0.022 + 0.012 * s.fins); });
        const k = st.charge, fl = 0.82 + 0.36 * hash(Math.floor(T * 30) + i * 7.1);
        const apagado = i === 1 && !_buffer && t.ta >= 0;
        c.ringM.color.copy(c.col).multiplyScalar(apagado ? 0.12 : 0.45 + 0.5 * (s.power - 0.35) + 2.0 * k * fl);
        const on = k > 0.001 && !apagado;
        c.orb.visible = c.core.visible = c.halo.visible = c.parts.visible = on;
        if (on) {
          const os = (0.01 + 0.04 * Math.pow(k, 1.5)) * fl;
          c.orb.scale.setScalar(os); c.orb.material.color.copy(c.col).multiplyScalar(1.1 + 1.6 * k);
          c.core.scale.setScalar(os * 0.4); c.core.material.color.setScalar(1.4 + 1.4 * k);
          const hp = (T * 2.2) % 1; c.halo.scale.setScalar(os * (1.3 + 1.8 * hp)); c.halo.material.opacity = k * (1 - hp) * 0.6;
          const arr = c.parts.geometry.attributes.position.array;
          for (let p = 0; p < c.NP; p++) { const d = c.dirs[p * 2], sd = c.dirs[p * 2 + 1]; const r = 0.09 * (1 - ((sd + T * 1.7) % 1)); arr[p * 3] = d.x * r; arr[p * 3 + 1] = d.y * r; arr[p * 3 + 2] = d.z * r; }
          c.parts.geometry.attributes.position.needsUpdate = true; c.parts.material.opacity = k;
        }
        c.light.intensity = apagado ? 0 : 0.012 * k * fl;
      });
    }
    // lasers disparados
    {
      const tp = t.tp, u = (tp - (CAP_FIRE + TUNE.laserT0)) / TUNE.laserDur;
      const on = tp >= 0 && t.te < 0 && u >= 0 && u <= 1;
      lasers.forEach((L, i) => {
        const vis = on && (i === 0 || _buffer);
        L.core.visible = L.glow.visible = vis;
        if (!vis) return;
        const aim = C.clone().add(aimDir());
        const from = LENS.clone().addScaledVector(E, L.side * TUNE.laserSep).addScaledVector(U, -TUNE.laserDrop).addScaledVector(N, -0.2);
        const grow = Math.min(1, u * 9), head = from.clone().lerp(aim, grow);
        const dir = head.clone().sub(from), len = Math.max(dir.length(), 1e-5); dir.normalize();
        const alpha = Math.min(1, u * 10) * (1 - seg(u, 0.72, 1)) * (0.85 + 0.15 * Math.sin(T * 60));
        for (const [m, w, k] of [[L.core, TUNE.laserW, 1], [L.glow, TUNE.laserW * 3.5, 0.4]]) {
          m.position.copy(from).addScaledVector(dir, len / 2); m.quaternion.setFromUnitVectors(Y, dir); m.scale.set(w, len, w);
          m.material.opacity = alpha * k;
        }
      });
    }
    // station capsules
    capGroup.visible = st.caps != null;
    if (capGroup.visible) {
      const tp = st.caps, p = V(), q = V();
      for (let i = 0; i < NCAP; i++) {
        const c = caps[i], pos = capPos(i, tp, p);
        c.g.visible = c.k.visible = !!pos;
        if (!pos) { trailPos.fill(0, i * 6, i * 6 + 6); continue; }
        c.g.position.copy(pos); c.k.position.copy(pos);
        const fl = 0.85 + 0.3 * hash(Math.floor(T * 40) + i);
        c.g.scale.setScalar(0.0013 * fl); c.k.scale.setScalar(0.0005);
        const prev = capPos(i, tp - 0.05, q) || CAP_START;
        trailPos.set([pos.x, pos.y, pos.z, prev.x, prev.y, prev.z], i * 6);
        trailCol.set([c.col.r * 2, c.col.g * 2, c.col.b * 2, 0, 0, 0], i * 6);
      }
      trailGeo.attributes.position.needsUpdate = true; trailGeo.attributes.color.needsUpdate = true;
      const lf = tp >= CAP_FIRE && tp < CAP_FIRE + CAP_SPAN + 0.1 ? 0.6 + 0.4 * hash(Math.floor(T * 30)) : 0;
      launchFlash.visible = lf > 0; launchFlash.material.opacity = lf;
    }
    // streaks
    const sa = Math.min(st.diveSpeed / 3.5, 1);
    streaks.visible = t.td >= 0 && t.te < 0 && sa > 0.01;
    if (streaks.visible) {
      const th = Math.tan(cam.fov / 2 * DEG), asp = W / H, len = 0.4 + 5 * sa;
      for (let i = 0; i < NSTK; i++) {
        const q = stkSeed[i], z = -(0.6 + ((q.z + st.travel * 0.55) % 1) * 9);
        const x = Math.cos(q.a) * q.r * asp * th, y = Math.sin(q.a) * q.r * th;
        stkPos.set([x * -z, y * -z, z, x * -z, y * -z, z + len], i * 6);
        const br = sa * (0.5 + q.c) * 1.4, cc = q.c > 0.82 ? ORANGE : CYAN;
        stkCol.set([0, 0, 0, cc.r * br + br * 0.4, cc.g * br + br * 0.4, cc.b * br + br * 0.4], i * 6);
      }
      stk.attributes.position.needsUpdate = true; stk.attributes.color.needsUpdate = true;
    }
    if (bloom) bloom.strength = 0.75 + 0.9 * st.pulse + 0.6 * b.hit + 0.2 * st.charge * (t.tp < 0 ? 1 : 0) + 0.3 * sa + (lasers[0].core.visible ? 0.25 : 0);
  }

  return {
    gpu, lowPower,
    setBox(lon, lat) {
      setBoxLonLat(lon, lat);
      const c = buildCol(); colMesh.geometry.dispose(); colMesh.geometry = fatLineGeometry(c.colSegs, c.colT);
    },
    destroy() {
      dead = true; _inst = null; clearTimeout(lostTimer);
      try { if (composer && composer.dispose) composer.dispose(); } catch (e) { /* ya liberado */ }
      try {
        scene.traverse(o => {
          if (o.geometry) o.geometry.dispose();
          const ms = o.material ? (Array.isArray(o.material) ? o.material : [o.material]) : [];
          ms.forEach(m => { for (const k in m) { const v = m[k]; if (v && v.isTexture) v.dispose(); } m.dispose(); });
        });
      } catch (e) { /* ya liberado */ }
      // el contexto se conserva para la siguiente repeticion; se encoge el lienzo y se sueltan las listas internas
      try { renderer.domElement.removeEventListener('webglcontextlost', onLost); renderer.domElement.removeEventListener('webglcontextrestored', onRestored); } catch (e) { /* ya quitados */ }
      try { renderer.setRenderTarget(null); renderer.renderLists.dispose(); renderer.setSize(1, 1, false); } catch (e) { /* ya liberado */ }
      renderer.domElement.remove(); listeners.clear();
    },
    attach(el) { if (el && renderer.domElement.parentNode !== el) el.appendChild(renderer.domElement); },
    detach(el) { if (renderer.domElement.parentNode === el) el.removeChild(renderer.domElement); },
    get lost() { return lost; },
    get dead() { return dead; },
    subscribe(f) { listeners.add(f); return () => listeners.delete(f); },
    render(T, K) { if (lost) return null; const st = frame(T, K); apply(st); if (composer) composer.render(); else renderer.render(scene, camera); return st; },
    hud(T, K) { return frame(T, K).hud; },
  };
}
