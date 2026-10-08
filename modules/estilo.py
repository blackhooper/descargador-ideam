import json
from html import escape

import streamlit as st
import streamlit.components.v1 as components

# ===========================================================================
# DISENO: TRES PANTALLAS SOBRE UN MISMO MAPA, CON CONTROLES DE VIDRIO LIQUIDO
# El mapa 2D ocupa siempre la ventana (escenario) y no se vuelve a cargar al
# cambiar de pantalla:
#   1. Parametros: el mapa se ve detras, velado y sin clics; encima, una
#      tarjeta de vidrio con la serie (estandar o especial), la variable, las
#      fechas y el boton "Seleccionar area en el mapa" (se enciende cuando todo
#      cargo; no hay textos de carga, solo el punto de la etiqueta).
#   2. Mapa: el mapa a pantalla completa con el panel de la consulta (area,
#      buffer y calidad de los datos; en el celular, una tarjeta que se abre con
#      el boton "Consulta"), una capsula de herramientas (dibujo, capas y zoom),
#      las pildoras de abajo (2D/3D y "Preparar descarga") y la ficha de la
#      estacion elegida.
#   3. Exportacion: el mapa velado otra vez y una tarjeta con el avance real,
#      el recibo de la descarga, el nombre del ZIP y las condiciones de uso.
# Arriba a la derecha, en todas: un unico menu de Ajustes (tema, alto
# contraste, modo Lite y manual).
# El vidrio deja ver el mapa (desenfoque y saturacion del fondo), tiene brillo
# especular que sigue al puntero, canto de luz y sombra de profundidad. Ninguna
# superficie de vidrio se desplaza: si el contenido no cabe, se desplaza un
# cuerpo interior (asi el brillo y el canto quedan fijos). Dos materiales:
#   - claro: controles pequenos (solo texto principal e iconos), mas transparente
#   - regular: superficies con texto (mas opaco, para leer sobre cualquier mapa)
# Ejes independientes: tema (claro/oscuro; sin elegir, el del sistema), alto
# contraste (sin activarlo, el del sistema) y modo Lite (sin desenfoque ni
# efectos; no depende del movimiento reducido).
# Los colores de Streamlit salen de [theme.light]/[theme.dark] (config.toml).
# ===========================================================================

FUENTE = {
    "nombre": "IDEAM · DHIME",
    "url": "http://dhime.ideam.gov.co/atencionciudadano/",
    "version": "2.0",
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

# Valores validos de las preferencias (?tema=, ?contraste=). "sistema" = sin eleccion: sigue al equipo
TEMAS = {"sistema": "Sistema", "claro": "Claro", "oscuro": "Oscuro"}
CONTRASTES = {"sistema": "Sistema", "alto": "Alto"}

# Celular en vertical: el panel pasa a ser una tarjeta flotante que se abre con el boton "Consulta". En horizontal
# (pantalla baja) se usa el panel lateral, mas compacto: la tarjeta dejaria el mapa en una franja.
MOVIL = "(max-width: 760px)"
BAJO = "(max-height: 560px) and (min-width: 761px)"

# Selectores de cada pantalla: los marca guiones_globales() con un elemento .y2k-pantalla (ver CSS)
P_PARAM = '.stApp:has(.y2k-pantalla[data-p="parametros"])'
P_MAPA = '.stApp:has(.y2k-pantalla[data-p="mapa"])'
P_EXPORT = '.stApp:has(.y2k-pantalla[data-p="exportar"])'

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
        "y2k-ok": "#0E6B36", "y2k-ok-luz": "#22C55E", "y2k-peligro": "#A8201A",
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
        "y2k-velo": "radial-gradient(120% 95% at 50% 45%,rgba(233,238,245,.30),rgba(214,224,238,.62))",
        "y2k-mapa-fondo": "#C9D6E4", "y2k-cielo": "linear-gradient(180deg,#8FBBE6 0%,#C9DFF3 55%,#E8F0F8 100%)",
    },
    "oscuro": {
        "y2k-tono": "oscuro", "y2k-alto": "0",
        "y2k-bg": "#0B0E14", "y2k-ink": "#F4F6FA", "y2k-ink-2": "#DCE1EA", "y2k-ink-3": "#C8D0DC",
        "y2k-line": "rgba(255,255,255,.12)", "y2k-line-2": "rgba(255,255,255,.24)",
        "y2k-accent": "#7DB6FF", "y2k-accent-texto": "#8EC0FF", "y2k-accent-2": "#5EE0F5", "y2k-sobre-acento": "#071226",
        "y2k-foco": "#9CCBFF", "y2k-alerta": "#FFB37E", "y2k-alerta-borde": "#E7864E", "y2k-alerta-bg": "rgba(66,30,10,.88)",
        "y2k-ok": "#6EE0A0", "y2k-ok-luz": "#4ADE80", "y2k-peligro": "#FF9B94",
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
        "y2k-velo": "radial-gradient(120% 95% at 50% 45%,rgba(8,11,17,.38),rgba(6,9,14,.74))",
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
        "y2k-alerta-bg": "#FFF1E8", "y2k-ok": "#00561F", "y2k-ok-luz": "#00561F", "y2k-peligro": "#8A0000",
        "y2k-campo": "#FFFFFF", "y2k-campo-borde": "#000000", "y2k-hover": "#E6E6E6", "y2k-pista": "#FFFFFF",
        "y2k-lente": "#000000", "y2k-lente-sombra": "none",
        "lg-claro": "#FFFFFF", "lg-regular": "#FFFFFF", "lg-denso": "#FFFFFF", "lg-brillo": "none",
        "lg-borde": "#000000", "lg-luz": "transparent", "lg-filo": "#000000", "lg-especular": "transparent",
        "lg-sombra": "0 0 #0000", "lg-filtro-claro": "none", "lg-filtro-regular": "none",
        "y2k-velo": "rgba(255,255,255,.82)",
    },
    "oscuro": {
        "y2k-alto": "1", "y2k-bg": "#000000", "y2k-ink": "#FFFFFF", "y2k-ink-2": "#F2F2F2", "y2k-ink-3": "#E0E0E0",
        "y2k-line": "#C8C8C8", "y2k-line-2": "#FFFFFF", "y2k-accent": "#9CCBFF", "y2k-accent-texto": "#9CCBFF",
        "y2k-sobre-acento": "#000000", "y2k-foco": "#FFD60A", "y2k-alerta": "#FFB98A", "y2k-alerta-borde": "#FFB98A",
        "y2k-alerta-bg": "#2A1406", "y2k-ok": "#7CF0A8", "y2k-ok-luz": "#7CF0A8", "y2k-peligro": "#FFA3A3",
        "y2k-campo": "#000000", "y2k-campo-borde": "#FFFFFF", "y2k-hover": "#262626", "y2k-pista": "#000000",
        "y2k-lente": "#FFFFFF", "y2k-lente-sombra": "none",
        "lg-claro": "#000000", "lg-regular": "#000000", "lg-denso": "#000000", "lg-brillo": "none",
        "lg-borde": "#FFFFFF", "lg-luz": "transparent", "lg-filo": "#FFFFFF", "lg-especular": "transparent",
        "lg-sombra": "0 0 #0000", "lg-filtro-claro": "none", "lg-filtro-regular": "none",
        "y2k-velo": "rgba(0,0,0,.84)",
    },
}


def md(html):
    """HTML propio en la pagina. st.html quita los SVG en linea; st.markdown (con HTML permitido) los conserva.
    El envoltorio y2k-md anula el margen negativo que Streamlit pone a los bloques de markdown."""
    st.markdown(f'<div class="y2k-md">{html}</div>', unsafe_allow_html=True)


def _vars(tokens):
    return ";".join(f"--{k}:{v}" for k, v in tokens.items())


def _tokens_css(tema, contraste):
    """Variables segun la eleccion. Sin eleccion ("sistema") se resuelve en el navegador con media queries
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
VIDRIO_CLARO = (".st-key-y2k_ajustes,.st-key-y2k_herr,.st-key-y2k_abrir,.st-key-y2k_dock_izq,.st-key-y2k_dock_der,"
                ".lg-claro")
VIDRIO_REGULAR = ".st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_inicio,.st-key-y2k_exportar,.lg-regular"
VIDRIO = VIDRIO_CLARO + "," + VIDRIO_REGULAR

CSS = """
@import url("https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600;700&display=swap");
:root{
  --y2k-g:12px; --y2k-panel-w:360px; --y2k-capsula:44px; --y2k-r:22px; --y2k-r-ctl:12px;
  --y2k-libre-izq:0px; --y2k-dock-h:64px; --y2k-hoja-h:62px;
  --y2k-ov-top:12px; --y2k-ov-izq:12px; --y2k-ov-der:68px; --y2k-ov-abajo:72px;
  --y2k-ley-abajo:72px; --y2k-atrib-abajo:72px;
  /* esquina de abajo a la derecha reservada al boton de Streamlit Community Cloud ("Manage app" o su logo), que va
     fuera de la app y no se puede mover: la pone aplicar(sello=True) */
  --y2k-sello:0px;
  --y2k-lite:0; --y2k-dur:.32s; --y2k-curva:cubic-bezier(.2,.8,.2,1);
  --y2k-centro:calc(var(--y2k-libre-izq) + (100vw - var(--y2k-libre-izq)) / 2);
  color-scheme:light dark;
}
/* sin "jalar para recargar" del navegador del celular (recargaba la pagina sin querer) */
html,body{overscroll-behavior:none}
html, body, .stApp, [class*="st-"], button, input, textarea, select{font-family:"Figtree",system-ui,-apple-system,"Segoe UI",sans-serif}
/* los iconos de Streamlit son una fuente: sin esto salen como texto ("dark_mode") */
[data-testid="stIconMaterial"], [data-testid="stExpanderIcon"]{font-family:"Material Symbols Rounded" !important}
.stApp{background:var(--y2k-bg);color:var(--y2k-ink)}
[data-testid="stAppViewContainer"],[data-testid="stMain"]{background:transparent}
/* el menu de Streamlit se oculta: tema y contraste se cambian en "Ajustes" */
[data-testid="stMainMenu"]{visibility:hidden !important}
header[data-testid="stHeader"]{background:transparent;pointer-events:none;height:0;min-height:0}
[data-testid="stDecoration"]{display:none}
[data-testid="stToolbar"]{pointer-events:none !important}
header[data-testid="stHeader"] button,[data-testid="stToolbar"] button{pointer-events:auto !important}
[data-testid="stStatusWidget"]{display:none !important}
/* Streamlit atenua lo que recalcula (en oscuro parece una pantalla negra): cada pantalla avisa su propia carga */
[data-stale="true"]{opacity:1 !important;transition:none !important}
[data-testid="stMarkdownContainer"]:has(> .y2k-md){margin-bottom:0 !important}
.y2k-md [data-testid="stHeaderActionElements"]{display:none}
/* contenedores de guiones (alto cero): no ocupan lugar */
.st-key-y2k_orbita,.st-key-y2k_escaner,.st-key-y2k_hipso,.st-key-y2k_velo,.st-key-y2k_precal,.st-key-y2k_guiones,
.st-key-y2k_ocultos{height:0 !important;min-height:0 !important;overflow:hidden !important;margin:0 !important;
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
/* brillo especular: una luz suave que sigue al puntero (la mueve el guion de la interfaz). Va en el fondo del
   propio vidrio, que no se desplaza: la luz siempre queda bajo el puntero */
:is(__VIDRIO_CLARO__){background:radial-gradient(240px 150px at var(--mx,22%) var(--my,-40%),var(--lg-especular),transparent 70%),
  var(--lg-brillo),var(--lg-claro);-webkit-backdrop-filter:var(--lg-filtro-claro);backdrop-filter:var(--lg-filtro-claro)}
:is(__VIDRIO_REGULAR__){background:radial-gradient(240px 150px at var(--mx,22%) var(--my,-40%),var(--lg-especular),transparent 70%),
  var(--lg-brillo),var(--lg-regular);-webkit-backdrop-filter:var(--lg-filtro-regular);backdrop-filter:var(--lg-filtro-regular)}
:is(__VIDRIO__){isolation:isolate;border-radius:var(--y2k-r);color:var(--y2k-ink);
  box-shadow:inset 0 1px 0 var(--lg-luz),inset 0 -1px 0 var(--lg-borde),0 0 0 .5px var(--lg-filo),var(--lg-sombra);
  transition:box-shadow var(--y2k-dur) ease}
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
:is(__VIDRIO_CLARO__) button[kind="primary"]{background:var(--y2k-accent) !important;color:var(--y2k-sobre-acento) !important}
.st-key-y2k_dock_izq [data-testid="stButtonGroup"]{width:auto}
.st-key-y2k_dock_izq [data-testid="stButtonGroup"] > div{gap:2px;background:transparent;border:0;flex-wrap:nowrap}
.st-key-y2k_dock_izq button[role="radio"]{padding:0 14px !important;min-height:36px !important;min-width:52px}
.st-key-y2k_dock_izq button[aria-checked="true"],[data-testid="stPopoverBody"] button[aria-checked="true"]{background:var(--y2k-lente) !important;
  box-shadow:var(--y2k-lente-sombra) !important}
.st-key-y2k_dock_izq button[aria-checked="true"] p{font-weight:700 !important}

/* ================= ESCENARIO: EL MAPA, SIEMPRE DETRAS ================= */
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
/* al pasar a 3D, el mapa 2D viejo sigue un momento en el mismo lugar (ya con la clave del visor): que siga llenando */
.st-key-y2k_visor3d > [data-testid="stElementContainer"]:has(iframe[title*="st_folium"]),
.st-key-y2k_visor3d > [data-testid="stElementContainer"]:has(iframe[title*="st_folium"]) > div{height:100% !important;width:100% !important}
.st-key-y2k_visor3d iframe[title*="st_folium"]{height:100% !important;width:100% !important;display:block;border:0}
/* cielo detras del relieve 3D (el 3D no tiene mapa plano de fondo) */
[data-testid="stDeckGlJsonChart"]{background:var(--y2k-cielo);overflow:hidden}
/* velo sobre el mapa en Parametros y Exportacion: se ve detras, desenfocado, y no recibe clics */
.st-key-y2k_escenario::after{content:"";position:absolute;inset:0;z-index:30;pointer-events:none;opacity:0;visibility:hidden;
  background:var(--y2k-velo);-webkit-backdrop-filter:blur(5px) saturate(125%);backdrop-filter:blur(5px) saturate(125%);
  transition:opacity .6s var(--y2k-curva),visibility 0s .6s}
:is(__P_PARAM__,__P_EXPORT__) .st-key-y2k_escenario::after{opacity:1;visibility:visible;pointer-events:auto;
  transition:opacity .6s var(--y2k-curva),visibility 0s}
/* piezas HTML sobre el mapa: el contenedor de Streamlit no debe ser su referencia de posicion */
.st-key-y2k_escenario > [data-testid="stElementContainer"]:has(.y2k-sobre){position:absolute !important;inset:0;width:auto !important;
  height:auto !important;pointer-events:none;z-index:25;margin:0}
.st-key-y2k_escenario > [data-testid="stElementContainer"]:has(.y2k-sobre) *:has(.y2k-sobre){position:static !important}
.y2k-sobre{position:absolute;pointer-events:auto;z-index:25}
/* intro satelital (static/intro_satelital): cubre toda la ventana, encima de los controles */
.y2k-sat{border-radius:0 !important}
.y2k-sat > button{right:20px !important;bottom:20px !important;border-radius:999px !important;padding:10px 16px !important;
  font-size:13px !important;-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px)}

