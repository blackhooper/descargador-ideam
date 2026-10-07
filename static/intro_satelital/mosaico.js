// Primer plano de la intro: mosaico de imagenes de satelite (Esri) centrado en el cuadro del usuario.
// El cuadro de la intro representa justo la cuenca: la imagen se escala para que su caja envolvente
// ocupe el cuadro (a la escala a la que la intro muestra la imagen en el momento de resaltarlo).
const S_IMG = 1.2;          // la intro agranda la imagen 1,25 -> 1,2 durante el primer plano
const CW = 960, CH = 540;   // el lienzo se muestra al doble (1920x1080)
const URL_TESELA = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}';

// Tamano (en pixeles de 1920x1080) del cuadro que dibuja la intro para esta cuenca
export function cajaDe(bbox) {
  const [x0, y0, x1, y1] = bbox, lat = (y0 + y1) / 2;
  const dx = Math.max(1, (x1 - x0) * 111320 * Math.cos(lat * Math.PI / 180)), dy = Math.max(1, (y1 - y0) * 110540);
  const r = dx / dy;
  let bw, bh;
  if (r >= 1.5) { bw = 420; bh = 420 / r; } else { bh = 280; bw = 280 * r; }
  return { bw: Math.max(bw, 90), bh: Math.max(bh, 60), dx, dy };
}

function cargar(url, ms) {
  return new Promise(ok => {
    const img = new Image();
    img.crossOrigin = 'anonymous';
    const t = setTimeout(() => { img.src = ''; ok(null); }, ms);
    img.onload = () => { clearTimeout(t); ok(img); };
    img.onerror = () => { clearTimeout(t); ok(null); };
    img.src = url;
  });
}

// Devuelve {url} (imagen JPEG) o null si no se pudo armar (sin red, sin permiso de lectura, demasiadas imagenes...)
export async function crearMosaico(bbox) {
  const { bw, dx } = cajaDe(bbox);
  const lon = (bbox[0] + bbox[2]) / 2, lat = (bbox[1] + bbox[3]) / 2, cosLat = Math.cos(lat * Math.PI / 180);
  const mppLienzo = 2 * S_IMG * dx / bw;                     // metros de terreno por pixel del lienzo
  let z = Math.floor(Math.log2(156543.03392 * cosLat / mppLienzo));
  z = Math.min(15, Math.max(3, z));
  const f = (156543.03392 * cosLat / Math.pow(2, z)) / mppLienzo;   // tamano en el lienzo de un pixel de imagen
  const n = Math.pow(2, z), sin = Math.sin(lat * Math.PI / 180);
  const wx = (lon + 180) / 360 * n * 256, wy = (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * n * 256;
  const mx = CW / 2 / f, my = CH / 2 / f;
  const tx0 = Math.floor((wx - mx) / 256), tx1 = Math.floor((wx + mx) / 256);
  const ty0 = Math.floor((wy - my) / 256), ty1 = Math.floor((wy + my) / 256);
  const cuantas = (tx1 - tx0 + 1) * (ty1 - ty0 + 1);
  if (cuantas > 30 || cuantas < 1) return null;
  const cv = document.createElement('canvas');
  cv.width = CW; cv.height = CH;
  const cx = cv.getContext('2d');
  cx.fillStyle = '#0b1a14'; cx.fillRect(0, 0, CW, CH);
  let falla = 0;
  const trabajos = [];
  for (let ty = ty0; ty <= ty1; ty++) {
    for (let tx = tx0; tx <= tx1; tx++) {
      if (ty < 0 || ty >= n) continue;
      const txw = ((tx % n) + n) % n;
      const url = URL_TESELA.replace('{z}', z).replace('{y}', ty).replace('{x}', txw);
      trabajos.push(cargar(url, 7000).then(img => {
        if (!img) { falla++; return; }
        cx.drawImage(img, CW / 2 + (tx * 256 - wx) * f, CH / 2 + (ty * 256 - wy) * f, 256 * f + 1, 256 * f + 1);
      }));
    }
  }
  await Promise.all(trabajos);
  if (falla > cuantas / 2) return null;
  try { return { url: cv.toDataURL('image/jpeg', 0.84), real: true }; } catch (e) { return null; }
}
