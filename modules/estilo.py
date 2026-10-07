import json

import streamlit as st
import streamlit.components.v1 as components

# ===========================================================================
# DISENO: EL MAPA ES LA PAGINA; LOS CONTROLES SON VIDRIO LIQUIDO ENCIMA
# El mapa 2D/3D ocupa toda la ventana. Encima flota una capa funcional de
# vidrio: capsulas arriba (marca, 2D/3D, utilidades), un panel con pestanas
# (Consulta / Resumen), una isla de accion abajo con el siguiente paso y la
# ficha de la estacion elegida. El vidrio deja ver el mapa (desenfoque y
# saturacion del fondo), tiene brillo especular que sigue al puntero, canto
# de luz y sombra de profundidad. Dos materiales:
#   - claro: controles pequenos (solo texto principal e iconos), mas transparente
#   - regular: superficies con texto (mas opaco, para leer sobre cualquier mapa)
# Ejes independientes: tema (Sistema/Claro/Oscuro), contraste (Sistema/Normal/
# Alto) y modo Lite (sin desenfoque ni efectos; no depende de movimiento reducido).
# Los colores de Streamlit salen de [theme.light]/[theme.dark] (config.toml).
# ===========================================================================

FUENTE = {
    "nombre": "IDEAM · DHIME",
    "url": "http://dhime.ideam.gov.co/atencionciudadano/",
    "version": "1.0",
}

# Creditos de las capas de mapa (cada proveedor pide su atribucion). Los textos cortos van en el
# borde de cada mapa; este bloque es la version completa. Revisar los textos de Esri en
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
    "claro": {"tinta": "#0B1324", "tinta_3": "#36425A", "rejilla": "#D5DCE6", "superficie": "#F7F9FC",
              "borde": "#B9C4D6", "acento": "#1258D6", "alerta": "#8A3208"},
    "oscuro": {"tinta": "#F4F6FA", "tinta_3": "#C8D0DC", "rejilla": "#3A404C", "superficie": "#16191F",
               "borde": "#4A5160", "acento": "#7DB6FF", "alerta": "#FFB37E"},
}

# Opciones de las preferencias (lo que se ve en "Apariencia")
TEMAS = {"sistema": "Sistema", "claro": "Claro", "oscuro": "Oscuro"}
CONTRASTES = {"sistema": "Sistema", "normal": "Normal", "alto": "Alto"}

# Celular en vertical: el panel pasa a ser una hoja inferior. En horizontal (pantalla baja) se usa el panel
# lateral, mas compacto: una hoja inferior dejaria el mapa en una franja.
MOVIL = "(max-width: 760px)"
BAJO = "(max-height: 560px) and (min-width: 761px)"

# ---------------------------------------------------------------------------
# Tokens. Los textos cumplen AA (4,5:1) sobre el vidrio ya compuesto con el
# peor fondo (negro bajo el vidrio claro, blanco bajo el oscuro); ademas se
# midieron sobre el mapa renderizado (satelite, calles y relieve 3D).
# ---------------------------------------------------------------------------
TOKENS = {
    "claro": {
        "y2k-tono": "claro", "y2k-alto": "0",
        "y2k-bg": "#E9EEF5", "y2k-ink": "#0B1324", "y2k-ink-2": "#26324A", "y2k-ink-3": "#36425A",
        "y2k-line": "rgba(8,20,45,.12)", "y2k-line-2": "rgba(8,20,45,.24)",
        "y2k-accent": "#1258D6", "y2k-accent-texto": "#0A3F9F", "y2k-accent-2": "#0891B2", "y2k-sobre-acento": "#FFFFFF",
        "y2k-foco": "#0A3F9F", "y2k-alerta": "#8A3208", "y2k-alerta-borde": "#D9692F", "y2k-alerta-bg": "rgba(255,237,224,.88)",
        "y2k-ok": "#0E6B36", "y2k-peligro": "#A8201A",
        "y2k-campo": "rgba(255,255,255,.72)", "y2k-campo-borde": "rgba(8,20,45,.20)",
        "y2k-hover": "rgba(255,255,255,.55)", "y2k-pista": "rgba(8,20,45,.07)",
        "y2k-lente": "rgba(255,255,255,.94)",
        "y2k-lente-sombra": "inset 0 1px 0 #fff, 0 0 0 .5px rgba(8,20,45,.14), 0 4px 12px -4px rgba(8,20,45,.35)",
        "lg-claro": "rgba(255,255,255,.52)", "lg-regular": "rgba(247,249,252,.76)", "lg-denso": "rgba(249,250,252,.95)",
        "lg-brillo": "linear-gradient(180deg,rgba(255,255,255,.55),rgba(255,255,255,.12) 24%,rgba(255,255,255,0) 52%,rgba(255,255,255,.14))",
        "lg-borde": "rgba(255,255,255,.50)", "lg-luz": "rgba(255,255,255,.98)", "lg-filo": "rgba(8,20,45,.18)",
        "lg-especular": "rgba(255,255,255,.60)",
        "lg-sombra": "0 24px 48px -22px rgba(5,15,35,.62), 0 3px 10px -4px rgba(5,15,35,.30)",
        "lg-filtro-claro": "blur(14px) saturate(210%) brightness(1.06)",
        "lg-filtro-regular": "blur(24px) saturate(185%) brightness(1.05)",
        "y2k-aurora-1": "rgba(34,197,145,.30)", "y2k-aurora-2": "rgba(56,140,248,.32)", "y2k-aurora-3": "rgba(250,178,25,.20)",
        "y2k-mapa-fondo": "#C9D6E4", "y2k-cielo": "linear-gradient(180deg,#8FBBE6 0%,#C9DFF3 55%,#E8F0F8 100%)",
    },
    "oscuro": {
        "y2k-tono": "oscuro", "y2k-alto": "0",
        "y2k-bg": "#0B0E14", "y2k-ink": "#F4F6FA", "y2k-ink-2": "#DCE1EA", "y2k-ink-3": "#C8D0DC",
        "y2k-line": "rgba(255,255,255,.12)", "y2k-line-2": "rgba(255,255,255,.24)",
        "y2k-accent": "#7DB6FF", "y2k-accent-texto": "#8EC0FF", "y2k-accent-2": "#5EE0F5", "y2k-sobre-acento": "#071226",
        "y2k-foco": "#9CCBFF", "y2k-alerta": "#FFB37E", "y2k-alerta-borde": "#E7864E", "y2k-alerta-bg": "rgba(66,30,10,.88)",
        "y2k-ok": "#6EE0A0", "y2k-peligro": "#FF9B94",
        "y2k-campo": "rgba(255,255,255,.06)", "y2k-campo-borde": "rgba(255,255,255,.22)",
        "y2k-hover": "rgba(255,255,255,.12)", "y2k-pista": "rgba(0,0,0,.24)",
        "y2k-lente": "rgba(255,255,255,.20)",
        "y2k-lente-sombra": "inset 0 1px 0 rgba(255,255,255,.35), 0 4px 12px -4px rgba(0,0,0,.6)",
        "lg-claro": "rgba(30,34,42,.56)", "lg-regular": "rgba(22,25,32,.66)", "lg-denso": "rgba(20,23,29,.96)",
        "lg-brillo": "linear-gradient(180deg,rgba(255,255,255,.10),rgba(255,255,255,.03) 28%,rgba(255,255,255,0) 58%,rgba(255,255,255,.04))",
        "lg-borde": "rgba(255,255,255,.14)", "lg-luz": "rgba(255,255,255,.36)", "lg-filo": "rgba(0,0,0,.50)",
        "lg-especular": "rgba(255,255,255,.17)",
        "lg-sombra": "0 26px 50px -20px rgba(0,0,0,.82), 0 3px 10px -4px rgba(0,0,0,.45)",
        "lg-filtro-claro": "blur(16px) saturate(180%) brightness(.6)",
        "lg-filtro-regular": "blur(26px) saturate(160%) brightness(.55)",
        "y2k-aurora-1": "rgba(16,185,129,.20)", "y2k-aurora-2": "rgba(59,130,246,.26)", "y2k-aurora-3": "rgba(245,158,11,.10)",
        "y2k-mapa-fondo": "#11161F", "y2k-cielo": "linear-gradient(180deg,#0A1224 0%,#16264A 60%,#233A63 100%)",
    },
}
# Alto contraste: superficies opacas, bordes nitidos, sin desenfoque ni brillos (no es el modo oscuro: va con
# el tono vigente, claro u oscuro)
TOKENS_ALTO = {
    "claro": {
        "y2k-alto": "1", "y2k-bg": "#FFFFFF", "y2k-ink": "#000000", "y2k-ink-2": "#111111", "y2k-ink-3": "#222222",
        "y2k-line": "#3A3A3A", "y2k-line-2": "#000000", "y2k-accent": "#0037A6", "y2k-accent-texto": "#0037A6",
        "y2k-sobre-acento": "#FFFFFF", "y2k-foco": "#000000", "y2k-alerta": "#7A2E00", "y2k-alerta-borde": "#7A2E00",
        "y2k-alerta-bg": "#FFF1E8", "y2k-ok": "#00561F", "y2k-peligro": "#8A0000",
        "y2k-campo": "#FFFFFF", "y2k-campo-borde": "#000000", "y2k-hover": "#E6E6E6", "y2k-pista": "#FFFFFF",
        "y2k-lente": "#000000", "y2k-lente-sombra": "none",
        "lg-claro": "#FFFFFF", "lg-regular": "#FFFFFF", "lg-denso": "#FFFFFF", "lg-brillo": "none",
        "lg-borde": "#000000", "lg-luz": "transparent", "lg-filo": "#000000", "lg-especular": "transparent",
        "lg-sombra": "0 0 #0000", "lg-filtro-claro": "none", "lg-filtro-regular": "none",
        "y2k-aurora-1": "transparent", "y2k-aurora-2": "transparent", "y2k-aurora-3": "transparent",
    },
    "oscuro": {
        "y2k-alto": "1", "y2k-bg": "#000000", "y2k-ink": "#FFFFFF", "y2k-ink-2": "#F2F2F2", "y2k-ink-3": "#E0E0E0",
        "y2k-line": "#C8C8C8", "y2k-line-2": "#FFFFFF", "y2k-accent": "#9CCBFF", "y2k-accent-texto": "#9CCBFF",
        "y2k-sobre-acento": "#000000", "y2k-foco": "#FFD60A", "y2k-alerta": "#FFB98A", "y2k-alerta-borde": "#FFB98A",
        "y2k-alerta-bg": "#2A1406", "y2k-ok": "#7CF0A8", "y2k-peligro": "#FFA3A3",
        "y2k-campo": "#000000", "y2k-campo-borde": "#FFFFFF", "y2k-hover": "#262626", "y2k-pista": "#000000",
        "y2k-lente": "#FFFFFF", "y2k-lente-sombra": "none",
        "lg-claro": "#000000", "lg-regular": "#000000", "lg-denso": "#000000", "lg-brillo": "none",
        "lg-borde": "#FFFFFF", "lg-luz": "transparent", "lg-filo": "#FFFFFF", "lg-especular": "transparent",
        "lg-sombra": "0 0 #0000", "lg-filtro-claro": "none", "lg-filtro-regular": "none",
        "y2k-aurora-1": "transparent", "y2k-aurora-2": "transparent", "y2k-aurora-3": "transparent",
    },
}


def md(html):
    """HTML propio en la pagina. st.html quita los SVG en linea; st.markdown (con HTML permitido) los conserva.
    El envoltorio y2k-md anula el margen negativo que Streamlit pone a los bloques de markdown."""
    st.markdown(f'<div class="y2k-md">{html}</div>', unsafe_allow_html=True)


def _vars(tokens):
    return ";".join(f"--{k}:{v}" for k, v in tokens.items())


