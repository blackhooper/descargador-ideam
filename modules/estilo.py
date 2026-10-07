import json

import streamlit as st
import streamlit.components.v1 as components

# ===========================================================================
# ESTETICA "LIQUID GLASS" SOBRIA, CON EL MAPA COMO FOCO
# Superficies translucidas (vidrio) sobre un fondo ambiental suave, una sola
# familia tipografica (Figtree) y tokens CSS semanticos. Ejes independientes:
#   - tema: Sistema / Claro / Oscuro (sigue prefers-color-scheme en Sistema)
#   - contraste: Sistema / Normal / Alto (sigue prefers-contrast en Sistema)
#   - modo Lite: menos coste grafico (sin desenfoque, sombras ni animaciones
#     decorativas, 3D mas liviano). No depende de "movimiento reducido".
# Los colores de Streamlit salen de [theme.light]/[theme.dark] (config.toml);
# el resto va en variables CSS que genera este modulo.
# ===========================================================================

# Pie de pagina institucional: fuente de los datos y condiciones de uso
FUENTE = {
    "nombre": "IDEAM · DHIME",
    "url": "http://dhime.ideam.gov.co/atencionciudadano/",
    "version": "1.0",
}

# Creditos de las capas de mapa (cada proveedor pide su atribucion). Los textos cortos van en el
# borde de cada mapa; este bloque es la version completa del pie. Revisar los textos de Esri en
# https://developers.arcgis.com/documentation/mapping-apis-and-services/deployment/basemap-attribution/
ATRIB_ESRI_SATELITE = "Powered by Esri · Maxar, Earthstar Geographics"
ATRIB_ESRI_RELIEVE = "Powered by Esri · HERE, Garmin, FAO, NOAA, USGS, OpenStreetMap"
ATRIB_NASA = "NASA EOSDIS GIBS"
ATRIB_RELIEVE_3D = ("Relieve 3D: modelo de elevación Terrarium (Mapzen, AWS Open Data), construido con datos SRTM y "
                    "GMTED2010, cortesía del U.S. Geological Survey, entre otras fuentes")
ATRIB_RELIEVE_3D_CORTO = "Relieve: Terrarium (Mapzen · AWS · SRTM/USGS) · Imagen: Esri"
CREDITOS_MAPAS = (
    "<b>Datos:</b> IDEAM · DHIME. "
    "<b>Mapas base:</b> Satélite y Relieve, Esri (Maxar, Earthstar Geographics, HERE, Garmin, FAO, NOAA, USGS y la "
    "comunidad de usuarios de GIS); Calles, © colaboradores de OpenStreetMap; Satélite de noche, NASA EOSDIS GIBS "
    "(“We acknowledge the use of imagery provided by services from NASA's Global Imagery Browse Services (GIBS), "
    "part of NASA's Earth Science Data and Information System (ESDIS)”). "
    f"<b>Relieve 3D:</b> {ATRIB_RELIEVE_3D.split(': ', 1)[1]}. "
    "Estas capas pertenecen a sus proveedores y no están respaldadas por el IDEAM."
)

# Colores que usan las graficas y los mapas (no pueden leer variables CSS)
PALETAS = {
    "claro": {"tinta": "#0E1A2F", "tinta_3": "#4F5D78", "rejilla": "#DDE3EC", "superficie": "#FBFCFD",
              "borde": "#B9C4D6", "acento": "#1A5FD0"},
    "oscuro": {"tinta": "#E9EFF9", "tinta_3": "#97A4BD", "rejilla": "#26324A", "superficie": "#0F182B",
               "borde": "#34435F", "acento": "#6CB0FF"},
}

# Opciones de las preferencias (lo que se ve en el menu "Apariencia")
TEMAS = {"sistema": "Sistema", "claro": "Claro", "oscuro": "Oscuro"}
CONTRASTES = {"sistema": "Sistema", "normal": "Normal", "alto": "Alto"}

# Pantallas que usan la hoja inferior en vez de paneles laterales (celular vertical u horizontal)
MOVIL = "(max-width: 760px), (max-height: 520px) and (max-width: 1100px)"
ESCRITORIO = "(min-width: 761px) and (min-height: 521px), (min-width: 1101px)"

# ---------------------------------------------------------------------------
# Tokens semanticos por tema. Los textos se comprobaron (WCAG 2.2 AA) sobre el
# vidrio ya compuesto con el fondo y sobre la hoja movil encima del satelite.
# ---------------------------------------------------------------------------
TOKENS = {
    "claro": {
        "y2k-bg": "#EEF2F7", "y2k-ink": "#0E1A2F", "y2k-ink-2": "#334360", "y2k-ink-3": "#4F5D78",
        "y2k-line": "rgba(14,26,47,.10)", "y2k-line-2": "rgba(14,26,47,.18)",
        "y2k-surface": "#FFFFFF", "y2k-surface-2": "rgba(14,26,47,.04)", "y2k-ctl": "rgba(255,255,255,.86)",
        "y2k-glass": "rgba(255,255,255,.78)", "y2k-glass-fuerte": "rgba(255,255,255,.88)",
        "y2k-glass-borde": "rgba(255,255,255,.75)", "y2k-glass-filo": "rgba(14,26,47,.10)",
        "y2k-brillo": "rgba(255,255,255,.9)", "y2k-sombra": "rgba(20,35,70,.22)",
        "y2k-elev": "0 1px 0 rgba(255,255,255,.9) inset, 0 0 0 1px rgba(14,26,47,.06), 0 18px 40px -22px rgba(20,35,70,.35)",
        "y2k-accent": "#1A5FD0", "y2k-accent-2": "#0E7490", "y2k-sobre-acento": "#FFFFFF",
        "y2k-accent-suave": "rgba(26,95,208,.10)", "y2k-foco": "#1A5FD0",
        "y2k-alerta": "#A4430F", "y2k-alerta-borde": "#E07A45", "y2k-alerta-bg": "rgba(236,131,90,.12)",
        "y2k-ok": "#11713A", "y2k-peligro": "#B42318",
        "y2k-halo-1": "rgba(56,189,248,.20)", "y2k-halo-2": "rgba(99,102,241,.14)", "y2k-halo-3": "rgba(45,212,191,.14)",
        "y2k-rejilla": "rgba(14,26,47,.035)", "y2k-mapa-fondo": "#D9E1EC",
        "y2k-cielo": "linear-gradient(180deg,#8FBBE6 0%,#C9DFF3 55%,#E8F0F8 100%)",
    },
    "oscuro": {
        "y2k-bg": "#070D1A", "y2k-ink": "#E9EFF9", "y2k-ink-2": "#BAC6DB", "y2k-ink-3": "#97A4BD",
        "y2k-line": "rgba(233,239,249,.10)", "y2k-line-2": "rgba(233,239,249,.18)",
        "y2k-surface": "#0F182B", "y2k-surface-2": "rgba(233,239,249,.05)", "y2k-ctl": "rgba(20,30,52,.86)",
        "y2k-glass": "rgba(15,24,43,.78)", "y2k-glass-fuerte": "rgba(12,19,35,.90)",
        "y2k-glass-borde": "rgba(148,170,210,.18)", "y2k-glass-filo": "rgba(148,170,210,.14)",
        "y2k-brillo": "rgba(255,255,255,.06)", "y2k-sombra": "rgba(0,0,0,.55)",
        "y2k-elev": "0 1px 0 rgba(255,255,255,.06) inset, 0 0 0 1px rgba(0,0,0,.25), 0 22px 48px -24px rgba(0,0,0,.75)",
        "y2k-accent": "#6CB0FF", "y2k-accent-2": "#22D3EE", "y2k-sobre-acento": "#06101F",
        "y2k-accent-suave": "rgba(108,176,255,.14)", "y2k-foco": "#8EC5FF",
        "y2k-alerta": "#FFA36B", "y2k-alerta-borde": "#EC835A", "y2k-alerta-bg": "rgba(236,131,90,.14)",
        "y2k-ok": "#5BD68A", "y2k-peligro": "#FF8A80",
        "y2k-halo-1": "rgba(34,211,238,.10)", "y2k-halo-2": "rgba(99,102,241,.14)", "y2k-halo-3": "rgba(14,165,233,.08)",
        "y2k-rejilla": "rgba(148,170,210,.05)", "y2k-mapa-fondo": "#0C1426",
        "y2k-cielo": "linear-gradient(180deg,#0A1224 0%,#16264A 60%,#233A63 100%)",
    },
}
# Alto contraste: superficies opacas, texto puro, bordes nitidos y foco muy visible
TOKENS_ALTO = {
    "claro": {
        "y2k-bg": "#FFFFFF", "y2k-ink": "#000000", "y2k-ink-2": "#111111", "y2k-ink-3": "#2B2B2B",
        "y2k-line": "#4A4A4A", "y2k-line-2": "#000000", "y2k-surface": "#FFFFFF", "y2k-surface-2": "#F2F2F2",
        "y2k-ctl": "#FFFFFF", "y2k-glass": "#FFFFFF", "y2k-glass-fuerte": "#FFFFFF", "y2k-glass-borde": "#000000",
        "y2k-glass-filo": "#000000", "y2k-elev": "none", "y2k-accent": "#0037A6", "y2k-accent-2": "#0037A6",
        "y2k-sobre-acento": "#FFFFFF", "y2k-accent-suave": "#E3EBFF", "y2k-foco": "#000000",
        "y2k-alerta": "#7A2E00", "y2k-alerta-borde": "#7A2E00", "y2k-alerta-bg": "#FFF1E8",
        "y2k-ok": "#00561F", "y2k-peligro": "#8A0000",
        "y2k-halo-1": "transparent", "y2k-halo-2": "transparent", "y2k-halo-3": "transparent",
        "y2k-rejilla": "transparent", "y2k-mapa-fondo": "#FFFFFF",
    },
    "oscuro": {
        "y2k-bg": "#000000", "y2k-ink": "#FFFFFF", "y2k-ink-2": "#F2F2F2", "y2k-ink-3": "#DADADA",
        "y2k-line": "#BDBDBD", "y2k-line-2": "#FFFFFF", "y2k-surface": "#000000", "y2k-surface-2": "#141414",
        "y2k-ctl": "#000000", "y2k-glass": "#000000", "y2k-glass-fuerte": "#000000", "y2k-glass-borde": "#FFFFFF",
        "y2k-glass-filo": "#FFFFFF", "y2k-elev": "none", "y2k-accent": "#9CCBFF", "y2k-accent-2": "#9CCBFF",
        "y2k-sobre-acento": "#000000", "y2k-accent-suave": "#0B2545", "y2k-foco": "#FFD60A",
        "y2k-alerta": "#FFB98A", "y2k-alerta-borde": "#FFB98A", "y2k-alerta-bg": "#2A1406",
        "y2k-ok": "#7CF0A8", "y2k-peligro": "#FFA3A3",
        "y2k-halo-1": "transparent", "y2k-halo-2": "transparent", "y2k-halo-3": "transparent",
        "y2k-rejilla": "transparent", "y2k-mapa-fondo": "#000000",
    },
}


def md(html):
    """HTML propio en la pagina. st.html quita los SVG en linea; st.markdown (con HTML permitido) los conserva.
    El envoltorio y2k-md anula el margen negativo que Streamlit pone a los bloques de markdown."""
    st.markdown(f'<div class="y2k-md">{html}</div>', unsafe_allow_html=True)


def _vars(tokens):
    return ";".join(f"--{k}:{v}" for k, v in tokens.items())


