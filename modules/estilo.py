import streamlit as st
import streamlit.components.v1 as components

# ===========================================================================
# ESTETICA "Y2K SOBRIO"
# Ventanas con barra iridiscente, botones gel, titulos en pixel (Silkscreen),
# texto en Figtree y consola retro (VT323). Colores de calidad = calidad.py
# Dos temas: claro (predeterminado) y oscuro. Los colores propios van en
# variables CSS; los de Streamlit salen de [theme.light]/[theme.dark].
# ===========================================================================

# Colores que usan las graficas y los mapas (no pueden leer variables CSS)
PALETAS = {
    "claro": {"tinta": "#16213A", "tinta_3": "#7C87A3", "rejilla": "#E3E7EE", "superficie": "#FBFCFE",
              "borde": "#B8C4D8", "acento": "#1C6FD8"},
    "oscuro": {"tinta": "#E6ECF7", "tinta_3": "#8491AE", "rejilla": "#26324D", "superficie": "#131B2E",
               "borde": "#34436A", "acento": "#5AA2F5"},
}

CSS_OSCURO = """
<style>
:root{
  --y2k-bg:#0C1220; --y2k-dots:#18223A;
  --y2k-ink:#E6ECF7; --y2k-ink-2:#B4C0D8; --y2k-ink-3:#8491AE;
  --y2k-line:#26324D; --y2k-line-2:#34436A; --y2k-surface:#131B2E; --y2k-surface-2:#182238;
  --y2k-accent:#5AA2F5; --y2k-brillo:rgba(255,255,255,.04); --y2k-sombra:rgba(0,0,0,.55);
  --y2k-holo:linear-gradient(100deg,#3A2C6E 0%,#1F3F73 35%,#1B5A55 65%,#4B2D6B 100%);
  --y2k-titulo:#EEF2FA; --y2k-titulo-meta:#C9D3E8;
  --y2k-cielo:linear-gradient(180deg,#0A1224 0%,#16264A 60%,#233A63 100%);
}
</style>
"""

CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&family=Silkscreen:wght@400;700&family=VT323&display=swap");
:root{
  --y2k-bg:#EDF1F7; --y2k-dots:#E0E6F0;
  --y2k-ink:#16213A; --y2k-ink-2:#4A5673; --y2k-ink-3:#7C87A3;
  --y2k-line:#CFD8E6; --y2k-line-2:#B8C4D8; --y2k-surface:#FBFCFE; --y2k-surface-2:#F3F6FB;
  --y2k-accent:#1C6FD8; --y2k-brillo:#fff; --y2k-sombra:rgba(22,33,58,.35);
  --y2k-holo:linear-gradient(100deg,#C9B8FF 0%,#B8D8FF 35%,#A8F0DC 65%,#E9D5FF 100%);
  --y2k-titulo:#16213A; --y2k-titulo-meta:#2C3754;
  --y2k-cielo:linear-gradient(180deg,#8FBBE6 0%,#C9DFF3 55%,#E8F0F8 100%);
  --y2k-gel:linear-gradient(180deg,#8CC4FF 0%,#3C8CF0 48%,#1C6FD8 52%,#2A86EE 100%);
  --y2k-gel-shadow:0 1px 0 rgba(255,255,255,.7) inset,0 -2px 6px rgba(0,40,110,.25) inset,0 2px 6px rgba(28,111,216,.35);
}
html, body, .stApp, [class*="st-"], button, input, textarea, select{font-family:"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif}
/* los iconos de Streamlit son una fuente: sin esto salen como texto ("dark_mode") */
[data-testid="stIconMaterial"], [data-testid="stExpanderIcon"]{font-family:"Material Symbols Rounded" !important}
.stApp{background-color:var(--y2k-bg);background-image:radial-gradient(circle at 1px 1px,var(--y2k-dots) 1px,transparent 0);background-size:14px 14px}
/* cielo detras del relieve 3D (el mapa 3D no tiene mapa plano de fondo) */
[data-testid="stDeckGlJsonChart"]{background:var(--y2k-cielo);border-radius:12px;overflow:hidden}
/* el menu de Streamlit se oculta: el tema se cambia con el boton propio */
[data-testid="stMainMenu"]{visibility:hidden !important}
.st-key-y2k_tema{position:fixed;top:14px;right:18px;z-index:999991;width:auto !important}
.st-key-y2k_tema .stButton > button{width:36px;height:36px;min-height:36px;padding:0 !important;border-radius:50% !important;
  background:var(--y2k-surface) !important;border:1px solid var(--y2k-line-2) !important;color:var(--y2k-ink-2) !important;
  box-shadow:0 1px 0 var(--y2k-brillo) inset,0 4px 12px -6px var(--y2k-sombra)}
.st-key-y2k_tema iframe{display:none}
.st-key-y2k_orbita{height:0;overflow:hidden;margin:0}
/* tarjetas de cifras del resumen: la etiqueta se parte en dos lineas si no cabe */
.y2k-cifras{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:2px 0 8px}
.y2k-cifra{background:var(--y2k-surface-2);border:1px solid var(--y2k-line);border-radius:10px;padding:8px 11px;min-width:0}
.y2k-cifra .l{font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;font-weight:600;color:var(--y2k-ink-3);line-height:1.25}
.y2k-cifra .v{font-family:"Silkscreen",monospace;font-size:clamp(15px,1.35vw,21px);color:var(--y2k-ink);line-height:1.2;margin-top:3px;overflow-wrap:anywhere}
.y2k-cifra .s{font-size:11.5px;color:var(--y2k-ink-3);margin-top:2px;line-height:1.3}
.y2k-alerta{border:1px solid #EC835A;background:rgba(236,131,90,.12);border-radius:10px;padding:8px 11px;font-size:13px;color:var(--y2k-ink);margin:0 0 8px}
.y2k-alerta b{color:var(--y2k-ink)}
/* alertas compactas de altitud: un desplegable naranja de una linea */
.st-key-alerta_altura [data-testid="stExpander"] details,.st-key-alerta_ficha [data-testid="stExpander"] details{
  border-color:#EC835A !important;background:rgba(236,131,90,.10)}
.st-key-alerta_altura summary p,.st-key-alerta_ficha summary p{font-size:13px !important;font-weight:600}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:1.2rem;padding-bottom:2rem;max-width:1560px}
h1,h2,h3,h4,h1 *,h2 *,h3 *,h4 *{font-family:"Silkscreen","Courier New",monospace !important;font-weight:400 !important;letter-spacing:.03em;color:var(--y2k-ink)}
h3{font-size:14px !important;padding:0 0 2px !important}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] *{font-family:"Silkscreen",monospace !important;font-size:22px !important}
[data-testid="stMetricLabel"] p{font-size:11px !important;text-transform:uppercase;letter-spacing:.06em;font-weight:600;color:var(--y2k-ink-3)}
[data-testid="stMetric"]{background:var(--y2k-surface-2);border:1px solid var(--y2k-line);border-radius:10px;padding:8px 12px}

/* tarjetas (contenedores con borde) como ventanas */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]){
  background:var(--y2k-surface);border-color:var(--y2k-line-2) !important;border-radius:14px !important;
  box-shadow:0 1px 0 var(--y2k-brillo) inset,0 18px 40px -22px var(--y2k-sombra),0 2px 6px rgba(22,33,58,.06)}

/* botones: primario = gel, secundario = pastilla */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button{border-radius:999px !important;font-weight:600 !important}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"]{
  background:var(--y2k-gel) !important;border:1px solid rgba(0,50,120,.35) !important;color:#fff !important;
  box-shadow:var(--y2k-gel-shadow) !important;text-shadow:0 1px 0 rgba(0,40,110,.45);font-weight:700 !important}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover{filter:brightness(1.07)}
.stButton > button[kind="secondary"]{background:var(--y2k-surface) !important;border:1px solid var(--y2k-line-2) !important;color:var(--y2k-ink-2) !important}

/* ventana principal */
.y2k-titlebar{display:flex;align-items:center;gap:12px;padding:9px 14px;background:var(--y2k-holo);border:1px solid var(--y2k-line-2);border-radius:14px 14px 0 0}
.y2k-dots{display:flex;gap:7px}
.y2k-dots i{width:13px;height:13px;border-radius:50%;display:block;box-shadow:0 1px 0 rgba(255,255,255,.8) inset,0 -2px 3px rgba(0,0,0,.2) inset,0 0 0 1px rgba(0,0,0,.18)}
.y2k-dots i:nth-child(1){background:radial-gradient(circle at 40% 35%,#ffb4b4,#e0443e 60%)}
.y2k-dots i:nth-child(2){background:radial-gradient(circle at 40% 35%,#ffe7a8,#f0b400 60%)}
.y2k-dots i:nth-child(3){background:radial-gradient(circle at 40% 35%,#c4f5c0,#3cb83a 60%)}
.y2k-titlebar .nombre{font-family:"Silkscreen",monospace;font-size:13px;color:var(--y2k-titulo);flex:1;text-align:center;letter-spacing:.06em}
.y2k-titlebar .meta{font-size:12px;color:var(--y2k-titulo-meta);margin-right:44px}
.y2k-steps{display:flex;align-items:center;padding:12px 18px;border:1px solid var(--y2k-line-2);border-top:0;border-radius:0 0 14px 14px;background:var(--y2k-surface-2);overflow-x:auto;margin-bottom:14px}
.y2k-step{display:flex;align-items:center;gap:9px;white-space:nowrap;color:var(--y2k-ink-3)}
.y2k-step .n{width:26px;height:26px;border-radius:50%;display:grid;place-items:center;font-family:"Silkscreen",monospace;font-size:12px;border:1px solid var(--y2k-line-2);background:var(--y2k-surface)}
.y2k-step .t{font-weight:600;font-size:13px}
.y2k-step.done{color:var(--y2k-ink-2)} .y2k-step.done .n{color:#0CA30C;border-color:#0CA30C}
.y2k-step.on{color:var(--y2k-ink)} .y2k-step.on .n{background:var(--y2k-gel);color:#fff;border-color:transparent;box-shadow:var(--y2k-gel-shadow)}
.y2k-line{flex:1;min-width:26px;height:2px;margin:0 12px;background:repeating-linear-gradient(90deg,var(--y2k-line-2) 0 4px,transparent 4px 8px)}
.y2k-line.done{background:#0CA30C;opacity:.55}

/* inicio */
.y2k-hello{text-align:center;padding:10px 0 4px}
.y2k-hello h1{font-size:clamp(20px,2.6vw,30px) !important;margin:0}
.y2k-hello p{color:var(--y2k-ink-2);margin:6px auto 0;max-width:60ch}
.y2k-card-head{display:flex;gap:14px;align-items:center}
.y2k-card-head h2{font-size:18px !important;margin:0;padding:0 !important}
.y2k-card-head p{margin:2px 0 0;color:var(--y2k-ink-2);font-size:13px}
.y2k-chips{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 2px}
.y2k-chip{font-size:11px;font-family:"Silkscreen",monospace;border:1px solid var(--y2k-line-2);border-radius:6px;padding:2px 7px;color:var(--y2k-ink-2);background:var(--y2k-surface-2)}

/* consola retro y barra pixel de la descarga */
.y2k-consola{background:#0E1A12;border-radius:12px;border:1px solid #1F3A28;padding:12px 14px;font-family:"VT323",monospace;font-size:17px;line-height:1.25;color:#8CFF9E;height:360px;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end}
.y2k-consola div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.y2k-consola .d{color:#4E8F5A} .y2k-consola .w{color:#FFD37A}
.y2k-pbar{display:grid;grid-template-columns:repeat(32,1fr);gap:3px;padding:6px;border:1px solid var(--y2k-line-2);border-radius:8px;background:var(--y2k-surface-2)}
.y2k-pbar i{height:14px;border-radius:2px;background:var(--y2k-line)}
.y2k-pbar i.on{background:var(--y2k-gel);box-shadow:0 1px 0 rgba(255,255,255,.6) inset}
.y2k-pmeta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;font-size:13px;color:var(--y2k-ink-2);margin-top:6px}
.y2k-pmeta b{color:var(--y2k-ink)}
.ideam-estado{display:none}
.y2k-hint,[data-testid="stMarkdownContainer"] p.y2k-hint{font-size:12.5px !important;line-height:1.45 !important;color:var(--y2k-ink-3) !important;margin:0 0 4px !important}
</style>
"""


def aplicar(tema="claro"):
    # st.html con solo <style> aplica los estilos a toda la pagina sin dibujar nada
    st.html(CSS)
    if tema == "oscuro":
        st.html(CSS_OSCURO)


# Streamlit no deja cambiar el tema desde Python: este guion pulsa, sin que se
# vea, el boton Light/Dark del menu de Streamlit (que esta oculto con CSS).
_SINCRONIZAR_TEMA = """
<script>
(async () => {
  const quiero = "__TEMA__";
  const w = window.parent, d = w.document;
  try {
    const guardado = JSON.parse(w.localStorage.getItem("stActiveTheme-" + w.location.pathname + "-v2") || '"System"');
    if (guardado === quiero) return;
  } catch (e) {}
  const velo = d.createElement("style");
  velo.textContent = "[data-baseweb=popover]{opacity:0 !important}";
  d.head.appendChild(velo);
  const esperar = ms => new Promise(r => setTimeout(r, ms));
  try {
    for (let i = 0; i < 60 && !d.querySelector('[data-testid="stMainMenu"] button'); i++) await esperar(100);
    d.querySelector('[data-testid="stMainMenu"] button').click();
    for (let i = 0; i < 40; i++) {
      const boton = d.querySelector('[data-testid="stMainMenuItem-theme-' + quiero + '"]');
      if (boton) { boton.click(); break; }
      await esperar(50);
    }
    await esperar(120);
    d.body.dispatchEvent(new KeyboardEvent("keydown", {key: "Escape", code: "Escape", keyCode: 27, bubbles: true}));
    await esperar(300);
    if (d.querySelector('[data-testid="stMainMenuItem-theme-' + quiero + '"]')) {
      d.querySelector('[data-testid="stMainMenu"] button').click();
      await esperar(300);
    }
  } finally {
    velo.remove();
  }
})();
</script>
"""


def _cambiar_tema():
    st.session_state.tema = "claro" if st.session_state.tema == "oscuro" else "oscuro"
    if st.session_state.tema == "oscuro":
        st.query_params["tema"] = "oscuro"
    else:
        st.query_params.pop("tema", None)


def control_tema():
    """Boton redondo de la esquina superior derecha (sol / luna) y sincronizacion con Streamlit."""
    tema = st.session_state.tema
    with st.container(key="y2k_tema"):
        st.button("", icon=":material/light_mode:" if tema == "oscuro" else ":material/dark_mode:",
                  help="Cambiar a modo claro" if tema == "oscuro" else "Cambiar a modo oscuro",
                  key="btn_tema", on_click=_cambiar_tema)
        components.html(_SINCRONIZAR_TEMA.replace("__TEMA__", "Dark" if tema == "oscuro" else "Light"), height=0)


def ventana(meta=""):
    st.markdown(
        f'<div class="y2k-titlebar"><div class="y2k-dots"><i></i><i></i><i></i></div>'
        f'<div class="nombre">DESCARGADOR IDEAM</div><div class="meta">{meta}</div></div>',
        unsafe_allow_html=True,
    )


def pasos(activos, hechos):
    """Barra de pasos. activos/hechos: conjuntos con los numeros de paso (1-4)."""
    nombres = ["Cuenca", "Estaciones", "Parámetro y fechas", "Descarga"]
    partes = []
    for i, nombre in enumerate(nombres, start=1):
        clase = "on" if i in activos else "done" if i in hechos else ""
        partes.append(f'<div class="y2k-step {clase}"><span class="n">{i}</span><span class="t">{nombre}</span></div>')
        if i < len(nombres):
            partes.append(f'<div class="y2k-line {"done" if i in hechos else ""}"></div>')
    st.markdown(f'<nav class="y2k-steps">{"".join(partes)}</nav>', unsafe_allow_html=True)


def icono_pixel(filas, paleta, tam=56):
    """Icono pixel art como SVG a partir de una matriz de letras."""
    rects = "".join(
        f'<rect x="{x}" y="{y}" width="1" height="1" fill="{paleta[ch]}"/>'
        for y, fila in enumerate(filas) for x, ch in enumerate(fila) if ch in paleta
    )
    return (f'<svg width="{tam}" height="{tam}" viewBox="0 0 {len(filas[0])} {len(filas)}" '
            f'shape-rendering="crispEdges" aria-hidden="true">{rects}</svg>')


ICONO_DIBUJAR = icono_pixel(
    ["................", "..B.........B...", ".BWB.......BWB..", "..BLLLLLLLLLB...", "..L.........L...",
     ".L...........L..", ".L.....GG.....L.", "L.....GGGG....L.", "L....GGGGGG...L.", ".L....GGGG...L..",
     "..L....GG...L...", "..BLLLLLLLLLB...", ".BWB.......BWB..", "..B.........B...", "................",
     "................"],
    {"B": "#1C6FD8", "W": "#FFFFFF", "L": "#5AA2F5", "G": "#0CA30C"})

ICONO_SUBIR = icono_pixel(
    ["................", "..YYYYY.........", ".YFFFFFY........", ".YFFFFFYYYYYYYY.", ".YFFFFFFFFFFFFY.",
     ".YFFFFFFBBFFFFY.", ".YFFFFFFBBFFFFY.", ".YFFFFFBBBBFFFY.", ".YFFFFBBBBBBFFY.", ".YFFFFFFBBFFFFY.",
     ".YFFFFFFBBFFFFY.", ".YFFFFFFBBFFFFY.", ".YFFFFFFFFFFFFY.", ".YYYYYYYYYYYYYY.", "................",
     "................"],
    {"Y": "#C98A00", "F": "#FAB219", "B": "#16213A"})


def barra_pixel(fraccion):
    llenos = round(max(0.0, min(1.0, fraccion)) * 32)
    return '<div class="y2k-pbar">' + "".join('<i class="on"></i>' if i < llenos else "<i></i>" for i in range(32)) + "</div>"