/* ================= AJUSTES (arriba a la derecha, en todas las pantallas) ================= */
.st-key-y2k_ajustes{position:fixed !important;top:var(--y2k-g);right:var(--y2k-g);z-index:55;height:var(--y2k-capsula);
  width:auto !important;border-radius:999px;padding:4px !important;margin:0 !important;display:flex !important;flex-direction:row !important;
  align-items:center;gap:2px !important;flex-wrap:nowrap !important}
.st-key-y2k_ajustes > div{width:auto !important;flex:none !important}
/* capsulas flotantes: Streamlit pone overflow:auto a sus contenedores horizontales y, con el contenido justo del alto
   de la capsula, un pixel de mas (fuente, zoom) abria una barra de desplazamiento al pasar el puntero */
:is(.st-key-y2k_ajustes,.st-key-y2k_dock,.st-key-y2k_dock_izq,.st-key-y2k_dock_der),
:is(.st-key-y2k_ajustes,.st-key-y2k_dock_izq) > div,.st-key-y2k_ajustes .stPopover{overflow:visible !important}
.st-key-y2k_ajustes .stPopover button{width:36px;min-width:36px;padding:0 !important;justify-content:center}
.st-key-y2k_ajustes .stPopover button [data-testid="stMarkdownContainer"]{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.st-key-y2k_ajustes .stPopover button [data-testid="stIconMaterial"]{font-size:21px !important}
.st-key-y2k_ajustes [data-testid="stPopoverButton"] > div > div[aria-hidden="true"]{display:none !important}
.y2k-lite-chip{display:inline-flex;align-items:center;height:28px;padding:0 10px 0 8px;border-radius:999px;font:700 12px/1 "Figtree",sans-serif;
  letter-spacing:.04em;color:var(--y2k-sobre-acento);background:var(--y2k-accent);gap:4px}
.y2k-lite-chip svg{width:13px;height:13px}
[data-testid="stPopoverBody"]{border-radius:18px !important;border:0 !important;background:var(--lg-brillo),var(--lg-denso) !important;
  -webkit-backdrop-filter:var(--lg-filtro-regular);backdrop-filter:var(--lg-filtro-regular);
  box-shadow:inset 0 1px 0 var(--lg-luz),0 0 0 .5px var(--lg-filo),var(--lg-sombra) !important}
[data-testid="stPopoverBody"] .y2k-hint{margin-top:2px !important}
.y2k-menu-tit,[data-testid="stMarkdownContainer"] p.y2k-menu-tit{font-size:11.5px !important;text-transform:uppercase;letter-spacing:.08em;
  font-weight:700;color:var(--y2k-ink-3) !important;margin:0 0 -4px !important;line-height:1.3 !important}
.y2k-enlace{display:flex;align-items:center;gap:8px;font-weight:600;font-size:13.5px;color:var(--y2k-accent-texto) !important;text-decoration:none !important;
  padding:10px 0 2px;border-top:1px solid var(--y2k-line)}
.y2k-enlace:hover{text-decoration:underline !important}
.y2k-enlace svg{width:17px;height:17px}

/* ================= PANTALLA 1: PARAMETROS ================= */
.st-key-y2k_inicio{position:fixed !important;z-index:40;left:50%;top:50%;transform:translate(-50%,-50%);
  width:min(580px,calc(100vw - 32px)) !important;max-height:calc(100dvh - 2 * (var(--y2k-g) + var(--y2k-capsula) + 8px));overflow:hidden;
  padding:0 !important;gap:0 !important;border-radius:30px;display:flex !important;flex-direction:column;
  animation:y2k-entra-centro .5s var(--y2k-curva) both}
/* tarjetas centradas: el vidrio queda quieto y se desplaza su cuerpo; la barra, delgada y dentro de la curva */
:is(.st-key-y2k_inicio,.st-key-y2k_exportar,.st-key-y2k_ficha) > [data-testid="stLayoutWrapper"]{flex:1 1 auto;min-height:0;display:flex;
  flex-direction:column;width:100% !important}
.st-key-y2k_inicio_cuerpo,.st-key-y2k_exportar_cuerpo,.st-key-y2k_ficha_cuerpo{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;
  scrollbar-width:thin;scrollbar-color:var(--y2k-line-2) transparent;scrollbar-gutter:auto}
.st-key-y2k_inicio_cuerpo{margin:16px 4px 16px 0 !important;padding:12px 26px 6px 30px !important;gap:14px !important}
@keyframes y2k-entra-centro{from{opacity:0;transform:translate(-50%,calc(-50% + 14px)) scale(.985)}}
.y2k-cab-inicio .eyebrow{font-size:12px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--y2k-accent-texto);margin:0}
.y2k-cab-inicio h1{font-size:clamp(25px,3.1vw,32px) !important;line-height:1.12 !important;font-weight:700 !important;letter-spacing:-.022em;
  margin:6px 0 0 !important;padding:0 !important;color:var(--y2k-ink)}
.y2k-etq{display:flex;align-items:center;gap:8px;font-size:13px;font-weight:600;color:var(--y2k-ink);margin:0 0 -8px;min-height:18px}
.y2k-etq .opc{font-weight:500;color:var(--y2k-ink-3)}
.st-key-y2k_fechas [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important}
.st-key-y2k_fechas [data-testid="stColumn"]{min-width:0 !important;flex:1 1 0 !important;width:auto !important}
/* punto de estado de la lista de parametros: gris mientras carga, se enciende al estar lista */
.y2k-punto{width:7px;height:7px;border-radius:50%;background:var(--y2k-line-2);flex:none;margin-left:2px}
.y2k-punto[data-estado="cargando"]{animation:y2k-respira 1.6s ease-in-out infinite}
.y2k-punto[data-estado="listo"]{background:var(--y2k-ok-luz);box-shadow:0 0 0 2.5px color-mix(in srgb,var(--y2k-ok-luz) 24%,transparent),
  0 0 9px 1px color-mix(in srgb,var(--y2k-ok-luz) 70%,transparent);animation:y2k-enciende 1s ease-out 1}
.y2k-punto[data-estado="error"]{background:var(--y2k-peligro)}
@keyframes y2k-respira{50%{opacity:.3}}
@keyframes y2k-enciende{0%{transform:scale(.3);opacity:.4}55%{transform:scale(1.5);opacity:1}100%{transform:scale(1)}}
.st-key-y2k_inicio [data-baseweb="select"] > div,.st-key-y2k_inicio [data-baseweb="input"],.st-key-y2k_inicio [data-baseweb="base-input"],
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_exportar) [data-baseweb="select"] > div,
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_exportar) [data-baseweb="input"],
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_exportar) [data-baseweb="base-input"]{background:var(--y2k-campo) !important;
  border-color:var(--y2k-campo-borde) !important;border-radius:var(--y2k-r-ctl) !important}
.st-key-y2k_inicio [data-baseweb="select"] > div{min-height:46px}
.st-key-y2k_inicio [data-baseweb="select"]:has(input:disabled) > div{opacity:.55;cursor:not-allowed}
/* serie de tiempo: dos opciones del mismo ancho */
.st-key-serie [data-testid="stButtonGroup"] > div{width:100%;flex-wrap:nowrap}
.st-key-serie button[role="radio"]{flex:1 1 0 !important;min-height:40px}
.st-key-serie button[aria-checked="true"]{background:var(--y2k-lente) !important;box-shadow:var(--y2k-lente-sombra) !important;
  border-color:transparent !important}
.st-key-serie button[aria-checked="true"] p{font-weight:700 !important}
/* boton principal: alto y ancho; espera (gris) hasta que el mapa y los datos esten listos */
.st-key-ir_mapa button{min-height:52px !important;font-size:15.5px !important;border-radius:999px !important}
.st-key-ir_mapa button p{font-size:15.5px !important}
html:not([data-y2k-mapa-listo]) .st-key-ir_mapa button,.st-key-ir_mapa button[aria-disabled="true"]{opacity:.5;filter:saturate(.3);
  box-shadow:none !important;cursor:progress}
/* pasos de la consulta: el actual resaltado, los demas en linea fina */
.y2k-como{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:2px 0 0;padding:0;list-style:none;counter-reset:paso}
.y2k-como li{display:flex;flex-direction:column;gap:4px;padding:10px 12px 11px;border-radius:16px;margin:0;font-size:12.5px;line-height:1.4;
  color:var(--y2k-ink-3);box-shadow:inset 0 0 0 1px var(--y2k-line)}
.y2k-como li[aria-current]{background:var(--y2k-campo);box-shadow:inset 0 0 0 1px var(--y2k-campo-borde)}
.y2k-como li b{font-size:13px;color:var(--y2k-ink);display:flex;align-items:center;gap:7px;line-height:1.2}
.y2k-como li b::before{counter-increment:paso;content:counter(paso);width:20px;height:20px;border-radius:50%;flex:none;display:grid;place-items:center;
  font-size:11px;color:var(--y2k-ink-2);box-shadow:inset 0 0 0 1.5px var(--y2k-line-2)}
.y2k-como li[aria-current] b::before{background:var(--y2k-accent);color:var(--y2k-sobre-acento);box-shadow:none}
.y2k-pie-inicio{display:flex;flex-direction:column;gap:6px;padding-top:12px;border-top:1px solid var(--y2k-line);font-size:12px;line-height:1.5;color:var(--y2k-ink-3)}
.y2k-pie-inicio p{margin:0;font-size:12px;color:var(--y2k-ink-3)}
.st-key-y2k_inicio [data-testid="stExpander"] details,.st-key-y2k_exportar [data-testid="stExpander"] details{border-radius:16px !important;border:0 !important;
  background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset}

/* ================= PANTALLA 2: MAPA ================= */
/* panel lateral */
html[data-y2k-panel="abierto"],html:not([data-y2k-panel]){--y2k-libre-izq:calc(var(--y2k-panel-w) + var(--y2k-g) * 2)}
.st-key-y2k_panel{position:fixed !important;z-index:40;top:var(--y2k-g);bottom:var(--y2k-g);left:var(--y2k-g);
  width:var(--y2k-panel-w) !important;padding:0 !important;gap:0 !important;display:flex !important;flex-direction:column;overflow:hidden;
  transform-origin:10% 0;transition:transform var(--y2k-dur) var(--y2k-curva),opacity var(--y2k-dur) ease,visibility 0s;
  animation:y2k-entra-izq .45s var(--y2k-curva) both}
@keyframes y2k-entra-izq{from{opacity:0;transform:translateX(-18px)}}
html[data-y2k-panel="cerrado"] .st-key-y2k_panel{transform:translate(-12px,-8px) scale(.94);opacity:0;visibility:hidden;
  transition:transform var(--y2k-dur) var(--y2k-curva),opacity .2s ease,visibility 0s var(--y2k-dur)}