def _tokens_css(tema, contraste):
    """Variables de color segun la eleccion. "Sistema" se resuelve en el navegador con media queries
    (prefers-color-scheme y prefers-contrast), sin esperar a ningun guion: no hay destello de tema."""
    tonos = [("", "claro"), ("(prefers-color-scheme: dark)", "oscuro")] if tema == "sistema" else [("", tema)]
    cond_alto = {"alto": "", "sistema": "(prefers-contrast: more)"}.get(contraste)

    def bloque(condiciones, cuerpo):
        condiciones = [c for c in condiciones if c]
        return f"@media {' and '.join(condiciones)}{{{cuerpo}}}" if condiciones else cuerpo

    partes = [bloque([c], ":root{" + _vars(TOKENS[t]) + "}") for c, t in tonos]
    if cond_alto is not None:   # el alto contraste usa el tono vigente (claro u oscuro)
        partes += [bloque([cond_alto, c], ":root{" + _vars(TOKENS_ALTO[t]) + "}") for c, t in tonos]
        partes.append(bloque([cond_alto], CSS_ALTO))
    return "".join(partes)


# ---------------------------------------------------------------------------
# CSS base (estructura, componentes). Todo color sale de las variables.
# ---------------------------------------------------------------------------
CSS = """
@import url("https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap");
:root{
  --y2k-top:56px; --y2k-g:12px; --y2k-izq-w:320px; --y2k-der-w:360px; --y2k-riel:48px;
  --y2k-izq-ef:var(--y2k-izq-w); --y2k-der-ef:var(--y2k-der-w);
  --y2k-r-panel:18px; --y2k-r-card:14px; --y2k-r-ctl:10px; --y2k-hoja-min:60px; --y2k-hoja-h:var(--y2k-hoja-min);
  --y2k-filtro:blur(18px) saturate(1.5); --y2k-filtro-chico:blur(10px) saturate(1.4);
  --y2k-lite:0; --y2k-dur:.22s;
  color-scheme:light dark;
}
html, body, .stApp, [class*="st-"], button, input, textarea, select{font-family:"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif}
/* los iconos de Streamlit son una fuente: sin esto salen como texto ("dark_mode") */
[data-testid="stIconMaterial"], [data-testid="stExpanderIcon"]{font-family:"Material Symbols Rounded" !important}
.stApp{background:var(--y2k-bg);color:var(--y2k-ink)}
/* fondo ambiental: halos suaves y una rejilla tenue (no compite con el contenido) */
.stApp::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(55% 45% at 6% 0%,var(--y2k-halo-1),transparent 70%),
    radial-gradient(45% 40% at 100% 8%,var(--y2k-halo-2),transparent 70%),
    radial-gradient(60% 45% at 50% 105%,var(--y2k-halo-3),transparent 70%),
    linear-gradient(var(--y2k-rejilla) 1px,transparent 1px) 0 0/48px 48px,
    linear-gradient(90deg,var(--y2k-rejilla) 1px,transparent 1px) 0 0/48px 48px}
[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:transparent}
/* el menu de Streamlit se oculta: tema y contraste se cambian en "Apariencia" */
[data-testid="stMainMenu"]{visibility:hidden !important}
header[data-testid="stHeader"]{background:transparent;pointer-events:none;height:0;min-height:0}
[data-testid="stToolbar"]{pointer-events:none !important}
header[data-testid="stHeader"] button,header[data-testid="stHeader"] a,[data-testid="stToolbar"] button{pointer-events:auto !important}
[data-testid="stStatusWidget"]{display:none !important}
/* Streamlit atenua lo que recalcula (en oscuro parece una pantalla negra): el mapa y el escaner avisan la carga */
[data-stale="true"]{opacity:1 !important;transition:none !important}
.stMainBlockContainer{padding:calc(var(--y2k-top) + 24px) 24px 32px;max-width:1180px}
/* contenedores de guiones (alto cero): no ocupan lugar */
.st-key-y2k_orbita,.st-key-y2k_escaner,.st-key-y2k_hipso,.st-key-y2k_velo,.st-key-y2k_precal,.st-key-y2k_precal_mapa,
.st-key-y2k_guiones,.st-key-y2k_ocultos{height:0 !important;min-height:0 !important;overflow:hidden !important;margin:0 !important;padding:0 !important;gap:0 !important;position:absolute !important;pointer-events:none}
h1,h2,h3,h4{color:var(--y2k-ink);font-weight:650 !important;letter-spacing:-.01em}
h1 *,h2 *,h3 *,h4 *{font-weight:inherit !important}
a{color:var(--y2k-accent)}
/* foco visible en todos los temas */
:is(button,a,input,select,textarea,summary,[role="radio"],[role="tab"],[tabindex]):focus-visible{
  outline:2px solid var(--y2k-foco) !important;outline-offset:2px !important;box-shadow:none !important}
.stMarkdown p, [data-testid="stMarkdownContainer"] p{color:var(--y2k-ink-2)}
[data-testid="stWidgetLabel"] p{color:var(--y2k-ink) !important;font-weight:600;font-size:13px !important}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p{color:var(--y2k-ink-3) !important}
.y2k-hint,[data-testid="stMarkdownContainer"] p.y2k-hint{font-size:12.5px !important;line-height:1.45 !important;color:var(--y2k-ink-3) !important;margin:0 !important}
[data-testid="stMarkdownContainer"]:has(> .y2k-md){margin-bottom:0 !important}
[data-testid="stCheckbox"] label:has(input:focus-visible) > span + div{outline:2px solid var(--y2k-foco);outline-offset:2px}
.y2k-vh{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}

/* ---------- barra superior ---------- */
.y2k-top{position:fixed;top:0;left:0;right:0;height:var(--y2k-top);z-index:999990;display:flex;align-items:center;gap:18px;
  padding:0 16px;padding-right:var(--y2k-acciones-w,320px);background:var(--y2k-glass-fuerte);
  -webkit-backdrop-filter:var(--y2k-filtro);backdrop-filter:var(--y2k-filtro);border-bottom:1px solid var(--y2k-glass-filo)}
.y2k-top::after{content:"";position:absolute;left:0;right:0;bottom:-1px;height:1px;opacity:.6;
  background:linear-gradient(90deg,transparent,var(--y2k-accent-2) 30%,var(--y2k-accent) 70%,transparent)}
.y2k-marca{display:flex;align-items:center;gap:10px;color:var(--y2k-ink);white-space:nowrap;text-decoration:none}
.y2k-marca svg{width:28px;height:28px;flex:none}
.y2k-marca b{font-size:15px;font-weight:700;letter-spacing:-.01em}
.y2k-marca span{font-size:12px;color:var(--y2k-ink-3);font-weight:500}
.y2k-top nav{min-width:0;overflow:hidden;flex:0 1 auto}
.y2k-pasos{display:flex;align-items:center;gap:4px;list-style:none;margin:0;padding:0;min-width:0;overflow:hidden}
@media (max-width: 1200px){.y2k-pasos li:not(.on) .t{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
  .y2k-pasos li:not(.on){padding-right:5px}}
.y2k-pasos li{display:flex;align-items:center;gap:6px;padding:4px 10px 4px 5px;border-radius:999px;font-size:12.5px;
  font-weight:600;color:var(--y2k-ink-3);white-space:nowrap}
.y2k-pasos li .n{width:20px;height:20px;border-radius:50%;display:grid;place-items:center;font-size:11px;
  border:1px solid var(--y2k-line-2);font-variant-numeric:tabular-nums}
.y2k-pasos li.done{color:var(--y2k-ink-2)}
.y2k-pasos li.done .n{border-color:var(--y2k-ok);color:var(--y2k-ok)}
.y2k-pasos li.on{color:var(--y2k-ink);background:var(--y2k-accent-suave)}
.y2k-pasos li.on .n{background:var(--y2k-accent);border-color:var(--y2k-accent);color:var(--y2k-sobre-acento)}
.y2k-pasos li.sep{padding:0;width:14px;height:1px;border-radius:0;background:var(--y2k-line-2);flex:none}
.y2k-top .meta{font-size:12px;color:var(--y2k-ink-3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0}

/* acciones globales (Lite, Apariencia, Manual), fijas en la barra */
.st-key-y2k_acciones{position:fixed !important;top:calc((var(--y2k-top) - 36px) / 2);right:14px;z-index:999991;width:auto !important;
  display:flex !important;flex-direction:row !important;align-items:center;gap:8px !important}
.st-key-y2k_acciones > div{width:auto !important}
.st-key-y2k_acciones button,.y2k-accion{height:36px !important;min-height:36px !important;padding:0 12px !important;border-radius:var(--y2k-r-ctl) !important;
  background:var(--y2k-ctl) !important;border:1px solid var(--y2k-line-2) !important;color:var(--y2k-ink) !important;
  font:600 13px/1 "Figtree",system-ui,sans-serif !important;display:inline-flex;align-items:center;gap:6px;text-decoration:none !important;
  box-shadow:none !important;white-space:nowrap}
.st-key-y2k_acciones button:hover,.y2k-accion:hover{border-color:var(--y2k-accent) !important;color:var(--y2k-accent) !important}
.st-key-y2k_acciones button p{font-size:13px !important;font-weight:600 !important;color:inherit !important}
.y2k-accion svg{width:16px;height:16px}
/* Lite activo: se distingue por color y por el texto del boton (no solo por color) */
.st-key-btn_lite button[kind="primary"]{background:var(--y2k-accent) !important;border-color:var(--y2k-accent) !important;color:var(--y2k-sobre-acento) !important}
.st-key-btn_lite button[kind="primary"]:hover{color:var(--y2k-sobre-acento) !important;filter:brightness(1.08)}
.st-key-y2k_acciones iframe{display:none}
[data-testid="stPopoverBody"]{border-radius:14px !important;border:1px solid var(--y2k-line-2) !important;background:var(--y2k-surface) !important}
[data-testid="stPopoverBody"] .y2k-hint{margin-top:6px !important}

/* ---------- controles ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button{border-radius:var(--y2k-r-ctl) !important;font-weight:600 !important;
  min-height:40px;transition:filter var(--y2k-dur),border-color var(--y2k-dur),background var(--y2k-dur)}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"]{
  background:linear-gradient(180deg,color-mix(in srgb,var(--y2k-accent) 88%,#fff 12%),var(--y2k-accent)) !important;
  border:1px solid color-mix(in srgb,var(--y2k-accent) 70%,#000 30%) !important;color:var(--y2k-sobre-acento) !important;
  box-shadow:0 1px 0 rgba(255,255,255,.25) inset,0 6px 16px -8px var(--y2k-accent) !important;font-weight:700 !important}
.stButton > button[kind="primary"] p, .stDownloadButton > button[kind="primary"] p{color:var(--y2k-sobre-acento) !important}
.stButton > button[kind="primary"]:hover, .stDownloadButton > button[kind="primary"]:hover{filter:brightness(1.07)}
.stButton > button[kind="primary"]:disabled{filter:grayscale(.6);opacity:.55}
.stButton > button[kind="secondary"], .stDownloadButton > button[kind="secondary"]{background:var(--y2k-ctl) !important;
  border:1px solid var(--y2k-line-2) !important;color:var(--y2k-ink) !important}
.stButton > button[kind="secondary"] p{color:var(--y2k-ink) !important}
.stButton > button[kind="secondary"]:hover{border-color:var(--y2k-accent) !important;color:var(--y2k-accent) !important}
.stButton > button[kind="tertiary"]{color:var(--y2k-accent) !important;min-height:32px;padding:0 4px !important}
[data-testid="stExpander"] details{border-radius:12px !important;border-color:var(--y2k-line-2) !important;background:var(--y2k-surface-2)}
[data-testid="stExpander"] summary p{font-weight:600;color:var(--y2k-ink) !important}
[data-testid="stAlert"]{border-radius:12px}
[data-testid="stDataFrame"]{border-radius:10px;overflow:hidden}
[data-testid="stButtonGroup"] button[role="radio"]{min-height:34px}

/* tarjetas de vidrio (contenedores con clave y2k_card...) */
[class*="st-key-y2k_card"]{background:var(--y2k-glass);-webkit-backdrop-filter:var(--y2k-filtro);backdrop-filter:var(--y2k-filtro);
  border:1px solid var(--y2k-glass-borde);border-radius:var(--y2k-r-card);box-shadow:var(--y2k-elev);padding:16px 18px}
.st-key-y2k_card_sel{padding:12px 14px;gap:6px !important;background:var(--y2k-surface-2);box-shadow:none;border-color:var(--y2k-line-2);
  -webkit-backdrop-filter:none;backdrop-filter:none}

/* cifras del resumen: la etiqueta se parte en dos lineas si no cabe */
.y2k-cifras{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:0}
.y2k-cifra{background:var(--y2k-surface-2);border:1px solid var(--y2k-line);border-radius:12px;padding:9px 11px;min-width:0}
.y2k-cifra .l{font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;color:var(--y2k-ink-3);line-height:1.25}
.y2k-cifra .v{font-size:clamp(17px,1.4vw,22px);font-weight:700;color:var(--y2k-ink);line-height:1.2;margin-top:3px;
  overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
.y2k-cifra .s{font-size:12px;color:var(--y2k-ink-3);margin-top:1px;line-height:1.3}
.y2k-alerta{border:1px solid var(--y2k-alerta-borde);background:var(--y2k-alerta-bg);border-radius:10px;padding:8px 11px;font-size:13px;color:var(--y2k-ink);margin:0}
/* alertas compactas de altitud: un desplegable naranja de una linea */
.st-key-alerta_altura [data-testid="stExpander"] details,.st-key-alerta_ficha [data-testid="stExpander"] details{
  border-color:var(--y2k-alerta-borde) !important;background:var(--y2k-alerta-bg)}
.st-key-alerta_altura summary p,.st-key-alerta_ficha summary p{font-size:13px !important;font-weight:600}
.st-key-alerta_altura [data-testid="stIconMaterial"],.st-key-alerta_ficha [data-testid="stIconMaterial"]{color:var(--y2k-alerta) !important}

/* detalles desplegables propios (elemento details): resumen breve + "Ver detalles" */
details.y2k-det{font-size:12.5px;line-height:1.45;color:var(--y2k-ink-3);margin:0}
details.y2k-det summary{cursor:pointer;list-style:none;display:flex;flex-wrap:wrap;gap:2px 8px;align-items:baseline;border-radius:6px}
details.y2k-det summary::-webkit-details-marker{display:none}
details.y2k-det summary .ver{color:var(--y2k-accent);font-weight:600;text-decoration:underline;text-underline-offset:2px;white-space:nowrap}
details.y2k-det summary .ver::after{content:" ▾";text-decoration:none;display:inline-block}
details.y2k-det[open] summary .ver::after{content:" ▴"}
details.y2k-det > div{margin-top:6px;color:var(--y2k-ink-2)}
details.y2k-det > div p{margin:0 0 6px !important;font-size:12.5px !important;color:var(--y2k-ink-2) !important}
details.y2k-det b{color:var(--y2k-ink)}
/* aviso legal: una linea; el texto completo se despliega */
details.y2k-legal{font-size:12px}

/* pie institucional */
.y2k-pie{margin-top:8px;padding:10px 2px 4px;font-size:12px;line-height:1.5;color:var(--y2k-ink-3);border-top:1px solid var(--y2k-line)}
.y2k-pie b{color:var(--y2k-ink);font-weight:600}
.y2k-pie a{color:var(--y2k-accent) !important;text-decoration:none}
.y2k-pie a:hover{text-decoration:underline}
.y2k-pie .fila{display:flex;flex-wrap:wrap;gap:2px 14px}
.y2k-pie details{margin-top:4px}

/* ---------- pantalla de inicio ---------- */
.y2k-hello{text-align:center;padding:18px 0 6px}
.y2k-hello h1{font-size:clamp(26px,3.4vw,40px) !important;margin:0;line-height:1.1;font-weight:700 !important}
.y2k-hello p{color:var(--y2k-ink-2);margin:10px auto 0;max-width:56ch;font-size:16px}
.y2k-chip-dato{display:inline-flex;align-items:center;gap:6px;margin-top:12px;padding:4px 12px;border-radius:999px;font-size:12.5px;
  font-weight:600;color:var(--y2k-ink-2);background:var(--y2k-glass);border:1px solid var(--y2k-glass-borde)}
.y2k-chip-dato i{width:7px;height:7px;border-radius:50%;background:var(--y2k-ok);display:block}
.y2k-card-head{display:flex;gap:14px;align-items:flex-start}
.y2k-card-head svg{width:40px;height:40px;flex:none;padding:8px;border-radius:12px;color:var(--y2k-accent);background:var(--y2k-accent-suave)}
.y2k-card-head h2{font-size:18px !important;margin:0;padding:0 !important}
.y2k-card-head p{margin:3px 0 0;color:var(--y2k-ink-2);font-size:13.5px}
p.y2k-formatos,[data-testid="stMarkdownContainer"] p.y2k-formatos{font-size:12.5px !important;color:var(--y2k-ink-3) !important;margin:10px 0 0 !important}
[data-testid="stFileUploaderDropzone"]{border-radius:12px;background:var(--y2k-surface-2);border:1px dashed var(--y2k-line-2)}

/* ---------- descarga ---------- */
.y2k-consola{background:#08120D;border-radius:12px;border:1px solid #1F3A28;padding:12px 14px;
  font:13px/1.45 ui-monospace,"SFMono-Regular","Cascadia Mono",Menlo,Consolas,monospace;color:#8CFFA8;height:360px;overflow:hidden;
  display:flex;flex-direction:column;justify-content:flex-end}
.y2k-consola div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.y2k-consola .d{color:#7FB98C} .y2k-consola .w{color:#FFD37A}
.y2k-pbar{display:grid;grid-template-columns:repeat(32,1fr);gap:3px;padding:5px;border:1px solid var(--y2k-line-2);border-radius:10px;background:var(--y2k-surface-2)}
.y2k-pbar i{height:10px;border-radius:3px;background:var(--y2k-line)}
.y2k-pbar i.on{background:linear-gradient(90deg,var(--y2k-accent-2),var(--y2k-accent))}
.y2k-pmeta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;font-size:13px;color:var(--y2k-ink-2);margin-top:6px;font-variant-numeric:tabular-nums}
.y2k-pmeta b{color:var(--y2k-ink)}
.ideam-estado{display:none}
.y2k-titulo-seccion{font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--y2k-ink-3);margin:0}
"""

