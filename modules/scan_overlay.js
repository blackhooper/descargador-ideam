/* ScanOverlay — escáner de carga que se adapta a cualquier rectángulo.
   Canvas transparente, pointer-events:none → no bloquea los controles del mapa.

   Leaflet:
     const scan = ScanOverlay.leaflet(L, rectangle.getBounds(), { cycle: 1.8 }).addTo(map);
     await fetchStations();          // tu carga real
     await scan.finish();            // fundido de salida (≈450 ms) y se elimina
     addPins();

   Otro motor (Mapbox, OpenLayers…): usa el núcleo en tu propio <canvas>:
     ScanOverlay.drawFrame(ctx, anchoPx, altoPx, segundos, opciones)
*/
(function () {
  var DEFAULTS = {
    cycle: 1.8, sweep: 0.82, direction: 'vertical', color: '#5fe0ff', halo: 'rgba(4,10,16,.6)',
    grid: true, gridSpacing: 16, pings: true, brackets: true, readout: true, trail: 0.32,
    label: 'Buscando estaciones', fade: 450
  };
  function rgb(hex) {
    var h = hex.replace('#', '');
    if (h.length === 3) h = h.split('').map(function (c) { return c + c; }).join('');
    var n = parseInt(h, 16); return [n >> 16 & 255, n >> 8 & 255, n & 255];
  }
  function rnd(a) { var x = Math.sin(a * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); }
  function ease(p) { return (1 - Math.cos(Math.PI * p)) / 2; }
  function inv(u) { return Math.acos(1 - 2 * Math.min(1, Math.max(0, u))) / Math.PI; }

  function drawFrame(ctx, w, h, t, opts) {
    var o = Object.assign({}, DEFAULTS, opts);
    var vert = o.direction !== 'horizontal';
    var L = vert ? h : w, A = vert ? w : h;
    if (L < 2 || A < 2) return;
    var C = o.cycle, S = o.sweep, tc = t % C, k = Math.floor(t / C), ph = tc / C;
    var sweeping = ph < S, sp = ph / S;
    var u = sweeping ? ease(sp) : 1, pos = u * L;
    var env = sweeping ? Math.max(0, Math.min(1, sp / 0.06, (1 - sp) / 0.1)) : 0;
    var c = rgb(o.color);
    var view = o.view || { x0: 0, y0: 0, x1: w, y1: h };
    function col(a) { return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + a.toFixed(3) + ')'; }
    function rect(a0, al, b0, bl) { if (vert) ctx.fillRect(b0, a0, bl, al); else ctx.fillRect(a0, b0, al, bl); }
    function grad(a0, a1) { return vert ? ctx.createLinearGradient(0, a0, 0, a1) : ctx.createLinearGradient(a0, 0, a1, 0); }
    // tiempo desde que la línea pasó por la coordenada normalizada v (continuo entre ciclos)
    function since(v) { var d = tc - inv(v) * S * C; return d < 0 ? d + C : d; }

    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, w, h); ctx.clip();
    ctx.fillStyle = col(0.05); ctx.fillRect(0, 0, w, h);

    if (env > 0) {
      var tl = Math.max(40, L * o.trail), g = grad(pos - tl, pos);
      g.addColorStop(0, col(0)); g.addColorStop(1, col(0.24 * env));
      ctx.fillStyle = g; rect(pos - tl, tl, 0, A);
      var gb = grad(pos - 12, pos + 12);
      gb.addColorStop(0, col(0)); gb.addColorStop(0.5, col(0.35 * env)); gb.addColorStop(1, col(0));
      ctx.fillStyle = gb; rect(pos - 12, 24, 0, A);
    }

    if (o.grid) {
      var vx0 = Math.max(0, view.x0), vy0 = Math.max(0, view.y0), vx1 = Math.min(w, view.x1), vy1 = Math.min(h, view.y1);
      var s = Math.max(o.gridSpacing, Math.sqrt(Math.max(1, (vx1 - vx0) * (vy1 - vy0)) / 5000));
      var B = 10, buckets = [], i, j;
      for (i = 0; i <= B; i++) buckets.push([]);
      for (var y = (Math.floor(vy0 / s) + 0.5) * s; y < vy1; y += s)
        for (var x = (Math.floor(vx0 / s) + 0.5) * s; x < vx1; x += s) {
          var gl = Math.exp(-since((vert ? y : x) / L) / 0.5);
          buckets[Math.round(gl * B)].push(x, y);
        }
      for (i = 0; i <= B; i++) {
        var arr = buckets[i]; if (!arr.length) continue;
        var gv = i / B, r = 0.8 + 1.2 * gv;
        ctx.fillStyle = col(0.16 + 0.8 * gv); ctx.beginPath();
        for (j = 0; j < arr.length; j += 2) ctx.rect(arr[j] - r, arr[j + 1] - r, r * 2, r * 2);
        ctx.fill();
      }
    }

    if (o.pings) {
      var base = Math.max(4, Math.min(36, Math.round(w * h / 12000))), sd = o.seed || 0;
      ctx.lineWidth = 1.25;
      for (var cy = k; cy >= Math.max(0, k - 1); cy--) {
        var cs = sd + cy * 97.31, n = Math.round(base * (0.5 + rnd(cs) * 0.9));
        for (i = 0; i < n; i++) {
          var ps = cs + i * 13.17;
          var px = rnd(ps + 0.11) * w, py = rnd(ps + 0.53) * h;
          var life = 0.55 + rnd(ps + 0.79) * 0.7, maxR = 8 + rnd(ps + 0.97) * 14;
          var age = t - (cy * C + inv((vert ? py : px) / L) * S * C) - rnd(ps + 0.31) * 0.25;
          if (age < 0 || age > life) continue;
          var q = age / life, rr = 2 + maxR * (1 - Math.pow(1 - q, 3));
          ctx.strokeStyle = col(0.85 * (1 - q));
          ctx.beginPath(); ctx.arc(px, py, rr, 0, Math.PI * 2); ctx.stroke();
          ctx.fillStyle = col(1 - 0.75 * q);
          ctx.beginPath(); ctx.arc(px, py, 2, 0, Math.PI * 2); ctx.fill();
        }
      }
    }
    ctx.restore();

    if (env > 0) {
      ctx.save();
      ctx.shadowColor = col(0.9 * env); ctx.shadowBlur = 12; ctx.fillStyle = col(env);
      rect(pos - 1, 2, -7, A + 14);
      ctx.restore();
      ctx.fillStyle = col(env);
      rect(pos - 3, 6, -10, 3); rect(pos - 3, 6, A + 7, 3);
    }

    if (o.brackets) {
      var bl = Math.min(18, w * 0.22, h * 0.22), off = 5, pulse = 0.7 + 0.3 * Math.sin(t * Math.PI * 2 / C);
      ctx.strokeStyle = col(pulse); ctx.lineWidth = 2; ctx.lineCap = 'square';
      ctx.beginPath();
      [[-off, -off, 1, 1], [w + off, -off, -1, 1], [-off, h + off, 1, -1], [w + off, h + off, -1, -1]].forEach(function (p) {
        ctx.moveTo(p[0] + p[2] * bl, p[1]); ctx.lineTo(p[0], p[1]); ctx.lineTo(p[0], p[1] + p[3] * bl);
      });
      ctx.stroke();
    }

    if (typeof o.readout === 'function' && env > 0 && A > 90) {
      var txt = o.readout(u), tx, ty;
      ctx.save();
      ctx.globalAlpha = env;
      ctx.font = '500 11px "IBM Plex Mono", ui-monospace, monospace';
      ctx.lineWidth = 3; ctx.lineJoin = 'round'; ctx.strokeStyle = o.halo; ctx.fillStyle = col(1);
      if (vert) { ctx.textAlign = 'right'; tx = w - 6; ty = pos < 18 ? pos + 15 : pos - 7; }
      else { var right = pos > w - 80; ctx.textAlign = right ? 'right' : 'left'; tx = pos + (right ? -7 : 7); ty = 15; }
      ctx.strokeText(txt, tx, ty); ctx.fillText(txt, tx, ty);
      ctx.restore();
    }
  }

  var css = false;
  function injectCss() {
    if (css) return; css = true;
    var st = document.createElement('style');
    st.textContent = '@keyframes scanOverlayPulse{0%,100%{opacity:1}50%{opacity:.3}}';
    document.head.appendChild(st);
  }

  var Cls = null;
  function leafletClass(L) {
    if (Cls) return Cls;
    var EV = 'move zoomend viewreset resize';
    Cls = L.Layer.extend({
      initialize: function (bounds, opts) { this._b = L.latLngBounds(bounds); this._o = Object.assign({ seed: Math.random() * 1e4 }, DEFAULTS, opts); },
      setOptions: function (opts) { Object.assign(this._o, opts); if (this._map) this._reset(); return this; },
      setBounds: function (b) { this._b = L.latLngBounds(b); if (this._map) this._reset(); return this; },
      onAdd: function (map) {
        injectCss();
        var pane = map.getPane('scanPane') || map.createPane('scanPane');
        pane.style.zIndex = 450; pane.style.pointerEvents = 'none';
        var el = this._el = L.DomUtil.create('div', 'leaflet-zoom-hide', pane);
        el.style.cssText = 'position:absolute;left:0;top:0;pointer-events:none;opacity:0;transition:opacity ' + this._o.fade + 'ms ease;';
        this._cv = L.DomUtil.create('canvas', '', el);
        this._cv.style.cssText = 'position:absolute;left:0;top:0;';
        this._ctx = this._cv.getContext('2d');
        this._lb = L.DomUtil.create('div', '', el);
        this._lb.style.cssText = 'position:absolute;display:flex;align-items:center;gap:7px;padding:4px 9px 4px 8px;border-radius:3px;background:rgba(9,13,19,.84);color:#e9f1f8;font:500 10.5px/1.25 "IBM Plex Mono",ui-monospace,monospace;letter-spacing:.08em;text-transform:uppercase;white-space:nowrap;';
        this._dot = L.DomUtil.create('span', '', this._lb);
        this._dot.style.cssText = 'width:6px;height:6px;border-radius:50%;animation:scanOverlayPulse 1s ease-in-out infinite;';
        this._txt = L.DomUtil.create('span', '', this._lb);
        map.on(EV, this._reset, this);
        this._t0 = performance.now();
        this._reset(); this._tick();
        requestAnimationFrame(function () { requestAnimationFrame(function () { el.style.opacity = 1; }); });
      },
      onRemove: function (map) {
        cancelAnimationFrame(this._raf); map.off(EV, this._reset, this); L.DomUtil.remove(this._el);
      },
      finish: function () {
        var self = this;
        return new Promise(function (res) {
          if (!self._map) return res();
          self._el.style.opacity = 0;
          setTimeout(function () { if (self._map) self._map.removeLayer(self); res(); }, self._o.fade);
        });
      },
      _reset: function () {
        var m = this._map, o = this._o, pad = 24;
        var nw = m.latLngToLayerPoint(this._b.getNorthWest()), se = m.latLngToLayerPoint(this._b.getSouthEast());
        var w = se.x - nw.x, h = se.y - nw.y;
        var tl = m.containerPointToLayerPoint([0, 0]), br = m.containerPointToLayerPoint(m.getSize());
        var x0 = Math.round(Math.max(nw.x - pad, tl.x)), y0 = Math.round(Math.max(nw.y - pad, tl.y));
        var x1 = Math.min(se.x + pad, br.x), y1 = Math.min(se.y + pad, br.y);
        var cw = Math.max(0, Math.ceil(x1 - x0)), ch = Math.max(0, Math.ceil(y1 - y0));
        var dpr = Math.min(2, window.devicePixelRatio || 1);
        L.DomUtil.setPosition(this._el, L.point(x0, y0));
        if (this._cv.width !== cw * dpr || this._cv.height !== ch * dpr) {
          this._cv.width = cw * dpr; this._cv.height = ch * dpr;
          this._cv.style.width = cw + 'px'; this._cv.style.height = ch + 'px';
        }
        this._g = { w: w, h: h, ox: nw.x - x0, oy: nw.y - y0, cw: cw, ch: ch, dpr: dpr,
          view: { x0: x0 - nw.x, y0: y0 - nw.y, x1: x1 - nw.x, y1: y1 - nw.y } };
        this._lb.style.display = o.label ? 'flex' : 'none';
        this._lb.style.left = (nw.x - x0) + 'px'; this._lb.style.top = (nw.y - y0 - 32) + 'px';
        this._dot.style.background = o.color; this._txt.textContent = o.label || '';
      },
      _readout: function () {
        var o = this._o, b = this._b;
        if (typeof o.readout === 'function') return o.readout;
        if (!o.readout) return null;
        var N = b.getNorth(), S = b.getSouth(), W = b.getWest(), E = b.getEast();
        if (o.direction === 'horizontal') return function (u) { var g = W + u * (E - W); return Math.abs(g).toFixed(3) + '°' + (g < 0 ? 'O' : 'E'); };
        return function (u) { var a = N - u * (N - S); return Math.abs(a).toFixed(3) + '°' + (a >= 0 ? 'N' : 'S'); };
      },
      _tick: function () {
        var self = this;
        this._raf = requestAnimationFrame(function () { self._tick(); });
        var g = this._g; if (!g || !g.cw || !g.ch) return;
        var ctx = this._ctx;
        ctx.setTransform(g.dpr, 0, 0, g.dpr, 0, 0);
        ctx.clearRect(0, 0, g.cw, g.ch);
        ctx.translate(g.ox, g.oy);
        drawFrame(ctx, g.w, g.h, (performance.now() - this._t0) / 1000,
          Object.assign({}, this._o, { view: g.view, readout: this._readout() }));
      }
    });
    return Cls;
  }

  window.ScanOverlay = {
    defaults: DEFAULTS,
    drawFrame: drawFrame,
    leaflet: function (L, bounds, opts) { return new (leafletClass(L))(bounds, opts); }
  };
})();