html[data-y2k-panel="cerrado"]{--y2k-libre-izq:0px}
.st-key-y2k_panel > div{width:100% !important}
.st-key-y2k_panel > [data-testid="stElementContainer"]{flex:none}
.st-key-y2k_panel > [data-testid="stLayoutWrapper"]{flex:1 1 auto;min-height:0;display:flex;flex-direction:column}
.st-key-y2k_panel > [data-testid="stLayoutWrapper"]:has(> .st-key-y2k_panel_cab){flex:none}
.st-key-y2k_panel_cab{padding:12px 12px 2px 20px !important;gap:0 !important}
.y2k-panel-cab{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:36px}
.y2k-panel-cab .t,[data-testid="stMarkdownContainer"] .y2k-panel-cab p.t{margin:0;font-size:17px !important;font-weight:700;letter-spacing:-.01em;
  color:var(--y2k-ink) !important;line-height:1.2 !important}
.y2k-hoja-cerrar{display:none !important}
.st-key-y2k_cuerpo{flex:1 1 auto;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:0 18px 18px !important;
  gap:12px !important;scrollbar-width:thin;scrollbar-color:var(--y2k-line-2) transparent}
/* secciones del panel: titulo y, a la derecha, su dato (cifra en capsula o la variable consultada) */
.y2k-sec{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:10px 0 -2px;min-height:30px}
.y2k-sec .t{font-size:11.5px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--y2k-ink-3);margin:0;flex:none}
.y2k-sec .valor{font-size:13px;font-weight:600;color:var(--y2k-ink-3);white-space:nowrap}
/* area marcada: su cifra en una capsula propia */
.y2k-km{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 11px 0 9px;border-radius:999px;white-space:nowrap;
  font:700 13px/1 "Figtree",sans-serif;font-variant-numeric:tabular-nums;color:var(--y2k-accent-texto);
  background:color-mix(in srgb,var(--y2k-accent) 14%,var(--lg-denso));box-shadow:inset 0 0 0 1px color-mix(in srgb,var(--y2k-accent) 34%,transparent)}
.y2k-km svg{width:15px;height:15px;flex:none}
/* la variable consultada: al pulsarla se vuelve a Parametros */
.y2k-chip{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:6px;min-width:0;max-width:60%;height:30px;padding:0 12px 0 8px;
  border-radius:999px;cursor:pointer;font:600 13px/1 "Figtree",sans-serif;color:var(--y2k-ink);background:var(--y2k-campo);
  box-shadow:inset 0 0 0 1px var(--y2k-campo-borde);transition:box-shadow var(--y2k-dur),transform .12s}
.y2k-chip span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.y2k-chip svg{width:16px;height:16px;flex:none;color:var(--y2k-accent-texto)}
.y2k-chip:hover{box-shadow:inset 0 0 0 1.5px var(--y2k-accent)}
.y2k-chip:active{transform:scale(.96)}
/* buffer: una pildora pequena; al pulsarla se cambia el ancho */
.st-key-y2k_buffer{margin-top:-2px}
.st-key-y2k_buffer [data-testid="stPopoverButton"],.st-key-y2k_buffer .stPopover button{min-height:32px !important;height:32px;padding:0 10px 0 8px !important;
  border-radius:999px !important;background:var(--y2k-campo) !important;border:0 !important;box-shadow:inset 0 0 0 1px var(--y2k-campo-borde) !important;
  color:var(--y2k-ink) !important;gap:6px}
.st-key-y2k_buffer .stPopover button p{font-size:13px !important;font-weight:600 !important;color:var(--y2k-ink) !important}
.st-key-y2k_buffer .stPopover button [data-testid="stIconMaterial"]{font-size:17px !important;color:var(--y2k-accent-texto)}
.st-key-y2k_buffer .stPopover button:hover{box-shadow:inset 0 0 0 1.5px var(--y2k-accent) !important}
.y2k-acciones{display:flex;flex-wrap:wrap;gap:6px}
.y2k-acciones .y2k-boton{flex:1 1 auto;justify-content:center}
/* con un area marcada: tres acciones compactas en una fila (icono arriba, texto abajo) */
.y2k-acciones.fichas{display:grid;grid-template-columns:repeat(3,minmax(0,1fr))}
.y2k-acciones.fichas .y2k-boton{flex-direction:column;height:auto;padding:9px 4px 8px;gap:5px;border-radius:14px;font-size:12.5px;font-weight:600}
.y2k-acciones.fichas .y2k-boton svg{width:18px;height:18px}
.y2k-boton{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:8px;height:40px;padding:0 14px;border-radius:999px;cursor:pointer;
  font:700 13.5px/1 "Figtree",sans-serif;white-space:nowrap;transition:transform .12s,filter var(--y2k-dur),box-shadow var(--y2k-dur)}
.y2k-boton svg{width:17px;height:17px;flex:none}
.y2k-boton.prim{background:var(--y2k-accent);color:var(--y2k-sobre-acento);box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 8px 18px -10px var(--y2k-accent)}
.y2k-boton.sec{color:var(--y2k-ink);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;background:var(--y2k-campo)}
.y2k-boton.sec svg{color:var(--y2k-accent-texto)}
.y2k-boton.sec:hover{box-shadow:0 0 0 1.5px var(--y2k-accent) inset}
.y2k-boton.peligro svg{color:var(--y2k-peligro)}
.y2k-boton:hover{filter:brightness(1.05)}
.y2k-boton:active{transform:scale(.96)}
/* tablero de calidad */
.y2k-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}
.y2k-kpi{background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;border-radius:14px;padding:9px 10px 8px;min-width:0}
.y2k-kpi .v{font-size:19px;font-weight:700;color:var(--y2k-ink);line-height:1.1;font-variant-numeric:tabular-nums;white-space:nowrap;letter-spacing:-.02em}
.y2k-kpi .l{font-size:11.5px;font-weight:700;color:var(--y2k-ink-2);line-height:1.25;margin-top:4px}
.y2k-kpi .s{font-size:11.5px;color:var(--y2k-ink-3);line-height:1.3}
.y2k-lista-cab{display:flex;align-items:baseline;justify-content:space-between;gap:8px;font-size:12.5px;color:var(--y2k-ink-3);margin:2px 0 -6px}
.y2k-lista-cab b{color:var(--y2k-ink);font-variant-numeric:tabular-nums}
.st-key-y2k_panel [data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
/* avisos discretos: una linea con su icono; el detalle, al abrirla */
.st-key-alerta_altura [data-testid="stExpander"] details,.st-key-alerta_ficha [data-testid="stExpander"] details{
  background:transparent !important;box-shadow:0 0 0 1px color-mix(in srgb,var(--y2k-alerta-borde) 45%,transparent) inset !important;border-radius:12px !important}
.st-key-alerta_altura [data-testid="stExpander"] summary,.st-key-alerta_ficha [data-testid="stExpander"] summary{min-height:0;padding-top:5px;padding-bottom:5px}
.st-key-alerta_altura [data-testid="stIconMaterial"],.st-key-alerta_ficha [data-testid="stIconMaterial"]{color:var(--y2k-alerta) !important}
.st-key-alerta_altura summary p,.st-key-alerta_ficha summary p{font-size:12.5px !important;font-weight:500 !important;color:var(--y2k-ink-2) !important}
/* boton para volver a mostrar el panel (escritorio) */
.st-key-y2k_abrir{position:fixed !important;top:var(--y2k-g);left:var(--y2k-g);z-index:50;height:var(--y2k-capsula);width:auto !important;
  border-radius:999px;padding:4px !important;margin:0 !important}
html:not([data-y2k-panel="cerrado"]) .st-key-y2k_abrir{display:none !important}
.y2k-ico{all:unset;box-sizing:border-box;min-width:36px;height:36px;display:inline-flex;align-items:center;justify-content:center;gap:6px;border-radius:999px;
  cursor:pointer;flex:none;color:var(--y2k-ink);transition:background var(--y2k-dur),transform .12s;font:600 13.5px/1 "Figtree",sans-serif}
.y2k-ico.con-texto{padding:0 12px 0 9px}
.y2k-ico:hover{background:var(--y2k-hover)}
.y2k-ico:active{transform:scale(.94)}
.y2k-ico svg{width:19px;height:19px;transition:transform var(--y2k-dur)}
/* capsula de herramientas (derecha, bajo Ajustes): dibujo, capas y zoom en 2D; camara en 3D */
.st-key-y2k_herr{position:fixed !important;right:var(--y2k-g);top:calc(var(--y2k-g) + var(--y2k-capsula) + 8px);z-index:50;width:auto !important;
  padding:4px !important;margin:0 !important;border-radius:24px;gap:0 !important;animation:y2k-menu .3s var(--y2k-curva) both}
.st-key-y2k_herr:not(:has(.y2k-herr)),.st-key-y2k_abrir:not(:has([data-y2k-panel-btn])),.st-key-y2k_dock:not(:has(.st-key-y2k_dock_izq)),
.st-key-y2k_panel:not(:has(.st-key-y2k_panel_cab)),.st-key-y2k_inicio:not(:has(.y2k-cab-inicio)),
.st-key-y2k_exportar:not(:has(.y2k-cab-export)){display:none !important}
.y2k-herr{display:flex;flex-direction:column;align-items:center;gap:2px}
.y2k-herr button.h,.y2k-camara button{all:unset;box-sizing:border-box;width:36px;height:36px;display:grid;place-items:center;border-radius:50%;cursor:pointer;
  color:var(--y2k-ink);transition:background var(--y2k-dur),transform .12s}
.y2k-herr button.h:hover,.y2k-camara button:hover{background:var(--y2k-hover)}
.y2k-herr button.h[aria-expanded="true"]{box-shadow:var(--y2k-lente-sombra);background:var(--y2k-lente)}
.y2k-herr button.h:active,.y2k-camara button:active{transform:scale(.92)}
.y2k-herr button.h:focus-visible,.y2k-camara button:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:-2px}
.y2k-herr svg{width:19px;height:19px}
.y2k-herr hr{width:20px;border:0;border-top:1px solid var(--y2k-line);margin:3px 0}
.y2k-grupo{position:relative}
.y2k-menu{position:absolute;right:calc(100% + 12px);top:-4px;min-width:240px;padding:6px;border-radius:18px;display:flex;flex-direction:column;gap:1px;
  background:var(--lg-brillo),var(--lg-denso);box-shadow:inset 0 1px 0 var(--lg-luz),0 0 0 .5px var(--lg-filo),var(--lg-sombra);
  transform-origin:100% 0;animation:y2k-menu .18s var(--y2k-curva) both}
@keyframes y2k-menu{from{opacity:0;transform:translateX(6px) scale(.97)}}
.y2k-menu[hidden]{display:none}
.y2k-menu .tit{font-size:11px;text-transform:uppercase;letter-spacing:.08em;font-weight:700;color:var(--y2k-ink-3);padding:6px 10px 4px;margin:0}
.y2k-menu hr{border:0;border-top:1px solid var(--y2k-line);margin:4px 6px}
.y2k-menu button{all:unset;box-sizing:border-box;display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:12px;cursor:pointer;
  font:600 13.5px/1.25 "Figtree",sans-serif;color:var(--y2k-ink)}
.y2k-menu button:hover,.y2k-menu button:focus-visible{background:var(--y2k-hover)}
.y2k-menu button:focus-visible{outline:2px solid var(--y2k-foco);outline-offset:-2px}
.y2k-menu button[aria-disabled="true"]{cursor:not-allowed}
.y2k-menu button[aria-disabled="true"] > span{opacity:.6}
.y2k-menu button svg{width:18px;height:18px;color:var(--y2k-accent-texto);flex:none}
.y2k-menu button > span{display:flex;flex-direction:column;gap:1px;min-width:0}
.y2k-menu button small{font-weight:500;font-size:11.5px;color:var(--y2k-ink-3)}
.y2k-menu button[role="menuitemradio"]::after{content:"";margin-left:auto;width:16px;height:16px;flex:none}
.y2k-menu button[role="menuitemradio"][aria-checked="true"]::after{content:"✓";color:var(--y2k-accent-texto);font-weight:700;text-align:center}
.y2k-menu button.peligro svg{color:var(--y2k-peligro)}
/* pildoras de abajo: 2D/3D (y textura del 3D) a la izquierda, "Preparar descarga" a la derecha */
.st-key-y2k_dock{position:fixed !important;z-index:45;bottom:var(--y2k-g);left:max(var(--y2k-g),var(--y2k-libre-izq));right:var(--y2k-g);
  width:auto !important;display:flex !important;flex-direction:row !important;justify-content:space-between;align-items:flex-end;gap:10px !important;
  pointer-events:none;margin:0 !important;padding:0 !important;transition:left var(--y2k-dur) var(--y2k-curva);
  animation:y2k-entra-abajo .45s var(--y2k-curva) both}