# ---------------------------------------------------------------------------
# Pantalla de estaciones: el mapa ocupa el viewport; paneles plegables a los
# lados (escritorio) o una hoja inferior contraible (celular).
# ---------------------------------------------------------------------------
_PLEGADO = """
{P}{{--y2k-{lado}-ef:var(--y2k-riel)}}
{P} .st-key-y2k_{panel}{{padding:8px 6px !important;overflow:hidden !important}}
{P} .st-key-y2k_{panel} > :not(:first-child){{display:none !important}}
{P} .st-key-y2k_{panel} .y2k-panel-cab{{flex-direction:column;gap:12px}}
{P} .st-key-y2k_{panel} .y2k-panel-cab h2{{writing-mode:vertical-rl;transform:rotate(180deg);font-size:13px !important;letter-spacing:.04em}}
{P} .st-key-y2k_{panel} .y2k-plegar svg{{transform:rotate(180deg)}}
{P} .st-key-y2k_{panel} .y2k-panel-cab h2 small{{display:none}}
"""

CSS_MAPA = """
/* cambio de pantalla: lo fijo de la pantalla anterior no debe tapar la nueva mientras Streamlit termina */
.stMain:has([data-stale="false"] .y2k-top:not([data-pantalla="estaciones"])) :is(.st-key-y2k_escenario,.st-key-y2k_hoja,
  .st-key-y2k_consulta,.st-key-y2k_resumen){display:none !important}
.stMain:has([data-stale="false"] .y2k-top) [data-stale="true"] .y2k-top{display:none}
.stMain:has(.st-key-y2k_escenario){overflow:hidden !important}
.stMainBlockContainer:has(.st-key-y2k_escenario){padding:0 !important;max-width:none}
.st-key-y2k_hoja{height:0;min-height:0;gap:0 !important}
.y2k-hoja-cab{display:none}
/* paneles laterales */
.st-key-y2k_consulta,.st-key-y2k_resumen{position:fixed !important;top:calc(var(--y2k-top) + var(--y2k-g));bottom:var(--y2k-g);z-index:20;
  overflow-y:auto;overscroll-behavior:contain;scrollbar-width:thin;scrollbar-color:var(--y2k-line-2) transparent;
  padding:12px 16px 0 !important;gap:14px !important;border-radius:var(--y2k-r-panel);background:var(--y2k-glass);
  -webkit-backdrop-filter:var(--y2k-filtro);backdrop-filter:var(--y2k-filtro);border:1px solid var(--y2k-glass-borde);box-shadow:var(--y2k-elev);
  transition:width var(--y2k-dur) ease}
.st-key-y2k_consulta{left:var(--y2k-g);width:var(--y2k-izq-ef) !important}
.st-key-y2k_resumen{right:var(--y2k-g);width:var(--y2k-der-ef) !important}
.st-key-y2k_consulta > div,.st-key-y2k_resumen > div{width:100% !important}
.y2k-panel-cab{display:flex;align-items:center;justify-content:space-between;gap:8px;position:sticky;top:0}
.y2k-panel-cab h2{font-size:15px !important;margin:0;padding:0 !important;font-weight:700 !important;letter-spacing:0}
.y2k-panel-cab h2 small{font-size:12px;font-weight:600;color:var(--y2k-ink-3);margin-left:6px}
.y2k-plegar{all:unset;box-sizing:border-box;width:34px;height:34px;display:grid;place-items:center;border-radius:10px;cursor:pointer;
  color:var(--y2k-ink-2);border:1px solid var(--y2k-line-2);background:var(--y2k-ctl);flex:none}
.y2k-plegar:hover{color:var(--y2k-accent);border-color:var(--y2k-accent)}
.y2k-plegar svg{width:18px;height:18px;transition:transform var(--y2k-dur)}
p.y2k-seccion,[data-testid="stMarkdownContainer"] p.y2k-seccion{font-size:11.5px !important;line-height:1.2 !important;text-transform:uppercase;
  letter-spacing:.08em;font-weight:700;color:var(--y2k-ink-3) !important;margin:10px 0 -6px !important}
.st-key-y2k_consulta [data-testid="stMarkdownContainer"] p,.st-key-y2k_resumen [data-testid="stMarkdownContainer"] p{font-size:13.5px}
/* accion principal siempre a la vista al final del panel */
[data-testid="stLayoutWrapper"]:has(> .st-key-y2k_accion){position:sticky;bottom:0;z-index:2;margin:0 -16px;width:calc(100% + 32px) !important;max-width:none !important}
.st-key-y2k_accion{padding:12px 16px 12px !important;gap:8px !important;background:var(--y2k-glass-fuerte);border-top:1px solid var(--y2k-line);
  -webkit-backdrop-filter:var(--y2k-filtro-chico);backdrop-filter:var(--y2k-filtro-chico)}
.st-key-y2k_resumen .st-key-y2k_pie_panel{padding-bottom:12px}
/* escenario del mapa */
.st-key-y2k_escenario{position:fixed !important;top:calc(var(--y2k-top) + var(--y2k-g));bottom:var(--y2k-g);z-index:10;
  left:calc(var(--y2k-izq-ef) + var(--y2k-g) * 2);right:calc(var(--y2k-der-ef) + var(--y2k-g) * 2);width:auto !important;
  border-radius:var(--y2k-r-panel);overflow:hidden;background:var(--y2k-mapa-fondo);border:1px solid var(--y2k-glass-filo);
  box-shadow:var(--y2k-elev);gap:0 !important;transition:left var(--y2k-dur) ease,right var(--y2k-dur) ease}
.st-key-y2k_mapa2d,.st-key-y2k_visor3d{position:absolute !important;inset:0;width:auto !important;height:auto !important;min-height:0 !important;gap:0 !important}
.st-key-y2k_mapa2d > [data-testid="stElementContainer"],.st-key-y2k_mapa2d > [data-testid="stElementContainer"] > div,
.st-key-y2k_visor3d > [data-testid="stElementContainer"],.st-key-y2k_visor3d [data-testid="stFullScreenFrame"],
.st-key-y2k_visor3d [data-testid="stDeckGlJsonChart"],.st-key-y2k_visor3d [data-testid="stDeckGlJsonChart"] > div{
  height:100% !important;width:100% !important;max-height:none !important}
.st-key-y2k_mapa2d > [data-testid="stElementContainer"],.st-key-y2k_visor3d > [data-testid="stElementContainer"]{flex:1 1 auto !important}
.st-key-y2k_mapa2d iframe{height:100% !important;width:100% !important;display:block}
/* cielo detras del relieve 3D (el 3D no tiene mapa plano de fondo) */
[data-testid="stDeckGlJsonChart"]{background:var(--y2k-cielo);overflow:hidden}
/* herramientas sobre el mapa (vidrio chico, sin tapar los controles de Leaflet de las esquinas) */
.st-key-vista{position:absolute !important;top:10px;left:50%;transform:translateX(-50%);z-index:30;width:auto !important}
.st-key-y2k_tex3d{position:absolute !important;top:10px;left:10px;z-index:30;width:auto !important;max-width:calc(50% - 80px);
  flex-direction:row !important;flex-wrap:wrap;gap:6px !important}
.st-key-y2k_tex3d > div{width:auto !important}
.st-key-vista [data-testid="stButtonGroup"] > div,.st-key-y2k_tex3d [data-testid="stButtonGroup"] > div{
  background:var(--y2k-glass-fuerte);-webkit-backdrop-filter:var(--y2k-filtro-chico);backdrop-filter:var(--y2k-filtro-chico);
  padding:3px;border-radius:12px;border:1px solid var(--y2k-glass-borde);box-shadow:0 6px 18px -10px var(--y2k-sombra);gap:2px}
.st-key-vista button[role="radio"],.st-key-y2k_tex3d button[role="radio"]{border-radius:9px !important;border:0 !important;min-height:32px;padding:0 12px}
.st-key-vista button[role="radio"]{min-width:52px}
.st-key-vista button[aria-checked="true"],.st-key-y2k_tex3d button[aria-checked="true"]{background:var(--y2k-accent) !important;color:var(--y2k-sobre-acento) !important}
.st-key-vista button[aria-checked="true"] p,.st-key-y2k_tex3d button[aria-checked="true"] p{color:var(--y2k-sobre-acento) !important;font-weight:700}
.y2k-sobre{position:absolute;z-index:25;pointer-events:auto}
.y2k-sobre-caja{background:var(--y2k-glass-fuerte);-webkit-backdrop-filter:var(--y2k-filtro-chico);backdrop-filter:var(--y2k-filtro-chico);
  border:1px solid var(--y2k-glass-borde);border-radius:12px;box-shadow:0 8px 22px -12px var(--y2k-sombra);color:var(--y2k-ink)}
.st-key-y2k_escenario > [data-testid="stElementContainer"]:has(.y2k-sobre){position:absolute !important;inset:0;width:auto !important;
  height:auto !important;pointer-events:none;z-index:25;margin:0}
.st-key-y2k_escenario > [data-testid="stElementContainer"]:has(.y2k-sobre) *:has(.y2k-sobre){position:static !important}
/* leyenda (desplegable) */
.y2k-leyenda{left:10px;bottom:60px;max-width:min(320px,calc(100% - 20px))}
.y2k-leyenda.en3d{bottom:10px}
.y2k-leyenda summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;padding:7px 11px;font-size:12.5px;font-weight:700;border-radius:12px}
.y2k-leyenda summary::-webkit-details-marker{display:none}
.y2k-leyenda summary::after{content:"▴";font-size:10px;color:var(--y2k-ink-3)}
.y2k-leyenda[open] summary::after{content:"▾"}
.y2k-leyenda ul{list-style:none;margin:0;padding:0 11px 9px;display:grid;grid-template-columns:auto auto;gap:3px 14px;font-size:12px;color:var(--y2k-ink-2)}
.y2k-leyenda li{display:flex;align-items:center;gap:8px;margin:0}
.y2k-leyenda .pin{width:12px;height:12px;border-radius:50%;flex:none;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.45)}
.y2k-leyenda .pin.hueco{background:transparent !important;border-color:#E6ECF7}
.y2k-leyenda .pin.duda{border-color:#D0602F;box-shadow:0 0 0 1px #fff}
.y2k-leyenda .linea{width:18px;height:0;border-top:3px solid;flex:none}
.y2k-leyenda .rampa{height:10px;border-radius:5px;margin:2px 11px 2px;border:1px solid var(--y2k-line)}
.y2k-leyenda .marcas{display:flex;justify-content:space-between;font-size:11.5px;color:var(--y2k-ink-3);padding:0 11px 9px;font-variant-numeric:tabular-nums}
/* controles de camara 3D (alternativa a los gestos) */
.y2k-camara{right:10px;top:50%;transform:translateY(-50%);display:flex;flex-direction:column;gap:2px;padding:3px}
/* pantallas bajas (celular en horizontal): la leyenda 2D no tapa la barra de dibujo y la camara va en fila */
@media (max-height: 520px){
  .y2k-leyenda:not(.en3d){left:auto;right:10px;bottom:28px}
  .y2k-camara{flex-direction:row;top:auto;bottom:10px;transform:none}
  .y2k-camara hr{border-top:0;border-left:1px solid var(--y2k-line);margin:4px 2px}
  .y2k-sobre.y2k-atrib3d{bottom:62px}
}
.y2k-camara button{all:unset;box-sizing:border-box;width:36px;height:36px;display:grid;place-items:center;border-radius:9px;cursor:pointer;color:var(--y2k-ink)}
.y2k-camara button:hover{background:var(--y2k-accent-suave);color:var(--y2k-accent)}
.y2k-camara button:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:-2px}
.y2k-camara svg{width:18px;height:18px}
.y2k-camara hr{border:0;border-top:1px solid var(--y2k-line);margin:2px 4px}
/* aviso de navegador con proteccion de privacidad (terreno.AVISO_NAVEGADOR): arriba al centro, sin chocar con la leyenda */
.y2k-aviso3d{left:50% !important;top:56px !important;bottom:auto !important;transform:translateX(-50%);z-index:26 !important}
.y2k-vacio{left:50%;top:50%;transform:translate(-50%,-50%);padding:12px 16px;font-size:14px;font-weight:600;text-align:center;max-width:80%}
.y2k-leyenda-alt{width:min(280px,calc(100% - 80px))}
.y2k-leyenda-alt .tit{margin:0;padding:8px 11px 4px;font-size:12.5px;font-weight:700;color:var(--y2k-ink)}
.y2k-atrib3d{right:10px;bottom:8px;font-size:10.5px;line-height:1.3;padding:2px 8px;border-radius:6px;color:var(--y2k-ink-2);max-width:60%}
.y2k-leyenda .nota{grid-column:1 / -1;font-size:11.5px;color:var(--y2k-ink-3);margin-top:2px}
/* dialogos de fallo (los pone el guion de la interfaz) */
.y2k-dialogo{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);z-index:60;width:min(400px,calc(100% - 28px));
  display:flex;flex-direction:column;gap:8px;padding:16px 18px;border-radius:16px;background:var(--y2k-glass-fuerte);
  -webkit-backdrop-filter:var(--y2k-filtro);backdrop-filter:var(--y2k-filtro);border:1px solid var(--y2k-alerta-borde);
  box-shadow:0 24px 60px -24px rgba(0,0,0,.6);color:var(--y2k-ink);font-size:13.5px;line-height:1.45}
.y2k-dialogo h3{font-size:15.5px !important;margin:0 !important;padding:0 !important;display:flex;gap:8px;align-items:center;color:var(--y2k-ink)}
.y2k-dialogo h3 svg{width:18px;height:18px;color:var(--y2k-alerta);flex:none}
.y2k-dialogo p{margin:0;color:var(--y2k-ink-2)}
.y2k-dialogo .tipo{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;font-weight:700;color:var(--y2k-alerta)}
.y2k-dialogo .botones{display:flex;flex-wrap:wrap;gap:8px;margin-top:4px}
.y2k-dialogo button{font:600 13px/1 "Figtree",system-ui,sans-serif;border-radius:10px;padding:10px 14px;cursor:pointer;
  border:1px solid var(--y2k-line-2);background:var(--y2k-ctl);color:var(--y2k-ink)}
.y2k-dialogo button.prim{background:var(--y2k-accent);border-color:var(--y2k-accent);color:var(--y2k-sobre-acento)}
.y2k-dialogo button:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:2px}

"""
MEDIANA = "(min-width: 761px) and (max-width: 1279px) and (min-height: 521px), (min-width: 1101px) and (max-width: 1279px)"
CSS_MAPA += "@media " + ESCRITORIO + "{" + "".join(
    _PLEGADO.format(P=f'html[data-y2k-{lado}="cerrado"]', lado=lado, panel=panel)
    for lado, panel in (("izq", "consulta"), ("der", "resumen"))) + "}"