def _tokens_css(tema, contraste):
    """Variables segun la eleccion. "Sistema" se resuelve en el navegador con media queries
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


# Superficies de vidrio: contenedores de Streamlit (por su clave) y piezas HTML propias
VIDRIO_CLARO = ".st-key-y2k_marca,.st-key-y2k_modo,.st-key-y2k_tex3d,.st-key-y2k_acciones,.lg-claro"
VIDRIO_REGULAR = ".st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_dock,.lg-regular"
VIDRIO = VIDRIO_CLARO + "," + VIDRIO_REGULAR

CSS = """
@import url("https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap");
:root{
  --y2k-g:12px; --y2k-panel-w:344px; --y2k-capsula:44px; --y2k-r:22px; --y2k-r-ctl:12px;
  --y2k-libre-izq:0px; --y2k-dock-h:96px; --y2k-hoja-h:58px;
  --y2k-ov-top:64px; --y2k-ov-izq:12px; --y2k-ov-der:12px; --y2k-ov-abajo:12px;
  --y2k-ley-abajo:56px; --y2k-atrib-abajo:12px; --y2k-cam-top:50%; --y2k-ficha-top:64px;
  --y2k-lite:0; --y2k-dur:.32s; --y2k-curva:cubic-bezier(.2,.8,.2,1);
  --y2k-centro:calc(var(--y2k-libre-izq) + (100vw - var(--y2k-libre-izq)) / 2);
  color-scheme:light dark;
}
html, body, .stApp, [class*="st-"], button, input, textarea, select{font-family:"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif}
/* los iconos de Streamlit son una fuente: sin esto salen como texto ("dark_mode") */
[data-testid="stIconMaterial"], [data-testid="stExpanderIcon"]{font-family:"Material Symbols Rounded" !important}
.stApp{background:var(--y2k-bg);color:var(--y2k-ink)}
[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:transparent}
/* el menu de Streamlit se oculta: tema y contraste se cambian en "Apariencia" */
[data-testid="stMainMenu"]{visibility:hidden !important}
header[data-testid="stHeader"]{background:transparent;pointer-events:none;height:0;min-height:0}
[data-testid="stDecoration"]{display:none}
[data-testid="stToolbar"]{pointer-events:none !important}
header[data-testid="stHeader"] button,[data-testid="stToolbar"] button{pointer-events:auto !important}
[data-testid="stStatusWidget"]{display:none !important}
/* Streamlit atenua lo que recalcula (en oscuro parece una pantalla negra): el mapa y el escaner avisan la carga */
[data-stale="true"]{opacity:1 !important;transition:none !important}
[data-testid="stMarkdownContainer"]:has(> .y2k-md){margin-bottom:0 !important}
/* contenedores de guiones (alto cero): no ocupan lugar */
.st-key-y2k_orbita,.st-key-y2k_escaner,.st-key-y2k_hipso,.st-key-y2k_velo,.st-key-y2k_precal,.st-key-y2k_guiones,
.st-key-y2k_ocultos,.st-key-y2k_vigia{height:0 !important;min-height:0 !important;overflow:hidden !important;margin:0 !important;
  padding:0 !important;gap:0 !important;position:absolute !important;pointer-events:none}
h1,h2,h3,h4{color:var(--y2k-ink);letter-spacing:-.01em}
a{color:var(--y2k-accent-texto)}
/* foco visible en todos los temas */
:is(button,a,input,select,textarea,summary,[role="radio"],[role="tab"],[tabindex]):focus-visible{
  outline:2px solid var(--y2k-foco) !important;outline-offset:2px !important;box-shadow:none !important}
[data-testid="stCheckbox"] label:has(input:focus-visible) > span + div{outline:2px solid var(--y2k-foco);outline-offset:2px}
.stMarkdown p,[data-testid="stMarkdownContainer"] p{color:var(--y2k-ink-2)}
[data-testid="stWidgetLabel"] p{color:var(--y2k-ink) !important;font-weight:600;font-size:13px !important}
/* Streamlit pinta los captions al 60 % de opacidad (quedan bajo 4,5:1): color del token, opaco */
[data-testid="stCaptionContainer"],[data-testid="stCaptionContainer"] p{color:var(--y2k-ink-3) !important;opacity:1 !important}
.y2k-hint,[data-testid="stMarkdownContainer"] p.y2k-hint{font-size:12.5px !important;line-height:1.45 !important;color:var(--y2k-ink-3) !important;margin:0 !important}
.y2k-vh{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}

/* ================= MATERIAL: VIDRIO LIQUIDO ================= */
:is(__VIDRIO_CLARO__){background:var(--lg-brillo),var(--lg-claro);-webkit-backdrop-filter:var(--lg-filtro-claro);
  backdrop-filter:var(--lg-filtro-claro)}
:is(__VIDRIO_REGULAR__){background:var(--lg-brillo),var(--lg-regular);-webkit-backdrop-filter:var(--lg-filtro-regular);
  backdrop-filter:var(--lg-filtro-regular)}
:is(__VIDRIO__){isolation:isolate;border-radius:var(--y2k-r);color:var(--y2k-ink);
  box-shadow:inset 0 1px 0 var(--lg-luz),inset 0 -1px 0 var(--lg-borde),0 0 0 .5px var(--lg-filo),var(--lg-sombra);
  transition:box-shadow var(--y2k-dur) ease}
/* brillo especular: una luz suave que sigue al puntero (la mueve el guion de la interfaz) */
:is(__VIDRIO__)::before{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;z-index:-1;
  background:radial-gradient(240px 150px at var(--mx,22%) var(--my,-40%),var(--lg-especular),transparent 70%)}
/* canto de luz: degradado diagonal solo en el contorno (mascara), como el borde de un vidrio */
:is(__VIDRIO__)::after{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;padding:1px;
  background:linear-gradient(135deg,var(--lg-luz),transparent 30%,transparent 64%,var(--lg-borde));
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;
  mask:linear-gradient(#000 0 0) content-box exclude,linear-gradient(#000 0 0)}
:is(__VIDRIO__):hover{box-shadow:inset 0 1px 0 var(--lg-luz),inset 0 -1px 0 var(--lg-borde),0 0 0 .5px var(--lg-filo),var(--lg-sombra),
  0 0 0 1px var(--lg-borde)}
/* sin desenfoque en el navegador: el vidrio se vuelve casi opaco para que el texto se siga leyendo */
@supports not ((backdrop-filter:blur(1px)) or (-webkit-backdrop-filter:blur(1px))){
  :is(__VIDRIO__){background:var(--lg-denso)}
}
/* botones dentro del vidrio claro: transparentes; el elegido es una "lente" elevada */
:is(__VIDRIO_CLARO__) button{background:transparent !important;border:0 !important;box-shadow:none !important;color:var(--y2k-ink) !important;
  border-radius:999px !important;min-height:36px !important;transition:background var(--y2k-dur),transform .12s}
:is(__VIDRIO_CLARO__) button p{color:inherit !important;font-weight:600 !important;font-size:13.5px !important}
:is(__VIDRIO_CLARO__) button:hover{background:var(--y2k-hover) !important}
:is(__VIDRIO_CLARO__) button:active{transform:scale(.96)}
:is(.st-key-y2k_modo,.st-key-y2k_tex3d) [data-testid="stButtonGroup"]{width:auto}
:is(.st-key-y2k_modo,.st-key-y2k_tex3d) [data-testid="stButtonGroup"] > div{gap:2px;background:transparent;border:0;flex-wrap:nowrap}
:is(.st-key-y2k_modo,.st-key-y2k_tex3d) button[role="radio"]{padding:0 14px !important;min-height:36px !important}
.st-key-y2k_modo button[role="radio"]{min-width:56px}
:is(.st-key-y2k_modo,.st-key-y2k_tex3d) button[aria-checked="true"]{background:var(--y2k-lente) !important;box-shadow:var(--y2k-lente-sombra) !important}
:is(.st-key-y2k_modo,.st-key-y2k_tex3d) button[aria-checked="true"] p{font-weight:700 !important}

/* ================= COMPOSICION: PANTALLA DEL MAPA ================= */
.stMain:has(.st-key-y2k_escenario){overflow:hidden !important}
.stMainBlockContainer:has(.st-key-y2k_escenario){padding:0 !important;max-width:none;gap:0 !important}
.st-key-y2k_escenario{position:fixed !important;inset:0;z-index:0;width:auto !important;gap:0 !important;background:var(--y2k-mapa-fondo)}
.st-key-y2k_mapa2d,.st-key-y2k_visor3d{position:absolute !important;inset:0;width:auto !important;height:auto !important;min-height:0 !important;gap:0 !important}
.st-key-y2k_mapa2d > [data-testid="stElementContainer"],.st-key-y2k_mapa2d > [data-testid="stElementContainer"] > div,
.st-key-y2k_visor3d > [data-testid="stElementContainer"],.st-key-y2k_visor3d [data-testid="stFullScreenFrame"],
.st-key-y2k_visor3d [data-testid="stDeckGlJsonChart"],.st-key-y2k_visor3d [data-testid="stDeckGlJsonChart"] > div{
  height:100% !important;width:100% !important;max-height:none !important}
.st-key-y2k_mapa2d > [data-testid="stElementContainer"],.st-key-y2k_visor3d > [data-testid="stElementContainer"]{flex:1 1 auto !important}
.st-key-y2k_mapa2d iframe{height:100% !important;width:100% !important;display:block;border:0}
/* cielo detras del relieve 3D (el 3D no tiene mapa plano de fondo) */
[data-testid="stDeckGlJsonChart"]{background:var(--y2k-cielo);overflow:hidden}
/* piezas HTML sobre el mapa: el contenedor de Streamlit no debe ser su referencia de posicion */
.st-key-y2k_escenario > [data-testid="stElementContainer"]:has(.y2k-sobre){position:absolute !important;inset:0;width:auto !important;
  height:auto !important;pointer-events:none;z-index:25;margin:0}
.st-key-y2k_escenario > [data-testid="stElementContainer"]:has(.y2k-sobre) *:has(.y2k-sobre){position:static !important}
.y2k-sobre{position:absolute;pointer-events:auto;z-index:25}
/* intro satelital (static/intro_satelital): ocupa la ventana; su boton de saltar no queda bajo la isla de accion */
.st-key-y2k_escenario .y2k-sat{border-radius:0 !important}
.y2k-sat > button{right:calc(var(--y2k-ov-der) + 4px) !important;bottom:calc(var(--y2k-atrib-abajo) + 4px) !important;
  border-radius:999px !important;padding:8px 14px !important}

/* capsulas superiores */
.st-key-y2k_marca,.st-key-y2k_modo,.st-key-y2k_acciones{position:fixed !important;top:var(--y2k-g);z-index:50;height:var(--y2k-capsula);
  width:auto !important;border-radius:999px;padding:4px !important;display:flex !important;flex-direction:row !important;align-items:center;
  gap:2px !important;flex-wrap:nowrap !important;margin:0 !important}
.st-key-y2k_marca{left:var(--y2k-g);padding:4px 4px 4px 6px !important}
.st-key-y2k_modo{left:var(--y2k-centro);transform:translateX(-50%);transition:left var(--y2k-dur) var(--y2k-curva)}
.st-key-y2k_acciones{right:var(--y2k-g)}
:is(.st-key-y2k_marca,.st-key-y2k_modo,.st-key-y2k_acciones,.st-key-y2k_tex3d) > div{width:auto !important;flex:none !important}
.y2k-marca{display:flex;align-items:center;gap:8px;height:36px;color:var(--y2k-ink)}
.y2k-marca .logo,.y2k-marca .logo svg{width:32px;height:32px;flex:none;display:block}
.y2k-marca b{font-size:14.5px;font-weight:700;letter-spacing:-.01em;white-space:nowrap;padding-right:2px}
.y2k-ico{all:unset;box-sizing:border-box;width:36px;height:36px;display:grid;place-items:center;border-radius:999px;cursor:pointer;flex:none;
  color:var(--y2k-ink);transition:background var(--y2k-dur),transform .12s}
.y2k-ico:hover{background:var(--y2k-hover)}
.y2k-ico:active{transform:scale(.94)}
.y2k-ico svg{width:19px;height:19px;transition:transform var(--y2k-dur)}
.y2k-ico[aria-expanded="false"] svg{transform:scaleX(-1)}
.y2k-accion{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 10px;border-radius:999px;color:var(--y2k-ink) !important;
  text-decoration:none !important;font:600 13.5px/1 "Figtree",system-ui,sans-serif}
.y2k-accion:hover{background:var(--y2k-hover)}
.y2k-accion svg{width:18px;height:18px}
.st-key-y2k_acciones button{padding:0 12px !important}
.st-key-btn_lite button[kind="primary"]{background:var(--y2k-accent) !important;color:var(--y2k-sobre-acento) !important}
.st-key-btn_lite button[kind="primary"]:hover{filter:brightness(1.08);background:var(--y2k-accent) !important}
.st-key-y2k_acciones iframe{display:none}
[data-testid="stPopoverBody"]{border-radius:18px !important;border:0 !important;background:var(--lg-brillo),var(--lg-denso) !important;
  -webkit-backdrop-filter:var(--lg-filtro-regular);backdrop-filter:var(--lg-filtro-regular);
  box-shadow:inset 0 1px 0 var(--lg-luz),0 0 0 .5px var(--lg-filo),var(--lg-sombra) !important}
[data-testid="stPopoverBody"] .y2k-hint{margin-top:4px !important}
/* texturas del 3D: capsula bajo la de 2D/3D, centrada sobre la zona libre del mapa */
.st-key-y2k_tex3d{position:fixed !important;top:calc(var(--y2k-g) + var(--y2k-capsula) + 8px);z-index:50;border-radius:999px;padding:4px !important;
  width:max-content !important;
  left:var(--y2k-centro);transform:translateX(-50%);display:flex !important;flex-direction:row !important;flex-wrap:wrap;justify-content:center;
  gap:2px 6px !important;max-width:calc(100vw - var(--y2k-libre-izq) - 24px);transition:left var(--y2k-dur) var(--y2k-curva);margin:0 !important}
.st-key-y2k_tex3d:has(.st-key-escala_altura){border-radius:22px}
.st-key-y2k_tex3d:not(:has([data-testid="stButtonGroup"])),.st-key-y2k_ficha:not(:has(.y2k-ficha-cab)){display:none !important}
.y2k-md [data-testid="stHeaderActionElements"]{display:none}

/* panel flotante (Consulta / Resumen) */
html[data-y2k-panel="abierto"],html:not([data-y2k-panel]){--y2k-libre-izq:calc(var(--y2k-panel-w) + var(--y2k-g) * 2)}
.st-key-y2k_panel{position:fixed !important;z-index:40;top:calc(var(--y2k-g) + var(--y2k-capsula) + 8px);bottom:var(--y2k-g);left:var(--y2k-g);
  width:var(--y2k-panel-w) !important;padding:0 !important;gap:0 !important;display:flex !important;flex-direction:column;overflow:hidden;
  transform-origin:10% 0;transition:transform var(--y2k-dur) var(--y2k-curva),opacity var(--y2k-dur) ease,visibility 0s}
html[data-y2k-panel="cerrado"] .st-key-y2k_panel{transform:translate(-12px,-8px) scale(.94);opacity:0;visibility:hidden;
  transition:transform var(--y2k-dur) var(--y2k-curva),opacity .2s ease,visibility 0s var(--y2k-dur)}
html[data-y2k-panel="cerrado"]{--y2k-libre-izq:0px}
.st-key-y2k_panel > div{width:100% !important}
.st-key-y2k_panel > [data-testid="stElementContainer"]{flex:none}
.st-key-y2k_panel > [data-testid="stLayoutWrapper"]{flex:1 1 auto;min-height:0;display:flex;flex-direction:column}
.st-key-y2k_panel > [data-testid="stLayoutWrapper"]:has(> .st-key-y2k_panel_cab){flex:none}
.st-key-y2k_consulta,.st-key-y2k_resumen{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:4px 18px 18px !important;
  gap:12px !important;scrollbar-width:thin;scrollbar-color:var(--y2k-line-2) transparent}
html:not([data-y2k-tab="resumen"]) .st-key-y2k_panel > [data-testid="stLayoutWrapper"]:has(> .st-key-y2k_resumen),
html[data-y2k-tab="resumen"] .st-key-y2k_panel > [data-testid="stLayoutWrapper"]:has(> .st-key-y2k_consulta){display:none !important}
.y2k-cab{display:flex;flex-direction:column;padding:10px 10px 8px}
.y2k-cab-fila{display:flex;align-items:center;gap:6px}
.y2k-asa,.y2k-hoja-max{display:none !important}
.y2k-tabs{display:flex;flex:1;gap:2px;padding:3px;border-radius:999px;background:var(--y2k-pista)}
.y2k-tabs button{all:unset;box-sizing:border-box;flex:1;display:flex;align-items:center;justify-content:center;gap:6px;min-height:34px;padding:0 10px;
  border-radius:999px;cursor:pointer;font:600 13.5px/1.1 "Figtree",system-ui,sans-serif;color:var(--y2k-ink-2);
  transition:background var(--y2k-dur),color var(--y2k-dur)}
.y2k-tabs button:hover{color:var(--y2k-ink)}
.y2k-tabs button[aria-selected="true"]{background:var(--y2k-lente);box-shadow:var(--y2k-lente-sombra);color:var(--y2k-ink);font-weight:700}
.y2k-tabs .cuenta{min-width:20px;padding:2px 6px;border-radius:999px;font-size:11.5px;font-weight:700;line-height:1;text-align:center;
  background:var(--y2k-accent);color:var(--y2k-sobre-acento);font-variant-numeric:tabular-nums}
/* pasos numerados de Consulta */
.y2k-paso{display:flex;align-items:center;gap:10px;margin:8px 0 -2px}
.y2k-paso .n{width:24px;height:24px;border-radius:50%;flex:none;display:grid;place-items:center;font:700 12px/1 "Figtree",sans-serif;
  color:var(--y2k-sobre-acento);background:var(--y2k-accent)}
.y2k-paso.hecho .n{background:var(--y2k-ok)}
.y2k-paso .t{font-size:15px;font-weight:700;margin:0;flex:1;color:var(--y2k-ink);line-height:1.2}
.y2k-paso .estado{font-size:12px;font-weight:600;color:var(--y2k-ink-3);white-space:nowrap}
.y2k-dato{display:flex;flex-wrap:wrap;align-items:baseline;gap:2px 8px;font-size:13.5px;color:var(--y2k-ink-2);margin:0}
.y2k-dato b{color:var(--y2k-ink);font-variant-numeric:tabular-nums}
/* formas de marcar la cuenca (botones grandes) */
.y2k-opciones{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.y2k-opcion{all:unset;box-sizing:border-box;display:flex;flex-direction:column;gap:5px;padding:12px;border-radius:16px;cursor:pointer;
  background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;color:var(--y2k-ink);font:700 13.5px/1.25 "Figtree",sans-serif;
  transition:transform .12s,box-shadow var(--y2k-dur)}
.y2k-opcion:hover{box-shadow:0 0 0 1.5px var(--y2k-accent) inset}
.y2k-opcion:active{transform:scale(.97)}
.y2k-opcion[aria-disabled="true"]{cursor:not-allowed;box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;transform:none}
.y2k-opcion[aria-disabled="true"] > span{opacity:.6}
.y2k-opcion svg{width:22px;height:22px;color:var(--y2k-accent-texto)}
.y2k-opcion small{font-weight:500;font-size:12px;line-height:1.3;color:var(--y2k-ink-3)}
.y2k-opcion.prim{background:var(--y2k-accent);color:var(--y2k-sobre-acento);box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 8px 18px -10px var(--y2k-accent)}
.y2k-opcion.prim svg,.y2k-opcion.prim small{color:var(--y2k-sobre-acento)}

/* isla de accion (abajo, sobre la zona libre): el estado y el siguiente paso siempre a la vista */
.st-key-y2k_dock{position:fixed !important;z-index:45;bottom:var(--y2k-g);left:var(--y2k-centro);transform:translateX(-50%);
  width:min(580px,calc(100vw - var(--y2k-libre-izq) - 24px)) !important;padding:12px 12px 10px 18px !important;gap:6px !important;
  transition:left var(--y2k-dur) var(--y2k-curva)}
.st-key-y2k_dock [data-stale="true"]{opacity:.55 !important;transition:opacity .2s !important}
.st-key-y2k_dock_fila{align-items:center !important;gap:12px !important;flex-wrap:nowrap !important}
.st-key-y2k_dock_fila > div:first-child{flex:1 1 auto !important;min-width:0;width:auto !important}
.st-key-y2k_dock_fila > div:not(:first-child){flex:none !important;width:auto !important}
.y2k-estado{display:flex;flex-direction:column;gap:2px;min-width:0}
.y2k-estado b{font-size:15px;font-weight:700;color:var(--y2k-ink);line-height:1.25}
.y2k-estado > span{font-size:12.5px;color:var(--y2k-ink-3);line-height:1.35;font-variant-numeric:tabular-nums}
.y2k-estado.alerta b{color:var(--y2k-alerta)}
.y2k-vinculo{all:unset;cursor:pointer;color:var(--y2k-accent-texto);font-weight:600;text-decoration:underline;text-underline-offset:2px}
.y2k-dock-botones{display:flex;gap:8px;align-items:center}
.y2k-boton{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:8px;height:42px;padding:0 16px;border-radius:999px;cursor:pointer;
  font:700 14px/1 "Figtree",sans-serif;white-space:nowrap;transition:transform .12s,filter var(--y2k-dur)}
.y2k-boton svg{width:18px;height:18px}
.y2k-boton.prim{background:var(--y2k-accent);color:var(--y2k-sobre-acento);box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 8px 18px -10px var(--y2k-accent)}
.y2k-boton.sec{color:var(--y2k-ink);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;background:var(--y2k-campo)}
.y2k-boton:hover{filter:brightness(1.07)}
.y2k-boton:active{transform:scale(.96)}
.st-key-y2k_dock .stButton > button{min-height:42px;padding:0 18px !important;white-space:nowrap}
.st-key-y2k_dock details.y2k-legal{font-size:12px;padding-top:6px;border-top:1px solid var(--y2k-line)}

/* ficha de la estacion seleccionada */
.st-key-y2k_ficha{position:fixed !important;z-index:40;top:calc(var(--y2k-g) + var(--y2k-capsula) + 8px);right:var(--y2k-g);
  width:320px !important;max-height:calc(100dvh - 190px);overflow-y:auto;overscroll-behavior:contain;padding:14px 16px !important;gap:8px !important}
.y2k-ficha-cab{display:flex;flex-direction:column;gap:2px}
.y2k-ficha-cab small{font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--y2k-ink-3)}
.y2k-ficha-cab b{font-size:15.5px;line-height:1.25;color:var(--y2k-ink)}
.y2k-ficha-cab span{font-size:12.5px;color:var(--y2k-ink-3);font-variant-numeric:tabular-nums}

/* controles de Streamlit dentro del vidrio regular */
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_dock) .stButton > button{border-radius:999px !important;font-weight:600 !important;min-height:40px}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) .stButton > button[kind="secondary"]{background:var(--y2k-campo) !important;
  border:0 !important;box-shadow:0 0 0 1px var(--y2k-campo-borde) inset !important;color:var(--y2k-ink) !important}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) .stButton > button[kind="secondary"] p{color:var(--y2k-ink) !important}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) .stButton > button[kind="secondary"]:hover{box-shadow:0 0 0 1.5px var(--y2k-accent) inset !important}