@keyframes y2k-entra-abajo{from{opacity:0;transform:translateY(14px)}}
.st-key-y2k_dock > div{pointer-events:auto;width:auto !important;flex:none !important;min-width:0}
.st-key-y2k_dock_izq,.st-key-y2k_dock_der{border-radius:999px;padding:4px !important;display:flex !important;flex-direction:row !important;
  align-items:center;gap:4px !important;flex-wrap:nowrap !important;margin:0 !important;width:auto !important}
/* "Preparar descarga" sube por encima del boton de Streamlit Community Cloud (abajo a la derecha) */
.st-key-y2k_dock_der{margin-bottom:var(--y2k-sello) !important}
/* boton "Consulta": solo en el celular */
.st-key-y2k_dock_izq [data-testid="stElementContainer"]:has(.y2k-consulta){display:none}
.y2k-consulta[aria-expanded="true"]{background:var(--y2k-lente);box-shadow:var(--y2k-lente-sombra)}
/* capa invisible sobre el mapa con la consulta abierta (celular): tocar el mapa la cierra */
.y2k-cierre-hoja{display:none}
.st-key-y2k_dock_izq > div,.st-key-y2k_dock_der > div{width:auto !important;flex:none !important}
.st-key-y2k_dock_izq .stPopover button{padding:0 12px !important}
.st-key-y2k_dock_izq .stPopover button p{font-size:13.5px !important}
.st-key-y2k_repetir_intro button{width:36px;min-width:36px;padding:0 !important}
.st-key-y2k_repetir_intro button [data-testid="stMarkdownContainer"]{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.st-key-preparar button{min-height:44px !important;padding:0 20px !important;font-size:15px !important;gap:8px}
.st-key-preparar button p{font-size:15px !important;font-weight:700 !important}
.st-key-preparar button:disabled{opacity:.55 !important;filter:saturate(.35)}
.st-key-y2k_dock_der .stButton > button[kind="primary"]{box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 10px 22px -10px var(--y2k-accent) !important}
/* ficha de la estacion seleccionada (arriba a la derecha, junto a la columna de Ajustes) */
.st-key-y2k_ficha{position:fixed !important;z-index:42;top:var(--y2k-g);right:calc(var(--y2k-g) * 2 + var(--y2k-capsula));
  width:320px !important;max-height:calc(100dvh - var(--y2k-dock-h) - var(--y2k-g) * 3);overflow:hidden;display:flex !important;
  flex-direction:column;padding:0 !important;gap:0 !important;animation:y2k-menu .25s var(--y2k-curva) both}
.st-key-y2k_ficha_cuerpo{padding:14px 16px !important;gap:8px !important}
.st-key-y2k_ficha:not(:has(.y2k-ficha-cab)){display:none !important}
.y2k-ficha-cab{display:flex;flex-direction:column;gap:2px}
.y2k-ficha-cab small{font-size:11.5px;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--y2k-ink-3)}
.y2k-ficha-cab b{font-size:15.5px;line-height:1.25;color:var(--y2k-ink)}
.y2k-ficha-cab span{font-size:12.5px;color:var(--y2k-ink-3);font-variant-numeric:tabular-nums}

/* controles de Streamlit dentro del vidrio regular */
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_inicio,.st-key-y2k_exportar) .stButton > button,
:is(.st-key-y2k_inicio,.st-key-y2k_exportar) .stDownloadButton > button{border-radius:999px !important;font-weight:600 !important;min-height:40px}
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_inicio,.st-key-y2k_exportar) .stButton > button[kind="secondary"]{background:var(--y2k-campo) !important;
  border:0 !important;box-shadow:0 0 0 1px var(--y2k-campo-borde) inset !important;color:var(--y2k-ink) !important}
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_inicio,.st-key-y2k_exportar) .stButton > button[kind="secondary"] p{color:var(--y2k-ink) !important}
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_inicio,.st-key-y2k_exportar) .stButton > button[kind="secondary"]:hover{
  box-shadow:0 0 0 1.5px var(--y2k-accent) inset !important}
.stButton > button[kind="primary"],.stDownloadButton > button[kind="primary"]{background:var(--y2k-accent) !important;border:0 !important;
  color:var(--y2k-sobre-acento) !important;box-shadow:inset 0 1px 0 rgba(255,255,255,.35),0 8px 18px -10px var(--y2k-accent) !important;
  border-radius:999px !important;font-weight:700 !important}
.stButton > button[kind="primary"] p,.stDownloadButton > button[kind="primary"] p{color:var(--y2k-sobre-acento) !important;font-weight:700 !important}
.stButton > button[kind="primary"]:hover,.stDownloadButton > button[kind="primary"]:hover{filter:brightness(1.07)}
.stButton > button:disabled,.stButton > button[kind="primary"]:disabled{opacity:.5;filter:saturate(.3);box-shadow:none !important}
.stButton > button[kind="tertiary"]{color:var(--y2k-accent-texto) !important;min-height:32px;padding:0 6px !important}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-testid="stExpander"] details{border-radius:14px !important;
  border:0 !important;background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset}
[data-testid="stExpander"] summary p{font-weight:600;color:var(--y2k-ink) !important}
[data-testid="stAlert"]{border-radius:14px}
[data-testid="stFileUploaderDropzone"]{border-radius:14px;background:var(--y2k-campo);border:1px dashed var(--y2k-campo-borde)}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-testid="stMarkdownContainer"] p{font-size:13.5px;line-height:1.5}
:is(.st-key-y2k_panel,.st-key-y2k_ficha) [data-testid="stCaptionContainer"] p{font-size:12.5px;line-height:1.45}
[data-testid="stDialog"] [role="dialog"]{border-radius:24px !important;background:var(--lg-brillo),var(--lg-denso) !important;
  box-shadow:inset 0 1px 0 var(--lg-luz),0 0 0 .5px var(--lg-filo),var(--lg-sombra) !important}