CSS_MAPA += ("@media " + MEDIANA + "{" +
             _PLEGADO.format(P='html:not([data-y2k-der="abierto"])', lado="der", panel="resumen") + "}")
# Hoja inferior (celular): el mapa casi a pantalla completa; consulta y resumen en pestanas
CSS_MAPA += "@media " + MOVIL + """{
:root{--y2k-top:52px;--y2k-acciones-w:150px}
html:not([data-y2k-hoja]),html[data-y2k-hoja="min"]{--y2k-hoja-h:calc(var(--y2k-hoja-min) + env(safe-area-inset-bottom))}
html[data-y2k-hoja="media"]{--y2k-hoja-h:min(56dvh,calc(100dvh - var(--y2k-top) - 80px))}
html[data-y2k-hoja="max"]{--y2k-hoja-h:calc(100dvh - var(--y2k-top) - 8px)}
.st-key-y2k_escenario{left:0 !important;right:0 !important;top:var(--y2k-top);bottom:calc(var(--y2k-hoja-min) + env(safe-area-inset-bottom));
  border-radius:0;border:0;box-shadow:none}
.st-key-y2k_hoja{position:fixed !important;left:0;right:0;bottom:0;height:var(--y2k-hoja-h) !important;z-index:40;display:flex !important;
  flex-direction:column;border-radius:18px 18px 0 0;background:var(--y2k-glass-fuerte);-webkit-backdrop-filter:var(--y2k-filtro);
  backdrop-filter:var(--y2k-filtro);border:1px solid var(--y2k-glass-borde);border-bottom:0;box-shadow:0 -14px 40px -20px rgba(0,0,0,.55);
  padding-bottom:env(safe-area-inset-bottom);transition:height var(--y2k-dur) ease;overflow:hidden}
.st-key-y2k_hoja.arrastrando{transition:none}
.st-key-y2k_hoja > div{width:100% !important}
.y2k-hoja-cab{display:flex;flex-direction:column;gap:6px;padding:0 12px 8px;flex:none}
.y2k-asa{all:unset;box-sizing:border-box;align-self:stretch;height:22px;display:grid;place-items:center;cursor:grab;touch-action:none}
.y2k-asa::before{content:"";width:40px;height:5px;border-radius:3px;background:var(--y2k-line-2)}
.y2k-asa:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:-2px;border-radius:8px}
.y2k-hoja-fila{display:flex;align-items:center;gap:8px}
.y2k-tabs{display:flex;gap:4px;padding:3px;border-radius:12px;background:var(--y2k-surface-2);border:1px solid var(--y2k-line)}
.y2k-tabs button{all:unset;box-sizing:border-box;padding:7px 12px;border-radius:9px;font:600 13px/1 "Figtree",system-ui,sans-serif;
  color:var(--y2k-ink-2);cursor:pointer;min-height:32px;display:flex;align-items:center}
.y2k-tabs button[aria-selected="true"]{background:var(--y2k-accent);color:var(--y2k-sobre-acento)}
.y2k-tabs button:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:1px}
.y2k-estado{font-size:12.5px;color:var(--y2k-ink-2);min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1}
.y2k-atrib3d{font-size:10px;max-width:55%}
.y2k-hoja-max{all:unset;box-sizing:border-box;width:36px;height:36px;display:grid;place-items:center;border-radius:10px;cursor:pointer;
  border:1px solid var(--y2k-line-2);color:var(--y2k-ink-2);flex:none}
.y2k-hoja-max svg{width:18px;height:18px;transition:transform var(--y2k-dur)}
html[data-y2k-hoja="max"] .y2k-hoja-max svg{transform:rotate(180deg)}
.st-key-y2k_consulta,.st-key-y2k_resumen{position:static !important;width:auto !important;flex:1 1 auto;min-height:0;border:0;border-radius:0;
  box-shadow:none;background:transparent;-webkit-backdrop-filter:none;backdrop-filter:none;padding:4px 14px 0 !important;
  border-top:1px solid var(--y2k-line)}
html:not([data-y2k-tab="resumen"]) .st-key-y2k_resumen,html[data-y2k-tab="resumen"] .st-key-y2k_consulta{display:none !important}
html:not([data-y2k-hoja]) :is(.st-key-y2k_consulta,.st-key-y2k_resumen),
html[data-y2k-hoja="min"] :is(.st-key-y2k_consulta,.st-key-y2k_resumen){display:none !important}
.y2k-panel-cab{display:none !important}
[data-testid="stLayoutWrapper"]:has(> .st-key-y2k_accion){margin:0 -14px;width:calc(100% + 28px) !important}
.st-key-y2k_accion{padding:10px 14px calc(10px + env(safe-area-inset-bottom)) !important}
.y2k-top .y2k-pasos,.y2k-top .meta{display:none}
.y2k-top .y2k-marca span,.y2k-marca .largo{display:none}
.y2k-marca .corto{display:inline !important}
.y2k-paso-movil{display:inline-flex !important}
.st-key-y2k_acciones{right:8px;gap:6px !important}
.st-key-y2k_acciones button,.y2k-accion{padding:0 10px !important}
.y2k-oculto-movil,.st-key-y2k_acciones .stPopover button [data-testid="stMarkdownContainer"]{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.st-key-y2k_tex3d{top:52px;max-width:calc(100% - 70px)}
.y2k-leyenda{bottom:52px}
.y2k-leyenda.en3d{bottom:10px}
.y2k-camara button{width:40px;height:40px}
.y2k-aviso3d{top:100px !important}
}
"""

