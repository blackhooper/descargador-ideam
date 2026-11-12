
(function () {
  var V = "__V__";
  var w = window, d = document, raiz = d.documentElement;
  if (w.__y2kUI && w.__y2kUI.v === V) return;
  if (w.__y2kUI && w.__y2kUI.parar) w.__y2kUI.parar();
  var vivo = true, ciclos = [], T0 = w.performance.now();
  var ICONO_ALERTA = __ICONO_ALERTA__, MOVIL = __MOVIL__, VIDRIO = __VIDRIO__;
  var leer = function (k) { try { return w.localStorage.getItem("y2k_" + k); } catch (e) { return null; } };
  var guardar = function (k, v) { try { w.localStorage.setItem("y2k_" + k, v); } catch (e) {} };
  var css = function (n) { return w.getComputedStyle(raiz).getPropertyValue(n).trim(); };
  var num = function (n, defecto) { var v = parseFloat(css(n)); return isNaN(v) ? defecto : v; };
  var esLite = function () { return css("--y2k-lite") === "1"; };
  var menosMovimiento = function () { return !!(w.matchMedia && w.matchMedia("(prefers-reduced-motion: reduce)").matches); };
  var esMovil = function () { return !!(w.matchMedia && w.matchMedia(MOVIL).matches); };
  var pantalla = function () { var m = d.querySelector(".y2k-pantalla"); return m ? m.getAttribute("data-p") : ""; };
  var G = 10, MAX_PITCH = 70;

  // ---------- panel (escritorio) y tarjeta de la consulta (celular) ----------
  raiz.setAttribute("data-y2k-panel", leer("panel") === "cerrado" ? "cerrado" : "abierto");
  function estadoPanel() { return raiz.getAttribute("data-y2k-panel") || "abierto"; }
  function ponerPanel(v) { raiz.setAttribute("data-y2k-panel", v); guardar("panel", v); sincronizar(); distribuir(); setTimeout(distribuir, 380); }
  // en el celular la consulta arranca cerrada: se abre y se cierra con el boton "Consulta" (o tocando el mapa)
  function hojaAbierta() { return raiz.getAttribute("data-y2k-hoja") === "abierta"; }
  function ponerHoja(abierta) {
    raiz.setAttribute("data-y2k-hoja", abierta ? "abierta" : "cerrada");
    // con la consulta abierta el 3D no gira solo (el telefono no dibuja de mas debajo de la tarjeta)
    if (abierta) w.__y2kParaVuelta = w.performance.now();
    // la escala y los creditos del mapa se apartan al abrir y vuelven cuando la tarjeta ya se cerro
    if (abierta) marcarIframe(); else setTimeout(marcarIframe, 300);
    sincronizar(); distribuir(); setTimeout(distribuir, 380);
  }
  function abrirPanel() {
    if (esMovil()) { if (!hojaAbierta()) ponerHoja(true); }
    else if (estadoPanel() !== "abierto") ponerPanel("abierto");
  }
  // la escala y los creditos de Leaflet viven en el iframe del mapa: se apartan con la consulta abierta
  function marcarIframe() {
    var doc = docMapa();
    if (doc) doc.documentElement.classList.toggle("y2k-hoja-abierta", esMovil() && hojaAbierta() && pantalla() === "mapa");
  }

  function sincronizar() {
    var p = pantalla(), antes = raiz.getAttribute("data-y2k-p");
    if (p && antes !== p) {
      raiz.setAttribute("data-y2k-p", p);
      if (p !== "mapa" && hojaAbierta()) raiz.setAttribute("data-y2k-hoja", "cerrada");   // al volver al mapa, cerrada
      // escritorio: al llegar al mapa desde Parametros la consulta empieza cerrada; se abre con su boton
      if (p === "mapa" && antes === "parametros" && !esMovil()) { raiz.setAttribute("data-y2k-panel", "cerrado"); guardar("panel", "cerrado"); }
    }
    var abierto = estadoPanel() === "abierto";
    // consulta cerrada: inerte (sin foco ni toques). Algunos elementos de Streamlit se fuerzan visibles y, aunque
    // transparentes, recibian clics y el foco del teclado
    var panelEl = d.querySelector(".st-key-y2k_panel");
    if (panelEl) { var inerte = esMovil() ? !hojaAbierta() : !abierto; if (panelEl.inert !== inerte) panelEl.inert = inerte; }
    // el CSS aligera la consulta del celular cuando debajo esta el 3D
    var con3d = lienzo3d() ? "1" : "0";
    if (raiz.getAttribute("data-y2k-3d") !== con3d) raiz.setAttribute("data-y2k-3d", con3d);
    sincronizarFicha();
    d.querySelectorAll("[data-y2k-panel-btn]").forEach(function (b) {
      var txt = abierto ? "Ocultar la consulta" : "Mostrar la consulta";
      b.setAttribute("aria-expanded", abierto ? "true" : "false"); b.setAttribute("aria-label", txt); b.title = txt;
    });
    var h = hojaAbierta() ? "true" : "false";
    d.querySelectorAll("[data-y2k-consulta]").forEach(function (b) { if (b.getAttribute("aria-expanded") !== h) b.setAttribute("aria-expanded", h); });
    if (!d.querySelector(".y2k-cierre-hoja")) {
      var velo = d.createElement("div"); velo.className = "y2k-cierre-hoja"; velo.setAttribute("aria-hidden", "true"); d.body.appendChild(velo);
    }
    // en Parametros y Exportacion el mapa queda detras: sin foco ni clics
    var esc = d.querySelector(".st-key-y2k_escenario");
    if (esc) { var fuera = p === "parametros" || p === "exportar"; if (esc.inert !== fuera) esc.inert = fuera; }
    // los iconos de Streamlit son texto ("bolt", "delete"...): que no se lean como parte del nombre del boton
    d.querySelectorAll('button [data-testid="stIconMaterial"]:not([aria-hidden]), summary [data-testid="stIconMaterial"]:not([aria-hidden])')
      .forEach(function (i) { i.setAttribute("aria-hidden", "true"); });
    // la leyenda es un desplegable: empieza cerrada y se cierra al tocar fuera (alPulsar)
    d.querySelectorAll("details.y2k-leyenda").forEach(function (det) {
      if (det.__y2kLey) return;
      det.__y2kLey = true;
      det.addEventListener("toggle", function () { setTimeout(distribuir, 30); });
    });
    traducirCargador();
    traducirListas();
    estadoArea();
    estadoCapas();
    esperaMapa();
  }

  // ---------- ficha de la estacion elegida: pildora cerrada que se despliega ----------
  var fichaCodigo = null;
  function fichaAbierta() { return raiz.getAttribute("data-y2k-ficha") === "abierta"; }
  function ponerFicha(abierta) {
    raiz.setAttribute("data-y2k-ficha", abierta ? "abierta" : "cerrada");
    sincronizarFicha(); distribuir(); setTimeout(distribuir, 60);
  }
  function sincronizarFicha() {
    var pil = d.querySelector(".y2k-ficha-pil[data-codigo]"), cod = pil ? pil.getAttribute("data-codigo") : "";
    // otra estacion (o ninguna): la ficha vuelve a cerrarse
    if (cod !== fichaCodigo) { fichaCodigo = cod; if (fichaAbierta()) raiz.setAttribute("data-y2k-ficha", "cerrada"); }
    var v = fichaAbierta() ? "true" : "false";
    d.querySelectorAll("[data-y2k-ficha-btn]").forEach(function (b) { if (b.getAttribute("aria-expanded") !== v) b.setAttribute("aria-expanded", v); });
  }

  // ---------- un toque fuera de un desplegable lo cierra (menus, leyenda, ficha y menus de Streamlit) ----------
  function alPulsar(ev) {
    var t = ev && ev.target && ev.target.closest ? ev.target : null;
    d.querySelectorAll("details.y2k-leyenda[open], .y2k-aviso3d details[open]").forEach(function (det) { if (!t || !det.contains(t)) det.open = false; });
    if (fichaAbierta() && !(t && t.closest(".st-key-y2k_ficha"))) ponerFicha(false);
    if (!t || !t.closest(".y2k-grupo")) cerrarMenus(null);
  }
  d.addEventListener("pointerdown", alPulsar, true);
  // los toques en el mapa 2D caen en su iframe y no llegan a esta pagina: se reenvian. Los menus de Streamlit
  // (Ajustes, buffer, filtro) se cierran con un clic fuera de ellos
  function pulsadoEnMapa() {
    alPulsar(null);
    if (d.querySelector('[data-testid="stPopoverBody"]')) d.body.dispatchEvent(new w.MouseEvent("click", {bubbles: true}));
  }

  // Textos de las listas desplegables de Streamlit (vienen en ingles): el buscador de estaciones permite elegir
  // todas las coincidencias de una busqueda
  function traducirListas() {
    d.querySelectorAll('[role="listbox"], [data-baseweb="popover"]').forEach(function (z) {
      var it = d.createTreeWalker(z, NodeFilter.SHOW_TEXT), n, t;
      while ((n = it.nextNode())) {
        t = n.nodeValue.trim();
        if (t === "Select all") n.nodeValue = "Elegir todas";
        else if (t === "No results") n.nodeValue = "Sin resultados";
        else if (/^Select \d+ matches$/.test(t)) n.nodeValue = t.replace(/^Select (\d+) matches$/, "Elegir las $1 coincidencias");
      }
    });
    d.querySelectorAll('[aria-label="Clear value"]').forEach(function (b) { b.setAttribute("aria-label", "Borrar"); });
    d.querySelectorAll('[aria-label="Clear all"]').forEach(function (b) { b.setAttribute("aria-label", "Quitar todas"); });
  }

  // Textos del cargador de archivos de Streamlit (vienen en ingles)
  var TEXTOS = {"Drag and drop files here": "Arrastra los archivos aquí", "Drag and drop file here": "Arrastra el archivo aquí",
                "Browse files": "Elegir archivos", "Upload": "Elegir archivos"};
  function traducirCargador() {
    d.querySelectorAll('[data-testid="stFileUploaderDropzone"]').forEach(function (z) {
      var it = d.createTreeWalker(z, NodeFilter.SHOW_TEXT), n, t;
      while ((n = it.nextNode())) {
        t = n.nodeValue.trim();
        if (TEXTOS[t]) n.nodeValue = n.nodeValue.replace(t, TEXTOS[t]);
        else if (/^Limit \d+\s?MB per file/.test(t)) n.nodeValue = t.replace(/^Limit (\d+)\s?MB per file/, "Hasta $1 MB por archivo");
        else if (/^\d+\s?MB per file/.test(t)) n.nodeValue = t.replace(/^(\d+)\s?MB per file/, "Hasta $1 MB por archivo");
      }
    });
  }

  // ---------- "Seleccionar area en el mapa": espera a que el mapa 2D haya cargado ----------
  var mapaVisto = 0;
  function mapaListo() { return raiz.getAttribute("data-y2k-mapa-listo") === "1"; }
  // listo para pasar al mapa: lo dice Python (lista, variable, fechas y series) y el navegador (el mapa cargo)
  function ctaListo() {
    var m = d.querySelector(".y2k-cta-listo");
    return mapaListo() && !!m && m.getAttribute("data-listo") === "1";
  }
  function esperaMapa() {
    var v = ctaListo() ? "false" : "true";
    d.querySelectorAll(".st-key-ir_mapa button").forEach(function (b) {
      if (b.getAttribute("aria-disabled") !== v) b.setAttribute("aria-disabled", v);
    });
  }
  function parpadear(b) {
    b.classList.remove("y2k-parpadeo"); void b.offsetWidth; b.classList.add("y2k-parpadeo");
    clearTimeout(b.__y2kParpadeo);
    b.__y2kParpadeo = setTimeout(function () { b.classList.remove("y2k-parpadeo"); }, 950);
  }
  function revisarMapaListo() {
    if (mapaListo()) return;
    var win = winMapa(), map = win && win.map, ahora = w.performance.now();
    if (map && !mapaVisto) mapaVisto = ahora;
    var teselas = map && map.__y2kTeselas && map.__y2kTeselas.lista.some(function (x) { return x.ok; });
    // listo: llego alguna tesela; o el mapa existe hace 6 s (red lenta); o pasaron 15 s (el mapa no pudo cargar:
    // no se bloquea el boton para siempre)
    if (teselas || (mapaVisto && ahora - mapaVisto > 6000) || ahora - T0 > 15000) { raiz.setAttribute("data-y2k-mapa-listo", "1"); esperaMapa(); }
  }

  // ---------- menus de la capsula de herramientas ----------
  function cerrarMenus(excepto) {
    d.querySelectorAll("[data-y2k-menu]").forEach(function (b) {
      if (b === excepto) return;
      var m = d.querySelector('[data-y2k-menu-de="' + b.getAttribute("data-y2k-menu") + '"]');
      if (m && !m.hidden) { m.hidden = true; b.setAttribute("aria-expanded", "false"); }
    });
  }
  function alternarMenu(b, enfocar) {
    var m = d.querySelector('[data-y2k-menu-de="' + b.getAttribute("data-y2k-menu") + '"]');
    if (!m) return;
    var abrir = m.hidden;
    cerrarMenus(b);
    m.hidden = !abrir; b.setAttribute("aria-expanded", abrir ? "true" : "false");
    if (abrir) {
      estadoArea(); estadoCapas();
      if (enfocar) { var p = m.querySelector('button:not([aria-disabled="true"])'); if (p) try { p.focus({preventScroll: true}); } catch (e) {} }
    }
  }

  var SELECTORES = "[data-y2k-panel-btn],[data-y2k-consulta],[data-y2k-hoja-cerrar],[data-y2k-cam],[data-y2k-dibujar],[data-y2k-area]," +
    "[data-y2k-subir],[data-y2k-editar],[data-y2k-borrar],[data-y2k-capa],[data-y2k-zoom],[data-y2k-menu],[data-y2k-2d],[data-y2k-ver],[data-y2k-pulsar]," +
    "[data-y2k-ficha-btn],[data-y2k-ficha-quitar]";
  function alClic(ev) {
    var t = ev.target && ev.target.closest ? ev.target : null;
    // el boton principal de Parametros no avanza hasta que todo esta listo: parpadea en rojo
    var cta = t && t.closest(".st-key-ir_mapa button");
    if (cta && !ctaListo()) { ev.preventDefault(); ev.stopPropagation(); parpadear(cta); return; }
    // al pasar al mapa (escritorio) la consulta llega cerrada: se marca antes de que aparezca, sin parpadeo
    if (cta && !esMovil()) { raiz.setAttribute("data-y2k-panel", "cerrado"); guardar("panel", "cerrado"); }
    // con la consulta abierta (celular), tocar el mapa la cierra; elegir 2D o 3D tambien (para ver el mapa)
    if (t && t.closest(".y2k-cierre-hoja")) { ev.preventDefault(); ponerHoja(false); return; }
    if (t && esMovil() && hojaAbierta() && t.closest(".st-key-vista")) ponerHoja(false);
    var b = t ? t.closest(SELECTORES) : null;
    if (!t || !t.closest(".y2k-grupo")) cerrarMenus(null);
    if (!b) return;
    if (b.getAttribute("aria-disabled") === "true" && !b.hasAttribute("data-y2k-area")) return;
    // las opciones de camara se pulsan varias veces seguidas: su menu sigue abierto
    if (b.closest(".y2k-menu") && !b.hasAttribute("data-y2k-cam")) cerrarMenus(null);
    if (b.hasAttribute("data-y2k-menu")) { alternarMenu(b, ev.detail === 0); return; }
    if (b.hasAttribute("data-y2k-panel-btn")) ponerPanel(estadoPanel() === "abierto" ? "cerrado" : "abierto");
    else if (b.hasAttribute("data-y2k-consulta")) ponerHoja(!hojaAbierta());
    else if (b.hasAttribute("data-y2k-hoja-cerrar")) { ponerHoja(false); var c = d.querySelector("[data-y2k-consulta]"); if (c) try { c.focus({preventScroll: true}); } catch (e) {} }
    else if (b.hasAttribute("data-y2k-pulsar")) pulsarOculto(b.getAttribute("data-y2k-pulsar"));
    else if (b.hasAttribute("data-y2k-cam")) camara(b.getAttribute("data-y2k-cam"));
    else if (b.hasAttribute("data-y2k-dibujar")) dibujarRectangulo();
    else if (b.hasAttribute("data-y2k-area")) usarAreaVisible(b);
    else if (b.hasAttribute("data-y2k-subir")) pulsarOculto("y2k_subir");
    else if (b.hasAttribute("data-y2k-editar")) editarArea();
    else if (b.hasAttribute("data-y2k-borrar")) borrarArea();
    else if (b.hasAttribute("data-y2k-capa")) ponerCapa(b.getAttribute("data-y2k-capa"));
    else if (b.hasAttribute("data-y2k-zoom")) zoom(b.getAttribute("data-y2k-zoom"));
    else if (b.hasAttribute("data-y2k-2d")) pulsarOculto("y2k_pasar2d");
    else if (b.hasAttribute("data-y2k-ver")) abrirPanel();
    else if (b.hasAttribute("data-y2k-ficha-btn")) ponerFicha(!fichaAbierta());
    else if (b.hasAttribute("data-y2k-ficha-quitar")) { raiz.setAttribute("data-y2k-ficha", "cerrada"); pulsarOculto("quitar_sel"); }
  }
  d.addEventListener("click", alClic, true);

  // ---------- barras de desplazamiento (escritorio): visibles mientras se desplaza o con el puntero sobre la barra ----------
  var DESPLAZABLES = '.st-key-y2k_cuerpo,.st-key-y2k_inicio_cuerpo,.st-key-y2k_exportar_cuerpo,.st-key-y2k_ficha_cuerpo,' +
    '[data-testid="stPopoverBody"],.y2k-menu,.dvn-scroller,[data-testid="stDialog"] [role="dialog"],[data-testid="stExpanderDetails"]';
  function marcarDesplaza(e, ms) {
    if (!e.hasAttribute("data-y2k-desplaza")) e.setAttribute("data-y2k-desplaza", "");
    clearTimeout(e.__y2kDesplaza);
    e.__y2kDesplaza = setTimeout(function () { e.removeAttribute("data-y2k-desplaza"); }, ms);
  }
  function alDesplazar(ev) {
    var e = ev.target;
    if (e && e.nodeType === 1 && e.matches && e.matches(DESPLAZABLES)) marcarDesplaza(e, 900);
  }
  d.addEventListener("scroll", alDesplazar, true);
  function barraBajoPuntero(ev) {
    if (ev.pointerType && ev.pointerType !== "mouse") return;
    var e = ev.target && ev.target.closest ? ev.target.closest(DESPLAZABLES) : null;
    if (!e || e.scrollHeight <= e.clientHeight + 1) return;
    var r = e.getBoundingClientRect();
    if (ev.clientX > r.right - 14) marcarDesplaza(e, 700);
  }

  function alMover(ev) { especular(ev); barraBajoPuntero(ev); }
  d.addEventListener("pointermove", alMover, true);
  function alTecla(ev) {
    // menus: Escape cierra y devuelve el foco; flechas recorren las opciones
    var menu = ev.target && ev.target.closest ? ev.target.closest(".y2k-menu") : null;
    if (ev.key === "Escape") {
      var abierto = d.querySelector(".y2k-menu:not([hidden])");
      if (abierto) {
        var dueno = d.querySelector('[data-y2k-menu="' + abierto.getAttribute("data-y2k-menu-de") + '"]');
        cerrarMenus(null); if (dueno) dueno.focus(); ev.preventDefault(); return;
      }
    }
    if (menu && (ev.key === "ArrowDown" || ev.key === "ArrowUp" || ev.key === "Home" || ev.key === "End")) {
      var items = Array.prototype.slice.call(menu.querySelectorAll("button"));
      var i = items.indexOf(d.activeElement);
      var j = ev.key === "Home" ? 0 : ev.key === "End" ? items.length - 1 : (i + (ev.key === "ArrowDown" ? 1 : -1) + items.length) % items.length;
      if (items[j]) items[j].focus();
      ev.preventDefault(); return;
    }
    // Escape cierra la consulta del celular y devuelve el foco a su boton
    if (ev.key === "Escape" && esMovil() && hojaAbierta() && pantalla() === "mapa" && !d.querySelector('[role="dialog"]')) {
      ponerHoja(false);
      var c = d.querySelector("[data-y2k-consulta]"); if (c) try { c.focus({preventScroll: true}); } catch (e) {}
      ev.preventDefault();
    }
  }
  d.addEventListener("keydown", alTecla, true);

  // Brillo especular: la luz del vidrio sigue al puntero del raton (no en Lite ni con movimiento reducido)
  var luz = null, luzPedida = false;
  function especular(ev) {
    if (ev.pointerType && ev.pointerType !== "mouse") return;
    if (esLite() || menosMovimiento()) return;
    var el = ev.target && ev.target.closest ? ev.target.closest(VIDRIO) : null;
    if (!el) return;
    luz = {el: el, x: ev.clientX, y: ev.clientY};
    if (luzPedida) return;
    luzPedida = true;
    w.requestAnimationFrame(function () {
      luzPedida = false;
      if (!luz) return;
      var r = luz.el.getBoundingClientRect();
      luz.el.style.setProperty("--mx", Math.round(luz.x - r.left) + "px");
      luz.el.style.setProperty("--my", Math.round(luz.y - r.top) + "px");
    });
  }

  // Streamlit rehace sus elementos en cada recarga: se reponen los atributos ARIA y el reparto del espacio
  var pendiente = false;
  var obs = new MutationObserver(function () {
    if (pendiente) return;
    pendiente = true;
    w.requestAnimationFrame(function () { pendiente = false; sincronizar(); distribuir(); });
  });
  obs.observe(d.body, {childList: true, subtree: true});

  // ---------- reparto del espacio: nada tapa los controles ni la zona util del mapa ----------
  function caja(sel) {
    var e = d.querySelector(sel);
    if (!e) return null;
    var cs = w.getComputedStyle(e);
    if (cs.display === "none" || cs.visibility === "hidden" || +cs.opacity === 0) return null;
    var r = e.getBoundingClientRect();
    return r.width && r.height ? r : null;
  }
  function cruza(a, x0, x1) { return !!a && a.left < x1 && a.right > x0; }
  // boton de Streamlit Community Cloud en el escritorio ("Manage app"), abajo a la derecha
  var SELLO_ANCHO = 140, SELLO_ALTO = 38;
  var ultimo = "";
  function distribuir() {
    var W = w.innerWidth, H = w.innerHeight, movil = esMovil();
    var ajustes = caja(".st-key-y2k_ajustes"), herr = caja(".st-key-y2k_herr"), abrir = caja(".st-key-y2k_abrir");
    var ficha = caja(".st-key-y2k_ficha"), dock = caja(".st-key-y2k_dock"), panel = caja(".st-key-y2k_panel");
    var filtro = caja(".st-key-y2k_filtro");
    var pIzq = caja(".st-key-y2k_dock_izq"), pDer = caja(".st-key-y2k_dock_der");
    // ancho real de la capsula de Ajustes (lleva tambien el boton de idioma): la ficha se aparta de ella
    if (ajustes) raiz.style.setProperty("--y2k-ajustes-w", Math.round(ajustes.right - ajustes.left) + "px");
    var col = [ajustes, herr].filter(Boolean);
    var izq = G, der = col.length ? W - Math.min.apply(null, col.map(function (r) { return r.left; })) + G : G;
    var arriba = abrir ? abrir.bottom + G : G, abajo = G;
    if (!movil && estadoPanel() === "abierto" && panel) izq = panel.right + G;
    if (filtro) arriba = Math.max(arriba, filtro.bottom + G);
    if (abrir) raiz.style.setProperty("--y2k-abrir-w", Math.round(abrir.width) + "px");
    if (dock) raiz.style.setProperty("--y2k-dock-h", Math.round(movil ? H - dock.top : H - dock.top + G) + "px");
    if (movil) {
      // con la consulta abierta lo que va sobre el mapa se oculta: se reparte como si estuviera cerrada, asi al
      // cerrarla nada salta de lugar
      abajo = H - (dock ? dock.top : H) + G;
      if (ficha) arriba = Math.max(arriba, ficha.bottom + G);
    }
    // franja inferior: lo que comparte columna con una pildora sube por encima de ella
    var bajos = movil ? [] : [pIzq, pDer].filter(Boolean);
    var sobreDock = function (x0, x1) {
      return bajos.reduce(function (m, r) { return cruza(r, x0, x1) ? Math.max(m, H - r.top + G) : m; }, abajo);
    };
    var ley = caja(".y2k-leyenda"), doc = docMapa();
    var rinconL = function (sel) { var e = doc && doc.querySelector(sel); return e ? {w: e.offsetWidth, h: e.offsetHeight} : {w: 0, h: 0}; };
    var bl = rinconL(".leaflet-bottom.leaflet-left"), br = rinconL(".leaflet-bottom.leaflet-right");
    var blAbajo = sobreDock(izq, izq + Math.max(bl.w, 120));
    // la leyenda va encima de la escala de Leaflet (y de la pildora, si comparten columna)
    var leyAbajo = Math.max(abajo, ley ? sobreDock(izq, izq + ley.width) : abajo, bl.h ? blAbajo - 10 + bl.h + 4 : 0);
    var atrib = caja(".y2k-atrib3d"), atribAbajo = atrib ? sobreDock(W - der - atrib.width, W - der) : sobreDock(W - 200, W - G);
    var atribDer = der, sello = num("--y2k-sello", 0);
    if (atrib && sello > 0 && !movil) {
      // en la franja del boton de Streamlit, a su izquierda, si no choca con la pildora 2D/3D
      var x1 = W - SELLO_ANCHO - G, x0 = x1 - atrib.width;
      if (!pIzq || pIzq.right + G <= x0) { atribDer = W - x1; atribAbajo = Math.max(4, Math.round((SELLO_ALTO - atrib.height) / 2)); }
    }
    var ovAbajo = Math.max(abajo, sobreDock(izq, W - der));
    var clave = [W, H, arriba, izq, der, ovAbajo, leyAbajo, atribAbajo, atribDer].join("|");
    if (clave !== ultimo) {
      ultimo = clave;
      var s = raiz.style;
      s.setProperty("--y2k-ov-top", Math.round(arriba) + "px");
      s.setProperty("--y2k-ov-izq", Math.round(izq) + "px");
      s.setProperty("--y2k-ov-der", Math.round(der) + "px");
      s.setProperty("--y2k-ov-abajo", Math.round(ovAbajo) + "px");
      s.setProperty("--y2k-ley-abajo", Math.round(leyAbajo) + "px");
      s.setProperty("--y2k-ley-izq", Math.round(izq) + "px");
      s.setProperty("--y2k-atrib-abajo", Math.round(atribAbajo) + "px");
      s.setProperty("--y2k-atrib-der", Math.round(atribDer) + "px");
    }
    // esquinas de Leaflet (dentro del iframe; sus controles ya traen 10 px de margen). La barra de dibujo (oculta)
    // queda donde esta la capsula de herramientas, y sus acciones ("Guardar", "Cancelar") aparecen a su izquierda
    if (doc) {
      var brAbajo = sobreDock(W - G - br.w, W - G);
      var v = {"--tl-top": arriba, "--tl-izq": izq, "--tr-top": herr ? herr.top : G, "--tr-der": G,
               "--bl-abajo": blAbajo, "--bl-izq": izq, "--br-abajo": brAbajo, "--br-der": G,
               "--acc-top": (herr ? herr.top : G) + 10, "--acc-der": der + 10};
      // escritorio: el credito de los mapas va abajo, a la derecha de la pildora 2D/3D, centrado con ella; llega hasta
      // "Preparar descarga" si esta en la misma franja o, si no, hasta el boton de Streamlit
      var cred = null, credEl = doc.querySelector(".leaflet-control-attribution");
      if (!movil && pIzq && credEl) {
        var aH = credEl.offsetHeight || 18, centro = (pIzq.top + pIzq.bottom) / 2, x0 = pIzq.right + G;
        var limite = pDer && pDer.top < centro + aH / 2 && pDer.bottom > centro - aH / 2 ? pDer.left - G : W - G - (sello > 0 ? SELLO_ANCHO : 0);
        cred = {izq: x0, abajo: H - centro - aH / 2 - 4, ancho: Math.max(120, limite - x0)};
      }
      var claveIf = JSON.stringify([v, cred]);
      if (doc.__y2kClave !== claveIf) {
        doc.__y2kClave = claveIf;
        var es = doc.documentElement.style;
        for (var k in v) es.setProperty(k, Math.max(0, Math.round(v[k] - 10)) + "px");
        doc.documentElement.classList.toggle("y2k-credito-abajo", !!cred);
        if (cred) {
          es.setProperty("--cred-izq", Math.round(cred.izq) + "px"); es.setProperty("--cred-abajo", Math.max(0, Math.round(cred.abajo)) + "px");
          es.setProperty("--cred-ancho", Math.round(cred.ancho) + "px");
        }
      }
    }
  }
  w.addEventListener("resize", function () { sincronizar(); distribuir(); });

  // ---------- mapa 2D (Leaflet en el iframe de streamlit-folium) ----------
  var VIDRIO_CLARO_IF = "background:linear-gradient(180deg,rgba(255,255,255,.55),rgba(255,255,255,.12) 26%,rgba(255,255,255,0) 55%),rgba(249,250,252,.94) !important;" +
    "box-shadow:inset 0 1px 0 rgba(255,255,255,.98),0 0 0 .5px rgba(8,20,45,.2),0 16px 32px -16px rgba(5,15,35,.62) !important";
  var VIDRIO_OSCURO_IF = "background:linear-gradient(180deg,rgba(255,255,255,.12),rgba(255,255,255,0) 50%),rgba(20,23,29,.95) !important;" +
    "box-shadow:inset 0 1px 0 rgba(255,255,255,.36),0 0 0 .5px rgba(0,0,0,.5),0 18px 34px -16px rgba(0,0,0,.82) !important";
  var CSS_IFRAME = "html,body,#root,#parent,#parent>.float-child:first-child,#map_div{height:100% !important;width:100% !important;margin:0}" +
    "#parent>.float-child:first-child{float:none !important}" +
    ".leaflet-top.leaflet-left{top:var(--tl-top,0);left:var(--tl-izq,0)}.leaflet-top.leaflet-right{top:var(--tr-top,0);right:var(--tr-der,0)}" +
    ".leaflet-bottom.leaflet-left{bottom:var(--bl-abajo,0);left:var(--bl-izq,0)}.leaflet-bottom.leaflet-right{bottom:var(--br-abajo,0);right:var(--br-der,0)}" +
    ".leaflet-top,.leaflet-bottom{transition:top .32s cubic-bezier(.2,.8,.2,1),left .32s cubic-bezier(.2,.8,.2,1),right .32s,bottom .32s}" +
    // escritorio: credito abajo, a la derecha de la pildora 2D/3D (lo calcula distribuir)
    "html.y2k-credito-abajo .leaflet-bottom.leaflet-right{left:var(--cred-izq,auto);right:auto;bottom:var(--cred-abajo,0)}" +
    "html.y2k-credito-abajo .leaflet-control-attribution{float:left !important;max-width:var(--cred-ancho,60vw) !important}" +
    // zoom, capas y dibujo se manejan desde la capsula de herramientas de la pagina: sus controles de Leaflet no se ven
    // (la barra de dibujo sigue ahi, invisible, para que sus acciones "Guardar"/"Cancelar" salgan junto a la capsula)
    ".leaflet-control-zoom,.leaflet-control-layers{display:none !important}" +
    // con la consulta abierta en el celular, la escala y los creditos se apartan (vuelven al cerrarla)
    "html.y2k-hoja-abierta .leaflet-bottom{visibility:hidden !important}" +
    ".leaflet-draw.leaflet-control{visibility:hidden;pointer-events:none}" +
    ".leaflet-draw-actions{visibility:visible;pointer-events:auto;position:fixed !important;top:var(--acc-top,0) !important;right:var(--acc-der,0) !important;" +
    "left:auto !important;white-space:nowrap;border:0 !important;border-radius:999px !important;overflow:hidden;padding:4px !important;margin:0 !important;" + VIDRIO_CLARO_IF + "}" +
    ".leaflet-draw-actions li{display:inline-block}" +
    ".leaflet-draw-actions a{background:transparent !important;color:#0B1324 !important;font:600 13.5px/36px Figtree,system-ui,sans-serif !important;" +
    "height:36px !important;border:0 !important;padding:0 14px !important;border-radius:999px}" +
    ".leaflet-draw-actions a:hover{background:rgba(8,20,45,.07) !important}" +
    ".leaflet-control-scale-line{background:rgba(255,255,255,.78) !important;border-color:#0B1324 !important;color:#0B1324;font:11px Figtree,system-ui,sans-serif}" +
    ".leaflet-control-attribution{background:rgba(255,255,255,.78) !important;color:#1F2B40 !important;border-radius:999px;padding:1px 9px !important;margin:0 0 4px !important}" +
    ".leaflet-control-attribution a{color:#0A3F9F !important}" +
    ".leaflet-tooltip{border:0;border-radius:14px;padding:9px 11px;background:rgba(250,251,253,.92);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);" +
    "box-shadow:inset 0 1px 0 #fff,0 0 0 .5px rgba(8,20,45,.22),0 14px 30px -14px rgba(0,0,0,.6)}" +
    ".leaflet-draw-tooltip{background:rgba(11,19,36,.86);border:0;border-radius:10px;color:#fff;font:500 12.5px/1.35 Figtree,system-ui,sans-serif;padding:6px 10px}" +
    ".leaflet-draw-tooltip:before{display:none}" +
    "a:focus-visible,button:focus-visible,input:focus-visible,.leaflet-container:focus-visible{outline:2px solid #0A3F9F !important;outline-offset:2px}" +
    // tono oscuro
    "html.y2k-oscuro .leaflet-draw-actions{" + VIDRIO_OSCURO_IF + "}" +
    "html.y2k-oscuro .leaflet-draw-actions a{color:#F4F6FA !important}" +
    "html.y2k-oscuro .leaflet-draw-actions a:hover{background-color:rgba(255,255,255,.12) !important}" +
    "html.y2k-oscuro .leaflet-tooltip{background:rgba(22,25,32,.92);color:#F4F6FA;box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 0 0 .5px #000,0 14px 30px -14px #000}" +
    "html.y2k-oscuro .leaflet-tooltip>div{color:#F4F6FA !important}" +
    "html.y2k-oscuro .leaflet-tooltip [style*='4F5D78']{color:#B7C0CF !important}html.y2k-oscuro .leaflet-tooltip [style*='A4430F']{color:#FFB37E !important}" +
    "html.y2k-oscuro .leaflet-tooltip [style*='B42318']{color:#FF9B94 !important}" +
    "html.y2k-oscuro .leaflet-control-scale-line,html.y2k-oscuro .leaflet-control-attribution{background:rgba(20,23,29,.82) !important;color:#E3E7EE !important;border-color:#E3E7EE !important}" +
    "html.y2k-oscuro .leaflet-control-attribution a{color:#8EC0FF !important}" +
    "html.y2k-oscuro a:focus-visible,html.y2k-oscuro .leaflet-container:focus-visible{outline-color:#9CCBFF !important}" +
    // alto contraste: opaco y con bordes nitidos
    "html.y2k-alto .leaflet-draw-actions,html.y2k-alto .leaflet-tooltip{background:#fff !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:0 0 0 2px #000 !important}" +
    "html.y2k-alto.y2k-oscuro .leaflet-draw-actions,html.y2k-alto.y2k-oscuro .leaflet-tooltip{background:#000 !important;box-shadow:0 0 0 2px #fff !important}" +
    "html.y2k-alto .leaflet-control-attribution,html.y2k-alto .leaflet-control-scale-line{background:#fff !important;color:#000 !important}" +
    "html.y2k-alto.y2k-oscuro .leaflet-control-attribution,html.y2k-alto.y2k-oscuro .leaflet-control-scale-line{background:#000 !important;color:#fff !important}" +
    // Lite: sin desenfoque ni fundidos de teselas
    "html.y2k-lite .leaflet-tooltip{-webkit-backdrop-filter:none !important;backdrop-filter:none !important;background:rgba(249,250,252,.96) !important}" +
    "html.y2k-lite.y2k-oscuro .leaflet-tooltip{background:rgba(20,23,29,.96) !important}" +
    "html.y2k-lite .leaflet-fade-anim .leaflet-tile,html.y2k-lite .leaflet-top,html.y2k-lite .leaflet-bottom{transition:none !important}" +
    "@media (prefers-reduced-motion: reduce){.leaflet-top,.leaflet-bottom{transition:none !important}}" +
    "@media (forced-colors: active){.leaflet-draw-actions{border:1px solid CanvasText !important}}";
  // Leaflet.draw viene en ingles: textos en espanol (los botones de accion y las ayudas se leen al activar cada herramienta)
  var DRAW_ES = {
    draw: {toolbar: {actions: {title: "Cancelar el dibujo", text: "Cancelar"}, finish: {title: "Terminar el dibujo", text: "Terminar"},
                     undo: {title: "Borrar el último punto", text: "Deshacer"}, buttons: {rectangle: "Dibujar un rectángulo"}},
           handlers: {rectangle: {tooltip: {start: "Haz clic y arrastra para dibujar el rectángulo."}},
                      simpleshape: {tooltip: {end: "Suelta para terminar."}}}},
    edit: {toolbar: {actions: {save: {title: "Guardar los cambios", text: "Guardar"}, cancel: {title: "Descartar los cambios", text: "Cancelar"},
                               clearAll: {title: "Borrar todo", text: "Borrar todo"}},
                     buttons: {edit: "Ajustar las esquinas", editDisabled: "No hay nada que ajustar", remove: "Borrar el área",
                               removeDisabled: "No hay nada que borrar"}},
           handlers: {edit: {tooltip: {text: "Arrastra los vértices para ajustar el área.", subtext: "Pulsa «Guardar» al terminar o «Cancelar» para deshacer."}},
                      remove: {tooltip: {text: "Haz clic en el área para borrarla."}}}}};
  function fusionar(a, b) { for (var k in b) { if (b[k] && typeof b[k] === "object") { a[k] = a[k] || {}; fusionar(a[k], b[k]); } else a[k] = b[k]; } }
  function marco2d() { return d.querySelector(".st-key-y2k_mapa2d iframe") || d.querySelector("iframe[title*='st_folium']"); }
  function winMapa() { var f = marco2d(); try { return f && f.contentWindow; } catch (e) { return null; } }
  function docMapa() { var x = winMapa(); try { return x && x.document && x.document.head ? x.document : null; } catch (e) { return null; } }
  function vigilar2d() {
    var win = winMapa(), doc = docMapa();
    if (!doc) return;
    if (!doc.getElementById("y2k-iframe-css")) {
      var s = doc.createElement("style"); s.id = "y2k-iframe-css"; s.textContent = CSS_IFRAME; doc.head.appendChild(s);
      if (win.map && win.map.invalidateSize) try { win.map.invalidateSize(); } catch (e) {}
    }
    var cl = doc.documentElement.classList;
    // un iframe nuevo con la consulta abierta tambien aparta la escala (al cerrarla la quita ponerHoja, con demora)
    if (esMovil() && hojaAbierta() && pantalla() === "mapa") cl.add("y2k-hoja-abierta");
    cl.toggle("y2k-lite", esLite()); cl.toggle("y2k-oscuro", css("--y2k-tono") === "oscuro"); cl.toggle("y2k-alto", css("--y2k-alto") === "1");
    if (!doc.__y2kToques) { doc.__y2kToques = true; doc.addEventListener("pointerdown", pulsadoEnMapa, true); }
    var map = win.map, L = win.L;
    if (!map || !L) return;
    var c = doc.querySelector(".leaflet-container");
    if (c && !c.getAttribute("aria-label")) c.setAttribute("aria-label", "Mapa. Con el teclado: flechas para moverte, + y − para acercar o alejar");
    if (map.__y2kTeselas) return;
    map.__y2kTeselas = {lista: []};
    if (L.drawLocal) fusionar(L.drawLocal, DRAW_ES);
    // la ayuda inicial del rectangulo se copia al crear la barra (en ingles): se repone al activar la herramienta
    if (L.Draw && L.Draw.Rectangle && !L.Draw.Rectangle.prototype.__y2k) {
      var original = L.Draw.Rectangle.prototype.addHooks;
      L.Draw.Rectangle.prototype.addHooks = function () {
        this._initialLabelText = L.drawLocal.draw.handlers.rectangle.tooltip.start;
        return original.apply(this, arguments);
      };
      L.Draw.Rectangle.prototype.__y2k = true;
    }
    var anotar = function (capa, ok) {
      if (!map.hasLayer(capa)) return;
      var r = map.__y2kTeselas.lista; r.push({t: w.performance.now(), ok: ok, capa: capa});
      if (r.length > 120) r.shift();
    };
    var enganchar = function (capa) {
      if (!(capa instanceof L.TileLayer) || capa.__y2kVigia) return;
      capa.__y2kVigia = true;
      capa.on("tileerror", function () { anotar(capa, false); });
      capa.on("tileload", function () { anotar(capa, true); });
    };
    map.eachLayer(enganchar);
    map.on("layeradd", function (e) { enganchar(e.layer); });
    map.on("baselayerchange", function (e) { map.__y2kBase = e.name; estadoCapas(); });
    // mientras se dibuja o se ajustan las esquinas, el navegador no debe desplazar ni ampliar con el dedo: con el
    // arrastre del mapa apagado, Leaflet deja "touch-action: pan-x pan-y" y Safari puede cortar el gesto a la mitad
    var cont = map.getContainer();
    map.on("draw:drawstart draw:editstart", function () { cont.style.touchAction = "none"; });
    map.on("draw:drawstop draw:editstop", function () { cont.style.touchAction = ""; });
    map.on("zoomend", estadoArea);
    try { new w.ResizeObserver(function () { try { map.invalidateSize({pan: false}); } catch (e) {} }).observe(marco2d()); } catch (e) {}
    // el area recien montada (archivo, vuelta del 3D) se encuadra en la zona libre, no debajo del panel
    setTimeout(function () {
      try {
        var it = win.drawnItems;
        if (!it || !it.getLayers().length) return;
        distribuir();
        map.fitBounds(it.getBounds(), {paddingTopLeft: [num("--y2k-ov-izq", 12) + 24, num("--y2k-ov-top", 12) + 24],
          paddingBottomRight: [num("--y2k-ov-der", 60) + 24, num("--y2k-ov-abajo", 72) + 24], animate: false});
      } catch (e) {}
    }, 250);
    estadoArea(); estadoCapas();
  }
  // Herramientas: dibujar, ajustar las esquinas, capas y zoom (manejan los controles ocultos de Leaflet).
  // Dibujar y ajustar se activan por el manejador de Leaflet.draw: en iPhone, iPad y iPod sus botones responden al toque
  // (touchstart) y no al clic, asi que pulsarlos con .click() no hacia nada. El clic queda solo de respaldo
  function controlDibujo(win) {
    if (win.__y2kDraw && win.__y2kDraw._toolbars) return win.__y2kDraw;
    var k = Object.keys(win).find(function (x) { return x.indexOf("draw_control_") === 0 && win[x] && win[x]._toolbars; });
    return (win.__y2kDraw = k ? win[k] : null);
  }
  function activarHerramienta(barra, modo, selector) {
    var win = winMapa(), doc = docMapa();
    if (!win || !doc) return false;
    var ctl = controlDibujo(win), tb = ctl && ctl._toolbars && ctl._toolbars[barra];
    var m = tb && tb._modes && tb._modes[modo];
    if (m && m.handler) { if (!m.handler.enabled()) m.handler.enable(); return true; }
    var a = doc.querySelector(selector);
    if (a) a.click();
    return !!a;
  }
  function dibujarRectangulo() {
    if (esMovil()) ponerHoja(false);
    if (activarHerramienta("draw", "rectangle", ".leaflet-draw-draw-rectangle")) try { marco2d().focus(); } catch (e) {}
  }
  function editarArea() {
    if (esMovil()) ponerHoja(false);
    if (activarHerramienta("edit", "edit", ".leaflet-draw-edit-edit")) try { marco2d().focus(); } catch (e) {}
  }
  // "Borrar": en el 2D se quita el rectangulo en el navegador y se avisa al componente como si se hubiera borrado
  // con Leaflet.draw (Python recibe la lista vacia). Asi el mapa no se rehace y se queda el encuadre y el zoom.
  // En el 3D (sin mapa de Leaflet) lo hace Python.
  function borrarArea() {
    var win = lienzo3d() ? null : winMapa(), map = win && win.map, L = win && win.L, it = win && win.drawnItems;
    if (!map || !L || !it || !it.getLayers) { pulsarOculto("y2k_borrar"); return; }
    try {
      var quitadas = L.layerGroup(it.getLayers());
      it.clearLayers();
      map.fire("draw:deleted", {layers: quitadas});
    } catch (e) { pulsarOculto("y2k_borrar"); }
  }
  function zoom(sentido) {
    var win = winMapa(), map = win && win.map;
    if (!map) return;
    if (sentido === "mas") map.zoomIn(); else map.zoomOut();
  }
  function entradasCapas() {
    var doc = docMapa(), r = [];
    if (!doc) return r;
    doc.querySelectorAll(".leaflet-control-layers-base label").forEach(function (l) {
      var i = l.querySelector("input"), n = (l.textContent || "").trim();
      if (i && n) r.push({nombre: n, input: i});
    });
    return r;
  }
  function ponerCapa(nombre) {
    var e = entradasCapas().find(function (x) { return x.nombre === nombre; });
    if (e && !e.input.checked) e.input.click();
    estadoCapas();
  }
  function estadoCapas() {
    var activa = (entradasCapas().find(function (x) { return x.input.checked; }) || {}).nombre;
    if (!activa) return;
    d.querySelectorAll("[data-y2k-capa]").forEach(function (b) {
      var v = b.getAttribute("data-y2k-capa") === activa ? "true" : "false";
      if (b.getAttribute("aria-checked") !== v) b.setAttribute("aria-checked", v);
    });
  }
  // "Usar el area visible": alternativa al gesto de arrastrar (con el teclado: flechas y + / − en el mapa)
  var ZOOM_AREA = 10;
  function estadoArea() {
    var win = winMapa(), map = win && win.map, ok = !!(map && map.getZoom && map.getZoom() >= ZOOM_AREA);
    d.querySelectorAll("[data-y2k-area]").forEach(function (b) {
      var v = ok ? "false" : "true";
      if (b.getAttribute("aria-disabled") !== v) b.setAttribute("aria-disabled", v);
      var s = b.querySelector("small"), txt = !map ? "Disponible en la vista 2D" : ok ? "Lo que ves ahora en el mapa" : "Primero acércate a tu zona";
      if (s && s.textContent !== txt) s.textContent = txt;
    });
  }
  function usarAreaVisible(b) {
    var win = winMapa(), map = win && win.map, L = win && win.L;
    if (!map || !L) return;
    if (map.getZoom() < ZOOM_AREA) {
      try { marco2d().focus(); } catch (e) {}
      return;
    }
    distribuir();
    var W = w.innerWidth, H = w.innerHeight;
    var x0 = num("--y2k-ov-izq", 12), y0 = num("--y2k-ov-top", 12), x1 = W - num("--y2k-ov-der", 60), y1 = H - num("--y2k-ov-abajo", 72);
    var mx = (x1 - x0) * 0.1, my = (y1 - y0) * 0.1;
    var a = map.containerPointToLatLng([x0 + mx, y0 + my]), c = map.containerPointToLatLng([x1 - mx, y1 - my]);
    var rect = L.rectangle(L.latLngBounds(a, c), {color: "#1C6FD8", weight: 3, fillColor: "#1C6FD8", fillOpacity: 0.12});
    map.fire("draw:created", {layer: rect, layerType: "rectangle"});
    if (esMovil()) ponerHoja(false);
  }

  // ---------- deck.gl (3D) ----------
  function lienzo3d() { return d.querySelector('[data-testid="stDeckGlJsonChart"] canvas:not(.y2k-avion)'); }
  function buscarDeck() {
    var l = lienzo3d();
    if (!l) return null;
    var clave = Object.keys(l).find(function (k) { return k.indexOf("__reactFiber$") === 0; });
    var fibra = clave && l[clave];
    for (var i = 0; fibra && i < 40; i++, fibra = fibra.return) {
      var g = fibra.memoizedState;
      for (var j = 0; g && typeof g === "object" && j < 60; j++, g = g.next) {
        var v = g.memoizedState;
        if (v && v.current && v.current.deck && typeof v.current.deck.setProps === "function") return v.current.deck;
      }
    }
    return null;
  }
  function vistaActual(deck) {
    return Object.assign({}, deck.props.viewState || (deck.viewManager && deck.viewManager.getViewState && deck.viewManager.getViewState("default-view")) || {});
  }
  function mover(deck, nueva) {
    var actual = deck.props.viewState || {};
    if (w.__y2kEnIntro || typeof deck.props.onViewStateChange !== "function") deck.setProps({viewState: nueva});
    else deck.props.onViewStateChange({viewState: nueva, oldViewState: actual, interactionState: {}, viewId: "default-view"});
  }
  function camara(accion) {
    var deck = buscarDeck();
    if (!deck) return;
    w.__y2kParaVuelta = w.performance.now();   // detiene la vuelta automatica de la camara
    var v = vistaActual(deck), n = Object.assign({}, v);
    var lim = function (x, a, b) { return Math.min(b, Math.max(a, x)); };
    var tope = v.maxPitch || MAX_PITCH, minimo = v.minZoom || 1;
    if (accion === "acercar") n.zoom = lim((v.zoom || 10) + 0.6, minimo, 20);
    else if (accion === "alejar") n.zoom = lim((v.zoom || 10) - 0.6, minimo, 20);
    else if (accion === "izq") n.bearing = (((v.bearing || 0) - 20) + 540) % 360 - 180;
    else if (accion === "der") n.bearing = (((v.bearing || 0) + 20) + 540) % 360 - 180;
    else if (accion === "subir") n.pitch = lim((v.pitch || 0) + 10, 0, tope);
    else if (accion === "bajar") n.pitch = lim((v.pitch || 0) - 10, 0, tope);
    else if (accion === "norte") n.bearing = 0;
    n.maxPitch = tope;
    mover(deck, n);
    var r = d.querySelector(".y2k-camara-estado");
    if (r) r.textContent = "Rumbo " + Math.round(((n.bearing || 0) + 360) % 360) + "°, inclinación " + Math.round(n.pitch || 0) + "°, zoom " + (n.zoom || 0).toFixed(1);
    lecturaCamara(n);
  }
  // Menu de camara abierto: la brujula gira con el mapa y una linea dice rumbo e inclinacion
  function lecturaCamara(v) {
    var m = d.querySelector('[data-y2k-menu-de="camara"]:not([hidden])');
    if (!m) return;
    var rumbo = Math.round((((v.bearing || 0) % 360) + 360) % 360), incl = Math.round(v.pitch || 0);
    var aguja = m.querySelector('[data-y2k-cam="norte"] svg'), txt = "Rumbo " + rumbo + "° · Inclinación " + incl + "°";
    if (aguja) aguja.style.transform = "rotate(" + (-(v.bearing || 0)) + "deg)";
    var p = m.querySelector(".y2k-cam-lectura");
    if (p && p.textContent !== txt) p.textContent = txt;
  }
  // Neblina lejana, solo donde termina el relieve que se pide (el `extent` de la capa "terreno"): se busca en que altura
  // de la pantalla el suelo sale de ese recuadro (en tres columnas, la mas baja) y la neblina tapa de ahi hacia arriba,
  // con una franja de transicion. Si el borde no se ve (de cerca o mirando hacia abajo), no hay neblina. Antes dependia
  // solo de la inclinacion: de cerca, al levantar la vista, aparecia a pocos metros
  function bordeRelieve(deck, W, H) {
    var capa = deck.layerManager && deck.layerManager.getLayers().find(function (x) { return x.id === "terreno"; });
    var ext = capa && capa.props.extent, vps = deck.getViewports ? deck.getViewports() : [];
    var vp = vps && vps[0];
    if (!ext || !vp || !vp.unproject) return null;
    var fuera = function (x, y) {
      var q;
      try { q = vp.unproject([x, y], {targetZ: 0}); } catch (e) { return true; }
      return !q || !isFinite(q[0]) || !isFinite(q[1]) || q[0] < ext[0] || q[0] > ext[2] || q[1] < ext[1] || q[1] > ext[3];
    };
    var borde = null;
    [0.08, 0.5, 0.92].forEach(function (f) {
      var x = W * f;
      // se busca entre el borde de arriba y el centro (que es el punto que mira la camara, dentro de la zona)
      if (!fuera(x, 0) || fuera(x, H / 2)) return;   // arriba aun hay relieve (o ni el centro lo tiene): sin borde aqui
      var a = 0, b = H / 2;                          // a: fuera del recuadro; b: dentro
      for (var i = 0; i < 12 && b - a > 1.5; i++) { var m = (a + b) / 2; if (fuera(x, m)) a = m; else b = m; }
      borde = borde === null ? b : Math.max(borde, b);
    });
    return borde;
  }
  function neblina(deck) {
    var zona = d.querySelector('[data-testid="stDeckGlJsonChart"]'), l = lienzo3d();
    if (!zona || !l) return;
    // el clic derecho, que gira e inclina, no abre el menu del navegador
    if (!zona.__y2kMenuCtx) { zona.__y2kMenuCtx = true; zona.addEventListener("contextmenu", function (e) { e.preventDefault(); }); }
    var n = zona.querySelector(".y2k-neblina");
    if (!n) { n = d.createElement("div"); n.className = "y2k-neblina"; n.setAttribute("aria-hidden", "true"); l.insertAdjacentElement("afterend", n); }
    var r = zona.getBoundingClientRect(), y = w.__y2kEnIntro ? null : bordeRelieve(deck, r.width, r.height);
    var o = y === null ? "0" : "1";
    if (y !== null) {
      var yr = Math.round(y), banda = Math.round(Math.max(48, r.height * 0.12));
      if (n.__y !== yr) { n.__y = yr; n.style.setProperty("--n-y", yr + "px"); n.style.setProperty("--n-banda", banda + "px"); }
    }
    if (n.style.opacity !== o) n.style.opacity = o;
  }
  function vigia3d() {
    if (!lienzo3d()) return;
    var deck = buscarDeck();
    if (!deck) return;
    neblina(deck); lecturaCamara(vistaActual(deck));
  }

  // ---------- avisos de fallo (sobre la zona libre del mapa) ----------
  function cerrarDialogo(id) { var x = d.getElementById(id); if (x) x.remove(); }
  function dialogo(o) {
    if (d.getElementById(o.id)) return;
    var caja2 = d.createElement("div");
    caja2.className = "y2k-dialogo lg-regular"; caja2.id = o.id;
    caja2.setAttribute("role", "alertdialog"); caja2.setAttribute("aria-modal", "false");
    caja2.setAttribute("aria-labelledby", o.id + "_t"); caja2.setAttribute("aria-describedby", o.id + "_d");
    var tipo = d.createElement("span"); tipo.className = "tipo"; tipo.textContent = o.tipo;
    var h = d.createElement("h3"); h.id = o.id + "_t"; h.innerHTML = ICONO_ALERTA; h.appendChild(d.createTextNode(o.titulo));
    var p = d.createElement("p"); p.id = o.id + "_d"; p.textContent = o.texto;
    var fila = d.createElement("div"); fila.className = "botones";
    o.acciones.forEach(function (a) {
      var b = d.createElement("button"); b.type = "button"; b.textContent = a.etiqueta;
      if (a.primaria) b.className = "prim";
      b.addEventListener("click", function () { caja2.remove(); a.fn(); });
      fila.appendChild(b);
    });
    caja2.addEventListener("keydown", function (ev) { if (ev.key === "Escape") caja2.remove(); });
    caja2.append(tipo, h, p, fila);
    d.body.appendChild(caja2);
    var primero = fila.querySelector("button");
    if (primero) try { primero.focus({preventScroll: true}); } catch (e) {}
  }
  function pulsarOculto(clave) { var b = d.querySelector(".st-key-" + clave + " button"); if (b) b.click(); return !!b; }

  // la camara 3D se guarda antes de rehacer el visor y se repone en el nuevo
  function guardarCamara() { var deck = buscarDeck(); if (deck) w.__y2kCamaraGuardada = {vista: vistaActual(deck), lienzo: lienzo3d()}; }
  function reponerCamara() {
    var g = w.__y2kCamaraGuardada, l = lienzo3d();
    if (!g || !l || l === g.lienzo) return;
    var deck = buscarDeck();
    if (!deck) return;
    w.__y2kCamaraGuardada = null;
    w.__y2kParaVuelta = w.performance.now();
    var v = Object.assign({}, vistaActual(deck), g.vista);
    delete v.transitionDuration; delete v.transitionInterpolator;
    mover(deck, v);
  }
  function reintentar3d(conLite) { guardarCamara(); pulsarOculto(conLite ? "y2k_lite_reintentar" : "y2k_reintentar3d"); }

  // a) Contexto grafico perdido (WebGL): fallo grafico real, distinto de un fallo de red
  function vigilarContexto() {
    var l = lienzo3d();
    if (!l || l.__y2kVigia) return;
    l.__y2kVigia = true;
    l.addEventListener("webglcontextlost", function () {
      var lite = esLite();
      dialogo({
        id: "y2k_dlg_ctx", tipo: "Fallo gráfico", titulo: "Se perdió el contexto gráfico (WebGL)",
        texto: "La vista 3D se detuvo. Suele ocurrir cuando el navegador se queda sin memoria gráfica. " +
          (lite ? "El modo Lite ya está activo." : "El modo Lite usa menos memoria y muestra los mismos datos."),
        acciones: (lite ? [] : [{etiqueta: "Activar Lite y reintentar", primaria: true, fn: function () { reintentar3d(true); }}])
          .concat([{etiqueta: "Seguir intentando", primaria: lite, fn: function () { reintentar3d(false); }},
                   {etiqueta: "Ver en 2D", fn: function () { pulsarOculto("y2k_pasar2d"); }}])
      });
    });
  }
  // b) Red: se cuentan las descargas de teselas del 3D (relieve e imagen), por tipo. No es un fallo grafico.
  if (!w.__y2kRed) {
    var original = w.fetch.bind(w);
    w.__y2kRed = {lista: []};
    w.fetch = function (entrada, opciones) {
      var url = typeof entrada === "string" ? entrada : entrada ? (entrada.url || entrada.href || String(entrada)) : "";
      var p = original(entrada, opciones);
      if (!/elevation-tiles-prod|arcgisonline\.com|y2k_hipso/.test(url)) return p;
      var tipo = /arcgisonline\.com/.test(url) ? "imagen" : "relieve";
      var anotar = function (ok) { var r = w.__y2kRed.lista; r.push({t: w.performance.now(), ok: ok, tipo: tipo}); if (r.length > 80) r.shift(); };
      return p.then(function (resp) { anotar(!!(resp && resp.ok)); return resp; },
                    function (e) { if (!(e && e.name === "AbortError")) anotar(false); throw e; });
    };
  }
  var ultimoAviso3d = -1e9, montaje3d = null;
  function vigilarRed3d() {
    var l = lienzo3d();
    if (!l) { montaje3d = null; ["y2k_dlg_ctx", "y2k_dlg_red3d", "y2k_dlg_lento3d"].forEach(cerrarDialogo); return; }
    if (!montaje3d || montaje3d.lienzo !== l) montaje3d = {lienzo: l, t: w.performance.now(), cargado: false, avisado: false};
    var ahora = w.performance.now(), ventana = w.__y2kRed.lista.filter(function (x) { return ahora - x.t < 25000 && x.t > montaje3d.t; });
    if (d.getElementById("y2k_dlg_ctx") || d.getElementById("y2k_dlg_red3d") || d.getElementById("y2k_dlg_lento3d")) return;
    // cada tipo por separado: si falla el relieve, la imagen puede seguir llegando (y al reves)
    var falla = ["relieve", "imagen"].map(function (tipo) {
      var r = ventana.filter(function (x) { return x.tipo === tipo; }), m = r.filter(function (x) { return !x.ok; }).length;
      return {tipo: tipo, malos: m, buenos: r.length - m};
    }).find(function (c) { return c.malos >= 6 && c.buenos * 3 <= c.malos; });
    if (falla && ahora - ultimoAviso3d > 60000) {
      ultimoAviso3d = ahora;
      dialogo({
        id: "y2k_dlg_red3d", tipo: "Problema de red",
        titulo: falla.tipo === "relieve" ? "No cargan los datos del relieve 3D" : "No cargan las imágenes del 3D",
        texto: "Fallaron " + falla.malos + " descargas de teselas en los últimos segundos. Suele deberse a la conexión o al servidor de mapas, no a tu equipo.",
        acciones: (esLite() ? [] : [{etiqueta: "Activar Lite y reintentar", fn: function () { reintentar3d(true); }}])
          .concat([{etiqueta: "Seguir intentando", primaria: true, fn: function () { reintentar3d(false); }}])
      });
      return;
    }
    // c) Carga que no avanza (sin errores de red claros): se pregunta, no se cambia nada solo. Cuenta como avance que
    //    el relieve quede listo o que sigan llegando teselas
    var deck = buscarDeck(), capa = deck && deck.layerManager && deck.layerManager.getLayers().find(function (x) { return x.id === "terreno"; });
    var llegadas = w.__y2kRed.lista.filter(function (x) { return x.ok && x.t > montaje3d.t; }).length;
    if ((capa && capa.isLoaded) || llegadas >= 6) montaje3d.cargado = true;
    if (!montaje3d.cargado && !montaje3d.avisado && ahora - montaje3d.t > 40000) {
      montaje3d.avisado = true;
      dialogo({
        id: "y2k_dlg_lento3d", tipo: "Carga lenta", titulo: "El relieve 3D no termina de cargar",
        texto: "En 40 s llegó muy poco relieve y no hubo errores de red claros. Puede ser una conexión lenta o un equipo con pocos recursos gráficos.",
        acciones: (esLite() ? [] : [{etiqueta: "Activar Lite y reintentar", fn: function () { reintentar3d(true); }}])
          .concat([{etiqueta: "Seguir intentando", primaria: true, fn: function () { montaje3d.avisado = false; montaje3d.t = w.performance.now(); }}])
      });
    }
  }
  // d) Mapa 2D: teselas que fallan una y otra vez (solo en la pantalla del mapa)
  var ultimoAviso2d = -1e9;
  function revisar2d() {
    var win = winMapa(), map = win && win.map;
    if (pantalla() !== "mapa" || !map || !map.__y2kTeselas || d.getElementById("y2k_dlg_red2d")) return;
    var ahora = w.performance.now(), r = map.__y2kTeselas.lista.filter(function (x) { return ahora - x.t < 20000; });
    var malos = r.filter(function (x) { return !x.ok; }), buenos = r.length - malos.length;
    if (malos.length < 8 || buenos > 0 || ahora - ultimoAviso2d < 45000) return;
    ultimoAviso2d = ahora;
    var capa = malos[malos.length - 1].capa, nombre = map.__y2kBase || "Satélite con nombres";
    var redibujar = function () { map.__y2kTeselas.lista = []; try { capa.redraw(); } catch (e) {} };
    dialogo({
      id: "y2k_dlg_red2d", tipo: "Problema de red", titulo: "El mapa base no está cargando",
      texto: "Fallan las teselas de «" + nombre + "». Suele deberse a la conexión o al servidor de mapas. Tu área y las estaciones siguen en el mapa; prueba otro mapa base en Capas.",
      acciones: (esLite() ? [] : [{etiqueta: "Activar Lite y reintentar", fn: function () { pulsarOculto("y2k_lite_reintentar"); redibujar(); }}])
        .concat([{etiqueta: "Seguir intentando", primaria: true, fn: redibujar}])
    });
  }

  ciclos.push(setInterval(function () {
    if (!vivo) return;
    try { vigilarContexto(); vigilarRed3d(); reponerCamara(); vigilar2d(); revisarMapaListo(); revisar2d(); distribuir(); } catch (e) {}
  }, 500));
  // 3D: neblina y lectura de la camara siguen a la vista (consulta barata; sin 3D no hace nada)
  ciclos.push(setInterval(function () { if (vivo) try { vigia3d(); } catch (e) {} }, 150));
  sincronizar(); distribuir();

  w.__y2kUI = {
    v: V, camara: camara, buscarDeck: buscarDeck, esLite: esLite, distribuir: distribuir,
    parar: function () {
      vivo = false; ciclos.forEach(clearInterval); obs.disconnect();
      d.removeEventListener("click", alClic, true); d.removeEventListener("pointermove", alMover, true);
      d.removeEventListener("keydown", alTecla, true); d.removeEventListener("pointerdown", alPulsar, true);
      d.removeEventListener("scroll", alDesplazar, true);
    }
  };
})();