/* detalles desplegables propios: resumen breve siempre visible y el detalle al pulsar */
details.y2k-det{font-size:12px;line-height:1.45;color:var(--y2k-ink-3);margin:0}
details.y2k-det summary{cursor:pointer;list-style:none;display:flex;flex-wrap:wrap;gap:2px 8px;align-items:baseline;border-radius:6px}
details.y2k-det summary::-webkit-details-marker{display:none}
details.y2k-det summary .ver{color:var(--y2k-accent-texto);font-weight:600;text-decoration:underline;text-underline-offset:2px;white-space:nowrap}
details.y2k-det summary .ver::after{content:" ▾";display:inline-block}
details.y2k-det[open] summary .ver::after{content:" ▴"}
details.y2k-det > div{margin-top:6px;color:var(--y2k-ink-2)}
details.y2k-det > div p{margin:0 0 6px !important;font-size:12.5px !important;color:var(--y2k-ink-2) !important}
details.y2k-det b{color:var(--y2k-ink)}
.y2k-pie{margin-top:8px;padding-top:12px;font-size:12px;line-height:1.5;color:var(--y2k-ink-3);border-top:1px solid var(--y2k-line)}
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
.y2k-leyenda .pin.fuera{background:rgba(255,255,255,.35) !important;border:2px dashed #7C87A3}
.y2k-leyenda .pin.duda{border-color:#D0602F;box-shadow:0 0 0 1px #fff}
.y2k-leyenda .linea{width:18px;height:0;border-top:3px solid;flex:none}
.y2k-leyenda .nota{grid-column:1 / -1;font-size:12px;color:var(--y2k-ink-3);margin-top:2px}
.y2k-leyenda .tit{margin:0;padding:2px 14px 4px;font-size:12.5px;font-weight:600;color:var(--y2k-ink-2)}
.y2k-leyenda .rampa{height:10px;border-radius:5px;margin:2px 14px;box-shadow:0 0 0 1px var(--y2k-line) inset}
.y2k-leyenda .marcas{display:flex;justify-content:space-between;font-size:12px;color:var(--y2k-ink-3);padding:0 14px 10px;font-variant-numeric:tabular-nums}
.y2k-atrib3d{right:var(--y2k-ov-der);bottom:var(--y2k-atrib-abajo);font-size:10.5px;line-height:1.3;padding:4px 10px;border-radius:999px;color:var(--y2k-ink);
  max-width:min(460px,50vw)}
.y2k-vacio{left:var(--y2k-centro);top:45%;transform:translate(-50%,-50%);padding:14px 18px;border-radius:18px;font-size:14px;font-weight:600;
  text-align:center;color:var(--y2k-ink);max-width:min(420px,80vw)}
/* aviso para quien pidio reducir el movimiento: la intro del 3D no se reproduce sola */
.y2k-nota-mov{display:none;left:var(--y2k-centro);top:var(--y2k-g);transform:translateX(-50%);padding:9px 14px;border-radius:14px;font-size:12.5px;
  line-height:1.4;color:var(--y2k-ink);max-width:min(440px,calc(100vw - var(--y2k-libre-izq) - 140px));text-align:center}
@media (prefers-reduced-motion: reduce){.y2k-nota-mov{display:block;animation:y2k-ocultar 0s linear 14s forwards}}
@keyframes y2k-ocultar{to{visibility:hidden}}
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

/* ================= PANTALLA 3: EXPORTACION ================= */
.st-key-y2k_exportar{position:fixed !important;z-index:40;left:50%;top:50%;transform:translate(-50%,-50%);
  width:min(960px,calc(100vw - 32px)) !important;max-height:calc(100dvh - 2 * (var(--y2k-g) + var(--y2k-capsula) + 8px));overflow:hidden;
  padding:0 !important;gap:0 !important;border-radius:30px;display:flex !important;flex-direction:column;
  animation:y2k-entra-centro .5s var(--y2k-curva) both}
.st-key-y2k_exportar_cuerpo{margin:16px 4px 16px 0 !important;padding:10px 26px 8px 30px !important;gap:16px !important}
.y2k-cab-export .eyebrow{font-size:12px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--y2k-accent-texto);margin:0;
  display:flex;align-items:center;gap:8px}
.y2k-cab-export h1{font-size:clamp(23px,2.8vw,29px) !important;line-height:1.15 !important;font-weight:700 !important;letter-spacing:-.02em;
  margin:4px 0 0 !important;padding:0 !important;color:var(--y2k-ink)}
.y2k-cab-export .eyebrow .vivo{width:7px;height:7px;border-radius:50%;background:var(--y2k-accent);animation:y2k-respira 1.4s ease-in-out infinite}
.y2k-cab-export .eyebrow .hecho{width:7px;height:7px;border-radius:50%;background:var(--y2k-ok-luz)}
/* avance real: barra de vidrio con relleno luminoso */
.y2k-prog{display:flex;flex-direction:column;gap:10px}
.y2k-prog-cifras{display:flex;align-items:baseline;justify-content:space-between;gap:12px;flex-wrap:wrap}
.y2k-prog-cifras b{font-size:clamp(36px,5.2vw,48px);font-weight:700;letter-spacing:-.03em;line-height:1;font-variant-numeric:tabular-nums;color:var(--y2k-ink)}
.y2k-prog-cifras span{font-size:14.5px;font-weight:600;color:var(--y2k-ink-2);font-variant-numeric:tabular-nums}
.y2k-barra{position:relative;height:14px;border-radius:999px;background:var(--y2k-pista);overflow:hidden;
  box-shadow:inset 0 1px 3px rgba(0,0,0,.22),inset 0 0 0 1px var(--y2k-line)}
.y2k-barra i{position:absolute;left:0;top:0;bottom:0;width:var(--p);min-width:14px;border-radius:inherit;
  background:linear-gradient(90deg,var(--y2k-accent-2),var(--y2k-accent));
  box-shadow:inset 0 1px 0 rgba(255,255,255,.55),inset 0 -1px 0 rgba(0,0,0,.12),0 0 16px -2px var(--y2k-accent);transition:width .7s var(--y2k-curva)}
.y2k-barra i::after{content:"";position:absolute;inset:0;border-radius:inherit;
  background:linear-gradient(100deg,transparent 35%,rgba(255,255,255,.5) 50%,transparent 65%);background-size:220% 100%;animation:y2k-brillo 1.9s linear infinite}
.y2k-barra.fin i::after,.y2k-barra.alto i::after{display:none}
.y2k-barra.fin i{background:linear-gradient(90deg,var(--y2k-ok-luz),var(--y2k-ok))}
.y2k-barra.alto i{background:var(--y2k-line-2);box-shadow:none}
@keyframes y2k-brillo{from{background-position:160% 0}to{background-position:-60% 0}}
.y2k-prog-meta{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:13px;color:var(--y2k-ink-3);font-variant-numeric:tabular-nums}
.y2k-prog-meta b{color:var(--y2k-ink);font-weight:700}
/* recibo de la descarga */
.y2k-recibo{display:grid;grid-template-columns:max-content 1fr;gap:9px 18px;margin:0;padding:14px 16px;border-radius:18px;background:var(--y2k-campo);
  box-shadow:inset 0 0 0 1px var(--y2k-campo-borde)}
.y2k-recibo dt{font-size:11.5px;text-transform:uppercase;letter-spacing:.07em;font-weight:700;color:var(--y2k-ink-3);padding-top:2px;margin:0}
.y2k-recibo dd{margin:0;font-size:14px;color:var(--y2k-ink);font-weight:600;line-height:1.35;min-width:0;overflow-wrap:anywhere}
.y2k-recibo dd small{display:block;font-weight:500;color:var(--y2k-ink-3);font-size:12.5px}
/* contenido del ZIP: una lista ordenada, un archivo por linea */
.y2k-archivo{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:7px}
.y2k-archivo li{display:grid;grid-template-columns:18px 1fr;column-gap:8px;align-items:start;margin:0}
.y2k-archivo svg{width:17px;height:17px;color:var(--y2k-accent-texto);margin-top:1px}
.y2k-archivo b{font-weight:600;font-size:13.5px;color:var(--y2k-ink);overflow-wrap:anywhere}
.y2k-archivo small{grid-column:2;display:block;font-weight:500;font-size:12px;color:var(--y2k-ink-3);line-height:1.35}
/* resumen general de lo descargado */
.y2k-final{display:flex;flex-direction:column;gap:8px}
.y2k-final p{margin:0;font-size:14px;color:var(--y2k-ink-2)}
.y2k-final p b{color:var(--y2k-ink)}
.y2k-reparto{display:flex;height:10px;border-radius:999px;overflow:hidden;gap:2px;background:var(--y2k-pista)}
.y2k-reparto i{display:block;height:100%}
.y2k-reparto-ley{display:flex;flex-wrap:wrap;gap:4px 14px;margin:0;padding:0;list-style:none;font-size:12.5px;color:var(--y2k-ink-3)}
.y2k-reparto-ley li{display:flex;align-items:center;gap:6px;margin:0}
.y2k-reparto-ley li i{width:9px;height:9px;border-radius:50%;flex:none}
.y2k-reparto-ley b{color:var(--y2k-ink);font-variant-numeric:tabular-nums}
.y2k-legal-bloque{display:flex;flex-direction:column;gap:4px;padding-top:12px;border-top:1px solid var(--y2k-line);font-size:12.5px;line-height:1.5;color:var(--y2k-ink-3)}
.y2k-legal-bloque p{margin:0;font-size:12.5px;color:var(--y2k-ink-3)}
.y2k-legal-bloque p b{color:var(--y2k-ink-2);font-weight:600}
.st-key-y2k_exportar .stDownloadButton > button{min-height:48px !important;font-size:15px !important}
.st-key-y2k_exportar [data-testid="stColumn"] > div{gap:14px}

/* cambio de pantalla: lo de la pantalla anterior se esconde en cuanto llega la nueva (Streamlit lo quita al terminar) */
:is(__P_PARAM__,__P_EXPORT__) :is(.st-key-y2k_panel,.st-key-y2k_dock,.st-key-y2k_herr,.st-key-y2k_ficha,.st-key-y2k_abrir),
:is(__P_PARAM__,__P_EXPORT__) :is(.st-key-y2k_escenario .y2k-sobre,.st-key-y2k_visor3d){display:none !important}
:is(__P_MAPA__,__P_EXPORT__) .st-key-y2k_inicio,:is(__P_MAPA__,__P_PARAM__) .st-key-y2k_exportar{display:none !important}
"""

# Ventanas medianas: el panel se angosta un poco
CSS_MEDIO = """
:root{--y2k-panel-w:330px}
"""

# Celular en vertical: tarjetas flotantes con margen. En el mapa, la consulta es una tarjeta que se abre y se cierra
# con el boton "Consulta" de la barra de abajo (sin arrastres: el gesto se confundia con "jalar para recargar")
CSS_MOVIL = """
html{--y2k-libre-izq:0px !important;--y2k-g:10px}
.st-key-y2k_abrir,.y2k-panel-cerrar{display:none !important}
/* Parametros y Exportacion: tarjeta flotante abajo, con margen a los lados y libre la esquina del boton de Streamlit */
.st-key-y2k_inicio,.st-key-y2k_exportar{top:auto !important;bottom:calc(var(--y2k-g) + var(--y2k-sello) + env(safe-area-inset-bottom));
  left:var(--y2k-g);right:var(--y2k-g);transform:none !important;width:auto !important;border-radius:26px;
  max-height:calc(100dvh - var(--y2k-capsula) - var(--y2k-g) * 3 - var(--y2k-sello) - env(safe-area-inset-bottom));
  animation:y2k-entra-abajo .45s var(--y2k-curva) both}
.st-key-y2k_inicio_cuerpo,.st-key-y2k_exportar_cuerpo{margin:14px 3px 14px 0 !important;padding:8px 15px 6px 18px !important}
.y2k-como{gap:6px}
.y2k-como li{padding:8px 8px 9px;font-size:11.5px}
.y2k-como li span{display:none}
.y2k-como li b{font-size:12px;flex-direction:column;align-items:flex-start;gap:5px}
.st-key-y2k_exportar_cuerpo > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"],
.st-key-y2k_exportar_cuerpo > [data-testid="stHorizontalBlock"]{row-gap:14px !important}
/* Mapa: barra flotante abajo (Consulta, 2D/3D y "Preparar descarga"), encima de la esquina del boton de Streamlit */
.st-key-y2k_dock{left:var(--y2k-g) !important;right:var(--y2k-g);bottom:calc(var(--y2k-g) + var(--y2k-sello) + env(safe-area-inset-bottom));
  padding:4px !important;align-items:center;border-radius:999px;flex-wrap:nowrap !important;gap:4px !important;
  background:radial-gradient(240px 150px at var(--mx,22%) var(--my,-40%),var(--lg-especular),transparent 70%),var(--lg-brillo),var(--lg-regular);
  -webkit-backdrop-filter:var(--lg-filtro-regular);backdrop-filter:var(--lg-filtro-regular);
  box-shadow:inset 0 1px 0 var(--lg-luz),0 0 0 .5px var(--lg-filo),var(--lg-sombra);pointer-events:auto}
.st-key-y2k_dock_izq{background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:none !important;
  padding:0 !important;gap:2px !important}
.st-key-y2k_dock_der{background:transparent !important;-webkit-backdrop-filter:none !important;backdrop-filter:none !important;box-shadow:none !important;
  padding:0 !important;margin-bottom:0 !important}
.st-key-y2k_dock_der::after,.st-key-y2k_dock_izq::after{display:none}
.st-key-y2k_dock_izq [data-testid="stElementContainer"]:has(.y2k-consulta){display:block}
.st-key-y2k_dock_izq [data-testid="stButtonGroup"]{background:var(--y2k-pista);border-radius:999px;padding:2px}
.st-key-y2k_dock_izq button[role="radio"]{min-width:40px;padding:0 10px !important;min-height:34px !important}
.st-key-y2k_repetir_intro{display:none !important}
.st-key-y2k_dock_izq .stPopover button [data-testid="stMarkdownContainer"]{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
.st-key-preparar button{padding:0 12px !important;min-height:40px !important;gap:6px}
.st-key-preparar button p{font-size:14px !important}
.y2k-consulta.con-texto{padding:0 11px 0 9px;height:40px}
/* la consulta: tarjeta flotante sobre la barra, de hasta unas tres cuartas partes de la pantalla */
.st-key-y2k_panel,html[data-y2k-panel="cerrado"] .st-key-y2k_panel{top:auto !important;left:var(--y2k-g) !important;right:var(--y2k-g);
  bottom:calc(var(--y2k-dock-h) + 8px) !important;width:auto !important;height:auto !important;
  max-height:min(75dvh,calc(100dvh - var(--y2k-dock-h) - var(--y2k-capsula) - var(--y2k-g) * 2 - 14px));border-radius:24px !important;
  transform:none;opacity:1;visibility:visible;transform-origin:50% 100%;animation:none;
  transition:transform var(--y2k-dur) var(--y2k-curva),opacity .2s ease,visibility 0s}
html:not([data-y2k-hoja="abierta"]) .st-key-y2k_panel{transform:translateY(14px) scale(.98) !important;opacity:0 !important;visibility:hidden !important;
  pointer-events:none;transition:transform var(--y2k-dur) var(--y2k-curva),opacity .2s ease,visibility 0s var(--y2k-dur) !important}
.st-key-y2k_panel_cab{padding:10px 8px 0 18px !important}
.y2k-hoja-cerrar{display:inline-flex !important}
.st-key-y2k_cuerpo{padding:0 16px 16px !important}
/* con la consulta abierta se aparta lo demas (herramientas, leyenda, escala y creditos del mapa, ficha, camara 3D) */
html[data-y2k-hoja="abierta"] :is(.st-key-y2k_herr,.st-key-y2k_ficha,.y2k-leyenda,.y2k-atrib3d,.y2k-nota-mov,.y2k-aviso3d){
  opacity:0 !important;visibility:hidden !important;pointer-events:none !important;transition:opacity .15s,visibility 0s .15s}
html[data-y2k-hoja="abierta"][data-y2k-p="mapa"] .y2k-cierre-hoja{display:block;position:fixed;inset:0;z-index:39;background:transparent;
  -webkit-tap-highlight-color:transparent}
.st-key-y2k_ficha{top:var(--y2k-g) !important;left:var(--y2k-g);right:calc(var(--y2k-g) * 2 + var(--y2k-capsula)) !important;width:auto !important;
  max-height:38dvh}
.st-key-y2k_ficha_cuerpo{padding:12px 14px !important}
.y2k-menu{min-width:min(240px,calc(100vw - 90px))}
.y2k-atrib3d{font-size:10px;max-width:62vw}
.y2k-leyenda{max-width:calc(100vw - 80px)}
.y2k-vacio{top:35%}
"""
# Muy estrecho: las pildoras se compactan
CSS_ESTRECHO = """
.st-key-y2k_dock_izq button[role="radio"]{min-width:34px;padding:0 8px !important}
.y2k-consulta.con-texto{padding:0 10px 0 8px}
.st-key-preparar button{padding:0 11px !important;font-size:13.5px !important}
.st-key-preparar button p{font-size:13.5px !important}
"""
# Pantallas bajas (celular en horizontal): todo mas compacto
CSS_BAJO = """
:root{--y2k-capsula:40px;--y2k-g:8px;--y2k-panel-w:300px}
.st-key-y2k_inicio_cuerpo,.st-key-y2k_exportar_cuerpo{margin:10px 4px 10px 0 !important;padding:6px 16px 4px 20px !important;gap:10px !important}
.y2k-como{display:none}
.y2k-herr button.h,.y2k-camara button{width:32px;height:32px}
.st-key-preparar button{min-height:38px !important}
"""

# Alto contraste: superficies opacas, bordes nitidos, sin brillos ni desenfoque, foco grueso
CSS_ALTO = """
:is(__VIDRIO__){box-shadow:0 0 0 2px var(--lg-borde) !important;background:var(--lg-regular) !important}
:is(__VIDRIO__)::before,:is(__VIDRIO__)::after{display:none}
.st-key-y2k_dock_izq button[aria-checked="true"],[data-testid="stPopoverBody"] button[aria-checked="true"],.st-key-serie button[aria-checked="true"],
.y2k-herr button.h[aria-expanded="true"],.y2k-consulta[aria-expanded="true"]{background:var(--y2k-ink) !important;color:var(--y2k-bg) !important;box-shadow:none !important}
.st-key-y2k_dock_izq button[aria-checked="true"] p,[data-testid="stPopoverBody"] button[aria-checked="true"] p,
.st-key-serie button[aria-checked="true"] p{color:var(--y2k-bg) !important}
.y2k-kpi,.y2k-como li,.y2k-recibo,.y2k-boton.sec,.y2k-dialogo button,.y2k-menu,.y2k-chip,.y2k-km,
:is(.st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_inicio,.st-key-y2k_exportar) [data-testid="stExpander"] details,
.st-key-y2k_buffer .stPopover button{box-shadow:0 0 0 2px var(--y2k-line-2) inset !important}
.y2k-km{background:transparent;color:var(--y2k-ink)}
.y2k-menu{background:var(--lg-denso) !important}
.stButton > button,.stDownloadButton > button{border:2px solid var(--y2k-line-2) !important}
.stButton > button[kind="primary"],.stDownloadButton > button[kind="primary"],.y2k-boton.prim{box-shadow:none !important}
:is(button,a,input,select,textarea,summary,[role="radio"],[role="tab"],[tabindex]):focus-visible{outline:3px solid var(--y2k-foco) !important;outline-offset:3px !important}
.y2k-hint,[data-testid="stMarkdownContainer"] p.y2k-hint,[data-testid="stCaptionContainer"] p{color:var(--y2k-ink-2) !important}
a,details.y2k-det summary .ver{text-decoration:underline !important}
.st-key-y2k_escenario::after{-webkit-backdrop-filter:none;backdrop-filter:none}
.y2k-barra{box-shadow:0 0 0 2px var(--y2k-line-2) inset}
.y2k-barra i{background:var(--y2k-accent);box-shadow:none}
.y2k-aviso3d{border-width:2px !important;box-shadow:none !important}
.st-key-y2k_dock{box-shadow:0 0 0 2px var(--lg-borde) !important}
"""

# Lite: los mismos controles y datos sin desenfoque, brillos ni transiciones (variante de baja transparencia)
CSS_LITE = """
:root{--y2k-lite:1;--y2k-dur:0s;--lg-claro:var(--lg-denso);--lg-regular:var(--lg-denso);--lg-filtro-claro:none;--lg-filtro-regular:none;--lg-brillo:none;
  --lg-especular:transparent}
:is(__VIDRIO__){box-shadow:inset 0 1px 0 var(--lg-luz),0 0 0 1px var(--lg-filo),0 10px 24px -14px rgba(0,0,0,.5) !important}
[data-testid="stPopoverBody"]{-webkit-backdrop-filter:none;backdrop-filter:none}
.st-key-y2k_escenario::after{-webkit-backdrop-filter:none;backdrop-filter:none}
*,*::before,*::after{transition-duration:0s !important;animation-duration:0s !important;animation-iteration-count:1 !important}
"""

# Movimiento reducido (preferencia del sistema; independiente de Lite)
CSS_MOVIMIENTO = """
@media (prefers-reduced-motion: reduce){
  :root{--y2k-dur:0s}
  *,*::before,*::after{transition-duration:0s !important;scroll-behavior:auto !important}
  .st-key-y2k_inicio,.st-key-y2k_exportar,.st-key-y2k_panel,.st-key-y2k_dock,.st-key-y2k_ficha,.st-key-y2k_herr,.y2k-menu,.y2k-punto,
  .y2k-barra i::after,.y2k-cab-export .vivo{animation:none !important}
}
"""

# Colores forzados (Windows Alto contraste, etc.): se respetan los colores del usuario; solo se reponen los bordes
# y senales que el navegador quita junto con los fondos y las sombras.
CSS_FORZADOS = """
@media (forced-colors: active){
  :is(__VIDRIO__),.y2k-menu{border:1px solid CanvasText !important;forced-color-adjust:auto}
  :is(__VIDRIO__)::before,:is(__VIDRIO__)::after{display:none}
  .y2k-ico,.y2k-herr button.h,.y2k-camara button,.y2k-dialogo button,.y2k-chip,.y2k-km,.y2k-boton,.y2k-kpi,.y2k-menu button,.y2k-como li{
    border:1px solid ButtonText !important}
  .stButton > button,.stDownloadButton > button,.stPopover button,[data-testid="stExpander"] details,[data-testid="stFileUploaderDropzone"]{
    border:1px solid ButtonText !important}
  .st-key-y2k_dock_izq button[aria-checked="true"],[data-testid="stPopoverBody"] button[aria-checked="true"],
  .y2k-menu button[aria-checked="true"]{border:2px solid Highlight !important;outline:2px solid Highlight}
  .st-key-y2k_dock_izq button[role="radio"]{border:1px solid ButtonText !important}
  .y2k-consulta[aria-expanded="true"]{outline:2px solid Highlight}
  .y2k-leyenda .pin,.y2k-leyenda .rampa,.y2k-leyenda .linea,.y2k-reparto i,.y2k-reparto-ley i{forced-color-adjust:none}
  .y2k-punto{forced-color-adjust:none;border:1px solid CanvasText}
  /* interruptores y casillas de Streamlit: su forma es solo fondo, que el modo de colores forzados quita */
  [data-testid="stCheckbox"] label > span + div{border:1px solid ButtonText !important}
  [data-testid="stCheckbox"] label > span + div > div{forced-color-adjust:none;background:ButtonText !important}
  [data-testid="stCheckbox"][data-selected="true"] label > span + div{forced-color-adjust:none;background:Highlight !important;border-color:Highlight !important}
  [data-testid="stCheckbox"][data-selected="true"] label > span + div > div{background:HighlightText !important}
  [data-testid="stSlider"] [role="slider"]{outline:2px solid ButtonText}
  .y2k-barra{border:1px solid CanvasText}
  .y2k-barra i{forced-color-adjust:none;background:Highlight}
  :is(button,a,input,select,textarea,summary,[role="radio"],[tabindex]):focus-visible{outline:3px solid Highlight !important}
}
"""


def _vidrio(css):
    return (css.replace("__VIDRIO_CLARO__", VIDRIO_CLARO).replace("__VIDRIO_REGULAR__", VIDRIO_REGULAR)
            .replace("__VIDRIO__", VIDRIO).replace("__P_PARAM__", P_PARAM).replace("__P_MAPA__", P_MAPA)
            .replace("__P_EXPORT__", P_EXPORT))


def aplicar(tema="sistema", contraste="sistema", lite=False, sello=False):
    """Estilos de toda la pagina (st.html con solo <style> no dibuja nada). `sello`: la app corre en Streamlit
    Community Cloud, que pone su boton abajo a la derecha (fuera de la app): esa esquina queda libre."""
    css = (CSS + (":root{--y2k-sello:46px}@media " + MOVIL + "{:root{--y2k-sello:42px}}" if sello else "")
           + "@media (min-width: 761px) and (max-width: 1100px){" + CSS_MEDIO + "}"
           + "@media " + MOVIL + "{" + CSS_MOVIL + "}" + "@media (max-width: 380px){" + CSS_ESTRECHO + "}"
           + "@media " + BAJO + "{" + CSS_BAJO + "}"
           + _tokens_css(tema, contraste) + (CSS_LITE if lite else "") + CSS_MOVIMIENTO + CSS_FORZADOS)
    st.html("<style>" + _vidrio(css) + "</style>")


def tono(tema):
    """Tono vigente: el elegido o, sin eleccion, el que reporta el navegador."""
    if tema in ("claro", "oscuro"):
        return tema
    try:
        return "oscuro" if st.context.theme.type == "dark" else "claro"
    except Exception:
        return "claro"


def paleta(tema):
    """Paleta para graficas y mapas segun el tono vigente."""
    return PALETAS[tono(tema)]


# ---------------------------------------------------------------------------
# Iconos de linea (SVG en linea, heredan el color del texto)
# ---------------------------------------------------------------------------
def _svg(cuerpo, vista="0 0 24 24"):
    return (f'<svg viewBox="{vista}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" focusable="false">{cuerpo}</svg>')


ICONOS = {
    "panel": _svg('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d="M15 10l-2 2 2 2"/>'),
    "panel_abrir": _svg('<rect x="3" y="4" width="18" height="16" rx="3"/><path d="M9 4v16"/><path d="M13 10l2 2-2 2"/>'),
    "manual": _svg('<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>'),
    "dibujar": _svg('<rect x="4" y="6" width="16" height="12" rx="1.5" stroke-dasharray="3 2.4"/><circle cx="4" cy="6" r="1.6" fill="currentColor"/>'
                    '<circle cx="20" cy="18" r="1.6" fill="currentColor"/>'),
    "lapiz": _svg('<path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z"/>'),
    "area": _svg('<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"/>'
                 '<circle cx="12" cy="12" r="2.5"/>'),
    "archivo": _svg('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M12 17v-6M9.5 13.5 12 11l2.5 2.5"/>'),
    "ajustar": _svg('<rect x="5" y="5" width="14" height="14" rx="1"/><circle cx="5" cy="5" r="2" fill="currentColor"/>'
                    '<circle cx="19" cy="19" r="2" fill="currentColor"/><circle cx="19" cy="5" r="2" fill="currentColor"/>'),
    "borrar": _svg('<path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>'),
    "capas": _svg('<path d="M12 3 2 8l10 5 10-5z"/><path d="m2 13 10 5 10-5"/>'),
    "alerta": _svg('<path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/><path d="M12 9v4M12 17h.01"/>'),
    "mas": _svg('<path d="M12 5v14M5 12h14"/>'),
    "menos": _svg('<path d="M5 12h14"/>'),
    "girar_izq": _svg('<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>'),
    "girar_der": _svg('<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>'),
    "inclinar_mas": _svg('<path d="M4 18h16"/><path d="M7 14l5-9 5 9"/>'),
    "inclinar_menos": _svg('<path d="M4 18h16"/><path d="M5 14h14"/>'),
    "norte": _svg('<circle cx="12" cy="12" r="9"/><path d="M12 6l3 7h-6z" fill="currentColor" stroke="none"/><path d="M12 13v5"/>'),
    "rayo": _svg('<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>'),
    "mapa2d": _svg('<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>'),
    "consulta": _svg('<path d="M4 6h16M4 12h16M4 18h10"/>'),
    "cerrar": _svg('<path d="M6 6l12 12M18 6 6 18"/>'),
    "volver": _svg('<path d="M15 6l-6 6 6 6"/>'),
    "excel": _svg('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 12l4 5M13 12l-4 5"/>'),
    "carpeta": _svg('<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'),
    "tabla": _svg('<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M4 15h16M10 4v16"/>'),
    "cita": _svg('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/>'),
}


# ---------------------------------------------------------------------------
# Ajustes: un solo menu (tema, alto contraste, modo Lite y manual)
# ---------------------------------------------------------------------------
def _query(clave, valor, defecto):
    if valor == defecto:
        st.query_params.pop(clave, None)
    else:
        st.query_params[clave] = valor


def poner_lite(valor):
    st.session_state.lite = bool(valor)
    _query("lite", "1" if valor else "0", "0")


def _cambiar_lite(clave):
    poner_lite(st.session_state.get(clave, False))


def _cambiar_tema():
    st.session_state.tema = "oscuro" if st.session_state.get("pref_tono") == "Oscuro" else "claro"
    _query("tema", st.session_state.tema, "sistema")


def _cambiar_contraste():
    st.session_state.contraste = "alto" if st.session_state.get("pref_alto") else "sistema"
    _query("contraste", st.session_state.contraste, "sistema")


def toggle_lite(clave, etiqueta="Modo Lite", ayuda=None, disabled=False):
    """Interruptor del modo Lite. Hay dos (Ajustes y la tarjeta de Parametros) y los dos leen y escriben ss.lite."""
    ss = st.session_state
    ss[clave] = bool(ss.get("lite", False))
    st.toggle(etiqueta, key=clave, on_change=_cambiar_lite, args=(clave,), disabled=disabled,
              help=ayuda or ("Menos efectos visuales (sin desenfoque ni animaciones) y un 3D más liviano. "
                             "Los datos y las funciones son los mismos."))


def ajustes(bloqueado=False):
    """Menu de Ajustes (arriba a la derecha). `bloqueado` lo desactiva mientras corre una descarga: cambiar algo
    recargaria la pagina y la detendria."""
    ss = st.session_state
    with st.container(key="y2k_ajustes", horizontal=True, gap=None, wrap=False, vertical_alignment="center"):
        if ss.get("lite"):
            md(f'<span class="y2k-lite-chip" title="Modo Lite activado">{ICONOS["rayo"]}Lite</span>')
        with st.popover("Ajustes", icon=":material/contrast:", disabled=bloqueado,
                        help="Durante la descarga los ajustes quedan bloqueados" if bloqueado else None):
            md('<p class="y2k-menu-tit">Apariencia</p>')
            ss.pref_tono = "Oscuro" if tono(ss.get("tema", "sistema")) == "oscuro" else "Claro"
            st.segmented_control("Tema", ["Claro", "Oscuro"], key="pref_tono", on_change=_cambiar_tema, required=True,
                                 width="stretch")
            ss.pref_alto = ss.get("contraste") == "alto"
            st.toggle("Alto contraste", key="pref_alto", on_change=_cambiar_contraste,
                      help="Superficies opacas, bordes nítidos y foco más grueso. Si tu equipo pide más contraste, "
                           "se aplica solo.")
            md('<p class="y2k-menu-tit">Rendimiento</p>')
            toggle_lite("lite_menu")
            md(f'<a class="y2k-enlace" href="app/static/manual.html" target="_blank" rel="noopener">{ICONOS["manual"]}'
               'Manual de usuario<span class="y2k-vh"> (se abre en otra pestaña)</span></a>')
            st.markdown('<p class="y2k-hint">Las animaciones respetan la opción de reducir el movimiento de tu equipo.</p>',
                        unsafe_allow_html=True)


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


def guiones_globales(pantalla):
    """Guiones invisibles de toda la pagina (interfaz del navegador y tema de Streamlit) y la marca de la pantalla
    actual, que usa el CSS para mostrar u ocultar lo de cada una."""
    with st.container(key="y2k_guiones"):
        md(f'<span class="y2k-pantalla" data-p="{pantalla}" hidden></span>')
        instalar_ui()
        quiero = {"claro": "Light", "oscuro": "Dark"}.get(st.session_state.get("tema", "sistema"), "System")
        components.html(_SINCRONIZAR_TEMA.replace("__TEMA__", quiero), height=0)


# ---------------------------------------------------------------------------
# Interfaz del lado del navegador (se instala una vez en la pagina principal):
#   - panel (escritorio) y tarjeta de la consulta (celular) sin recargar: atributos data-* en <html>
#   - menus de la capsula de herramientas (dibujo y capas) que manejan el mapa de Leaflet
#   - reparto del espacio: mueve las esquinas de Leaflet y las piezas sobre el mapa para que nada quede tapado
#   - vidrio de los controles de Leaflet (dentro de su iframe) y textos de Leaflet.draw en espanol
#   - "Seleccionar area en el mapa" espera a que el mapa haya cargado
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
  var G = 10;

  // ---------- panel (escritorio) y tarjeta de la consulta (celular) ----------
  raiz.setAttribute("data-y2k-panel", leer("panel") === "cerrado" ? "cerrado" : "abierto");
  function estadoPanel() { return raiz.getAttribute("data-y2k-panel") || "abierto"; }
  function ponerPanel(v) { raiz.setAttribute("data-y2k-panel", v); guardar("panel", v); sincronizar(); distribuir(); setTimeout(distribuir, 380); }
  // en el celular la consulta arranca cerrada: se abre y se cierra con el boton "Consulta" (o tocando el mapa)
  function hojaAbierta() { return raiz.getAttribute("data-y2k-hoja") === "abierta"; }
  function ponerHoja(abierta) {
    raiz.setAttribute("data-y2k-hoja", abierta ? "abierta" : "cerrada");
    marcarIframe(); sincronizar(); distribuir(); setTimeout(distribuir, 380);
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
    var abierto = estadoPanel() === "abierto", p = pantalla();
    if (p && raiz.getAttribute("data-y2k-p") !== p) {
      raiz.setAttribute("data-y2k-p", p);
      if (p !== "mapa" && hojaAbierta()) raiz.setAttribute("data-y2k-hoja", "cerrada");   // al volver al mapa, cerrada
    }
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
    d.querySelectorAll("details.y2k-leyenda").forEach(function (det) {
      if (det.__y2kLey) return;
      det.__y2kLey = true;
      var pref = leer("leyenda"), abierta = pref ? pref === "abierta" : !esMovil() && w.innerHeight > 560;
      if (det.open !== abierta) det.open = abierta;
      det.addEventListener("toggle", function () { guardar("leyenda", det.open ? "abierta" : "cerrada"); setTimeout(distribuir, 30); });
    });
    traducirCargador();
    estadoArea();
    estadoCapas();
    esperaMapa();
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
  function esperaMapa() {
    var listo = mapaListo();
    d.querySelectorAll(".st-key-ir_mapa button").forEach(function (b) {
      var v = b.disabled ? null : (listo ? "false" : "true");
      if (v && b.getAttribute("aria-disabled") !== v) b.setAttribute("aria-disabled", v);
    });
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
    "[data-y2k-subir],[data-y2k-editar],[data-y2k-borrar],[data-y2k-capa],[data-y2k-zoom],[data-y2k-menu],[data-y2k-2d],[data-y2k-ver],[data-y2k-pulsar]";
  function alClic(ev) {
    var t = ev.target && ev.target.closest ? ev.target : null;
    // el boton principal de Parametros no responde hasta que el mapa esta listo
    var cta = t && t.closest(".st-key-ir_mapa button");
    if (cta && !mapaListo()) { ev.preventDefault(); ev.stopPropagation(); return; }
    // con la consulta abierta (celular), tocar el mapa la cierra
    if (t && t.closest(".y2k-cierre-hoja")) { ev.preventDefault(); ponerHoja(false); return; }
    var b = t ? t.closest(SELECTORES) : null;
    if (!t || !t.closest(".y2k-grupo")) cerrarMenus(null);
    if (!b) return;
    if (b.getAttribute("aria-disabled") === "true" && !b.hasAttribute("data-y2k-area")) return;
    if (b.closest(".y2k-menu")) cerrarMenus(null);
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
    else if (b.hasAttribute("data-y2k-borrar")) pulsarOculto("y2k_borrar");
    else if (b.hasAttribute("data-y2k-capa")) ponerCapa(b.getAttribute("data-y2k-capa"));
    else if (b.hasAttribute("data-y2k-zoom")) zoom(b.getAttribute("data-y2k-zoom"));
    else if (b.hasAttribute("data-y2k-2d")) pulsarOculto("y2k_pasar2d");
    else if (b.hasAttribute("data-y2k-ver")) abrirPanel();
  }
  d.addEventListener("click", alClic, true);

  function alMover(ev) { especular(ev); }
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
  var ultimo = "";
  function distribuir() {
    var W = w.innerWidth, H = w.innerHeight, movil = esMovil();
    var ajustes = caja(".st-key-y2k_ajustes"), herr = caja(".st-key-y2k_herr"), abrir = caja(".st-key-y2k_abrir");
    var ficha = caja(".st-key-y2k_ficha"), dock = caja(".st-key-y2k_dock"), panel = caja(".st-key-y2k_panel");
    var pIzq = caja(".st-key-y2k_dock_izq"), pDer = caja(".st-key-y2k_dock_der");
    var col = [ajustes, herr].filter(Boolean);
    var izq = G, der = col.length ? W - Math.min.apply(null, col.map(function (r) { return r.left; })) + G : G;
    var arriba = abrir ? abrir.bottom + G : G, abajo = G;
    if (!movil && estadoPanel() === "abierto" && panel) izq = panel.right + G;
    if (dock) raiz.style.setProperty("--y2k-dock-h", Math.round(movil ? H - dock.top : H - dock.top + G) + "px");
    if (movil) {
      abajo = H - Math.min(panel ? panel.top : H, dock ? dock.top : H) + G;
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
    var ovAbajo = Math.max(abajo, sobreDock(izq, W - der));
    var clave = [W, H, arriba, izq, der, ovAbajo, leyAbajo, atribAbajo].join("|");
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
    }
    // esquinas de Leaflet (dentro del iframe; sus controles ya traen 10 px de margen). La barra de dibujo (oculta)
    // queda donde esta la capsula de herramientas, y sus acciones ("Guardar", "Cancelar") aparecen a su izquierda
    if (doc) {
      var brAbajo = sobreDock(W - G - br.w, W - G);
      var v = {"--tl-top": arriba, "--tl-izq": izq, "--tr-top": herr ? herr.top : G, "--tr-der": G,
               "--bl-abajo": blAbajo, "--bl-izq": izq, "--br-abajo": brAbajo, "--br-der": G,
               "--acc-top": (herr ? herr.top : G) + 10, "--acc-der": der + 10};
      var claveIf = JSON.stringify(v);
      if (doc.__y2kClave !== claveIf) {
        doc.__y2kClave = claveIf;
        for (var k in v) doc.documentElement.style.setProperty(k, Math.max(0, Math.round(v[k] - 10)) + "px");
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
    cl.toggle("y2k-hoja-abierta", esMovil() && hojaAbierta() && pantalla() === "mapa");
    cl.toggle("y2k-lite", esLite()); cl.toggle("y2k-oscuro", css("--y2k-tono") === "oscuro"); cl.toggle("y2k-alto", css("--y2k-alto") === "1");
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
  // Herramientas: dibujar, ajustar las esquinas, capas y zoom (manejan los controles ocultos de Leaflet)
  function dibujarRectangulo() {
    var doc = docMapa(), a = doc && doc.querySelector(".leaflet-draw-draw-rectangle");
    if (!a) return;
    if (esMovil()) ponerHoja(false);
    a.click();
    try { marco2d().focus(); } catch (e) {}
  }
  function editarArea() {
    var doc = docMapa(), a = doc && doc.querySelector(".leaflet-draw-edit-edit");
    if (!a) return;
    if (esMovil()) ponerHoja(false);
    a.click();
    try { marco2d().focus(); } catch (e) {}
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
  // d) Mapa 2D: teselas que fallan una y otra vez (solo en la pantalla del mapa)
  var ultimoAviso2d = -1e9;
  function revisar2d() {
    var win = winMapa(), map = win && win.map;
    if (pantalla() !== "mapa" || !map || !map.__y2kTeselas || d.getElementById("y2k_dlg_red2d")) return;
    var ahora = w.performance.now(), r = map.__y2kTeselas.lista.filter(function (x) { return ahora - x.t < 20000; });
    var malos = r.filter(function (x) { return !x.ok; }), buenos = r.length - malos.length;
    if (malos.length < 8 || buenos > 0 || ahora - ultimoAviso2d < 45000) return;
    ultimoAviso2d = ahora;
    var capa = malos[malos.length - 1].capa, nombre = map.__y2kBase || "Satélite";
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
  sincronizar(); distribuir();

  w.__y2kUI = {
    v: V, camara: camara, buscarDeck: buscarDeck, esLite: esLite, distribuir: distribuir,
    parar: function () {
      vivo = false; ciclos.forEach(clearInterval); obs.disconnect();
      d.removeEventListener("click", alClic, true); d.removeEventListener("pointermove", alMover, true);
      d.removeEventListener("keydown", alTecla, true);
    }
  };
})();
"""


def instalar_ui():
    """Inyecta el guion de la interfaz en la pagina principal (sobrevive a las recargas de Streamlit)."""
    codigo = (_UI.replace("__V__", "31").replace("__ICONO_ALERTA__", json.dumps(ICONOS["alerta"]))
              .replace("__MOVIL__", json.dumps(MOVIL)).replace("__VIDRIO__", json.dumps(VIDRIO)))
    cuerpo = ("(function(){var w=window.parent;var s=w.document.createElement('script');"
              f"s.textContent={json.dumps(codigo)};w.document.head.appendChild(s);s.remove();}})();")
    components.html("<script>" + cuerpo.replace("</", "<\\/") + "</script>", height=0)


# ---------------------------------------------------------------------------
# Piezas de la pantalla 1 (Parametros)
# ---------------------------------------------------------------------------
def cabecera_inicio():
    md('<header class="y2k-cab-inicio"><p class="eyebrow">IDEAM</p>'
       '<h1>Consulta y descarga de datos hidrometeorológicos</h1></header>')


def etiqueta(texto, punto=None, opcional=False):
    """Etiqueta visible de un campo (la del widget queda oculta pero accesible). `punto`: estado de la lista de
    variables del IDEAM ("cargando", "listo" o "error"): un punto pequeno que se enciende cuando esta lista. Es la
    unica senal de la carga (sin textos)."""
    titulos = {"cargando": "Lista de variables del IDEAM: pendiente", "listo": "Lista de variables del IDEAM: disponible",
               "error": "Lista de variables del IDEAM: no disponible"}
    pt = (f'<span class="y2k-punto" data-estado="{punto}" role="img" aria-label="{titulos[punto]}"></span>') if punto else ""
    md(f'<p class="y2k-etq"><span aria-hidden="true">{texto}</span>'
       f'{"<span class=opc aria-hidden=true>· opcional</span>" if opcional else ""}{pt}</p>')


def como_funciona():
    """Pasos de la consulta (el actual resaltado). En el celular solo los titulos."""
    md('<ol class="y2k-como" aria-label="Pasos de la consulta">'
       '<li aria-current="step"><b>Consulta</b><span>Serie, variable y periodo.</span></li>'
       '<li><b>Área y estaciones</b><span>Delimitación de la zona y revisión de la cobertura de cada estación.</span></li>'
       '<li><b>Descarga</b><span>Un Excel por estación, con resumen y cita de la fuente.</span></li></ol>')


def pie_inicio(texto_legal):
    md('<footer class="y2k-pie-inicio">'
       f'<details class="y2k-det"><summary><span>Datos del IDEAM: uso personal y no comercial; cita la fuente.</span>'
       f'<span class="ver">Ver condiciones</span></summary><div><p>{texto_legal}</p></div></details>'
       '<p>Herramienta independiente, no oficial del IDEAM · '
       '<a href="app/static/manual.html" target="_blank" rel="noopener">Manual de usuario</a></p></footer>')


# ---------------------------------------------------------------------------
# Piezas de la pantalla 2 (Mapa)
# ---------------------------------------------------------------------------
def cabecera_panel():
    """Titulo del panel de la consulta y su boton: plegar (escritorio) o cerrar la tarjeta (celular)."""
    md('<div class="y2k-panel-cab" id="y2k-panel"><p class="t" role="heading" aria-level="1">Consulta</p><div>'
       f'<button type="button" class="y2k-ico y2k-panel-cerrar" data-y2k-panel-btn aria-expanded="true" aria-label="Ocultar la consulta" '
       f'title="Ocultar la consulta">{ICONOS["panel"]}</button>'
       f'<button type="button" class="y2k-ico y2k-hoja-cerrar" data-y2k-hoja-cerrar aria-label="Cerrar la consulta" '
       f'title="Cerrar">{ICONOS["cerrar"]}</button></div></div>')


def boton_consulta():
    """Boton "Consulta" de la barra de abajo (solo en el celular): abre y cierra la tarjeta de la consulta."""
    md(f'<button type="button" class="y2k-ico con-texto y2k-consulta" data-y2k-consulta aria-expanded="false" '
       f'aria-controls="y2k-panel">{ICONOS["consulta"]}Consulta</button>')


def boton_abrir_panel():
    """Boton para volver a mostrar el panel cuando esta plegado (escritorio; va en el contenedor y2k_abrir)."""
    md(f'<button type="button" class="y2k-ico con-texto" data-y2k-panel-btn aria-expanded="false" aria-label="Mostrar la consulta">'
       f'{ICONOS["panel_abrir"]}Consulta</button>')


def seccion(titulo, valor="", capsula=None, chip=None):
    """Titulo de una seccion del panel y, a la derecha, un dato: `valor` (texto tenue), `capsula` (cifra destacada,
    como el area en km²) o `chip` = (texto, ayuda): la variable consultada, que al pulsarla vuelve a Parametros."""
    extra = ""
    if capsula:
        extra = f'<span class="y2k-km">{ICONOS["area"]}{escape(capsula)}</span>'
    elif chip:
        texto, ayuda = chip
        extra = (f'<button type="button" class="y2k-chip" data-y2k-pulsar="chip_param" title="{escape(ayuda)}" '
                 f'aria-label="Variable: {escape(texto)}. Cambiar la variable o el periodo">{ICONOS["volver"]}'
                 f'<span>{escape(texto)}</span></button>')
    elif valor:
        extra = f'<span class="valor">{escape(valor)}</span>'
    md(f'<div class="y2k-sec"><p class="t" role="heading" aria-level="2">{titulo}</p>{extra}</div>')


def acciones_area(hay_cuenca, vista="2D"):
    """Formas de marcar o cambiar el area (botones que maneja el guion de la interfaz, sin recargar)."""
    if vista == "3D":
        md('<p class="y2k-hint">Para cambiar el área, vuelve a la vista 2D.</p>'
           f'<div class="y2k-acciones"><button type="button" class="y2k-boton sec" data-y2k-2d>{ICONOS["mapa2d"]}Ver en 2D</button></div>')
        return
    if not hay_cuenca:
        return   # dibujar o subir el area se hace desde la capsula de herramientas (lapiz), sin repetirlo aqui
    md('<div class="y2k-acciones fichas">'
       f'<button type="button" class="y2k-boton sec" data-y2k-dibujar title="Dibujar otro rectángulo">{ICONOS["dibujar"]}Redibujar</button>'
       f'<button type="button" class="y2k-boton sec" data-y2k-editar title="Ajustar las esquinas">{ICONOS["ajustar"]}Ajustar</button>'
       f'<button type="button" class="y2k-boton sec peligro" data-y2k-borrar title="Borrar el área">{ICONOS["borrar"]}Borrar</button>'
       '</div>')


def kpis(items):
    """Tres cifras del tablero de calidad: (valor, etiqueta, subtitulo, ayuda)."""
    html = "".join(
        f'<div class="y2k-kpi" title="{escape(ayuda)}"><div class="v">{escape(str(valor))}</div>'
        f'<div class="l">{escape(etiqueta_)}</div>{f"<div class=s>{escape(sub)}</div>" if sub else ""}</div>'
        for valor, etiqueta_, sub, ayuda in items)
    md(f'<div class="y2k-kpis">{html}</div>')


def herramientas_2d(hay_cuenca):
    """Capsula de herramientas del mapa 2D (va en el contenedor y2k_herr): menu de dibujo, menu de capas y zoom."""
    extra = (f'<hr><button type="button" role="menuitem" data-y2k-editar>{ICONOS["ajustar"]}<span>Ajustar las esquinas'
             '<small>Arrastra los vértices y pulsa «Guardar»</small></span></button>'
             f'<button type="button" role="menuitem" class="peligro" data-y2k-borrar>{ICONOS["borrar"]}<span>Borrar el área</span></button>'
             ) if hay_cuenca else ""
    capas = "".join(f'<button type="button" role="menuitemradio" aria-checked="{"true" if n == "Satélite" else "false"}" '
                    f'data-y2k-capa="{n}"><span>{n}</span></button>'
                    for n in ("Satélite", "Relieve", "Calles", "Satélite de noche"))
    md('<div class="y2k-herr" role="toolbar" aria-orientation="vertical" aria-label="Herramientas del mapa">'
       '<div class="y2k-grupo">'
       f'<button type="button" class="h" data-y2k-menu="dibujo" aria-haspopup="menu" aria-expanded="false" '
       f'aria-label="Dibujo del área" title="Dibujo del área">{ICONOS["lapiz"]}</button>'
       '<div class="y2k-menu" role="menu" data-y2k-menu-de="dibujo" aria-label="Dibujo del área" hidden>'
       '<p class="tit" aria-hidden="true">Área de estudio</p>'
       f'<button type="button" role="menuitem" data-y2k-dibujar>{ICONOS["dibujar"]}<span>'
       f'{"Dibujar otro rectángulo" if hay_cuenca else "Dibujar un rectángulo"}<small>Haz clic y arrastra sobre el mapa</small></span></button>'
       f'<button type="button" role="menuitem" data-y2k-area aria-disabled="true">{ICONOS["area"]}<span>Usar el área visible'
       '<small>Primero acércate a tu zona</small></span></button>'
       f'<button type="button" role="menuitem" data-y2k-subir>{ICONOS["archivo"]}<span>Subir un archivo'
       '<small>SHP, GeoJSON, KML, KMZ o GPKG</small></span></button>'
       f'{extra}</div></div>'
       '<div class="y2k-grupo">'
       f'<button type="button" class="h" data-y2k-menu="capas" aria-haspopup="menu" aria-expanded="false" '
       f'aria-label="Mapa base" title="Mapa base">{ICONOS["capas"]}</button>'
       '<div class="y2k-menu" role="menu" data-y2k-menu-de="capas" aria-label="Mapa base" hidden>'
       f'<p class="tit" aria-hidden="true">Mapa base</p>{capas}</div></div>'
       '<hr>'
       f'<button type="button" class="h" data-y2k-zoom="mas" aria-label="Acercar" title="Acercar">{ICONOS["mas"]}</button>'
       f'<button type="button" class="h" data-y2k-zoom="menos" aria-label="Alejar" title="Alejar">{ICONOS["menos"]}</button>'
       '</div>')


def controles_camara():
    """Botones de camara del 3D (en la capsula de herramientas, y2k_herr): alternativa a arrastrar, girar e inclinar."""
    b = [("acercar", "mas", "Acercar"), ("alejar", "menos", "Alejar"), None,
         ("izq", "girar_izq", "Girar a la izquierda"), ("der", "girar_der", "Girar a la derecha"), None,
         ("subir", "inclinar_mas", "Inclinar más"), ("bajar", "inclinar_menos", "Inclinar menos"),
         ("norte", "norte", "Orientar al norte")]
    html = "".join("<hr>" if x is None else
                   f'<button type="button" data-y2k-cam="{x[0]}" aria-label="{x[2]}" title="{x[2]}">{ICONOS[x[1]]}</button>'
                   for x in b)
    md(f'<div class="y2k-herr y2k-camara" role="group" aria-label="Cámara 3D">{html}'
       '<span class="y2k-vh y2k-camara-estado" aria-live="polite"></span></div>')


def leyenda_estaciones(colores, en3d=False, hay_excluidas=False):
    """Leyenda compacta de los pines sobre el mapa (color, forma y texto; nunca solo color)."""
    filas = "".join(f'<li><span class="pin" style="background:{c}"></span>{n}</li>' for n, c in colores)
    filas += '<li><span class="pin hueco"></span>Sin serie</li>'
    if hay_excluidas:
        filas += '<li><span class="pin fuera"></span>Excluida</li>'
    filas += '<li><span class="pin duda" style="background:#9AA6BC"></span>Altitud dudosa</li>'
    filas += ('<li><span class="linea" style="border-color:#35F0FF"></span>Área</li>'
              '<li><span class="linea" style="border-color:#FF7A1A;border-top-style:dashed"></span>Buffer</li>'
              '<li class="nota">Relieve exagerado ×2 · Ctrl + arrastrar gira e inclina</li>') if en3d else (
              '<li><span class="linea" style="border-color:#1C6FD8"></span>Área</li>'
              '<li><span class="linea" style="border-color:#FAB219;border-top-style:dashed"></span>Buffer</li>')
    md(f'<details class="y2k-sobre lg-regular y2k-leyenda" open><summary>Leyenda</summary><ul>{filas}</ul></details>')


def leyenda_altura(html):
    """Leyenda de la textura "Altura" del 3D (la escala la arma terreno.leyenda_altura)."""
    md(f'<details class="y2k-sobre lg-regular y2k-leyenda" open><summary>Altitud</summary>{html}'
       '<p class="tit">Relieve exagerado ×2 · Ctrl + arrastrar gira e inclina</p></details>')


def sobre_mapa(html, clase, material="lg-regular"):
    md(f'<div class="y2k-sobre {material} {clase}">{html}</div>')


def detalles(resumen, cuerpo, ver="Ver detalles"):
    """Resumen breve siempre visible y el detalle desplegable (<details>, accesible con teclado)."""
    md(f'<details class="y2k-det"><summary><span>{resumen}</span><span class="ver">{ver}</span></summary>'
       f'<div>{cuerpo}</div></details>')


def pie():
    """Fuente de los datos, manual y creditos de los mapas (al final del panel)."""
    f = FUENTE
    md('<footer class="y2k-pie">'
       f'<p>Datos: <b>{f["nombre"]}</b> · <a href="{f["url"]}" target="_blank" rel="noopener">Instituto de Hidrología, '
       'Meteorología y Estudios Ambientales</a></p>'
       '<p>Uso personal, privado y no comercial; cita la fuente. Herramienta independiente, no oficial del IDEAM.</p>'
       f'<p><a href="app/static/manual.html" target="_blank" rel="noopener">Manual de usuario</a> · versión {f["version"]}</p>'
       f'<details class="y2k-det"><summary><span class="ver">Fuentes y créditos de los mapas</span></summary>'
       f'<div><p>{CREDITOS_MAPAS}</p></div></details>'
       '</footer>')


# ---------------------------------------------------------------------------
# Piezas de la pantalla 3 (Exportacion)
# ---------------------------------------------------------------------------
def cabecera_exportar(titulo, estado="vivo"):
    """`estado`: "vivo" (descargando), "hecho" o "alto" (detenida o con error)."""
    punto = {"vivo": '<span class="vivo" aria-hidden="true"></span>', "hecho": '<span class="hecho" aria-hidden="true"></span>'}.get(estado, "")
    md(f'<header class="y2k-cab-export"><p class="eyebrow">{punto}Exportación</p><h1>{titulo}</h1></header>')


def progreso(fraccion, principal, meta, estado="vivo"):
    """HTML del avance real de la descarga: porcentaje, texto principal (tiempo que falta o total) y una linea de
    cifras. `estado`: "vivo", "fin" o "alto"."""
    pct = round(max(0.0, min(1.0, fraccion)) * 100)
    clase = {"fin": " fin", "alto": " alto"}.get(estado, "")
    return (f'<div class="y2k-md"><div class="y2k-prog">'
            f'<div class="y2k-prog-cifras"><b>{pct} %</b><span>{principal}</span></div>'
            f'<div class="y2k-barra{clase}" role="progressbar" aria-label="Avance de la descarga" aria-valuemin="0" '
            f'aria-valuemax="100" aria-valuenow="{pct}" aria-valuetext="{pct} %, {escape(principal)}"><i style="--p:{pct}%"></i></div>'
            f'<div class="y2k-prog-meta">{meta}</div></div></div>')


def recibo(filas):
    """Recibo de la descarga: [(etiqueta, valor, detalle)]. Si `valor` es una lista de (nombre, icono, detalle), se
    muestra como una lista ordenada (por ejemplo, los archivos que trae el ZIP)."""
    def dd(v, s):
        if isinstance(v, list):
            items = "".join(f'<li>{ICONOS.get(i, "")}<b>{escape(n)}</b>{f"<small>{escape(x)}</small>" if x else ""}</li>'
                            for n, i, x in v)
            return f'<ul class="y2k-archivo">{items}</ul>'
        return escape(v) + (f"<small>{escape(s)}</small>" if s else "")
    html = "".join(f'<dt>{escape(e)}</dt><dd>{dd(v, s)}</dd>' for e, v, s in filas)
    md(f'<dl class="y2k-recibo" aria-label="Recibo de la descarga">{html}</dl>')


def resumen_final(texto, reparto):
    """Resumen general de lo descargado: una frase y el reparto por clase de cobertura [(nombre, n, color)]."""
    total = sum(n for _, n, _ in reparto) or 1
    barras = "".join(f'<i style="width:{n / total * 100:.2f}%;background:{c}" title="{escape(nm)}: {n}"></i>'
                     for nm, n, c in reparto if n)
    ley = "".join(f'<li><i style="background:{c}"></i>{escape(nm)} <b>{n}</b></li>' for nm, n, c in reparto if n)
    md(f'<div class="y2k-final"><p>{texto}</p>'
       + (f'<div class="y2k-reparto" aria-hidden="true">{barras}</div>'
          f'<ul class="y2k-reparto-ley" aria-label="Estaciones guardadas por cobertura">{ley}</ul>' if ley else "")
       + '</div>')


def legal_exportar(texto_legal):
    md('<div class="y2k-legal-bloque">'
       '<p>Datos del IDEAM: uso personal y no comercial; cita la fuente (el ZIP incluye CITACION.txt).</p>'
       f'<details class="y2k-det"><summary><span class="ver">Ver condiciones completas</span></summary>'
       f'<div><p>{texto_legal}</p></div></details></div>')