# Alto contraste: sin transparencias ni desenfoque, bordes nitidos, foco grueso
CSS_ALTO = """
:root{--y2k-filtro:none;--y2k-filtro-chico:none}
.stApp::before{display:none}
.y2k-top::after{display:none}
.y2k-top{border-bottom:2px solid var(--y2k-line-2)}
.st-key-y2k_consulta,.st-key-y2k_resumen,.st-key-y2k_escenario,.st-key-y2k_hoja,[class*="st-key-y2k_card"],.y2k-sobre-caja,.y2k-dialogo{
  border:2px solid var(--y2k-line-2) !important;box-shadow:none !important}
.stButton > button,.stDownloadButton > button,.y2k-plegar,.y2k-accion,.y2k-dialogo button,.y2k-tabs button,.y2k-camara button{border-width:2px !important}
.stButton > button[kind="primary"],.stDownloadButton > button[kind="primary"]{background:var(--y2k-accent) !important;box-shadow:none !important;text-decoration:none}
:is(button,a,input,select,textarea,summary,[role="radio"],[role="tab"],[tabindex]):focus-visible{outline:3px solid var(--y2k-foco) !important;outline-offset:3px !important}
.y2k-cifra,.y2k-alerta,[data-testid="stExpander"] details{border-width:2px !important;border-color:var(--y2k-line-2) !important}
.y2k-hint,[data-testid="stMarkdownContainer"] p.y2k-hint,[data-testid="stCaptionContainer"] p{color:var(--y2k-ink-2) !important}
a{text-decoration:underline !important}
.y2k-tabs button[aria-selected="true"],.st-key-vista button[aria-checked="true"],.st-key-y2k_tex3d button[aria-checked="true"]{outline:2px solid var(--y2k-ink);outline-offset:-4px}
"""

# Lite: el mismo contenido y las mismas funciones, sin efectos costosos para la tarjeta grafica
CSS_LITE = """
:root{--y2k-lite:1;--y2k-filtro:none;--y2k-filtro-chico:none;--y2k-dur:0s;--y2k-glass:var(--y2k-surface);--y2k-glass-fuerte:var(--y2k-surface)}
.stApp::before{background:none}
.y2k-top::after{display:none}
.st-key-y2k_consulta,.st-key-y2k_resumen,.st-key-y2k_escenario,[class*="st-key-y2k_card"],.y2k-dialogo,.st-key-y2k_hoja{box-shadow:0 0 0 1px var(--y2k-line-2) !important}
.stButton > button[kind="primary"],.stDownloadButton > button[kind="primary"]{box-shadow:none !important;background:var(--y2k-accent) !important}
.y2k-sobre-caja{box-shadow:none}
*,*::before,*::after{transition-duration:0s !important;animation-duration:0s !important}
"""

# Movimiento reducido (preferencia del sistema; independiente de Lite)
CSS_MOVIMIENTO = """
@media (prefers-reduced-motion: reduce){
  :root{--y2k-dur:0s}
  *,*::before,*::after{transition-duration:0s !important;scroll-behavior:auto !important}
}
"""

# Colores forzados (Windows Alto contraste, etc.): se respetan los colores del usuario; solo se reponen los bordes
# y senales que el navegador quita junto con los fondos y las sombras.
CSS_FORZADOS = """
@media (forced-colors: active){
  :root{--y2k-filtro:none;--y2k-filtro-chico:none}
  .stApp::before,.y2k-top::after{display:none}
  .y2k-top,.st-key-y2k_consulta,.st-key-y2k_resumen,.st-key-y2k_escenario,.st-key-y2k_hoja,[class*="st-key-y2k_card"],
  .y2k-sobre-caja,.y2k-dialogo,.y2k-cifra,.y2k-alerta{border:1px solid CanvasText !important;forced-color-adjust:auto}
  .y2k-plegar,.y2k-accion,.y2k-tabs button,.y2k-camara button,.y2k-dialogo button,.y2k-asa,.y2k-hoja-max{border:1px solid ButtonText !important}
  .y2k-tabs button[aria-selected="true"],.st-key-vista button[aria-checked="true"],.st-key-y2k_tex3d button[aria-checked="true"]{
    border:2px solid Highlight !important;outline:2px solid Highlight}
  .y2k-pasos li.on{outline:2px solid Highlight}
  .y2k-asa::before{background:ButtonText}
  .st-key-vista button[role="radio"],.st-key-y2k_tex3d button[role="radio"]{border:1px solid ButtonText !important}
  /* interruptores y casillas de Streamlit: su forma es solo fondo, que el modo de colores forzados quita */
  [data-testid="stCheckbox"] label > span + div{border:1px solid ButtonText !important}
  [data-testid="stCheckbox"] label > span + div > div{forced-color-adjust:none;background:ButtonText !important}
  [data-testid="stCheckbox"][data-selected="true"] label > span + div{forced-color-adjust:none;background:Highlight !important;border-color:Highlight !important}
  [data-testid="stCheckbox"][data-selected="true"] label > span + div > div{background:HighlightText !important}
  [data-testid="stSlider"] [role="slider"]{outline:2px solid ButtonText}
  .y2k-pbar i{border:1px solid CanvasText}
  .y2k-pbar i.on{forced-color-adjust:none;background:Highlight}
  .y2k-leyenda .pin,.y2k-leyenda .rampa{forced-color-adjust:none}
  :is(button,a,input,select,textarea,summary,[role="radio"],[tabindex]):focus-visible{outline:3px solid Highlight !important}
}
"""


def aplicar(tema="sistema", contraste="sistema", lite=False):
    """Estilos de toda la pagina. st.html con solo <style> no dibuja nada."""
    css = (CSS + CSS_MAPA + _tokens_css(tema, contraste) + (CSS_LITE if lite else "")
           + CSS_MOVIMIENTO + CSS_FORZADOS)
    st.html("<style>" + css + "</style>")


def paleta(tema):
    """Paleta para graficas y mapas. Con "Sistema" se usa el tono que reporta el navegador."""
    if tema == "sistema":
        try:
            tema = "oscuro" if st.context.theme.type == "dark" else "claro"
        except Exception:
            tema = "claro"
    return PALETAS.get(tema, PALETAS["claro"])


# ---------------------------------------------------------------------------
# Iconos de linea (SVG en linea, heredan el color del texto)
# ---------------------------------------------------------------------------
def _svg(cuerpo, vista="0 0 24 24"):
    return (f'<svg viewBox="{vista}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" focusable="false">{cuerpo}</svg>')


ICONOS = {
    "marca": ('<svg viewBox="0 0 32 32" aria-hidden="true" focusable="false"><defs><linearGradient id="y2kg" x1="0" y1="0" x2="1" y2="1">'
              '<stop offset="0" stop-color="#22D3EE"/><stop offset="1" stop-color="#2563EB"/></linearGradient></defs>'
              '<rect x="1" y="1" width="30" height="30" rx="9" fill="url(#y2kg)"/>'
              '<path d="M16 7c3.4 4.3 5.4 7.4 5.4 10a5.4 5.4 0 0 1-10.8 0c0-2.6 2-5.7 5.4-10z" fill="#fff" fill-opacity=".95"/>'
              '<path d="M8 25h16M10 21.5h12" stroke="#fff" stroke-opacity=".7" stroke-width="1.6" stroke-linecap="round"/></svg>'),
    "panel_izq": _svg('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d="M15 10l-2 2 2 2"/>'),
    "panel_der": _svg('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M15 4v16"/><path d="M9 10l2 2-2 2"/>'),
    "subir_hoja": _svg('<path d="M6 15l6-6 6 6"/>'),
    "manual": _svg('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'),
    "dibujar": _svg('<rect x="4" y="6" width="16" height="12" rx="1.5" stroke-dasharray="3 2.4"/><circle cx="4" cy="6" r="1.6" fill="currentColor"/>'
                    '<circle cx="20" cy="18" r="1.6" fill="currentColor"/><path d="M10 12h4M12 10v4"/>'),
    "archivo": _svg('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 17v-6M9.5 13.5 12 11l2.5 2.5"/>'),
    "alerta": _svg('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>'),
    "mas": _svg('<path d="M12 5v14M5 12h14"/>'),
    "menos": _svg('<path d="M5 12h14"/>'),
    "girar_izq": _svg('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>'),
    "girar_der": _svg('<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>'),
    "inclinar_mas": _svg('<path d="M4 18h16"/><path d="M7 14l5-9 5 9"/>'),
    "inclinar_menos": _svg('<path d="M4 18h16"/><path d="M5 14h14"/>'),
    "norte": _svg('<circle cx="12" cy="12" r="9"/><path d="M12 6l3 7h-6z" fill="currentColor" stroke="none"/><path d="M12 13v5"/>'),
}


def _icono(nombre):
    return ICONOS[nombre]


# Compatibilidad con el resto de la app (iconos de las tarjetas de inicio)
ICONO_DIBUJAR = ICONOS["dibujar"]
ICONO_SUBIR = ICONOS["archivo"]


# ---------------------------------------------------------------------------
# Barra superior, preferencias y acciones globales
# ---------------------------------------------------------------------------
NOMBRES_PASOS = ["Cuenca", "Estaciones", "Parámetro y fechas", "Descarga"]


