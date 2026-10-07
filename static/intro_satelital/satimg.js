// Imagen "satelital" del primer plano de la intro (terreno procedural, sin red): se dibuja una sola vez
const S = 420, SEG = 300, CELL = S / SEG, N1 = SEG + 1;
const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v);
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const smooth = (a, b, x) => { const t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); };
const RAMP = [[0, [176, 198, 150]], [1, [238, 232, 222]]];
function rng(seed) {
  let a = seed >>> 0;
  return () => { a = (a + 0x6D2B79F5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}
function perlin(seed) {
  const r = rng(seed), p = new Uint8Array(512), perm = new Uint8Array(256);
  for (let i = 0; i < 256; i++) perm[i] = i;
  for (let i = 255; i > 0; i--) { const j = (r() * (i + 1)) | 0; const t = perm[i]; perm[i] = perm[j]; perm[j] = t; }
  for (let i = 0; i < 512; i++) p[i] = perm[i & 255];
  const g = (h, x, y) => { switch (h & 7) { case 0: return x + y; case 1: return -x + y; case 2: return x - y; case 3: return -x - y; case 4: return x; case 5: return -x; case 6: return y; default: return -y; } };
  const f = t => t * t * t * (t * (t * 6 - 15) + 10);
  return (x, y) => {
    const X = Math.floor(x), Y = Math.floor(y), xf = x - X, yf = y - Y, xi = X & 255, yi = Y & 255;
    const u = f(xf), v = f(yf);
    const aa = p[p[xi] + yi], ab = p[p[xi] + yi + 1], ba = p[p[xi + 1] + yi], bb = p[p[xi + 1] + yi + 1];
    const g1 = g(aa, xf, yf), x1 = g1 + u * (g(ba, xf - 1, yf) - g1);
    const g2 = g(ab, xf, yf - 1), x2 = g2 + u * (g(bb, xf - 1, yf - 1) - g2);
    return (x1 + v * (x2 - x1)) * 0.7;
  };
}
function hash2(x, y) { let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263)) | 0; h = Math.imul(h ^ (h >>> 13), 1274126177); h ^= h >>> 16; return (h >>> 0) / 4294967296; }
function vnoise(x, y) {
  const X = Math.floor(x), Y = Math.floor(y); let fx = x - X, fy = y - Y;
  fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
  const a = hash2(X, Y), b = hash2(X + 1, Y), c = hash2(X, Y + 1), d = hash2(X + 1, Y + 1);
  return a + (b - a) * fx + (c - a) * fy + (a - b - c + d) * fx * fy;
}

function buildGrid(seed) {
  const n = perlin(seed), n2 = perlin(seed * 7 + 3);
  const h = new Float32Array(N1 * N1);
  let minH = Infinity, maxH = -Infinity;
  for (let iz = 0; iz < N1; iz++) for (let ix = 0; ix < N1; ix++) {
    const x = -S / 2 + ix * CELL, z = -S / 2 + iz * CELL;
    let base = 0, a = 1, f = 0.005;
    for (let o = 0; o < 4; o++) { base += n(x * f, z * f) * a; a *= 0.5; f *= 2.03; }
    let ridge = 0, w = 1; a = 1; f = 0.013;
    for (let o = 0; o < 5; o++) { let r = 1 - Math.abs(n2(x * f + 11.3, z * f - 4.7)); r *= r; r *= w; w = clamp01(r * 1.8); ridge += r * a; a *= 0.5; f *= 2.1; }
    const mask = smooth(-0.3, 0.35, n(x * 0.0042 + 40, z * 0.0042 - 25) + 0.5 - Math.hypot(x - 15, z - 10) / 190);
    const v = 4 + base * 7 + mask * (5 + ridge * 36);
    h[iz * N1 + ix] = v; if (v < minH) minH = v; if (v > maxH) maxH = v;
  }
  const shade = new Float32Array(N1 * N1), grad = new Float32Array(N1 * N1);
  const L = (() => { const x = -0.8, y = 0.62, z = -0.15, n = Math.hypot(x, y, z); return { x: x / n, y: y / n, z: z / n }; })();
  for (let iz = 0; iz < N1; iz++) for (let ix = 0; ix < N1; ix++) {
    const i = iz * N1 + ix;
    const gx = (h[iz * N1 + Math.min(ix + 1, SEG)] - h[iz * N1 + Math.max(ix - 1, 0)]) / (2 * CELL);
    const gz = (h[Math.min(iz + 1, SEG) * N1 + ix] - h[Math.max(iz - 1, 0) * N1 + ix]) / (2 * CELL);
    const len = Math.sqrt(gx * gx + gz * gz + 1);
    shade[i] = Math.max(0, (-gx * L.x + L.y - gz * L.z) / len);
    grad[i] = Math.sqrt(gx * gx + gz * gz);
  }
  const height = (x, z) => {
    const gx = clamp((x + S / 2) / CELL, 0, SEG - 1e-4), gz = clamp((z + S / 2) / CELL, 0, SEG - 1e-4);
    const ix = gx | 0, iz = gz | 0, fx = gx - ix, fz = gz - iz, i = iz * N1 + ix;
    return (h[i] * (1 - fx) + h[i + 1] * fx) * (1 - fz) + (h[i + N1] * (1 - fx) + h[i + N1 + 1] * fx) * fz;
  };
  return { h, shade, grad, minH, maxH, height };
}