.stButton > button[kind="primary"],.stDownloadButton > button[kind="primary"]{background:var(--y2k-accent) !important;border:0 !important;
  color:var(--y2k-sobre-acento) !important;box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 8px 18px -10px var(--y2k-accent) !important;
  border-radius:999px !important;font-weight:700 !important}
.stButton > button[kind="primary"] p,.stDownloadButton > button[kind="primary"] p{color:var(--y2k-sobre-acento) !important;font-weight:700 !important}
.stButton > button[kind="primary"]:hover,.stDownloadButton > button[kind="primary"]:hover{filter:brightness(1.07)}
.stButton > button:disabled,.stButton > button[kind="primary"]:disabled{opacity:.5;filter:saturate(.3);box-shadow:none !important}
.stButton > button[kind="tertiary"]{color:var(--y2k-accent-texto) !important;min-height:32px;padding:0 6px !important}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-baseweb="select"] > div,:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-baseweb="input"],
:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-baseweb="base-input"]{background:var(--y2k-campo) !important;border-color:var(--y2k-campo-borde) !important;
  border-radius:var(--y2k-r-ctl) !important}
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_dock) [data-testid="stExpander"] details{border-radius:14px !important;
  border:0 !important;background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset}
[data-testid="stExpander"] summary p{font-weight:600;color:var(--y2k-ink) !important}
[data-testid="stAlert"]{border-radius:14px}
[data-testid="stFileUploaderDropzone"]{border-radius:14px;background:var(--y2k-campo);border:1px dashed var(--y2k-campo-borde)}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
.st-key-y2k_panel [data-testid="stVegaLiteChart"]{background:transparent}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-testid="stMarkdownContainer"] p{font-size:13.5px;line-height:1.5}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-testid="stCaptionContainer"] p{font-size:12.5px;line-height:1.45}