def barra(meta="", activos=frozenset(), hechos=frozenset(), pantalla=""):
    """Barra superior fija: marca, pasos y un dato breve. Las acciones (Lite, Apariencia, Manual) van aparte.
    `pantalla` marca la barra: mientras Streamlit cambia de pantalla, la anterior queda "vieja" (data-stale) y el CSS
    la esconde junto con el mapa fijo (ver CSS_MAPA), para que no tape la pantalla nueva."""
    partes = []
    for i, nombre in enumerate(NOMBRES_PASOS, start=1):
        clase = "on" if i in activos else "done" if i in hechos else ""
        actual = ' aria-current="step"' if i in activos else ""
        marca = "✓" if i in hechos and i not in activos else str(i)
        if partes:
            partes.append('<li class="sep" aria-hidden="true"></li>')
        partes.append(f'<li class="{clase}"{actual}><span class="n" aria-hidden="true">{marca}</span><span class="t">{nombre}'
                      f'{"<span class=y2k-vh> (hecho)</span>" if clase == "done" else ""}</span></li>')
    actual = min(activos) if activos else 1
    md(
        f'<header class="y2k-top" data-pantalla="{pantalla}"><span class="y2k-marca">{ICONOS["marca"]}<b class="largo">Descargador IDEAM</b><b class="corto" style="display:none">IDEAM</b>'
        f'<span class="y2k-paso-movil" style="display:none">Paso {actual}/4</span></span>'
        f'<nav aria-label="Pasos"><ol class="y2k-pasos">{"".join(partes)}</ol></nav>'
        f'{f"<span class=meta>{meta}</span>" if meta else ""}</header>')


def _query(clave, valor, defecto):
    if valor == defecto:
        st.query_params.pop(clave, None)
    else:
        st.query_params[clave] = valor


def _cambiar_lite():
    st.session_state.lite = not st.session_state.get("lite", False)
    _query("lite", "1" if st.session_state.lite else "0", "0")


def _cambiar_tema():
    st.session_state.tema = {v: k for k, v in TEMAS.items()}.get(st.session_state.get("pref_tema"), "sistema")
    _query("tema", st.session_state.tema, "sistema")


def _cambiar_contraste():
    st.session_state.contraste = {v: k for k, v in CONTRASTES.items()}.get(st.session_state.get("pref_contraste"), "sistema")
    _query("contraste", st.session_state.contraste, "sistema")


# Streamlit no deja cambiar su tema desde Python: este guion pulsa, sin que se vea, la opcion
# Sistema/Light/Dark del menu de Streamlit (que esta oculto con CSS).
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


def control_tema():
    """Acciones globales de la barra superior: Lite, Apariencia (tema y contraste) y Manual."""
    ss = st.session_state
    lite = bool(ss.get("lite", False))
    with st.container(key="y2k_acciones", horizontal=True, gap="small"):
        st.button("Lite", key="btn_lite", icon=":material/bolt:", type="primary" if lite else "secondary",
                  on_click=_cambiar_lite,
                  help=("Modo Lite activado: menos efectos y detalle gráfico, mismos datos y funciones. Pulsa para volver "
                        "a calidad completa." if lite else
                        "Activar modo Lite: reduce efectos y detalle gráfico sin quitar datos ni funciones."))
        with st.popover("Apariencia", icon=":material/contrast:", help="Tema y contraste"):
            st.segmented_control("Tema", list(TEMAS.values()), default=TEMAS[ss.get("tema", "sistema")],
                                 key="pref_tema", on_change=_cambiar_tema, required=True)
            st.segmented_control("Contraste", list(CONTRASTES.values()), default=CONTRASTES[ss.get("contraste", "sistema")],
                                 key="pref_contraste", on_change=_cambiar_contraste, required=True)
            st.markdown('<p class="y2k-hint">«Sistema» sigue la configuración de tu equipo. Las animaciones respetan '
                        'su opción de movimiento reducido.</p>', unsafe_allow_html=True)
        md(f'<a class="y2k-accion" href="app/static/manual.html" target="_blank" rel="noopener" '
                f'aria-label="Manual de usuario (se abre en otra pestaña)">{ICONOS["manual"]}'
                f'<span class="y2k-oculto-movil">Manual</span></a>')