function buildTexture(grid, style, W = 1536) {
  const cv = document.createElement('canvas'); cv.width = cv.height = W;
  const ctx = cv.getContext('2d'), img = ctx.createImageData(W, W), d = img.data;
  const { h, shade, grad, minH, maxH } = grid, span = maxH - minH, pxw = S / W, topo = style === 'topo';
  for (let py = 0; py < W; py++) {
    const z = -S / 2 + (py + 0.5) * pxw, gz = Math.min((z + S / 2) / CELL, SEG - 1e-4), iz = gz | 0, fz = gz - iz;
    for (let px = 0; px < W; px++) {
      const x = -S / 2 + (px + 0.5) * pxw, gx = Math.min((x + S / 2) / CELL, SEG - 1e-4), ix = gx | 0, fx = gx - ix;
      const i0 = iz * N1 + ix, i1 = i0 + 1, i2 = i0 + N1, i3 = i2 + 1;
      const w0 = (1 - fx) * (1 - fz), w1 = fx * (1 - fz), w2 = (1 - fx) * fz, w3 = fx * fz;
      const H = h[i0] * w0 + h[i1] * w1 + h[i2] * w2 + h[i3] * w3;
      const sh = shade[i0] * w0 + shade[i1] * w1 + shade[i2] * w2 + shade[i3] * w3;
      const g = grad[i0] * w0 + grad[i1] * w1 + grad[i2] * w2 + grad[i3] * w3;
      const hn = (H - minH) / span, sl = 1 - 1 / Math.sqrt(1 + g * g);
      let r, gg, b;
      if (!topo) {
        const m1 = vnoise(x * 0.08, z * 0.08), m2 = vnoise(x * 0.31 + 50, z * 0.31), m3 = vnoise(x * 1.4, z * 1.4 + 20);
        const tv = smooth(0.1, 0.5, sl * 2.4 + (m1 - 0.5) * 0.35 + (m2 - 0.5) * 0.45 + hn * 0.25 - 0.08);
        let cr = 98 + (m1 - 0.5) * 18 + (m3 - 0.5) * 10, cg = 96 + (m1 - 0.5) * 14 + (m3 - 0.5) * 8, cb = 64 + (m1 - 0.5) * 8;
        cr += (40 + m2 * 16 - cr) * tv; cg += (54 + m2 * 16 - cg) * tv; cb += (32 + m2 * 8 - cb) * tv;
        const tr = smooth(0.55, 0.95, sl * 1.2 + hn * 0.5 + (m3 - 0.5) * 0.3) * 0.75;
        cr += (106 - cr) * tr; cg += (88 - cg) * tr; cb += (66 - cb) * tr;
        const lit = 0.36 + 1.05 * sh + (m3 - 0.5) * 0.08 + (m2 - 0.5) * 0.06;
        r = cr * lit; gg = cg * lit; b = cb * lit;
      } else {
        let k = 0; while (k < RAMP.length - 2 && hn > RAMP[k + 1][0]) k++;
        const [ta, ca] = RAMP[k], [tb, cbb] = RAMP[k + 1], tt = clamp01((hn - ta) / (tb - ta));
        const lit = 0.86 + 0.55 * (sh - 0.5);
        r = (ca[0] + (cbb[0] - ca[0]) * tt) * lit; gg = (ca[1] + (cbb[1] - ca[1]) * tt) * lit; b = (ca[2] + (cbb[2] - ca[2]) * tt) * lit;
        const f = H / 2.5, rf = Math.round(f), dd = Math.abs(f - rf), major = ((rf % 4) + 4) % 4 === 0;
        const lw = g * pxw / 2.5 + 1e-4;
        const line = (1 - smooth(0.5, 1.3, dd / lw / (major ? 1.7 : 1))) * (major ? 0.8 : 0.42);
        r += (104 - r) * line; gg += (74 - gg) * line; b += (48 - b) * line;
      }
      const o = (py * W + px) * 4; d[o] = r; d[o + 1] = gg; d[o + 2] = b; d[o + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return cv;
}



export function satelliteImage(W = 960, seed = 1234) { return buildTexture(buildGrid(seed), 'sat', W).toDataURL('image/jpeg', 0.88); }