/* bloques de informacion */
.y2k-cifras{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.y2k-cifra{background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;border-radius:14px;padding:10px 12px;min-width:0}
.y2k-cifra .l{font-size:11px;text-transform:uppercase;letter-spacing:.06em;font-weight:700;color:var(--y2k-ink-3);line-height:1.25}
.y2k-cifra .v{font-size:21px;font-weight:700;color:var(--y2k-ink);line-height:1.2;margin-top:2px;font-variant-numeric:tabular-nums;overflow-wrap:anywhere}
.y2k-cifra .s{font-size:12px;color:var(--y2k-ink-3);line-height:1.3}
.y2k-titulo-seccion,[data-testid="stMarkdownContainer"] p.y2k-titulo-seccion{font-size:11.5px !important;text-transform:uppercase;letter-spacing:.08em;
  font-weight:700 !important;color:var(--y2k-ink-3) !important;margin:4px 0 0 !important}
.st-key-alerta_altura [data-testid="stExpander"] details,.st-key-alerta_ficha [data-testid="stExpander"] details{
  background:var(--y2k-alerta-bg) !important;box-shadow:0 0 0 1px var(--y2k-alerta-borde) inset !important}
.st-key-alerta_altura [data-testid="stIconMaterial"],.st-key-alerta_ficha [data-testid="stIconMaterial"]{color:var(--y2k-alerta) !important}
.st-key-alerta_altura summary p,.st-key-alerta_ficha summary p{font-size:13px !important}
/* detalles desplegables propios: resumen breve siempre visible y el detalle al pulsar */
details.y2k-det{font-size:12.5px;line-height:1.45;color:var(--y2k-ink-3);margin:0}
details.y2k-det summary{cursor:pointer;list-style:none;display:flex;flex-wrap:wrap;gap:2px 8px;align-items:baseline;border-radius:6px}
details.y2k-det summary::-webkit-details-marker{display:none}
details.y2k-det summary .ver{color:var(--y2k-accent-texto);font-weight:600;text-decoration:underline;text-underline-offset:2px;white-space:nowrap}
details.y2k-det summary .ver::after{content:" ▾";display:inline-block}
details.y2k-det[open] summary .ver::after{content:" ▴"}
details.y2k-det > div{margin-top:6px;color:var(--y2k-ink-2)}
details.y2k-det > div p{margin:0 0 6px !important;font-size:12.5px !important;color:var(--y2k-ink-2) !important}
details.y2k-det b{color:var(--y2k-ink)}
.y2k-pie{margin-top:6px;padding-top:12px;font-size:12px;line-height:1.5;color:var(--y2k-ink-3);border-top:1px solid var(--y2k-line)}
.y2k-pie p{margin:0 0 4px;color:var(--y2k-ink-3);font-size:12px}
.y2k-pie b{color:var(--y2k-ink);font-weight:600}
.y2k-pie a{color:var(--y2k-accent-texto) !important;text-decoration:none}
.y2k-pie a:hover{text-decoration:underline}

/* piezas sobre el mapa */
.y2k-leyenda{left:var(--y2k-ley-izq,var(--y2k-ov-izq));bottom:var(--y2k-ley-abajo);max-width:min(340px,calc(100vw - var(--y2k-ov-izq) - 20px));border-radius:18px}
.y2k-leyenda summary{list-style:none;cursor:pointer;display:flex;align-items:center;gap:8px;padding:9px 14px;font-size:13px;font-weight:700;border-radius:18px;color:var(--y2k-ink)}
.y2k-leyenda summary::-webkit-details-marker{display:none}
.y2k-leyenda summary::after{content:"▴";font-size:10px;color:var(--y2k-ink-3)}
.y2k-leyenda[open] summary::after{content:"▾"}
.y2k-leyenda ul{list-style:none;margin:0;padding:0 14px 11px;display:grid;grid-template-columns:auto auto;gap:4px 14px;font-size:12.5px;color:var(--y2k-ink-2)}
.y2k-leyenda li{display:flex;align-items:center;gap:8px;margin:0}
.y2k-leyenda .pin{width:12px;height:12px;border-radius:50%;flex:none;border:2px solid #fff;box-shadow:0 0 0 1px rgba(0,0,0,.5)}
.y2k-leyenda .pin.hueco{background:transparent !important;border-color:#E6ECF7}
.y2k-leyenda .pin.duda{border-color:#D0602F;box-shadow:0 0 0 1px #fff}
.y2k-leyenda .linea{width:18px;height:0;border-top:3px solid;flex:none}
.y2k-leyenda .nota{grid-column:1 / -1;font-size:12px;color:var(--y2k-ink-3);margin-top:2px}
.y2k-leyenda .tit{margin:0;padding:2px 14px 4px;font-size:12.5px;font-weight:600;color:var(--y2k-ink-2)}
.y2k-leyenda .rampa{height:10px;border-radius:5px;margin:2px 14px;box-shadow:0 0 0 1px var(--y2k-line) inset}
.y2k-leyenda .marcas{display:flex;justify-content:space-between;font-size:12px;color:var(--y2k-ink-3);padding:0 14px 10px;font-variant-numeric:tabular-nums}
.y2k-camara{right:var(--y2k-ov-der);top:var(--y2k-cam-top);transform:translateY(-50%);display:flex;flex-direction:column;gap:2px;padding:4px;border-radius:26px}
.y2k-camara button{all:unset;box-sizing:border-box;width:38px;height:38px;display:grid;place-items:center;border-radius:50%;cursor:pointer;color:var(--y2k-ink);
  transition:background var(--y2k-dur),transform .12s}
.y2k-camara button:hover{background:var(--y2k-hover)}
.y2k-camara button:active{transform:scale(.92)}
.y2k-camara button:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:-2px}
.y2k-camara svg{width:18px;height:18px}
.y2k-camara hr{border:0;border-top:1px solid var(--y2k-line);margin:2px 8px}
.y2k-atrib3d{right:var(--y2k-ov-der);bottom:var(--y2k-atrib-abajo);font-size:10.5px;line-height:1.3;padding:4px 10px;border-radius:999px;color:var(--y2k-ink);
  max-width:min(460px,50vw)}
.y2k-vacio{left:var(--y2k-centro);top:50%;transform:translate(-50%,-50%);padding:14px 18px;border-radius:18px;font-size:14px;font-weight:600;
  text-align:center;color:var(--y2k-ink);max-width:min(420px,80vw)}
/* aviso de navegador que altera los pixeles (terreno.AVISO_NAVEGADOR): arriba, sobre la zona libre */
.y2k-aviso3d{left:var(--y2k-centro) !important;top:var(--y2k-ov-top) !important;bottom:auto !important;transform:translateX(-50%);z-index:26 !important;
  background:var(--y2k-alerta-bg) !important;color:var(--y2k-ink) !important;border:1px solid var(--y2k-alerta-borde) !important;border-radius:14px !important;
  padding:8px 8px 8px 12px !important;font-size:12.5px !important;-webkit-backdrop-filter:var(--lg-filtro-claro);backdrop-filter:var(--lg-filtro-claro);
  box-shadow:var(--lg-sombra)}
.y2k-aviso3d button{color:var(--y2k-ink) !important}
/* avisos de fallo (los pone el guion de la interfaz) */
.y2k-dialogo{position:fixed;z-index:70;left:var(--y2k-centro);top:45%;transform:translate(-50%,-50%);
  width:min(420px,calc(100vw - 28px));display:flex;flex-direction:column;gap:8px;padding:18px 20px;font-size:14px;line-height:1.45}
.y2k-dialogo h3{font-size:16px !important;margin:0 !important;padding:0 !important;display:flex;gap:8px;align-items:center;color:var(--y2k-ink)}
.y2k-dialogo h3 svg{width:19px;height:19px;color:var(--y2k-alerta);flex:none}
.y2k-dialogo p{margin:0;color:var(--y2k-ink-2)}
.y2k-dialogo .tipo{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;font-weight:700;color:var(--y2k-alerta)}
.y2k-dialogo .botones{display:flex;flex-wrap:wrap;gap:8px;margin-top:6px}
.y2k-dialogo button{all:unset;box-sizing:border-box;cursor:pointer;font:600 13.5px/1 "Figtree",sans-serif;border-radius:999px;padding:11px 16px;
  color:var(--y2k-ink);background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset}
.y2k-dialogo button.prim{background:var(--y2k-accent);color:var(--y2k-sobre-acento);box-shadow:none}
.y2k-dialogo button:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:2px}

/* ================= PANTALLA DE DESCARGA ================= */
.stApp:has(.st-key-y2k_descarga)::before{content:"";position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(45% 50% at 10% 15%,var(--y2k-aurora-1),transparent 70%),radial-gradient(50% 55% at 90% 20%,var(--y2k-aurora-2),transparent 72%),
    radial-gradient(55% 45% at 50% 105%,var(--y2k-aurora-3),transparent 70%)}
.stMainBlockContainer:has(.st-key-y2k_descarga){padding:76px 24px 32px;max-width:1180px;gap:0 !important}
.y2k-encabezado h1{font-size:clamp(22px,2.6vw,30px) !important;font-weight:700 !important;margin:0 !important;padding:0 !important;line-height:1.15}
.y2k-encabezado p{margin:6px 0 0 !important;color:var(--y2k-ink-2) !important;font-size:14.5px}
[class*="st-key-y2k_card_"]{background:var(--lg-brillo),var(--lg-regular);-webkit-backdrop-filter:var(--lg-filtro-regular);
  backdrop-filter:var(--lg-filtro-regular);border-radius:26px;padding:18px !important;position:relative;isolation:isolate;gap:12px !important;
  box-shadow:inset 0 1px 0 var(--lg-luz),inset 0 -1px 0 var(--lg-borde),0 0 0 .5px var(--lg-filo),var(--lg-sombra)}
.y2k-consola{background:#07110B;border-radius:16px;padding:12px 14px;font:13px/1.45 ui-monospace,"SFMono-Regular","Cascadia Mono",Menlo,Consolas,monospace;
  color:#8CFFA8;height:360px;overflow:hidden;display:flex;flex-direction:column;justify-content:flex-end;box-shadow:0 0 0 1px #1F3A28 inset}
.y2k-consola div{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.y2k-consola .d{color:#7FB98C} .y2k-consola .w{color:#FFD37A}
.y2k-pbar{display:grid;grid-template-columns:repeat(32,1fr);gap:3px;padding:5px;border-radius:12px;background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset}
.y2k-pbar i{height:10px;border-radius:3px;background:var(--y2k-line)}
.y2k-pbar i.on{background:linear-gradient(90deg,var(--y2k-accent-2),var(--y2k-accent))}
.y2k-pmeta{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px;font-size:13px;color:var(--y2k-ink-2);margin-top:6px;font-variant-numeric:tabular-nums}
.y2k-pmeta b{color:var(--y2k-ink)}
.ideam-estado{display:none}

/* cambio de pantalla: lo fijo del mapa no debe tapar la pantalla nueva mientras Streamlit termina */
.stMain:has([data-stale="false"] .y2k-pantalla[data-p="descarga"]) :is(.st-key-y2k_escenario,.st-key-y2k_panel,.st-key-y2k_dock,
  .st-key-y2k_ficha,.st-key-y2k_modo,.st-key-y2k_tex3d){display:none !important}
.stMain:has([data-stale="false"] .y2k-pantalla[data-p="mapa"]) .st-key-y2k_descarga{visibility:hidden}
"""

# Ventanas medianas: "Apariencia" queda solo con su icono
CSS_MEDIO = """
.st-key-y2k_acciones .stPopover button [data-testid="stMarkdownContainer"]{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
"""

# Celular en vertical: el panel es una hoja inferior, encima de la isla de accion
CSS_MOVIL = """
html{--y2k-libre-izq:0px !important}
.y2k-marca b,.st-key-y2k_marca [data-y2k-panel-btn],.st-key-y2k_acciones .y2k-accion{display:none !important}
.st-key-y2k_marca{padding:4px !important}
.st-key-y2k_dock{left:0 !important;right:0;bottom:0;transform:none !important;width:auto !important;border-radius:0 !important;
  padding:10px 14px calc(10px + env(safe-area-inset-bottom)) 16px !important}
html:not([data-y2k-hoja]),html[data-y2k-hoja="min"]{--y2k-hoja-h:58px}
html[data-y2k-hoja="media"]{--y2k-hoja-h:min(52dvh,calc(100dvh - var(--y2k-dock-h) - 120px))}
html[data-y2k-hoja="max"]{--y2k-hoja-h:calc(100dvh - var(--y2k-dock-h) - 64px)}
.st-key-y2k_panel,html[data-y2k-panel="cerrado"] .st-key-y2k_panel{top:auto !important;left:0 !important;right:0;bottom:calc(var(--y2k-dock-h) - 1px) !important;
  width:auto !important;height:var(--y2k-hoja-h) !important;border-radius:24px 24px 0 0 !important;transform:none !important;opacity:1 !important;
  visibility:visible !important;transition:height var(--y2k-dur) var(--y2k-curva) !important}
.st-key-y2k_panel.arrastrando{transition:none !important}
html:not([data-y2k-hoja]) .st-key-y2k_panel > [data-testid="stLayoutWrapper"]:not(:has(> .st-key-y2k_panel_cab)),
html[data-y2k-hoja="min"] .st-key-y2k_panel > [data-testid="stLayoutWrapper"]:not(:has(> .st-key-y2k_panel_cab)){display:none !important}
.y2k-cab{padding:0 10px 8px}
.y2k-asa{display:grid !important;all:unset;box-sizing:border-box;height:20px;place-items:center;cursor:grab;touch-action:none}
.y2k-asa::before{content:"";width:40px;height:5px;border-radius:3px;background:var(--y2k-line-2)}
.y2k-asa:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:-2px;border-radius:8px}
.y2k-hoja-max{display:grid !important}
html[data-y2k-hoja="max"] .y2k-hoja-max svg{transform:rotate(180deg)}
.st-key-y2k_consulta,.st-key-y2k_resumen{padding:4px 16px 16px !important}
.st-key-y2k_ficha{top:var(--y2k-ficha-top) !important;left:10px;right:10px !important;width:auto !important;max-height:34dvh;padding:12px 14px !important}
.st-key-y2k_modo{left:calc(var(--y2k-g) + var(--y2k-capsula) + 6px) !important;transform:none !important}
.st-key-y2k_tex3d{top:calc(var(--y2k-g) + var(--y2k-capsula) + 6px);left:50% !important}
.y2k-estado .y2k-ancho,.y2k-estado .y2k-vin:has([data-y2k-ver="resumen"]){display:none}
.st-key-y2k_dock_fila:has(.y2k-dock-botones){flex-wrap:wrap !important;row-gap:10px !important}
.st-key-y2k_dock_fila:has(.y2k-dock-botones) > div{flex:1 1 100% !important;width:100% !important}
.st-key-y2k_dock_fila:has(.y2k-dock-botones) .y2k-estado > span{display:none}
.y2k-dock-botones .y2k-boton{flex:1;justify-content:center}
.st-key-y2k_acciones .stPopover button [data-testid="stMarkdownContainer"]{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.y2k-camara button{width:42px;height:42px}
.y2k-atrib3d{font-size:10px;max-width:62vw}
.y2k-leyenda{max-width:calc(100vw - 20px)}
"""
# Muy estrecho: la capsula 2D/3D se compacta
CSS_ESTRECHO = """
.st-key-y2k_modo button[role="radio"]{min-width:44px;padding:0 10px !important}
"""
# Pantallas bajas (celular en horizontal): todo mas compacto
CSS_BAJO = """
:root{--y2k-capsula:40px;--y2k-g:8px;--y2k-panel-w:300px}
.y2k-camara{flex-direction:row;top:auto !important;bottom:var(--y2k-atrib-abajo);transform:none;border-radius:999px}
.y2k-camara hr{border-top:0;border-left:1px solid var(--y2k-line);margin:6px 2px}
.y2k-sobre.y2k-atrib3d{bottom:calc(var(--y2k-atrib-abajo) + 50px)}
.st-key-y2k_dock{padding:8px 10px 8px 14px !important}
.st-key-y2k_dock .y2k-estado > span{display:none}
"""

# Alto contraste: superficies opacas, bordes nitidos, sin brillos ni desenfoque, foco grueso
CSS_ALTO = """
:is(__VIDRIO__){box-shadow:0 0 0 2px var(--lg-borde) !important;background:var(--lg-regular) !important}
:is(__VIDRIO__)::before,:is(__VIDRIO__)::after{display:none}
:is(.st-key-y2k_modo,.st-key-y2k_tex3d) button[aria-checked="true"],.y2k-tabs button[aria-selected="true"]{background:var(--y2k-ink) !important;
  color:var(--y2k-bg) !important;box-shadow:none !important}
:is(.st-key-y2k_modo,.st-key-y2k_tex3d) button[aria-checked="true"] p{color:var(--y2k-bg) !important}
.y2k-tabs{box-shadow:0 0 0 2px var(--y2k-line-2) inset}
.y2k-cifra,.y2k-opcion,.y2k-boton.sec,.y2k-dialogo button,:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_dock) [data-testid="stExpander"] details{
  box-shadow:0 0 0 2px var(--y2k-line-2) inset !important}
.stButton > button,.stDownloadButton > button{border:2px solid var(--y2k-line-2) !important}
.stButton > button[kind="primary"],.stDownloadButton > button[kind="primary"],.y2k-boton.prim,.y2k-opcion.prim{box-shadow:none !important}
:is(button,a,input,select,textarea,summary,[role="radio"],[role="tab"],[tabindex]):focus-visible{outline:3px solid var(--y2k-foco) !important;outline-offset:3px !important}
.y2k-hint,[data-testid="stMarkdownContainer"] p.y2k-hint,[data-testid="stCaptionContainer"] p{color:var(--y2k-ink-2) !important}
a,.y2k-vinculo,details.y2k-det summary .ver{text-decoration:underline !important}
.stApp:has(.st-key-y2k_descarga)::before{display:none}
[class*="st-key-y2k_card_"]{box-shadow:0 0 0 2px var(--lg-borde) !important;background:var(--lg-regular) !important}
.y2k-aviso3d{border-width:2px !important;box-shadow:none !important}
"""

# Lite: los mismos controles y datos sin desenfoque, brillos ni transiciones (variante de baja transparencia)
CSS_LITE = """
:root{--y2k-lite:1;--y2k-dur:0s;--lg-claro:var(--lg-denso);--lg-regular:var(--lg-denso);--lg-filtro-claro:none;--lg-filtro-regular:none;--lg-brillo:none}
:is(__VIDRIO__)::before{display:none}
:is(__VIDRIO__){box-shadow:inset 0 1px 0 var(--lg-luz),0 0 0 1px var(--lg-filo),0 10px 24px -14px rgba(0,0,0,.5) !important}
[data-testid="stPopoverBody"]{-webkit-backdrop-filter:none;backdrop-filter:none}
.stApp:has(.st-key-y2k_descarga)::before{display:none}
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
  :is(__VIDRIO__),[class*="st-key-y2k_card_"]{border:1px solid CanvasText !important;forced-color-adjust:auto}
  :is(__VIDRIO__)::before,:is(__VIDRIO__)::after{display:none}
  .y2k-ico,.y2k-tabs button,.y2k-camara button,.y2k-dialogo button,.y2k-asa,.y2k-hoja-max,.y2k-opcion,.y2k-boton,.y2k-cifra{border:1px solid ButtonText !important}
  .stButton > button,.stDownloadButton > button,.stPopover button,[data-testid="stExpander"] details,[data-testid="stFileUploaderDropzone"]{
    border:1px solid ButtonText !important}
  .y2k-tabs button[aria-selected="true"],:is(.st-key-y2k_modo,.st-key-y2k_tex3d) button[aria-checked="true"]{border:2px solid Highlight !important;outline:2px solid Highlight}
  :is(.st-key-y2k_modo,.st-key-y2k_tex3d) button[role="radio"]{border:1px solid ButtonText !important}
  .y2k-paso .n{border:1px solid CanvasText}
  .y2k-asa::before{background:ButtonText}
  .y2k-leyenda .pin,.y2k-leyenda .rampa,.y2k-leyenda .linea{forced-color-adjust:none}
  /* interruptores y casillas de Streamlit: su forma es solo fondo, que el modo de colores forzados quita */
  [data-testid="stCheckbox"] label > span + div{border:1px solid ButtonText !important}
  [data-testid="stCheckbox"] label > span + div > div{forced-color-adjust:none;background:ButtonText !important}
  [data-testid="stCheckbox"][data-selected="true"] label > span + div{forced-color-adjust:none;background:Highlight !important;border-color:Highlight !important}
  [data-testid="stCheckbox"][data-selected="true"] label > span + div > div{background:HighlightText !important}
  [data-testid="stSlider"] [role="slider"]{outline:2px solid ButtonText}
  .y2k-pbar i{border:1px solid CanvasText}
  .y2k-pbar i.on{forced-color-adjust:none;background:Highlight}
  :is(button,a,input,select,textarea,summary,[role="radio"],[tabindex]):focus-visible{outline:3px solid Highlight !important}
}
"""


def _vidrio(css):
    return (css.replace("__VIDRIO_CLARO__", VIDRIO_CLARO).replace("__VIDRIO_REGULAR__", VIDRIO_REGULAR)
            .replace("__VIDRIO__", VIDRIO))


def aplicar(tema="sistema", contraste="sistema", lite=False):
    """Estilos de toda la pagina (st.html con solo <style> no dibuja nada)."""
    css = (CSS + "@media (min-width: 761px) and (max-width: 1100px){" + CSS_MEDIO + "}"
           + "@media " + MOVIL + "{" + CSS_MOVIL + "}" + "@media (max-width: 380px){" + CSS_ESTRECHO + "}"
           + "@media " + BAJO + "{" + CSS_BAJO + "}"
           + _tokens_css(tema, contraste) + (CSS_LITE if lite else "") + CSS_MOVIMIENTO + CSS_FORZADOS)
    st.html("<style>" + _vidrio(css) + "</style>")


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
              '<rect x="1" y="1" width="30" height="30" rx="10" fill="url(#y2kg)"/>'
              '<path d="M16 7c3.4 4.3 5.4 7.4 5.4 10a5.4 5.4 0 0 1-10.8 0c0-2.6 2-5.7 5.4-10z" fill="#fff" fill-opacity=".95"/>'
              '<path d="M8 25h16M10 21.5h12" stroke="#fff" stroke-opacity=".7" stroke-width="1.6" stroke-linecap="round"/></svg>'),
    "panel": _svg('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d="M15 10l-2 2 2 2"/>'),
    "subir_hoja": _svg('<path d="M6 15l6-6 6 6"/>'),
    "manual": _svg('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'),
    "dibujar": _svg('<rect x="4" y="6" width="16" height="12" rx="1.5" stroke-dasharray="3 2.4"/><circle cx="4" cy="6" r="1.6" fill="currentColor"/>'
                    '<circle cx="20" cy="18" r="1.6" fill="currentColor"/>'),
    "area": _svg('<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/>'
                 '<circle cx="12" cy="12" r="2.5"/>'),
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


# ---------------------------------------------------------------------------
# Capsulas superiores y preferencias
# ---------------------------------------------------------------------------
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


def marca(pantalla="mapa"):
    """Capsula de la marca. En la pantalla del mapa lleva el boton que muestra u oculta el panel.
    `pantalla` marca la capsula: al cambiar de pantalla, el CSS esconde lo fijo de la anterior (ver CSS)."""
    boton = (f'<button type="button" class="y2k-ico" data-y2k-panel-btn aria-expanded="true" aria-label="Ocultar el panel" '
             f'title="Ocultar el panel">{ICONOS["panel"]}</button>') if pantalla == "mapa" else ""
    with st.container(key="y2k_marca"):
        md(f'<div class="y2k-marca y2k-pantalla" data-p="{pantalla}"><span class="logo">{ICONOS["marca"]}</span>'
           f'<b>Descargador IDEAM</b>{boton}</div>')


def control_tema():
    """Capsula de utilidades: Lite (siempre visible), Apariencia (tema y contraste) y Manual."""
    ss = st.session_state
    lite = bool(ss.get("lite", False))
    with st.container(key="y2k_acciones", horizontal=True, gap=None, wrap=False, vertical_alignment="center"):
        st.button("Lite", key="btn_lite", icon=":material/check:" if lite else ":material/bolt:",
                  type="primary" if lite else "secondary", on_click=_cambiar_lite,
                  help=("Modo Lite activado: sin desenfoque ni animaciones y con un 3D más liviano. Los datos y las "
                        "funciones son los mismos. Pulsa para volver a la calidad completa." if lite else
                        "Activa el modo Lite para reducir el coste gráfico (desenfoque, animaciones y detalle del 3D) "
                        "sin quitar datos ni funciones."))
        with st.popover("Apariencia", icon=":material/contrast:", help="Tema y contraste"):
            st.segmented_control("Tema", list(TEMAS.values()), default=TEMAS[ss.get("tema", "sistema")],
                                 key="pref_tema", on_change=_cambiar_tema, required=True)
            st.segmented_control("Contraste", list(CONTRASTES.values()), default=CONTRASTES[ss.get("contraste", "sistema")],
                                 key="pref_contraste", on_change=_cambiar_contraste, required=True)
            st.markdown('<p class="y2k-hint">«Sistema» sigue la configuración de tu equipo. Las animaciones respetan la '
                        'opción de reducir el movimiento.</p>', unsafe_allow_html=True)
        md(f'<a class="y2k-accion" href="app/static/manual.html" target="_blank" rel="noopener" '
           f'aria-label="Manual de usuario (se abre en otra pestaña)" title="Manual de usuario">{ICONOS["manual"]}</a>')


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


def guiones_globales():
    """Guiones invisibles de toda la pagina: interfaz del navegador y sincronizacion del tema de Streamlit."""
    with st.container(key="y2k_guiones"):
        instalar_ui()
        quiero = {"claro": "Light", "oscuro": "Dark"}.get(st.session_state.get("tema", "sistema"), "System")
        components.html(_SINCRONIZAR_TEMA.replace("__TEMA__", quiero), height=0)


# ---------------------------------------------------------------------------
# Interfaz del lado del navegador (se instala una vez en la pagina principal):
#   - panel, pestanas y hoja inferior sin recargar (atributos data-* en <html>; las elecciones en localStorage)
#   - reparto del espacio: mueve los controles de Leaflet y las piezas del 3D para que nada quede tapado
#   - vidrio de los controles de Leaflet (dentro de su iframe) y textos de Leaflet.draw en espanol
#   - "Dibujar un rectangulo" y "Usar el area visible" (alternativa de teclado al gesto de arrastrar)
#   - botones de camara del 3D (alternativa a los gestos) y brillo especular que sigue al puntero
#   - avisos de fallo con eleccion explicita: perdida del contexto grafico (WebGL), fallos de red al bajar
#     teselas (2D y 3D) y carga que no termina. Nunca cambia de modo por su cuenta: ofrece
#     «Activar Lite y reintentar» o «Seguir intentando».
# ---------------------------------------------------------------------------
_UI = r"""
(function () {
  var V = "__V__";
  var w = window, d = document, raiz = d.documentElement;
  if (w.__y2kUI && w.__y2kUI.v === V) return;
  if (w.__y2kUI && w.__y2kUI.parar) w.__y2kUI.parar();
  var vivo = true, ciclos = [];
  var ICONO_ALERTA = __ICONO_ALERTA__, MOVIL = __MOVIL__, VIDRIO = __VIDRIO__;
  var leer = function (k) { try { return w.localStorage.getItem("y2k_" + k); } catch (e) { return null; } };
  var guardar = function (k, v) { try { w.localStorage.setItem("y2k_" + k, v); } catch (e) {} };
  var css = function (n) { return w.getComputedStyle(raiz).getPropertyValue(n).trim(); };
  var num = function (n, defecto) { var v = parseFloat(css(n)); return isNaN(v) ? defecto : v; };
  var esLite = function () { return css("--y2k-lite") === "1"; };
  var menosMovimiento = function () { return !!(w.matchMedia && w.matchMedia("(prefers-reduced-motion: reduce)").matches); };
  var esMovil = function () { return !!(w.matchMedia && w.matchMedia(MOVIL).matches); };
  var G = 10;

  // ---------- panel (escritorio), hoja (celular) y pestanas ----------
  (function () {
    raiz.setAttribute("data-y2k-panel", leer("panel") === "cerrado" ? "cerrado" : "abierto");
    var t = leer("tab");
    if (t === "consulta" || t === "resumen") raiz.setAttribute("data-y2k-tab", t);
  })();
  function estadoPanel() { return raiz.getAttribute("data-y2k-panel") || "abierto"; }
  function ponerPanel(v) { raiz.setAttribute("data-y2k-panel", v); guardar("panel", v); sincronizar(); distribuir(); }
  var ESTADOS = ["min", "media", "max"];
  function estadoHoja() { return raiz.getAttribute("data-y2k-hoja") || "min"; }
  function ponerHoja(v) { raiz.setAttribute("data-y2k-hoja", v); sincronizar(); distribuir(); setTimeout(distribuir, 380); }
  function ponerTab(t) {
    raiz.setAttribute("data-y2k-tab", t); guardar("tab", t);
    if (esMovil() && estadoHoja() === "min") ponerHoja("media");
    sincronizar();
  }
  function abrirPanel(tab) {
    if (tab) ponerTab(tab);
    if (esMovil()) { if (estadoHoja() === "min") ponerHoja("media"); }
    else if (estadoPanel() !== "abierto") ponerPanel("abierto");
  }

  function sincronizar() {
    var abierto = estadoPanel() === "abierto";
    d.querySelectorAll("[data-y2k-panel-btn]").forEach(function (b) {
      var txt = abierto ? "Ocultar el panel" : "Mostrar el panel";
      b.setAttribute("aria-expanded", abierto ? "true" : "false"); b.setAttribute("aria-label", txt); b.title = txt;
    });
    var h = estadoHoja(), t = raiz.getAttribute("data-y2k-tab") || "consulta";
    d.querySelectorAll("[data-y2k-asa]").forEach(function (b) {
      b.setAttribute("aria-expanded", h === "min" ? "false" : "true");
      b.setAttribute("aria-label", h === "min" ? "Mostrar el panel" : "Reducir el panel");
    });
    d.querySelectorAll("[data-y2k-hoja-max]").forEach(function (b) {
      var txt = h === "max" ? "Reducir el panel" : "Ampliar el panel";
      b.setAttribute("aria-label", txt); b.title = txt;
    });
    d.querySelectorAll("[data-y2k-tab-btn]").forEach(function (b) {
      var nombre = b.getAttribute("data-y2k-tab-btn"), sel = nombre === t;
      b.id = "y2k-tab-" + nombre; b.setAttribute("aria-controls", "y2k-panel-" + nombre);
      b.setAttribute("aria-selected", sel ? "true" : "false"); b.tabIndex = sel ? 0 : -1;
    });
    ["consulta", "resumen"].forEach(function (nombre) {
      var p = d.querySelector(".st-key-y2k_" + nombre);
      if (!p || p.id === "y2k-panel-" + nombre) return;
      p.id = "y2k-panel-" + nombre; p.setAttribute("role", "tabpanel"); p.setAttribute("aria-labelledby", "y2k-tab-" + nombre);
    });
    d.querySelectorAll(".st-key-btn_lite button").forEach(function (b) { b.setAttribute("aria-pressed", esLite() ? "true" : "false"); });
    // los iconos de Streamlit son texto ("bolt", "delete"...): que no se lean como parte del nombre del boton
    d.querySelectorAll('button [data-testid="stIconMaterial"]:not([aria-hidden]), summary [data-testid="stIconMaterial"]:not([aria-hidden])')
      .forEach(function (i) { i.setAttribute("aria-hidden", "true"); });
    d.querySelectorAll("details.y2k-leyenda").forEach(function (det) {
      if (det.__y2kLey) return;
      det.__y2kLey = true;
      var pref = leer("leyenda"), abierta = pref ? pref === "abierta" : !esMovil() && w.innerHeight > 560;
      if (det.open !== abierta) det.open = abierta;
      det.addEventListener("toggle", function () { guardar("leyenda", det.open ? "abierta" : "cerrada"); setTimeout(distribuir, 30); });
    });
    traducirCargador();
    estadoArea();
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

  var SELECTORES = "[data-y2k-panel-btn],[data-y2k-asa],[data-y2k-hoja-max],[data-y2k-tab-btn],[data-y2k-cam],[data-y2k-dibujar],[data-y2k-area],[data-y2k-subir],[data-y2k-ver]";
  function alClic(ev) {
    var b = ev.target && ev.target.closest ? ev.target.closest(SELECTORES) : null;
    if (!b) return;
    if (b.hasAttribute("data-y2k-panel-btn")) ponerPanel(estadoPanel() === "abierto" ? "cerrado" : "abierto");
    else if (b.hasAttribute("data-y2k-asa")) { if (b.__y2kArrastre) { b.__y2kArrastre = false; return; } ponerHoja(estadoHoja() === "min" ? "media" : "min"); }
    else if (b.hasAttribute("data-y2k-hoja-max")) ponerHoja(estadoHoja() === "max" ? "media" : "max");
    else if (b.hasAttribute("data-y2k-tab-btn")) ponerTab(b.getAttribute("data-y2k-tab-btn"));
    else if (b.hasAttribute("data-y2k-cam")) camara(b.getAttribute("data-y2k-cam"));
    else if (b.hasAttribute("data-y2k-dibujar")) dibujarRectangulo();
    else if (b.hasAttribute("data-y2k-area")) usarAreaVisible(b);
    else if (b.hasAttribute("data-y2k-subir")) abrirSubida();
    else if (b.hasAttribute("data-y2k-ver")) abrirPanel(b.getAttribute("data-y2k-ver"));
  }
  d.addEventListener("click", alClic, true);

  // Arrastre de la hoja (celular): solo desde el asa, asi no se confunde con mover el mapa
  var arr = null;
  function panelEl() { return d.querySelector(".st-key-y2k_panel"); }
  function alBajar(ev) {
    var asa = ev.target && ev.target.closest ? ev.target.closest("[data-y2k-asa]") : null, h = panelEl();
    if (!asa || !h || !esMovil()) return;
    arr = {asa: asa, y0: ev.clientY, alto0: h.getBoundingClientRect().height, movio: false, id: ev.pointerId};
    try { asa.setPointerCapture(ev.pointerId); } catch (e) {}
  }
  function alMover(ev) {
    if (arr && ev.pointerId === arr.id) {
      var dy = arr.y0 - ev.clientY, h = panelEl();
      if (!h) return;
      if (Math.abs(dy) > 6) arr.movio = true;
      if (!arr.movio) return;
      h.classList.add("arrastrando");
      h.style.setProperty("height", Math.max(48, Math.min(w.innerHeight - 140, arr.alto0 + dy)) + "px", "important");
      return;
    }
    especular(ev);
  }
  function alSoltar(ev) {
    if (!arr || ev.pointerId !== arr.id) return;
    var h = panelEl(), a = arr; arr = null;
    if (!h) return;
    h.classList.remove("arrastrando");
    if (!a.movio) return;
    a.asa.__y2kArrastre = true;
    var alto = h.getBoundingClientRect().height, vh = w.innerHeight;
    h.style.removeProperty("height");
    ponerHoja(alto < vh * 0.2 ? "min" : alto < vh * 0.6 ? "media" : "max");
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
  var ultimo = "";
  function distribuir() {
    var W = w.innerWidth, H = w.innerHeight, movil = esMovil();
    var tapas = [".st-key-y2k_marca", ".st-key-y2k_modo", ".st-key-y2k_acciones", ".st-key-y2k_tex3d"].map(caja).filter(Boolean);
    var arriba = tapas.reduce(function (m, r) { return Math.max(m, r.bottom); }, 0) + G;
    var ficha = caja(".st-key-y2k_ficha"), dock = caja(".st-key-y2k_dock"), panel = caja(".st-key-y2k_panel");
    var izq = G, der = G, abajo = G, derArriba = G, fichaTop = arriba;
    if (!movil && estadoPanel() === "abierto" && panel) izq = panel.right + G;
    if (!movil && ficha) derArriba = W - ficha.left + G;
    if (dock) raiz.style.setProperty("--y2k-dock-h", Math.round(dock.height) + "px");
    if (movil) {
      abajo = H - Math.min(panel ? panel.top : H, dock ? dock.top : H) + G;
      if (ficha) arriba = Math.max(arriba, ficha.bottom + G);
    }
    // franja inferior: lo que comparte columna con la isla de accion sube por encima de ella
    var sobreDock = function (x0, x1) { return !movil && dock && cruza(dock, x0, x1) ? H - dock.top + G : abajo; };
    var ley = caja(".y2k-leyenda"), doc = docMapa();
    var rinconL = function (sel) { var e = doc && doc.querySelector(sel); return e ? {w: e.offsetWidth, h: e.offsetHeight} : {w: 0, h: 0}; };
    var bl = rinconL(".leaflet-bottom.leaflet-left"), tl = rinconL(".leaflet-top.leaflet-left");
    var blAbajo = sobreDock(izq, izq + bl.w);
    // la leyenda va encima de la escala de Leaflet (y de la isla, si comparten columna)
    var leyAbajo = Math.max(abajo, ley ? sobreDock(izq, izq + ley.width) : abajo, bl.h ? blAbajo - 10 + bl.h + 4 : 0);
    // si no cabe debajo de la barra de herramientas de Leaflet, se pone a su lado
    var leyIzq = izq;
    if (ley && tl.h && H - leyAbajo - ley.height < arriba - 10 + tl.h + G) leyIzq = izq + tl.w + G - 10;
    var atrib = caja(".y2k-atrib3d"), atribAbajo = atrib ? sobreDock(W - der - atrib.width, W - der) : sobreDock(W - 160, W - der);
    var cam = caja(".y2k-camara"), camTop = "50%";
    if (cam) {
      var tope = Math.max(arriba, ficha && !movil ? ficha.bottom + G : 0) + cam.height / 2;
      var piso = H - sobreDock(W - der - cam.width, W - der) - (atrib ? atrib.height + G : 0) - cam.height / 2;
      camTop = Math.round(Math.max(tope, Math.min(H / 2, piso))) + "px";
    }
    var clave = [W, H, arriba, izq, der, abajo, fichaTop, leyAbajo, leyIzq, atribAbajo, camTop].join("|");
    if (clave !== ultimo) {
      ultimo = clave;
      var s = raiz.style;
      s.setProperty("--y2k-ov-top", Math.round(arriba) + "px");
      s.setProperty("--y2k-ov-izq", Math.round(izq) + "px");
      s.setProperty("--y2k-ov-der", Math.round(der) + "px");
      s.setProperty("--y2k-ov-abajo", Math.round(abajo) + "px");
      s.setProperty("--y2k-ficha-top", Math.round(fichaTop) + "px");
      s.setProperty("--y2k-ley-abajo", Math.round(leyAbajo) + "px");
      s.setProperty("--y2k-ley-izq", Math.round(leyIzq) + "px");
      s.setProperty("--y2k-atrib-abajo", Math.round(atribAbajo) + "px");
      s.setProperty("--y2k-cam-top", camTop);
    }
    // esquinas de Leaflet (dentro del iframe; sus controles ya traen 10 px de margen)
    if (doc) {
      var brAbajo = sobreDock(W - der - rinconL(".leaflet-bottom.leaflet-right").w, W - der);
      var v = {"--tl-top": arriba, "--tl-izq": izq, "--tr-top": arriba, "--tr-der": derArriba,
               "--bl-abajo": blAbajo, "--bl-izq": izq, "--br-abajo": brAbajo, "--br-der": der};
      var claveIf = JSON.stringify(v);
      if (doc.__y2kClave !== claveIf) {
        doc.__y2kClave = claveIf;
        for (var k in v) doc.documentElement.style.setProperty(k, Math.max(0, Math.round(v[k] - 10)) + "px");
      }
    }
  }
  w.addEventListener("resize", function () { sincronizar(); distribuir(); });

  // ---------- mapa 2D (Leaflet en el iframe de streamlit-folium) ----------
  var VIDRIO_CLARO_IF = "background:linear-gradient(180deg,rgba(255,255,255,.55),rgba(255,255,255,.12) 26%,rgba(255,255,255,0) 55%),rgba(255,255,255,.52) !important;" +
    "-webkit-backdrop-filter:blur(14px) saturate(210%) brightness(1.06);backdrop-filter:blur(14px) saturate(210%) brightness(1.06);" +
    "box-shadow:inset 0 1px 0 rgba(255,255,255,.98),0 0 0 .5px rgba(8,20,45,.2),0 16px 32px -16px rgba(5,15,35,.62) !important";
  var VIDRIO_OSCURO_IF = "background:linear-gradient(180deg,rgba(255,255,255,.12),rgba(255,255,255,0) 50%),rgba(30,34,42,.56) !important;" +
    "-webkit-backdrop-filter:blur(16px) saturate(180%) brightness(.6);backdrop-filter:blur(16px) saturate(180%) brightness(.6);" +
    "box-shadow:inset 0 1px 0 rgba(255,255,255,.36),0 0 0 .5px rgba(0,0,0,.5),0 18px 34px -16px rgba(0,0,0,.82) !important";
  var CAJAS = ".leaflet-bar,.leaflet-control-layers,.leaflet-draw-actions";
  var en = function (prefijo, sel) { return sel.split(",").map(function (s) { return prefijo + " " + s; }).join(","); };
  var CSS_IFRAME = "html,body,#root,#parent,#parent>.float-child:first-child,#map_div{height:100% !important;width:100% !important;margin:0}" +
    "#parent>.float-child:first-child{float:none !important}" +
    ".leaflet-top.leaflet-left{top:var(--tl-top,0);left:var(--tl-izq,0)}.leaflet-top.leaflet-right{top:var(--tr-top,0);right:var(--tr-der,0)}" +
    ".leaflet-bottom.leaflet-left{bottom:var(--bl-abajo,0);left:var(--bl-izq,0)}.leaflet-bottom.leaflet-right{bottom:var(--br-abajo,0);right:var(--br-der,0)}" +
    ".leaflet-top,.leaflet-bottom{transition:top .32s cubic-bezier(.2,.8,.2,1),left .32s cubic-bezier(.2,.8,.2,1),right .32s,bottom .32s}" +
    // vidrio claro sobre las teselas (el mismo material de la pagina)
    CAJAS + "{border:0 !important;border-radius:18px !important;overflow:hidden;" + VIDRIO_CLARO_IF + "}" +
    ".leaflet-bar a,.leaflet-bar a:hover{background-color:transparent !important;border-bottom:1px solid rgba(8,20,45,.12) !important;color:#0B1324 !important;" +
    "width:40px !important;height:40px !important;line-height:40px !important;font:600 19px/40px Figtree,system-ui,sans-serif !important}" +
    ".leaflet-bar a:last-child{border-bottom:0 !important}.leaflet-bar a:hover{background-color:rgba(255,255,255,.6) !important}" +
    ".leaflet-bar a.leaflet-disabled{color:#5B6578 !important;background-color:transparent !important}" +
    ".leaflet-draw-section{margin-top:8px}.leaflet-draw-toolbar{margin-top:0 !important}" +
    // los iconos de Leaflet.draw son un sprite de celdas de 30 px: se centran en el boton de 40 px con relleno
    ".leaflet-draw-toolbar a{padding:5px !important;box-sizing:border-box;background-origin:content-box !important;background-clip:content-box !important}" +
    ".leaflet-draw-actions{left:46px !important;top:0 !important;white-space:nowrap}.leaflet-draw-actions li{display:inline-block}" +
    ".leaflet-draw-actions a{background:transparent !important;color:#0B1324 !important;font:600 13px/40px Figtree,system-ui,sans-serif !important;" +
    "height:40px !important;border:0 !important;padding:0 12px !important}" +
    ".leaflet-draw-actions a:hover{background:rgba(255,255,255,.6) !important}" +
    ".leaflet-control-layers-toggle{width:40px !important;height:40px !important;background-size:20px}" +
    ".leaflet-control-layers-expanded{padding:10px 14px !important;color:#0B1324;font:500 13.5px/1.7 Figtree,system-ui,sans-serif}" +
    ".leaflet-control-scale-line{background:rgba(255,255,255,.78) !important;border-color:#0B1324 !important;color:#0B1324;font:11px Figtree,system-ui,sans-serif}" +
    ".leaflet-control-attribution{background:rgba(255,255,255,.78) !important;color:#1F2B40 !important;border-radius:999px;padding:1px 9px !important;margin:0 0 4px !important}" +
    ".leaflet-control-attribution a{color:#0A3F9F !important}" +
    ".leaflet-tooltip{border:0;border-radius:14px;padding:9px 11px;background:rgba(250,251,253,.92);-webkit-backdrop-filter:blur(14px);backdrop-filter:blur(14px);" +
    "box-shadow:inset 0 1px 0 #fff,0 0 0 .5px rgba(8,20,45,.22),0 14px 30px -14px rgba(0,0,0,.6)}" +
    "a:focus-visible,button:focus-visible,input:focus-visible,.leaflet-container:focus-visible{outline:2px solid #0A3F9F !important;outline-offset:2px}" +
    // tono oscuro
    en("html.y2k-oscuro", CAJAS) + "{" + VIDRIO_OSCURO_IF + "}" +
    "html.y2k-oscuro .leaflet-bar a,html.y2k-oscuro .leaflet-draw-actions a,html.y2k-oscuro .leaflet-control-layers-expanded{color:#F4F6FA !important;border-color:rgba(255,255,255,.14) !important}" +
    "html.y2k-oscuro .leaflet-bar a:hover,html.y2k-oscuro .leaflet-draw-actions a:hover{background-color:rgba(255,255,255,.12) !important}" +
    "html.y2k-oscuro .leaflet-bar a.leaflet-disabled{color:#9AA3B2 !important}" +
    "html.y2k-oscuro .leaflet-draw-toolbar a,html.y2k-oscuro .leaflet-control-layers-toggle{filter:invert(1) hue-rotate(180deg)}" +
    "html.y2k-oscuro .leaflet-tooltip{background:rgba(22,25,32,.92);color:#F4F6FA;box-shadow:inset 0 1px 0 rgba(255,255,255,.2),0 0 0 .5px #000,0 14px 30px -14px #000}" +
    "html.y2k-oscuro .leaflet-tooltip>div{color:#F4F6FA !important}" +
    "html.y2k-oscuro .leaflet-tooltip [style*='4F5D78']{color:#B7C0CF !important}html.y2k-oscuro .leaflet-tooltip [style*='A4430F']{color:#FFB37E !important}" +
    "html.y2k-oscuro .leaflet-tooltip [style*='B42318']{color:#FF9B94 !important}" +
    "html.y2k-oscuro .leaflet-control-scale-line,html.y2k-oscuro .leaflet-control-attribution{background:rgba(20,23,29,.82) !important;color:#E3E7EE !important;border-color:#E3E7EE !important}" +
    "html.y2k-oscuro .leaflet-control-attribution a{color:#8EC0FF !important}" +
    "html.y2k-oscuro a:focus-visible,html.y2k-oscuro .leaflet-container:focus-visible{outline-color:#9CCBFF !important}" +
    // alto contraste: opaco y con bordes nitidos
    en("html.y2k-alto", CAJAS) + ",html.y2k-alto .leaflet-tooltip{background:#fff !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:0 0 0 2px #000 !important}" +
    en("html.y2k-alto.y2k-oscuro", CAJAS) + ",html.y2k-alto.y2k-oscuro .leaflet-tooltip{background:#000 !important;box-shadow:0 0 0 2px #fff !important}" +
    "html.y2k-alto .leaflet-control-attribution,html.y2k-alto .leaflet-control-scale-line{background:#fff !important;color:#000 !important}" +
    "html.y2k-alto.y2k-oscuro .leaflet-control-attribution,html.y2k-alto.y2k-oscuro .leaflet-control-scale-line{background:#000 !important;color:#fff !important}" +
    // Lite: sin desenfoque ni fundidos de teselas
    en("html.y2k-lite", CAJAS) + ",html.y2k-lite .leaflet-tooltip{-webkit-backdrop-filter:none !important;backdrop-filter:none !important;background:rgba(249,250,252,.96) !important}" +
    en("html.y2k-lite.y2k-oscuro", CAJAS) + ",html.y2k-lite.y2k-oscuro .leaflet-tooltip{background:rgba(20,23,29,.96) !important}" +
    "html.y2k-lite .leaflet-fade-anim .leaflet-tile,html.y2k-lite .leaflet-top,html.y2k-lite .leaflet-bottom{transition:none !important}" +
    "html.y2k-bajo .leaflet-bar a{width:34px !important;height:34px !important;line-height:34px !important;font-size:17px !important}" +
    "html.y2k-bajo .leaflet-draw-toolbar a{padding:2px !important}html.y2k-bajo .leaflet-draw-section{margin-top:6px}" +
    "html.y2k-bajo .leaflet-draw-actions{left:40px !important}html.y2k-bajo .leaflet-draw-actions a{height:34px !important;line-height:34px !important}" +
    "@media (prefers-reduced-motion: reduce){.leaflet-top,.leaflet-bottom{transition:none !important}}" +
    "@media (forced-colors: active){" + CAJAS + "{border:1px solid CanvasText !important}}";
  // Leaflet.draw viene en ingles: textos en espanol (los botones de accion y las ayudas se leen al activar cada herramienta)
  var DRAW_ES = {
    draw: {toolbar: {actions: {title: "Cancelar el dibujo", text: "Cancelar"}, finish: {title: "Terminar el dibujo", text: "Terminar"},
                     undo: {title: "Borrar el último punto", text: "Deshacer"}, buttons: {rectangle: "Dibujar un rectángulo"}},
           handlers: {rectangle: {tooltip: {start: "Haz clic y arrastra para dibujar el rectángulo."}},
                      simpleshape: {tooltip: {end: "Suelta para terminar."}}}},
    edit: {toolbar: {actions: {save: {title: "Guardar los cambios", text: "Guardar"}, cancel: {title: "Descartar los cambios", text: "Cancelar"},
                               clearAll: {title: "Borrar todo", text: "Borrar todo"}},
                     buttons: {edit: "Ajustar la cuenca", editDisabled: "No hay nada que ajustar", remove: "Borrar la cuenca",
                               removeDisabled: "No hay nada que borrar"}},
           handlers: {edit: {tooltip: {text: "Arrastra los vértices para ajustar la cuenca.", subtext: "Pulsa «Cancelar» para deshacer los cambios."}},
                      remove: {tooltip: {text: "Haz clic en la cuenca para borrarla."}}}}};
  function fusionar(a, b) { for (var k in b) { if (b[k] && typeof b[k] === "object") { a[k] = a[k] || {}; fusionar(a[k], b[k]); } else a[k] = b[k]; } }
  function marco2d() { return d.querySelector(".st-key-y2k_mapa2d iframe") || d.querySelector("iframe[title*='st_folium']"); }
  function winMapa() { var f = marco2d(); try { return f && f.contentWindow; } catch (e) { return null; } }
  function docMapa() { var x = winMapa(); try { return x && x.document && x.document.head ? x.document : null; } catch (e) { return null; } }
  function titulos(doc) {
    var t = function (sel, txt) { doc.querySelectorAll(sel).forEach(function (a) { if (a.title !== txt) { a.title = txt; a.setAttribute("aria-label", txt); } }); };
    t(".leaflet-control-zoom-in", "Acercar"); t(".leaflet-control-zoom-out", "Alejar");
    t(".leaflet-draw-draw-rectangle", "Dibujar un rectángulo"); t(".leaflet-control-layers-toggle", "Mapa base");
    var c = doc.querySelector(".leaflet-container");
    if (c && !c.getAttribute("aria-label")) c.setAttribute("aria-label", "Mapa. Con el teclado: flechas para moverte, + y − para acercar o alejar");
  }
  function vigilar2d() {
    var win = winMapa(), doc = docMapa();
    if (!doc) return;
    if (!doc.getElementById("y2k-iframe-css")) {
      var s = doc.createElement("style"); s.id = "y2k-iframe-css"; s.textContent = CSS_IFRAME; doc.head.appendChild(s);
      if (win.map && win.map.invalidateSize) try { win.map.invalidateSize(); } catch (e) {}
    }
    var cl = doc.documentElement.classList;
    cl.toggle("y2k-lite", esLite()); cl.toggle("y2k-oscuro", css("--y2k-tono") === "oscuro"); cl.toggle("y2k-alto", css("--y2k-alto") === "1");
    cl.toggle("y2k-bajo", w.innerHeight <= 560);   // celular en horizontal: botones mas compactos
    var map = win.map, L = win.L;
    if (!map || !L) return;
    titulos(doc);
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
    map.on("zoomend", estadoArea);
    try { new w.ResizeObserver(function () { try { map.invalidateSize({pan: false}); } catch (e) {} }).observe(marco2d()); } catch (e) {}
    // la cuenca recien montada (archivo, vuelta del 3D) se encuadra en la zona libre, no debajo del panel
    setTimeout(function () {
      try {
        var it = win.drawnItems;
        if (!it || !it.getLayers().length) return;
        distribuir();
        map.fitBounds(it.getBounds(), {paddingTopLeft: [num("--y2k-ov-izq", 12) + 24, num("--y2k-ov-top", 64) + 24],
          paddingBottomRight: [num("--y2k-ov-der", 12) + 24, num("--y2k-ov-abajo", 12) + (esMovil() ? 24 : 110)], animate: false});
      } catch (e) {}
    }, 250);
    estadoArea();
  }
  // "Dibujar un rectangulo": activa la herramienta de Leaflet.draw y deja el foco en el mapa
  function dibujarRectangulo() {
    var doc = docMapa(), a = doc && doc.querySelector(".leaflet-draw-draw-rectangle");
    if (!a) return;
    if (esMovil()) ponerHoja("min");
    a.click();
    try { marco2d().focus(); } catch (e) {}
  }
  // "Usar el area visible": alternativa al gesto de arrastrar (con el teclado: flechas y + / − en el mapa)
  var ZOOM_AREA = 10;
  function estadoArea() {
    var win = winMapa(), map = win && win.map, ok = !!(map && map.getZoom && map.getZoom() >= ZOOM_AREA);
    d.querySelectorAll("[data-y2k-area]").forEach(function (b) {
      b.setAttribute("aria-disabled", ok ? "false" : "true");
      var s = b.querySelector("small");
      if (s) s.textContent = !map ? "Disponible en la vista 2D" : ok ? "La zona que ves ahora" : "Primero acércate a tu zona";
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
    var x0 = num("--y2k-ov-izq", 12), y0 = num("--y2k-ov-top", 64), x1 = W - num("--y2k-ov-der", 12);
    var y1 = H - (esMovil() ? num("--y2k-ov-abajo", 12) : Math.max(num("--y2k-ov-abajo", 12), num("--y2k-dock-h", 96) + 24));
    var mx = (x1 - x0) * 0.1, my = (y1 - y0) * 0.1;
    var a = map.containerPointToLatLng([x0 + mx, y0 + my]), c = map.containerPointToLatLng([x1 - mx, y1 - my]);
    var rect = L.rectangle(L.latLngBounds(a, c), {color: "#1C6FD8", weight: 3, fillColor: "#1C6FD8", fillOpacity: 0.12});
    map.fire("draw:created", {layer: rect, layerType: "rectangle"});
    if (esMovil()) ponerHoja("min");
  }
  function abrirSubida() {
    abrirPanel("consulta");
    setTimeout(function () {
      var det = d.querySelector(".st-key-y2k_subida details");
      if (det && !det.open) { var s = det.querySelector("summary"); if (s) s.click(); }
      var z = d.querySelector(".st-key-y2k_subida");
      if (z) try { z.scrollIntoView({block: "nearest", behavior: menosMovimiento() ? "auto" : "smooth"}); } catch (e) {}
      setTimeout(function () { var bt = d.querySelector(".st-key-y2k_subida [data-testid='stFileUploaderDropzone'] button"); if (bt) bt.focus(); }, 120);
    }, 60);
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
    if (accion === "acercar") n.zoom = lim((v.zoom || 10) + 0.6, 1, 20);
    else if (accion === "alejar") n.zoom = lim((v.zoom || 10) - 0.6, 1, 20);
    else if (accion === "izq") n.bearing = (((v.bearing || 0) - 20) + 540) % 360 - 180;
    else if (accion === "der") n.bearing = (((v.bearing || 0) + 20) + 540) % 360 - 180;
    else if (accion === "subir") n.pitch = lim((v.pitch || 0) + 10, 0, 85);
    else if (accion === "bajar") n.pitch = lim((v.pitch || 0) - 10, 0, 85);
    else if (accion === "norte") n.bearing = 0;
    n.maxPitch = 85;
    mover(deck, n);
    var r = d.querySelector(".y2k-camara-estado");
    if (r) r.textContent = "Rumbo " + Math.round(((n.bearing || 0) + 360) % 360) + "°, inclinación " + Math.round(n.pitch || 0) + "°, zoom " + (n.zoom || 0).toFixed(1);
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
  // d) Mapa 2D: teselas que fallan una y otra vez
  var ultimoAviso2d = -1e9;
  function revisar2d() {
    var win = winMapa(), map = win && win.map;
    if (!map || !map.__y2kTeselas || d.getElementById("y2k_dlg_red2d")) return;
    var ahora = w.performance.now(), r = map.__y2kTeselas.lista.filter(function (x) { return ahora - x.t < 20000; });
    var malos = r.filter(function (x) { return !x.ok; }), buenos = r.length - malos.length;
    if (malos.length < 8 || buenos > 0 || ahora - ultimoAviso2d < 45000) return;
    ultimoAviso2d = ahora;
    var capa = malos[malos.length - 1].capa, nombre = map.__y2kBase || "Satélite";
    var redibujar = function () { map.__y2kTeselas.lista = []; try { capa.redraw(); } catch (e) {} };
    dialogo({
      id: "y2k_dlg_red2d", tipo: "Problema de red", titulo: "El mapa base no está cargando",
      texto: "Fallan las teselas de «" + nombre + "». Suele deberse a la conexión o al servidor de mapas. Tu cuenca y las estaciones siguen en el mapa.",
      acciones: (esLite() ? [] : [{etiqueta: "Activar Lite y reintentar", fn: function () { pulsarOculto("y2k_lite_reintentar"); redibujar(); }}])
        .concat([{etiqueta: "Seguir intentando", primaria: true, fn: redibujar}])
    });
  }

  ciclos.push(setInterval(function () {
    if (!vivo) return;
    try { vigilarContexto(); vigilarRed3d(); reponerCamara(); vigilar2d(); revisar2d(); distribuir(); } catch (e) {}
  }, 700));
  sincronizar(); distribuir();

  w.__y2kUI = {
    v: V, camara: camara, buscarDeck: buscarDeck, esLite: esLite, distribuir: distribuir,
    parar: function () {
      vivo = false; ciclos.forEach(clearInterval); obs.disconnect();
      d.removeEventListener("click", alClic, true); d.removeEventListener("pointerdown", alBajar, true);
      d.removeEventListener("pointermove", alMover, true); d.removeEventListener("pointerup", alSoltar, true);
      d.removeEventListener("pointercancel", alSoltar, true); d.removeEventListener("keydown", alTecla, true);
    }
  };
})();
"""


def instalar_ui():
    """Inyecta el guion de la interfaz en la pagina principal (sobrevive a las recargas de Streamlit)."""
    codigo = (_UI.replace("__V__", "22").replace("__ICONO_ALERTA__", json.dumps(ICONOS["alerta"]))
              .replace("__MOVIL__", json.dumps(MOVIL)).replace("__VIDRIO__", json.dumps(VIDRIO)))
    cuerpo = ("(function(){var w=window.parent;var s=w.document.createElement('script');"
              f"s.textContent={json.dumps(codigo)};w.document.head.appendChild(s);s.remove();}})();")
    components.html("<script>" + cuerpo.replace("</", "<\\/") + "</script>", height=0)


# ---------------------------------------------------------------------------
# Piezas de la pantalla del mapa
# ---------------------------------------------------------------------------
def pestanas(n_resumen=None):
    """Cabecera del panel: pestanas Consulta / Resumen. En el celular lleva el asa de la hoja y el boton de ampliar."""
    cuenta = (f'<span class="cuenta" aria-hidden="true">{n_resumen}</span><span class="y2k-vh">, {n_resumen} estaciones'
              '</span>') if n_resumen is not None else ""
    md('<div class="y2k-cab"><button type="button" class="y2k-asa" data-y2k-asa aria-expanded="false" aria-label="Mostrar el panel"></button>'
       '<div class="y2k-cab-fila"><div class="y2k-tabs" role="tablist" aria-label="Contenido del panel">'
       '<button type="button" role="tab" data-y2k-tab-btn="consulta" aria-selected="true">Consulta</button>'
       f'<button type="button" role="tab" data-y2k-tab-btn="resumen" aria-selected="false">Resumen{cuenta}</button></div>'
       f'<button type="button" class="y2k-ico y2k-hoja-max" data-y2k-hoja-max aria-label="Ampliar el panel">{ICONOS["subir_hoja"]}</button>'
       '</div></div>')


def paso(numero, titulo, hecho=False, estado=""):
    """Encabezado de un paso de Consulta: numero (o marca de hecho), titulo y un estado breve."""
    md(f'<div class="y2k-paso{" hecho" if hecho else ""}"><span class="n" aria-hidden="true">{"✓" if hecho else numero}</span>'
       f'<div class="t" role="heading" aria-level="2">{titulo}{"<span class=y2k-vh> (listo)</span>" if hecho else ""}</div>'
       f'{f"<span class=estado>{estado}</span>" if estado else ""}</div>')


def opciones_cuenca(hay_cuenca=False):
    """Formas de marcar la cuenca en el mapa. "Usar el área visible" es la alternativa de teclado al gesto de arrastrar."""
    md('<div class="y2k-opciones">'
       f'<button type="button" class="y2k-opcion prim" data-y2k-dibujar>{ICONOS["dibujar"]}'
       f'<span>{"Dibujar otro rectángulo" if hay_cuenca else "Dibujar un rectángulo"}</span><small>Arrastra sobre el mapa</small></button>'
       f'<button type="button" class="y2k-opcion" data-y2k-area aria-disabled="true">{ICONOS["area"]}'
       '<span>Usar el área visible</span><small>Primero acércate a tu zona</small></button></div>')


def detalles(resumen, cuerpo, ver="Ver detalles"):
    """Resumen breve siempre visible y el detalle desplegable (<details>, accesible con teclado)."""
    md(f'<details class="y2k-det"><summary><span>{resumen}</span><span class="ver">{ver}</span></summary>'
       f'<div>{cuerpo}</div></details>')


def estado_accion(titulo, detalle="", vinculo=None, alerta=False, sep=" "):
    """Texto de la isla de accion: que hay y que sigue. `vinculo` = (texto, pestana) abre esa pestana del panel;
    `sep` va antes del vinculo y se oculta con el (en el celular, "Ver resumen" sobra: la pestana esta a la vista)."""
    extra = (f'<span class="y2k-vin">{sep}<button type="button" class="y2k-vinculo" data-y2k-ver="{vinculo[1]}">'
             f'{vinculo[0]}</button></span>') if vinculo else ""
    md(f'<div class="y2k-estado{" alerta" if alerta else ""}" role="status"><b>{titulo}</b>'
       f'{f"<span>{detalle}{extra}</span>" if detalle or extra else ""}</div>')


def botones_inicio():
    """Las dos formas de empezar, en la isla de accion."""
    md('<div class="y2k-dock-botones">'
       f'<button type="button" class="y2k-boton prim" data-y2k-dibujar>{ICONOS["dibujar"]}Dibujar</button>'
       f'<button type="button" class="y2k-boton sec" data-y2k-subir>{ICONOS["archivo"]}Subir archivo</button></div>')


def leyenda_estaciones(colores, en3d=False):
    """Leyenda compacta de los pines sobre el mapa (color, forma y texto; nunca solo color)."""
    filas = "".join(f'<li><span class="pin" style="background:{c}"></span>{n}</li>' for n, c in colores)
    filas += ('<li><span class="pin hueco"></span>Sin serie</li>'
              '<li><span class="pin duda" style="background:#9AA6BC"></span>Altitud dudosa</li>')
    filas += ('<li><span class="linea" style="border-color:#35F0FF"></span>Cuenca</li>'
              '<li><span class="linea" style="border-color:#FF7A1A;border-top-style:dashed"></span>Buffer</li>'
              '<li class="nota">Relieve exagerado ×2 · Ctrl + arrastrar gira e inclina</li>') if en3d else (
              '<li><span class="linea" style="border-color:#1C6FD8"></span>Cuenca</li>'
              '<li><span class="linea" style="border-color:#FAB219;border-top-style:dashed"></span>Buffer</li>')
    md(f'<details class="y2k-sobre lg-regular y2k-leyenda" open><summary>Leyenda</summary><ul>{filas}</ul></details>')


def leyenda_altura(html):
    """Leyenda de la textura "Altura" del 3D (la escala la arma terreno.leyenda_altura)."""
    md(f'<details class="y2k-sobre lg-regular y2k-leyenda" open><summary>Altitud</summary>{html}'
       '<p class="tit">Relieve exagerado ×2 · Ctrl + arrastrar gira e inclina</p></details>')


def controles_camara():
    """Botones de camara del 3D: alternativa accesible a arrastrar, girar e inclinar con gestos."""
    b = [("acercar", "mas", "Acercar"), ("alejar", "menos", "Alejar"), None,
         ("izq", "girar_izq", "Girar a la izquierda"), ("der", "girar_der", "Girar a la derecha"), None,
         ("subir", "inclinar_mas", "Inclinar más"), ("bajar", "inclinar_menos", "Inclinar menos"),
         ("norte", "norte", "Orientar al norte")]
    html = "".join("<hr>" if x is None else
                   f'<button type="button" data-y2k-cam="{x[0]}" aria-label="{x[2]}" title="{x[2]}">{ICONOS[x[1]]}</button>'
                   for x in b)
    md(f'<div class="y2k-sobre lg-claro y2k-camara" role="group" aria-label="Cámara 3D">{html}'
       '<span class="y2k-vh y2k-camara-estado" aria-live="polite"></span></div>')


def sobre_mapa(html, clase, material="lg-regular"):
    md(f'<div class="y2k-sobre {material} {clase}">{html}</div>')


def pie():
    """Fuente de los datos, condiciones de uso, manual y creditos de los mapas."""
    f = FUENTE
    md('<footer class="y2k-pie">'
       f'<p>Datos: <b>{f["nombre"]}</b> · <a href="{f["url"]}" target="_blank" rel="noopener">Instituto de Hidrología, '
       'Meteorología y Estudios Ambientales</a></p>'
       '<p>Uso personal, privado y no comercial; cita la fuente (el ZIP incluye CITACION.txt). '
       'Herramienta independiente, no oficial del IDEAM.</p>'
       f'<p><a href="app/static/manual.html" target="_blank" rel="noopener">Manual de usuario</a> · versión {f["version"]}</p>'
       f'<details class="y2k-det"><summary><span class="ver">Fuentes y créditos de los mapas</span></summary>'
       f'<div><p>{CREDITOS_MAPAS}</p></div></details>'
       '</footer>')


def aviso_legal(texto):
    """Condiciones de uso en una linea; el texto completo se despliega."""
    md('<details class="y2k-det y2k-legal"><summary><span>Datos del IDEAM: uso personal y no comercial; cita la '
       f'fuente.</span><span class="ver">Ver condiciones</span></summary><div><p>{texto}</p></div></details>')


def barra_pixel(fraccion):
    llenos = round(max(0.0, min(1.0, fraccion)) * 32)
    return ('<div class="y2k-pbar" role="progressbar" aria-label="Avance de la descarga" aria-valuemin="0" aria-valuemax="100" '
            f'aria-valuenow="{round(fraccion * 100)}">' + "".join('<i class="on"></i>' if i < llenos else "<i></i>"
                                                                  for i in range(32)) + "</div>")