# ---------------------------------------------------------------------------
# Interfaz del lado del navegador (se instala una vez en la pagina principal):
#   - pliega/despliega los paneles y la hoja inferior sin recargar nada (data-* en <html>)
#   - botones de camara del 3D (alternativa a los gestos)
#   - avisos de fallo con eleccion explicita: perdida del contexto grafico (WebGL),
#     fallos de red al bajar teselas (2D y 3D) y carga que no termina.
#     Nunca cambia de modo por su cuenta: ofrece «Activar Lite y reintentar» o «Seguir intentando».
# ---------------------------------------------------------------------------
_UI = r"""
(function () {
  var V = "__V__";
  var w = window, d = document, raiz = d.documentElement;
  if (w.__y2kUI && w.__y2kUI.v === V) return;
  if (w.__y2kUI && w.__y2kUI.parar) w.__y2kUI.parar();
  var vivo = true, ciclos = [];
  var ICONO_ALERTA = __ICONO_ALERTA__;
  var MOVIL = __MOVIL__;
  var leer = function (k) { try { return w.localStorage.getItem("y2k_" + k); } catch (e) { return null; } };
  var guardar = function (k, v) { try { w.localStorage.setItem("y2k_" + k, v); } catch (e) {} };
  var esLite = function () { return w.getComputedStyle(raiz).getPropertyValue("--y2k-lite").trim() === "1"; };
  var menosMovimiento = function () { return !!(w.matchMedia && w.matchMedia("(prefers-reduced-motion: reduce)").matches); };
  var esMovil = function () { return !!(w.matchMedia && w.matchMedia(MOVIL).matches); };

  // ---------- paneles (escritorio) ----------
  ["izq", "der"].forEach(function (p) {
    var v = leer("panel_" + p);
    if (v === "abierto" || v === "cerrado") raiz.setAttribute("data-y2k-" + p, v);
  });
  function estadoPanel(p) {
    var v = raiz.getAttribute("data-y2k-" + p);
    if (v) return v;
    return (p === "der" && w.innerWidth < 1280) ? "cerrado" : "abierto";
  }
  function ponerPanel(p, v) {
    raiz.setAttribute("data-y2k-" + p, v);
    guardar("panel_" + p, v);
    // en pantallas medianas cabe un solo panel abierto junto al mapa
    if (v === "abierto" && w.innerWidth < 1280) {
      var otro = p === "izq" ? "der" : "izq";
      raiz.setAttribute("data-y2k-" + otro, "cerrado");
    }
    sincronizar();
  }
  // ---------- hoja inferior (celular) ----------
  var ESTADOS = ["min", "media", "max"];
  function estadoHoja() { return raiz.getAttribute("data-y2k-hoja") || "min"; }
  function ponerHoja(v) { raiz.setAttribute("data-y2k-hoja", v); sincronizar(); }
  function ponerTab(t) { raiz.setAttribute("data-y2k-tab", t); if (estadoHoja() === "min") ponerHoja("media"); sincronizar(); }

  function sincronizar() {
    d.querySelectorAll("[data-y2k-panel]").forEach(function (b) {
      var p = b.getAttribute("data-y2k-panel"), abierto = estadoPanel(p) === "abierto";
      b.setAttribute("aria-expanded", abierto ? "true" : "false");
      var nombre = b.getAttribute("data-nombre") || "";
      b.setAttribute("aria-label", (abierto ? "Plegar " : "Desplegar ") + nombre);
      b.title = (abierto ? "Plegar " : "Desplegar ") + nombre;
    });
    var h = estadoHoja(), t = raiz.getAttribute("data-y2k-tab") || "consulta";
    d.querySelectorAll("[data-y2k-asa]").forEach(function (b) {
      b.setAttribute("aria-expanded", h === "min" ? "false" : "true");
      b.setAttribute("aria-label", h === "min" ? "Mostrar panel" : "Ocultar panel");
    });
    d.querySelectorAll("[data-y2k-hoja-max]").forEach(function (b) {
      b.setAttribute("aria-label", h === "max" ? "Reducir panel" : "Ampliar panel");
      b.title = b.getAttribute("aria-label");
    });
    d.querySelectorAll("[data-y2k-tab-btn]").forEach(function (b) {
      b.setAttribute("aria-selected", b.getAttribute("data-y2k-tab-btn") === t ? "true" : "false");
      b.tabIndex = b.getAttribute("data-y2k-tab-btn") === t ? 0 : -1;
    });
    d.querySelectorAll(".st-key-btn_lite button").forEach(function (b) { b.setAttribute("aria-pressed", esLite() ? "true" : "false"); });
    // los iconos de Streamlit son texto ("bolt", "delete"...): que no se lean como parte del nombre del boton
    d.querySelectorAll('button [data-testid="stIconMaterial"]:not([aria-hidden]), summary [data-testid="stIconMaterial"]:not([aria-hidden])')
      .forEach(function (i) { i.setAttribute("aria-hidden", "true"); });
    d.querySelectorAll("details.y2k-leyenda").forEach(function (det) {
      if (det.__y2kLey) return;
      det.__y2kLey = true;
      var pref = leer("leyenda");
      var abierta = pref ? pref === "abierta" : !esMovil();
      if (det.open !== abierta) det.open = abierta;
      det.addEventListener("toggle", function () { guardar("leyenda", det.open ? "abierta" : "cerrada"); });
    });
  }

  function alClic(ev) {
    var b = ev.target && ev.target.closest ? ev.target.closest("[data-y2k-panel],[data-y2k-asa],[data-y2k-hoja-max],[data-y2k-tab-btn],[data-y2k-cam]") : null;
    if (!b) return;
    if (b.hasAttribute("data-y2k-panel")) {
      var p = b.getAttribute("data-y2k-panel");
      ponerPanel(p, estadoPanel(p) === "abierto" ? "cerrado" : "abierto");
    } else if (b.hasAttribute("data-y2k-asa")) {
      if (b.__y2kArrastre) { b.__y2kArrastre = false; return; }
      ponerHoja(estadoHoja() === "min" ? "media" : "min");
    } else if (b.hasAttribute("data-y2k-hoja-max")) {
      ponerHoja(estadoHoja() === "max" ? "media" : "max");
    } else if (b.hasAttribute("data-y2k-tab-btn")) {
      ponerTab(b.getAttribute("data-y2k-tab-btn"));
    } else if (b.hasAttribute("data-y2k-cam")) {
      camara(b.getAttribute("data-y2k-cam"));
    }
  }
  d.addEventListener("click", alClic, true);

  // Arrastre de la hoja: solo desde el asa (asi no se confunde con mover el mapa)
  var arr = null;
  function hoja() { return d.querySelector(".st-key-y2k_hoja"); }
  function alBajar(ev) {
    var asa = ev.target && ev.target.closest ? ev.target.closest("[data-y2k-asa]") : null;
    var h = hoja();
    if (!asa || !h || !esMovil()) return;
    arr = {asa: asa, y0: ev.clientY, alto0: h.getBoundingClientRect().height, movio: false, id: ev.pointerId};
    try { asa.setPointerCapture(ev.pointerId); } catch (e) {}
  }
  function alMover(ev) {
    if (!arr || ev.pointerId !== arr.id) return;
    var dy = arr.y0 - ev.clientY, h = hoja();
    if (!h) return;
    if (Math.abs(dy) > 6) arr.movio = true;
    if (!arr.movio) return;
    h.classList.add("arrastrando");
    var tope = w.innerHeight - 60;
    h.style.setProperty("height", Math.max(48, Math.min(tope, arr.alto0 + dy)) + "px", "important");
  }
  function alSoltar(ev) {
    if (!arr || ev.pointerId !== arr.id) return;
    var h = hoja(), a = arr; arr = null;
    if (!h) return;
    h.classList.remove("arrastrando");
    if (!a.movio) return;
    a.asa.__y2kArrastre = true;
    var alto = h.getBoundingClientRect().height, vh = w.innerHeight;
    h.style.removeProperty("height");
    ponerHoja(alto < vh * 0.25 ? "min" : alto < vh * 0.72 ? "media" : "max");
  }
  d.addEventListener("pointerdown", alBajar, true);
  d.addEventListener("pointermove", alMover, true);
  d.addEventListener("pointerup", alSoltar, true);
  d.addEventListener("pointercancel", alSoltar, true);
  function alTecla(ev) {
    var tab = ev.target && ev.target.closest ? ev.target.closest("[data-y2k-tab-btn]") : null;
    if (tab && (ev.key === "ArrowLeft" || ev.key === "ArrowRight")) {
      var otra = tab.getAttribute("data-y2k-tab-btn") === "consulta" ? "resumen" : "consulta";
      ponerTab(otra);
      var b2 = d.querySelector('[data-y2k-tab-btn="' + otra + '"]'); if (b2) b2.focus();
      ev.preventDefault(); return;
    }
    var asa = ev.target && ev.target.closest ? ev.target.closest("[data-y2k-asa]") : null;
    if (!asa) return;
    var i = ESTADOS.indexOf(estadoHoja());
    if (ev.key === "ArrowUp") { ponerHoja(ESTADOS[Math.min(2, i + 1)]); ev.preventDefault(); }
    else if (ev.key === "ArrowDown") { ponerHoja(ESTADOS[Math.max(0, i - 1)]); ev.preventDefault(); }
  }
  d.addEventListener("keydown", alTecla, true);

  // Streamlit rehace sus elementos en cada recarga: se vuelven a poner los atributos ARIA
  var pendiente = false;
  var obs = new MutationObserver(function () {
    if (pendiente) return;
    pendiente = true;
    w.requestAnimationFrame(function () { pendiente = false; sincronizar(); });
  });
  obs.observe(d.body, {childList: true, subtree: true});
  sincronizar();

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
    if (accion === "acercar") n.zoom = lim((v.zoom || 10) + 0.6, 1, 20);
    else if (accion === "alejar") n.zoom = lim((v.zoom || 10) - 0.6, 1, 20);
    else if (accion === "izq") n.bearing = (((v.bearing || 0) - 20) + 540) % 360 - 180;
    else if (accion === "der") n.bearing = (((v.bearing || 0) + 20) + 540) % 360 - 180;
    else if (accion === "subir") n.pitch = lim((v.pitch || 0) + 10, 0, 85);
    else if (accion === "bajar") n.pitch = lim((v.pitch || 0) - 10, 0, 85);
    else if (accion === "norte") { n.bearing = 0; }
    n.maxPitch = 85;
    mover(deck, n);
    var r = d.querySelector(".y2k-camara-estado");
    if (r) r.textContent = "Rumbo " + Math.round(((n.bearing || 0) + 360) % 360) + "°, inclinación " + Math.round(n.pitch || 0) + "°, zoom " + (n.zoom || 0).toFixed(1);
  }

  // ---------- dialogos de fallo ----------
  function cerrarDialogo(id) { var x = d.getElementById(id); if (x) x.remove(); }
  function dialogo(contenedor, o) {
    if (!contenedor || d.getElementById(o.id)) return;
    var caja = d.createElement("div");
    caja.className = "y2k-dialogo"; caja.id = o.id;
    caja.setAttribute("role", "alertdialog"); caja.setAttribute("aria-modal", "false");
    caja.setAttribute("aria-labelledby", o.id + "_t"); caja.setAttribute("aria-describedby", o.id + "_d");
    var tipo = d.createElement("span"); tipo.className = "tipo"; tipo.textContent = o.tipo;
    var h = d.createElement("h3"); h.id = o.id + "_t"; h.innerHTML = ICONO_ALERTA; h.appendChild(d.createTextNode(o.titulo));
    var p = d.createElement("p"); p.id = o.id + "_d"; p.textContent = o.texto;
    var fila = d.createElement("div"); fila.className = "botones";
    o.acciones.forEach(function (a, i) {
      var b = d.createElement("button"); b.type = "button"; b.textContent = a.etiqueta;
      if (a.primaria) b.className = "prim";
      b.addEventListener("click", function () { caja.remove(); a.fn(); });
      fila.appendChild(b);
    });
    caja.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { caja.remove(); if (o.alCerrar) o.alCerrar(); } });
    caja.append(tipo, h, p, fila);
    contenedor.appendChild(caja);
    var primero = fila.querySelector("button");
    if (primero) try { primero.focus({preventScroll: true}); } catch (e) {}
  }
  function pulsarOculto(clave) {
    var b = d.querySelector(".st-key-" + clave + " button");
    if (b) b.click();
    return !!b;
  }
  function escenario() { return d.querySelector(".st-key-y2k_escenario"); }

  // Guarda la camara 3D antes de rehacer el visor; se repone cuando aparece el nuevo
  function guardarCamara() {
    var deck = buscarDeck();
    if (deck) w.__y2kCamaraGuardada = {vista: vistaActual(deck), lienzo: lienzo3d()};
  }
  function reponerCamara() {
    var g = w.__y2kCamaraGuardada;
    if (!g) return;
    var l = lienzo3d();
    if (!l || l === g.lienzo) return;
    var deck = buscarDeck();
    if (!deck) return;
    w.__y2kCamaraGuardada = null;
    w.__y2kParaVuelta = w.performance.now();
    var v = Object.assign({}, vistaActual(deck), g.vista);
    ["transitionDuration", "transitionInterpolator"].forEach(function (k) { delete v[k]; });
    mover(deck, v);
  }
  function reintentar3d(conLite) {
    guardarCamara();
    pulsarOculto(conLite ? "y2k_lite_reintentar" : "y2k_reintentar3d");
  }

  // a) Contexto grafico perdido (WebGL): fallo grafico real, distinto de un fallo de red
  function vigilarContexto() {
    var l = lienzo3d();
    if (!l || l.__y2kVigia) return;
    l.__y2kVigia = true;
    l.addEventListener("webglcontextlost", function () {
      var lite = esLite();
      dialogo(escenario(), {
        id: "y2k_dlg_ctx", tipo: "Fallo gráfico", titulo: "Se perdió el contexto gráfico (WebGL)",
        texto: "La vista 3D se detuvo. Suele pasar cuando el navegador se queda sin memoria gráfica. "
          + (lite ? "El modo Lite ya está activo." : "El modo Lite usa menos memoria y conserva los mismos datos."),
        acciones: (lite ? [] : [{etiqueta: "Activar Lite y reintentar", primaria: true, fn: function () { reintentar3d(true); }}])
          .concat([{etiqueta: "Seguir intentando", primaria: lite, fn: function () { reintentar3d(false); }},
                   {etiqueta: "Ver en 2D", fn: function () { pulsarOculto("y2k_pasar2d"); }}])
      });
    });
  }

  // b) Red: se cuentan las descargas de teselas del 3D (relieve e imagen). No es un fallo grafico.
  if (!w.__y2kRed) {
    var original = w.fetch.bind(w);
    w.__y2kRed = {lista: []};
    w.fetch = function (entrada, opciones) {
      var url = typeof entrada === "string" ? entrada : entrada ? (entrada.url || entrada.href || String(entrada)) : "";
      var p = original(entrada, opciones);
      if (!/elevation-tiles-prod|arcgisonline\.com|y2k_hipso/.test(url)) return p;
      var tipo = /arcgisonline\.com/.test(url) ? "imagen" : "relieve";
      var anotar = function (ok) {
        var r = w.__y2kRed.lista; r.push({t: w.performance.now(), ok: ok, tipo: tipo});
        if (r.length > 80) r.shift();
      };
      return p.then(function (resp) { anotar(!!(resp && resp.ok)); return resp; },
                    function (e) { if (!(e && e.name === "AbortError")) anotar(false); throw e; });
    };
  }
  var ultimoAviso3d = -1e9, montaje3d = null;
  function vigilarRed3d() {
    var l = lienzo3d();
    if (!l) {   // se salio del 3D: sus avisos ya no aplican
      montaje3d = null;
      ["y2k_dlg_ctx", "y2k_dlg_red3d", "y2k_dlg_lento3d"].forEach(cerrarDialogo);
      return;
    }
    if (!montaje3d || montaje3d.lienzo !== l) montaje3d = {lienzo: l, t: w.performance.now(), cargado: false, avisado: false};
    var ahora = w.performance.now(), ventana = w.__y2kRed.lista.filter(function (x) { return ahora - x.t < 25000 && x.t > montaje3d.t; });
    if (d.getElementById("y2k_dlg_ctx") || d.getElementById("y2k_dlg_red3d") || d.getElementById("y2k_dlg_lento3d")) return;
    // se mira cada tipo por separado: si falla el relieve, la imagen puede seguir llegando (y al reves)
    var falla = ["relieve", "imagen"].map(function (tipo) {
      var r = ventana.filter(function (x) { return x.tipo === tipo; }), m = r.filter(function (x) { return !x.ok; }).length;
      return {tipo: tipo, malos: m, buenos: r.length - m};
    }).find(function (c) { return c.malos >= 6 && c.buenos * 3 <= c.malos; });
    if (falla && ahora - ultimoAviso3d > 60000) {
      ultimoAviso3d = ahora;
      dialogo(escenario(), {
        id: "y2k_dlg_red3d", tipo: "Problema de red",
        titulo: falla.tipo === "relieve" ? "No cargan los datos de relieve 3D" : "No cargan las imágenes del 3D",
        texto: "Fallaron " + falla.malos + " descargas de teselas en los últimos segundos. Suele ser la conexión o el servidor de mapas, no tu equipo.",
        acciones: (esLite() ? [] : [{etiqueta: "Activar Lite y reintentar", fn: function () { reintentar3d(true); }}])
          .concat([{etiqueta: "Seguir intentando", primaria: true, fn: function () { reintentar3d(false); }}])
      });
      return;
    }
    // c) Carga que no avanza (sin errores de red claros): se pregunta, no se cambia nada solo. Cuenta como avance que el
    //    relieve quede completo o que sigan llegando teselas
    var deck = buscarDeck(), capa = deck && deck.layerManager && deck.layerManager.getLayers().find(function (x) { return x.id === "terreno"; });
    var llegadas = w.__y2kRed.lista.filter(function (x) { return x.ok && x.t > montaje3d.t; }).length;
    if ((capa && capa.isLoaded) || llegadas >= 6) montaje3d.cargado = true;
    if (!montaje3d.cargado && !montaje3d.avisado && ahora - montaje3d.t > 40000) {
      montaje3d.avisado = true;
      dialogo(escenario(), {
        id: "y2k_dlg_lento3d", tipo: "Carga lenta", titulo: "El relieve 3D no termina de cargar",
        texto: "En 40 s llegó muy poco relieve y no hubo errores de red claros. Puede ser una conexión lenta o un equipo con pocos recursos gráficos.",
        acciones: (esLite() ? [] : [{etiqueta: "Activar Lite y reintentar", fn: function () { reintentar3d(true); }}])
          .concat([{etiqueta: "Seguir intentando", primaria: true, fn: function () { montaje3d.avisado = false; montaje3d.t = w.performance.now(); }}])
      });
    }
  }

  // d) Mapa 2D (Leaflet en el iframe de streamlit-folium): teselas que fallan una y otra vez
  var CSS_IFRAME = "html,body,#root,#parent,#parent>.float-child:first-child,#map_div{height:100% !important;width:100% !important;margin:0}" +
    "#parent>.float-child:first-child{float:none !important}" +
    ".leaflet-bar{border:0 !important;border-radius:10px !important;overflow:hidden;box-shadow:0 0 0 1px rgba(14,26,47,.18),0 6px 16px -8px rgba(0,0,0,.45) !important}" +
    ".leaflet-bar a{width:34px !important;height:34px !important;line-height:34px !important;color:#0E1A2F !important}" +
    ".leaflet-touch .leaflet-bar a{width:38px !important;height:38px !important;line-height:38px !important}" +
    ".leaflet-control-layers{border:0 !important;border-radius:10px !important;box-shadow:0 0 0 1px rgba(14,26,47,.18),0 6px 16px -8px rgba(0,0,0,.45) !important;font:13px/1.5 Figtree,system-ui,sans-serif}" +
    ".leaflet-control-scale-line{background:rgba(255,255,255,.85) !important;border-color:#0E1A2F !important;color:#0E1A2F;font:11px Figtree,system-ui,sans-serif}" +
    ".leaflet-control-attribution{background:rgba(255,255,255,.85) !important;color:#253247}" +
    ".leaflet-control-attribution a{color:#1A5FD0}" +
    "a:focus-visible,button:focus-visible{outline:2px solid #1A5FD0 !important;outline-offset:1px}" +
    ".leaflet-tooltip{border-radius:10px;border:1px solid rgba(14,26,47,.18);box-shadow:0 10px 26px -14px rgba(0,0,0,.55);padding:8px 10px}" +
    "html.y2k-lite .leaflet-fade-anim .leaflet-tile,html.y2k-lite .leaflet-fade-anim .leaflet-popup{transition:none !important}" +
    "html.y2k-lite .leaflet-bar,html.y2k-lite .leaflet-control-layers,html.y2k-lite .leaflet-tooltip{box-shadow:0 0 0 1px rgba(14,26,47,.3) !important}";
  function marco2d() {
    var fs = d.querySelectorAll(".st-key-y2k_mapa2d iframe, iframe[title*='st_folium']");
    return fs.length ? fs[0] : null;
  }
  function vigilar2d() {
    var f = marco2d(), win;
    try { win = f && f.contentWindow; } catch (e) { return; }
    if (!win || !win.document || !win.document.head) return;
    var doc = win.document;
    if (!doc.getElementById("y2k-iframe-css")) {
      var s = doc.createElement("style"); s.id = "y2k-iframe-css"; s.textContent = CSS_IFRAME; doc.head.appendChild(s);
      if (win.map && win.map.invalidateSize) try { win.map.invalidateSize(); } catch (e) {}
    }
    doc.documentElement.classList.toggle("y2k-lite", esLite());
    var map = win.map, L = win.L;
    if (!map || !L || map.__y2kTeselas) return;
    map.__y2kTeselas = {lista: []};
    var enganchar = function (capa) {
      if (!(capa instanceof L.TileLayer) || capa.__y2kVigia) return;
      capa.__y2kVigia = true;
      capa.on("tileerror", function () { anotar(capa, false); });
      capa.on("tileload", function () { anotar(capa, true); });
    };
    var anotar = function (capa, ok) {
      if (!map.hasLayer(capa)) return;
      var r = map.__y2kTeselas.lista; r.push({t: w.performance.now(), ok: ok, capa: capa});
      if (r.length > 120) r.shift();
    };
    map.eachLayer(enganchar);
    map.on("layeradd", function (e) { enganchar(e.layer); });
    // si la ventana del mapa cambia de tamano (paneles, hoja, giro del celular), Leaflet se reajusta
    try { new w.ResizeObserver(function () { try { map.invalidateSize({pan: false}); } catch (e) {} }).observe(f); } catch (e) {}
  }
  var ultimoAviso2d = -1e9;
  function revisar2d() {
    var f = marco2d(), win;
    try { win = f && f.contentWindow; } catch (e) { return; }
    var map = win && win.map;
    if (!map || !map.__y2kTeselas || d.getElementById("y2k_dlg_red2d")) return;
    var ahora = w.performance.now(), r = map.__y2kTeselas.lista.filter(function (x) { return ahora - x.t < 20000; });
    var malos = r.filter(function (x) { return !x.ok; }), buenos = r.length - malos.length;
    if (malos.length < 8 || buenos > 0 || ahora - ultimoAviso2d < 45000) return;
    ultimoAviso2d = ahora;
    var capa = malos[malos.length - 1].capa, nombre = map.__y2kBase || "Satélite";
    var redibujar = function () { map.__y2kTeselas.lista = []; try { capa.redraw(); } catch (e) {} };
    dialogo(escenario(), {
      id: "y2k_dlg_red2d", tipo: "Problema de red", titulo: "El mapa base no está cargando",
      texto: "Fallan las teselas de «" + nombre + "». Suele ser la conexión o el servidor de mapas. Las estaciones y tu cuenca siguen en el mapa.",
      acciones: (esLite() ? [] : [{etiqueta: "Activar Lite y reintentar", fn: function () { pulsarOculto("y2k_lite_reintentar"); redibujar(); }}])
        .concat([{etiqueta: "Seguir intentando", primaria: true, fn: redibujar}])
    });
  }

  ciclos.push(setInterval(function () {
    if (!vivo) return;
    try { vigilarContexto(); vigilarRed3d(); reponerCamara(); vigilar2d(); revisar2d(); } catch (e) {}
  }, 1000));
  w.addEventListener("resize", sincronizar);

  w.__y2kUI = {
    v: V, camara: camara, buscarDeck: buscarDeck, esLite: esLite, menosMovimiento: menosMovimiento,
    parar: function () {
      vivo = false; ciclos.forEach(clearInterval); obs.disconnect();
      d.removeEventListener("click", alClic, true); d.removeEventListener("pointerdown", alBajar, true);
      d.removeEventListener("pointermove", alMover, true); d.removeEventListener("pointerup", alSoltar, true);
      d.removeEventListener("pointercancel", alSoltar, true); d.removeEventListener("keydown", alTecla, true);
      w.removeEventListener("resize", sincronizar);
    }
  };
})();
"""


def guiones_globales():
    """Guiones invisibles de toda la pagina: interfaz del navegador y sincronizacion del tema de Streamlit."""
    with st.container(key="y2k_guiones"):
        instalar_ui()
        quiero = {"claro": "Light", "oscuro": "Dark"}.get(st.session_state.get("tema", "sistema"), "System")
        components.html(_SINCRONIZAR_TEMA.replace("__TEMA__", quiero), height=0)


def instalar_ui():
    """Inyecta el guion de la interfaz en la pagina principal (sobrevive a las recargas de Streamlit)."""
    codigo = (_UI.replace("__V__", "10").replace("__ICONO_ALERTA__", json.dumps(ICONOS["alerta"]))
              .replace("__MOVIL__", json.dumps(MOVIL)))
    cuerpo = ("(function(){var w=window.parent;var s=w.document.createElement('script');"
              f"s.textContent={json.dumps(codigo)};w.document.head.appendChild(s);s.remove();}})();")
    components.html("<script>" + cuerpo.replace("</", "<\\/") + "</script>", height=0)


# ---------------------------------------------------------------------------
# Piezas de los paneles
# ---------------------------------------------------------------------------
def cabecera_panel(titulo, lado, extra=""):
    """Titulo del panel con el boton que lo pliega (lo maneja el guion de la interfaz, sin recargar)."""
    icono = ICONOS["panel_izq"] if lado == "izq" else ICONOS["panel_der"]
    md(f'<div class="y2k-panel-cab"><h2>{titulo}{f"<small>{extra}</small>" if extra else ""}</h2>'
            f'<button type="button" class="y2k-plegar" data-y2k-panel="{lado}" data-nombre="panel {titulo}" '
            f'aria-expanded="true" aria-label="Plegar panel {titulo}">{icono}</button></div>')


def cabecera_hoja(estado, n_resumen=None):
    """Cabecera de la hoja inferior (solo celular): asa, pestanas y un estado breve."""
    cuenta = f" ({n_resumen})" if n_resumen else ""
    md(
        '<div class="y2k-hoja-cab"><button type="button" class="y2k-asa" data-y2k-asa aria-expanded="false" '
        'aria-label="Mostrar panel"></button><div class="y2k-hoja-fila">'
        '<div class="y2k-tabs" role="tablist" aria-label="Paneles">'
        '<button type="button" role="tab" data-y2k-tab-btn="consulta" aria-selected="true">Consulta</button>'
        f'<button type="button" role="tab" data-y2k-tab-btn="resumen" aria-selected="false">Resumen{cuenta}</button></div>'
        f'<span class="y2k-estado" role="status">{estado}</span>'
        f'<button type="button" class="y2k-hoja-max" data-y2k-hoja-max aria-label="Ampliar panel">{ICONOS["subir_hoja"]}</button>'
        '</div></div>')


def seccion(titulo):
    md(f'<p class="y2k-seccion">{titulo}</p>')


def detalles(resumen, cuerpo, ver="Ver detalles"):
    """Resumen breve siempre visible y el detalle desplegable (<details>, accesible con teclado)."""
    md(f'<details class="y2k-det"><summary><span>{resumen}</span><span class="ver">{ver}</span></summary>'
            f'<div>{cuerpo}</div></details>')


def leyenda_estaciones(colores, abierta=True, en3d=False):
    """Leyenda compacta de los pines sobre el mapa (color + forma + texto)."""
    filas = "".join(f'<li><span class="pin" style="background:{c}"></span>{n}</li>' for n, c in colores)
    filas += ('<li><span class="pin hueco"></span>Sin serie</li>'
              '<li><span class="pin duda" style="background:#9AA6BC"></span>Altitud dudosa</li>')
    filas += ('<li><span class="linea" style="border-color:#35F0FF"></span>Cuenca</li>'
              '<li><span class="linea" style="border-color:#FF7A1A;border-top-style:dashed"></span>Buffer</li>'
              '<li class="nota">Relieve ×2 · Ctrl + arrastrar gira e inclina</li>') if en3d else (
              '<li><span class="linea" style="border-color:#1C6FD8"></span>Cuenca</li>'
              '<li><span class="linea" style="border-color:#FAB219;border-top-style:dashed"></span>Buffer</li>')
    md(f'<details class="y2k-sobre y2k-sobre-caja y2k-leyenda{" en3d" if en3d else ""}"{" open" if abierta else ""}>'
            f'<summary>Leyenda</summary><ul>{filas}</ul></details>')


def controles_camara():
    """Botones de camara del 3D: alternativa accesible a arrastrar, girar e inclinar con gestos."""
    b = [("acercar", "mas", "Acercar"), ("alejar", "menos", "Alejar"), None,
         ("izq", "girar_izq", "Girar a la izquierda"), ("der", "girar_der", "Girar a la derecha"), None,
         ("subir", "inclinar_mas", "Inclinar más"), ("bajar", "inclinar_menos", "Inclinar menos"),
         ("norte", "norte", "Orientar al norte")]
    html = "".join("<hr>" if x is None else
                   f'<button type="button" data-y2k-cam="{x[0]}" aria-label="{x[2]}" title="{x[2]}">{ICONOS[x[1]]}</button>'
                   for x in b)
    md(f'<div class="y2k-sobre y2k-sobre-caja y2k-camara" role="group" aria-label="Cámara 3D">{html}'
            '<span class="y2k-vh y2k-camara-estado" aria-live="polite"></span></div>')


def sobre_mapa(html, clase):
    md(f'<div class="y2k-sobre y2k-sobre-caja {clase}">{html}</div>')


def pie():
    """Pie institucional: de donde vienen los datos, condiciones de uso y creditos de los mapas."""
    f = FUENTE
    md(
        '<footer class="y2k-pie">'
        f'<div class="fila"><span>Datos: <b>{f["nombre"]}</b> · '
        f'<a href="{f["url"]}" target="_blank" rel="noopener">Instituto de Hidrología, Meteorología y Estudios '
        'Ambientales</a></span><span><a href="app/static/manual.html" target="_blank" rel="noopener">Manual</a> · '
        f'v{f["version"]}</span></div>'
        '<div>Uso personal, privado y no comercial; cita la fuente (el ZIP incluye CITACION.txt). '
        'Herramienta independiente, no oficial del IDEAM.</div>'
        f'<details class="y2k-det"><summary><span class="ver">Fuentes y créditos de mapas</span></summary>'
        f'<div>{CREDITOS_MAPAS}</div></details>'
        '</footer>')


def aviso_legal(texto):
    """Condiciones de uso en una sola linea; el texto completo se despliega."""
    md('<details class="y2k-det y2k-legal"><summary><span>Datos IDEAM: uso personal y no comercial; cita la '
       f'fuente.</span><span class="ver">Ver condiciones</span></summary><div><p>{texto}</p></div></details>')


def barra_pixel(fraccion):
    llenos = round(max(0.0, min(1.0, fraccion)) * 32)
    return ('<div class="y2k-pbar" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
            f'aria-valuenow="{round(fraccion * 100)}">' + "".join('<i class="on"></i>' if i < llenos else "<i></i>"
                                                                  for i in range(32)) + "</div>")
