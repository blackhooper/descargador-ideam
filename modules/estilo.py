import json
from html import escape
from pathlib import Path

import streamlit as st

from modules import acceso, guion, idioma
from modules.idioma import tr

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
# Arriba a la derecha, en todas: el boton de idioma (espanol o ingles) y un
# unico menu de Ajustes (tema, alto contraste, modo Lite y manual).
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

RECURSOS = Path(__file__).with_name("recursos")


def _recurso(nombre):
    """Texto de un archivo de `modules/recursos/` (las hojas de estilo y los guiones del navegador). Viven aparte
    para editarlos como CSS y JavaScript de verdad; aqui solo se leen, una vez, al arrancar."""
    return (RECURSOS / nombre).read_text(encoding="utf-8")


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
ATRIB_ESRI_NOMBRES = "Nombres: Esri, HERE, Garmin, OpenStreetMap"
ATRIB_NASA = "NASA EOSDIS GIBS"
ATRIB_RELIEVE_3D = ("Relieve 3D: modelo de elevación Terrarium (Mapzen, AWS Open Data), construido con datos SRTM y "
                    "GMTED2010, cortesía del U.S. Geological Survey, entre otras fuentes")
ATRIB_RELIEVE_3D_CORTO = "Relieve: Terrarium (Mapzen · AWS · SRTM/USGS) · Imagen: Esri"
CREDITOS_MAPAS = (
    "<b>Datos:</b> IDEAM · DHIME. "
    "<b>Mapas base:</b> Satélite, Satélite con nombres y Relieve, Esri (Maxar, Earthstar Geographics, HERE, Garmin, "
    "FAO, NOAA, USGS, OpenStreetMap y la comunidad de usuarios de GIS); Calles, © colaboradores de OpenStreetMap; Satélite de noche, NASA EOSDIS GIBS "
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
        # el 3D usa el cielo y la neblina oscuros tambien en el tema claro (se ven mejor sobre el relieve)
        "y2k-mapa-fondo": "#C9D6E4", "y2k-cielo": "linear-gradient(180deg,#0B1428 0%,#1C2D4F 38%,#1C2D4F 100%)",
        "y2k-niebla": "#1C2D4F",
        # boton principal: vidrio liquido azul (tinte, brillo superior, caustica abajo y canto de luz)
        "y2k-boton-tinte": "rgba(6,58,172,.92)",
        "y2k-boton-brillo": "linear-gradient(180deg,rgba(255,255,255,.38) 0%,rgba(255,255,255,.07) 40%,rgba(255,255,255,0) 50%,rgba(255,255,255,.05) 100%)",
        "y2k-boton-caustica": "radial-gradient(120% 70% at 50% 130%,rgba(140,200,255,.38),transparent 60%)",
        "y2k-boton-canto": "inset 0 1px 0 rgba(255,255,255,.62),inset 0 -1px 0 rgba(2,24,80,.40),inset 0 0 0 1px rgba(255,255,255,.20)",
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
        "y2k-mapa-fondo": "#11161F", "y2k-cielo": "linear-gradient(180deg,#0B1428 0%,#1C2D4F 38%,#1C2D4F 100%)",
        "y2k-niebla": "#1C2D4F",
        "y2k-boton-tinte": "rgba(125,182,255,.88)",
        "y2k-boton-brillo": "linear-gradient(180deg,rgba(255,255,255,.50) 0%,rgba(255,255,255,.14) 44%,rgba(255,255,255,0) 54%,rgba(255,255,255,.06) 100%)",
        "y2k-boton-caustica": "radial-gradient(120% 70% at 50% 128%,rgba(255,255,255,.40),transparent 62%)",
        "y2k-boton-canto": "inset 0 1px 0 rgba(255,255,255,.75),inset 0 -1px 0 rgba(0,20,60,.30),inset 0 0 0 1px rgba(255,255,255,.28)",
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
        "y2k-boton-tinte": "#0037A6", "y2k-boton-brillo": "none", "y2k-boton-caustica": "none", "y2k-boton-canto": "0 0 #0000",
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
        "y2k-boton-tinte": "#9CCBFF", "y2k-boton-brillo": "none", "y2k-boton-caustica": "none", "y2k-boton-canto": "0 0 #0000",
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
VIDRIO_CLARO = (".st-key-y2k_ajustes,.st-key-y2k_acceso_idioma,.st-key-y2k_herr,.st-key-y2k_abrir,.st-key-y2k_filtro,.st-key-y2k_dock_izq,"
                ".lg-claro")
VIDRIO_REGULAR = ".st-key-y2k_panel,.st-key-y2k_ficha,.st-key-y2k_inicio,.st-key-y2k_exportar,.st-key-y2k_acceso,.lg-regular"
VIDRIO = VIDRIO_CLARO + "," + VIDRIO_REGULAR

CSS = _recurso("base.css")

# Ventanas medianas: el panel se angosta un poco
CSS_MEDIO = _recurso("medio.css")

# Celular en vertical: tarjetas flotantes con margen. En el mapa, la consulta es una tarjeta que se abre y se cierra
# con el boton "Consulta" de la barra de abajo (sin arrastres: el gesto se confundia con "jalar para recargar")
CSS_MOVIL = _recurso("movil.css")
# Celular en Streamlit Community Cloud: la franja de abajo (junto a su boton) lleva el credito del relieve 3D
CSS_SELLO_MOVIL = _recurso("sello_movil.css")
# Muy estrecho: las pildoras se compactan
CSS_ESTRECHO = _recurso("estrecho.css")
# Barra angosta: "Preparar descarga" sin la flecha (asi cabe sin cortar el texto)
CSS_ANGOSTO = _recurso("angosto.css")
# Pantallas bajas (celular en horizontal): todo mas compacto
CSS_BAJO = _recurso("bajo.css")

# Alto contraste: superficies opacas, bordes nitidos, sin brillos ni desenfoque, foco grueso
CSS_ALTO = _recurso("alto_contraste.css")

# Lite: los mismos controles y datos sin desenfoque, brillos ni transiciones (variante de baja transparencia)
CSS_LITE = _recurso("lite.css")

# Movimiento reducido (preferencia del sistema; independiente de Lite)
CSS_MOVIMIENTO = _recurso("movimiento.css")

# Colores forzados (Windows Alto contraste, etc.): se respetan los colores del usuario; solo se reponen los bordes
# y senales que el navegador quita junto con los fondos y las sombras.
CSS_FORZADOS = _recurso("colores_forzados.css")


def _vidrio(css):
    return (css.replace("__VIDRIO_CLARO__", VIDRIO_CLARO).replace("__VIDRIO_REGULAR__", VIDRIO_REGULAR)
            .replace("__VIDRIO__", VIDRIO).replace("__P_PARAM__", P_PARAM).replace("__P_MAPA__", P_MAPA)
            .replace("__P_EXPORT__", P_EXPORT))


def aplicar(tema="sistema", contraste="sistema", lite=False, sello=False):
    """Estilos de toda la pagina (st.html con solo <style> no dibuja nada). `sello`: la app corre en Streamlit
    Community Cloud, que pone su boton abajo a la derecha (fuera de la app): esa esquina queda libre."""
    css = (CSS + (":root{--y2k-sello:46px}@media " + MOVIL + "{:root{--y2k-sello:42px}" + CSS_SELLO_MOVIL + "}" if sello else "")
           + "@media (min-width: 761px) and (max-width: 1100px){" + CSS_MEDIO + "}"
           + "@media " + MOVIL + "{" + CSS_MOVIL + "}" + "@media (max-width: 400px){" + CSS_ANGOSTO + "}" + "@media (max-width: 380px){" + CSS_ESTRECHO + "}"
           + "@media " + BAJO + "{" + CSS_BAJO + "}"
           + _tokens_css(tema, contraste) + (CSS_LITE if lite else "") + CSS_MOVIMIENTO + CSS_FORZADOS)
    # Streamlit sanea el bloque con DOMPurify, que lo descarta entero si su texto tiene algo con forma de etiqueta
    # (por ejemplo un comentario que nombre un elemento entre angulos): se escapa todo "<" (en CSS es valido)
    st.html("<style>" + _vidrio(css).replace("<", "\\3c ") + "</style>")


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
    "info": _svg('<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>'),
    "camara": _svg('<path d="M12 3a9 9 0 1 0 9 9"/><path d="M21 3v6h-6"/><path d="M21 9a9 9 0 0 0-3-4"/>'
                   '<circle cx="12" cy="12" r="2.5"/>'),
    "cerrar": _svg('<path d="M6 6l12 12M18 6 6 18"/>'),
    "volver": _svg('<path d="M15 6l-6 6 6 6"/>'),
    "excel": _svg('<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 12l4 5M13 12l-4 5"/>'),
    "carpeta": _svg('<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'),
    "tabla": _svg('<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M4 10h16M4 15h16M10 4v16"/>'),
    "aguja": _svg('<path d="M12 3.5 15 12H9z" fill="#E5484D" stroke="none"/><path d="M12 20.5 9 12h6z" fill="currentColor" '
                  'opacity=".5" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/>'),
    "chevron": _svg('<path d="M6 9l6 6 6-6"/>'),
    "estacion": _svg('<path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>'),
    "raton_izq": _svg('<rect x="6" y="2.5" width="12" height="19" rx="6"/><path d="M12 2.5v7M6 9.5h12"/>'
                      '<path class="on" d="M11.2 3.4A5.2 5.2 0 0 0 6.9 8.7h4.3z"/>'),
    "raton_der": _svg('<rect x="6" y="2.5" width="12" height="19" rx="6"/><path d="M12 2.5v7M6 9.5h12"/>'
                      '<path class="on" d="M12.8 3.4a5.2 5.2 0 0 1 4.3 5.3h-4.3z"/>'),
    "raton_rueda": _svg('<rect x="6" y="2.5" width="12" height="19" rx="6"/><path d="M6 9.5h4.5M13.5 9.5H18"/>'
                        '<rect class="on" x="10.6" y="4.6" width="2.8" height="6" rx="1.4"/>'),
    "un_dedo": _svg('<circle class="on" cx="12" cy="12" r="2.8"/><path d="M12 3v3.5M12 17.5V21M3 12h3.5M17.5 12H21"/>'
                    '<path d="M10.2 4.8 12 3l1.8 1.8M10.2 19.2 12 21l1.8-1.8M4.8 10.2 3 12l1.8 1.8M19.2 10.2 21 12l-1.8 1.8"/>'),
    "dos_dedos": _svg('<circle class="on" cx="8" cy="14" r="2.6"/><circle class="on" cx="16" cy="14" r="2.6"/>'
                      '<path d="M4.5 8.5a9 9 0 0 1 15 0"/><path d="M19.5 4.8v3.7h-3.7"/>'),
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


def _cambiar_idioma():
    """Boton de idioma: pasa de espanol a ingles o al reves. El mapa 2D se monta de nuevo para que los textos de su
    barra de dibujo (Leaflet.draw) salgan en el idioma nuevo."""
    ss = st.session_state
    ss.idioma = "es" if idioma.actual() == "en" else "en"
    _query("lang", ss.idioma, "es")
    ss.version_mapa = ss.get("version_mapa", 0) + 1


def toggle_lite(clave, etiqueta=None, ayuda=None, disabled=False):
    """Interruptor del modo Lite (en Ajustes); lee y escribe ss.lite."""
    ss = st.session_state
    ss[clave] = bool(ss.get("lite", False))
    st.toggle(etiqueta or tr("Modo Lite"), key=clave, on_change=_cambiar_lite, args=(clave,), disabled=disabled,
              help=ayuda or tr("Menos efectos visuales (sin desenfoque ni animaciones) y un 3D más liviano. "
                               "Los datos y las funciones son los mismos."))


def ajustes(bloqueado=False):
    """Boton de idioma y menu de Ajustes (arriba a la derecha). `bloqueado` los desactiva mientras corre una
    descarga: cambiar algo recargaria la pagina y la detendria."""
    ss = st.session_state
    with st.container(key="y2k_ajustes", horizontal=True, gap=None, wrap=False, vertical_alignment="center"):
        if ss.get("lite"):
            md(f'<span class="y2k-lite-chip" title="{tr("Modo Lite activado")}">{ICONOS["rayo"]}Lite</span>')
        # muestra el idioma al que se cambia: "EN" en espanol, "ES" en ingles
        en = idioma.actual() == "en"
        st.button("ES" if en else "EN", key="y2k_idioma", type="tertiary", on_click=_cambiar_idioma,
                  disabled=bloqueado, help="Ver en español" if en else "View in English")
        with st.popover(tr("Ajustes"), icon=":material/contrast:", disabled=bloqueado,
                        help=tr("Durante la descarga los ajustes quedan bloqueados") if bloqueado else None):
            md(f'<p class="y2k-menu-tit">{tr("Apariencia")}</p>')
            ss.pref_tono = "Oscuro" if tono(ss.get("tema", "sistema")) == "oscuro" else "Claro"
            st.segmented_control(tr("Tema"), ["Claro", "Oscuro"], key="pref_tono", on_change=_cambiar_tema,
                                 required=True, width="stretch", format_func=tr)
            ss.pref_alto = ss.get("contraste") == "alto"
            st.toggle(tr("Alto contraste"), key="pref_alto", on_change=_cambiar_contraste,
                      help=tr("Superficies opacas, bordes nítidos y foco más grueso. Si tu equipo pide más contraste, "
                              "se aplica solo."))
            md(f'<p class="y2k-menu-tit">{tr("Rendimiento")}</p>')
            toggle_lite("lite_menu")
            md(f'<a class="y2k-enlace" href="app/static/manual.html" target="_blank" rel="noopener">{ICONOS["manual"]}'
               f'{tr("Manual de usuario")}<span class="y2k-vh"> ({tr("se abre en otra pestaña")})</span></a>')
            st.markdown(f'<p class="y2k-hint">{tr("Las animaciones respetan la opción de reducir el movimiento de tu equipo.")}</p>',
                        unsafe_allow_html=True)
            acceso.menu()


# Streamlit no deja cambiar su tema desde Python: este guion pulsa, sin que se vea, la opcion
# Sistema/Light/Dark del menu de Streamlit (que esta oculto con CSS).
_SINCRONIZAR_TEMA = _recurso("sincronizar_tema.html")


def guiones_globales(pantalla):
    """Guiones invisibles de toda la pagina (interfaz del navegador y tema de Streamlit) y la marca de la pantalla
    actual, que usa el CSS para mostrar u ocultar lo de cada una."""
    with st.container(key="y2k_guiones"):
        md(f'<span class="y2k-pantalla" data-p="{pantalla}" hidden></span>')
        instalar_ui()
        quiero = {"claro": "Light", "oscuro": "Dark"}.get(st.session_state.get("tema", "sistema"), "System")
        guion.inyectar(_SINCRONIZAR_TEMA.replace("__TEMA__", quiero))


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
_UI = _recurso("ui.js")


def instalar_ui():
    """Inyecta el guion de la interfaz en la pagina principal (sobrevive a las recargas de Streamlit)."""
    # la version lleva el idioma: al cambiarlo, el guion se instala de nuevo con sus textos
    codigo = (idioma.traducir_js(_UI).replace("__V__", "37-" + idioma.actual())
              .replace("__ICONO_ALERTA__", json.dumps(ICONOS["alerta"]))
              .replace("__MOVIL__", json.dumps(MOVIL)).replace("__VIDRIO__", json.dumps(VIDRIO)))
    cuerpo = ("(function(){var w=window.parent;var s=w.document.createElement('script');"
              f"s.textContent={json.dumps(codigo)};w.document.head.appendChild(s);s.remove();}})();")
    guion.inyectar("<script>" + cuerpo.replace("</", "<\\/") + "</script>")


# ---------------------------------------------------------------------------
# Piezas de la pantalla 1 (Parametros)
# ---------------------------------------------------------------------------
def cabecera_inicio():
    # "no oficial" arriba: el rotulo "IDEAM" solo hacia pensar que la pagina era del instituto
    md(f'<header class="y2k-cab-inicio"><p class="eyebrow">{tr("Descargador IDEAM · no oficial")}</p>'
       f'<h1>{tr("Consulta y descarga de datos hidrometeorológicos")}</h1>{_pasos(1)}</header>')


def etiqueta(texto, punto=None, opcional=False):
    """Etiqueta visible de un campo (la del widget queda oculta pero accesible). `punto`: estado de la lista de
    variables del IDEAM ("cargando", "listo" o "error"): un punto pequeno que se enciende cuando esta lista. Es la
    unica senal de la carga (sin textos)."""
    titulos = {"cargando": tr("Lista de variables del IDEAM: pendiente"),
               "listo": tr("Lista de variables del IDEAM: disponible"),
               "error": tr("Lista de variables del IDEAM: no disponible")}
    pt = (f'<span class="y2k-punto" data-estado="{punto}" role="img" aria-label="{titulos[punto]}"></span>') if punto else ""
    md(f'<p class="y2k-etq"><span aria-hidden="true">{texto}</span>'
       f'{"<span class=opc aria-hidden=true>· " + tr("opcional") + "</span>" if opcional else ""}{pt}</p>')


def marca_listo(listo):
    """Marca invisible para el guion: si la consulta ya puede pasar al mapa (el guion suma si el mapa cargo)."""
    md(f'<span class="y2k-oculto y2k-cta-listo" data-listo="{1 if listo else 0}" hidden></span>')


def aviso(resumen, detalle="", tono="alerta"):
    """Aviso discreto: una linea con su icono y, si hay detalle, "Ver más". `tono`: "alerta", "error" o "info"."""
    icono = ICONOS["info"] if tono == "info" else ICONOS["alerta"]
    rol = ' role="alert"' if tono == "error" else ""
    if detalle:
        md(f'<details class="y2k-aviso" data-tono="{tono}"{rol}><summary>{icono}<span>{escape(resumen)}</span>'
           f'<span class="ver">{tr("Ver más")}</span></summary><div><p>{escape(detalle)}</p></div></details>')
    else:
        md(f'<p class="y2k-aviso" data-tono="{tono}"{rol}>{icono}<span>{escape(resumen)}</span></p>')


PASOS = ("Parámetros", "Área y estaciones", "Descarga")


def _pasos(actual):
    """Indicador 1 · 2 · 3 de la consulta, delgado e igual en las tres pantallas (`actual`: 1, 2 o 3). Reemplaza a
    las tres tarjetas de pasos de Parametros, que solo se veian en la primera pantalla."""
    items = "".join(f'<li{" aria-current=\"step\"" if n == actual else ""}{" class=\"hecho\"" if n < actual else ""}>'
                    f'<span>{tr(t)}</span></li>' for n, t in enumerate(PASOS, 1))
    return f'<ol class="y2k-pasos" aria-label="{tr("Pasos de la consulta")}">{items}</ol>'


def pasos(actual):
    md(_pasos(actual))


def pie_inicio(texto_legal):
    md('<footer class="y2k-pie-inicio">'
       # una sola linea: de quien son los datos, como se pueden usar y que la herramienta no es oficial
       f'<details class="y2k-det"><summary><span>{tr("Herramienta no oficial. Datos del IDEAM: uso personal y no comercial; cita la fuente.")}</span>'
       f'<span class="ver">{tr("Ver condiciones")}</span></summary><div><p>{texto_legal}</p></div></details>'
       f'<p><a href="app/static/manual.html" target="_blank" rel="noopener">{tr("Manual de usuario")}</a></p></footer>')


# ---------------------------------------------------------------------------
# Piezas de la pantalla 2 (Mapa)
# ---------------------------------------------------------------------------
def cabecera_panel():
    """Titulo del panel de la consulta y su boton: plegar (escritorio) o cerrar la tarjeta (celular)."""
    md(f'<div class="y2k-panel-cab" id="y2k-panel"><p class="t" role="heading" aria-level="1">{tr("Consulta")}</p><div>'
       f'<button type="button" class="y2k-ico y2k-panel-cerrar" data-y2k-panel-btn aria-expanded="true" '
       f'aria-label="{tr("Ocultar la consulta")}" title="{tr("Ocultar la consulta")}">{ICONOS["panel"]}</button>'
       f'<button type="button" class="y2k-ico y2k-hoja-cerrar" data-y2k-hoja-cerrar aria-label="{tr("Cerrar la consulta")}" '
       f'title="{tr("Cerrar")}">{ICONOS["cerrar"]}</button></div></div>')


def boton_consulta():
    """Boton "Consulta" de la barra de abajo (solo en el celular): abre y cierra la tarjeta de la consulta."""
    md(f'<button type="button" class="y2k-ico con-texto y2k-consulta" data-y2k-consulta aria-expanded="false" '
       f'aria-controls="y2k-panel">{ICONOS["consulta"]}{tr("Consulta")}</button>')


def boton_abrir_panel():
    """Boton para volver a mostrar el panel cuando esta plegado (escritorio; va en el contenedor y2k_abrir)."""
    md(f'<button type="button" class="y2k-ico con-texto" data-y2k-panel-btn aria-expanded="false" '
       f'aria-label="{tr("Mostrar la consulta")}">{ICONOS["panel_abrir"]}{tr("Consulta")}</button>')


def seccion(titulo, valor="", capsula=None, chip=None):
    """Titulo de una seccion del panel y, a la derecha, un dato: `valor` (texto tenue), `capsula` (cifra destacada,
    como el area en km²) o `chip` = (texto, ayuda): la variable consultada, que al pulsarla vuelve a Parametros."""
    extra = ""
    if capsula:
        extra = f'<span class="y2k-km">{ICONOS["area"]}{escape(capsula)}</span>'
    elif chip:
        texto, ayuda = chip
        extra = (f'<button type="button" class="y2k-chip" data-y2k-pulsar="chip_param" title="{escape(ayuda)}" '
                 f'aria-label="{tr("Variable")}: {escape(texto)}. {tr("Cambiar la variable o el periodo")}">{ICONOS["volver"]}'
                 f'<span>{escape(texto)}</span></button>')
    elif valor:
        extra = f'<span class="valor">{escape(valor)}</span>'
    md(f'<div class="y2k-sec"><p class="t" role="heading" aria-level="2">{titulo}</p>{extra}</div>')


def acciones_area(hay_cuenca, vista="2D"):
    """Formas de marcar o cambiar el area (botones que maneja el guion de la interfaz, sin recargar)."""
    if vista == "3D":
        md(f'<p class="y2k-hint">{tr("Para cambiar el área, vuelve a la vista 2D.")}</p>'
           f'<div class="y2k-acciones"><button type="button" class="y2k-boton sec" data-y2k-2d>{ICONOS["mapa2d"]}'
           f'{tr("Ver en 2D")}</button></div>')
        return
    if not hay_cuenca:
        return   # dibujar o subir el area se hace desde la capsula de herramientas (lapiz), sin repetirlo aqui
    md('<div class="y2k-acciones fichas">'
       f'<button type="button" class="y2k-boton sec" data-y2k-dibujar title="{tr("Dibujar otro rectángulo")}">'
       f'{ICONOS["dibujar"]}{tr("Redibujar")}</button>'
       f'<button type="button" class="y2k-boton sec" data-y2k-editar title="{tr("Ajustar las esquinas")}">'
       f'{ICONOS["ajustar"]}{tr("Ajustar")}</button>'
       f'<button type="button" class="y2k-boton sec peligro" data-y2k-borrar title="{tr("Borrar el área")}">'
       f'{ICONOS["borrar"]}{tr("Borrar")}</button>'
       '</div>')


def ubicacion_elegida(texto):
    """Panel con estaciones elegidas por ubicacion (en Parametros), en lugar del area: de donde son y «Quitar filtro»
    (pulsa el boton oculto y2k_quitar_ubicacion; vuelve al modo area)."""
    md(f'<p class="y2k-hint y2k-ubic">{ICONOS["estacion"]}<span>{escape(texto)}</span></p>'
       '<div class="y2k-acciones"><button type="button" class="y2k-boton sec" data-y2k-pulsar="y2k_quitar_ubicacion" '
       f'title="{tr("Elegir las estaciones con un área del mapa")}">{ICONOS["cerrar"]}{tr("Quitar filtro")}</button></div>')


def kpis(items):
    """Tres cifras del tablero de calidad: (valor, etiqueta, subtitulo, ayuda)."""
    html = "".join(
        f'<div class="y2k-kpi" title="{escape(ayuda)}"><div class="v">{escape(str(valor))}</div>'
        f'<div class="l">{escape(etiqueta_)}</div>{f"<div class=s>{escape(sub)}</div>" if sub else ""}</div>'
        for valor, etiqueta_, sub, ayuda in items)
    md(f'<div class="y2k-kpis">{html}</div>')


# Mapas base del 2D en el orden del menu (el primero es el que arranca; los nombres son los de map_view.mapa_base)
CAPAS_2D = ("Satélite con nombres", "Satélite", "Relieve", "Calles", "Satélite de noche")


def herramientas_2d(hay_cuenca):
    """Capsula de herramientas del mapa 2D (va en el contenedor y2k_herr): menu de dibujo, menu de capas y zoom."""
    extra = (f'<hr><button type="button" role="menuitem" data-y2k-editar>{ICONOS["ajustar"]}<span>{tr("Ajustar las esquinas")}'
             f'<small>{tr("Arrastra los vértices y pulsa «Guardar»")}</small></span></button>'
             f'<button type="button" role="menuitem" class="peligro" data-y2k-borrar>{ICONOS["borrar"]}'
             f'<span>{tr("Borrar el área")}</span></button>'
             ) if hay_cuenca else ""
    capas = "".join(f'<button type="button" role="menuitemradio" aria-checked="{"true" if i == 0 else "false"}" '
                    f'data-y2k-capa="{n}"><span>{tr(n)}</span></button>'
                    for i, n in enumerate(CAPAS_2D))
    md(f'<div class="y2k-herr" role="toolbar" aria-orientation="vertical" aria-label="{tr("Herramientas del mapa")}">'
       '<div class="y2k-grupo">'
       f'<button type="button" class="h" data-y2k-menu="dibujo" aria-haspopup="menu" aria-expanded="false" '
       f'aria-label="{tr("Dibujo del área")}" title="{tr("Dibujo del área")}">{ICONOS["lapiz"]}</button>'
       f'<div class="y2k-menu" role="menu" data-y2k-menu-de="dibujo" aria-label="{tr("Dibujo del área")}" hidden>'
       f'<p class="tit" aria-hidden="true">{tr("Área de estudio")}</p>'
       f'<button type="button" role="menuitem" data-y2k-dibujar>{ICONOS["dibujar"]}<span>'
       f'{tr("Dibujar otro rectángulo") if hay_cuenca else tr("Dibujar un rectángulo")}'
       f'<small>{tr("Haz clic y arrastra sobre el mapa")}</small></span></button>'
       f'<button type="button" role="menuitem" data-y2k-area aria-disabled="true">{ICONOS["area"]}<span>'
       f'{tr("Usar el área visible")}<small>{tr("Primero acércate a tu zona")}</small></span></button>'
       f'<button type="button" role="menuitem" data-y2k-subir>{ICONOS["archivo"]}<span>{tr("Subir un archivo")}'
       f'<small>{tr("SHP, GeoJSON, KML, KMZ o GPKG")}</small></span></button>'
       f'{extra}</div></div>'
       '<div class="y2k-grupo">'
       f'<button type="button" class="h" data-y2k-menu="capas" aria-haspopup="menu" aria-expanded="false" '
       f'aria-label="{tr("Mapa base")}" title="{tr("Mapa base")}">{ICONOS["capas"]}</button>'
       f'<div class="y2k-menu" role="menu" data-y2k-menu-de="capas" aria-label="{tr("Mapa base")}" hidden>'
       f'<p class="tit" aria-hidden="true">{tr("Mapa base")}</p>{capas}</div></div>'
       '<hr>'
       f'<button type="button" class="h" data-y2k-zoom="mas" aria-label="{tr("Acercar")}" title="{tr("Acercar")}">{ICONOS["mas"]}</button>'
       f'<button type="button" class="h" data-y2k-zoom="menos" aria-label="{tr("Alejar")}" title="{tr("Alejar")}">{ICONOS["menos"]}</button>'
       '</div>')


def _guia_gestos():
    """Representacion grafica de los gestos del 3D: raton en equipos con puntero fino, dedos en pantallas tactiles."""
    filas = (("raton", "raton_izq", "Arrastrar", "Mover el mapa"),
             ("raton", "raton_der", "Clic derecho y arrastrar", "Girar e inclinar"),
             ("raton", "raton_rueda", "Rueda", "Acercar o alejar"),
             ("tactil", "un_dedo", "Un dedo", "Mover el mapa"),
             ("tactil", "dos_dedos", "Dos dedos", "Girar; deslizar arriba o abajo inclina; pellizcar acerca"))
    return (f'<div class="y2k-guia" role="note" aria-label="{tr("Gestos del mapa 3D")}">' + "".join(
        f'<div class="{c}">{ICONOS[i]}<span><b>{tr(g)}</b>{tr(t)}</span></div>' for c, i, g, t in filas) + '</div>')


def herramientas_3d(textura, escala):
    """Capsula de herramientas del 3D (va en y2k_herr), como la del 2D: menu de camara y menu de capas (textura del
    relieve y, con Altura, su escala). La camara agrupa en un solo desplegable una cruceta (arriba y abajo inclinan, a
    los lados gira, al centro una brujula que vuelve al norte), el zoom y la guia de gestos del raton o tactiles; es la
    alternativa a los gestos. Las opciones de capas pulsan botones ocultos (y2k_tex_<n>, y2k_esc_<n>)."""
    cruz = "".join(f'<button type="button" data-y2k-cam="{c}" aria-label="{tr(t)}" title="{tr(t)}">{ICONOS[i]}</button>'
                   for c, i, t in (("subir", "inclinar_mas", "Inclinar más"), ("izq", "girar_izq", "Girar a la izquierda"),
                                   ("norte", "aguja", "Orientar al norte"), ("der", "girar_der", "Girar a la derecha"),
                                   ("bajar", "inclinar_menos", "Inclinar menos")))
    zoom = "".join(f'<button type="button" data-y2k-cam="{c}" aria-label="{tr(t)}" title="{tr(t)}">{ICONOS[i]}</button>'
                   for c, i, t in (("acercar", "mas", "Acercar"), ("alejar", "menos", "Alejar")))
    camara = (f'<div class="y2k-pad"><div class="y2k-cruz">{cruz}</div><div class="y2k-zoom-cam">{zoom}</div></div>'
              '<p class="y2k-cam-lectura" aria-hidden="true"></p><hr>' + _guia_gestos())
    texturas = "".join(f'<button type="button" role="menuitemradio" aria-checked="{"true" if t == textura else "false"}" '
                       f'data-y2k-pulsar="y2k_tex_{i}"><span>{tr(t)}</span></button>'
                       for i, t in enumerate(("Satélite", "Topográfico", "Altura")))
    escalas = (f"<hr><p class=\"tit\" aria-hidden=\"true\">{tr('Escala de colores')}</p>" + "".join(
        f'<button type="button" role="menuitemradio" aria-checked="{"true" if e == escala else "false"}" '
        f'data-y2k-pulsar="y2k_esc_{i}"><span>{tr(e.replace("Rango", "Escala"))}</span></button>'
        for i, e in enumerate(("Rango de la zona", "Rango de Colombia")))) if textura == "Altura" else ""
    md(f'<div class="y2k-herr" role="toolbar" aria-orientation="vertical" aria-label="{tr("Herramientas del 3D")}">'
       '<div class="y2k-grupo">'
       f'<button type="button" class="h" data-y2k-menu="camara" aria-controls="y2k-menu-camara" aria-expanded="false" '
       f'aria-label="{tr("Cámara: girar, inclinar y acercar")}" title="{tr("Cámara")}">{ICONOS["camara"]}</button>'
       f'<div class="y2k-menu y2k-cam-menu" role="group" id="y2k-menu-camara" data-y2k-menu-de="camara" '
       f'aria-label="{tr("Cámara")}" hidden>'
       f'<p class="tit" aria-hidden="true">{tr("Cámara")}</p>{camara}</div></div>'
       '<div class="y2k-grupo">'
       f'<button type="button" class="h" data-y2k-menu="capas3d" aria-haspopup="menu" aria-expanded="false" '
       f'aria-label="{tr("Textura del relieve")}" title="{tr("Textura del relieve")}">{ICONOS["capas"]}</button>'
       f'<div class="y2k-menu" role="menu" data-y2k-menu-de="capas3d" aria-label="{tr("Textura del relieve")}" hidden>'
       f'<p class="tit" aria-hidden="true">{tr("Textura del relieve")}</p>{texturas}{escalas}</div></div>'
       '<span class="y2k-vh y2k-camara-estado" aria-live="polite"></span></div>')


def marca_filtro():
    """Marca (invisible) de que el filtro de cobertura esta activo: el boton muestra el rango en vez del icono solo."""
    md('<span class="y2k-oculto y2k-filtro-on" hidden></span>')


TITULO_LEYENDA = "Cobertura estimada del periodo"


def leyenda_estaciones(colores, en3d=False, hay_excluidas=False):
    """Leyenda compacta de los pines sobre el mapa (color, forma y texto; nunca solo color). Es un desplegable: empieza
    cerrada (el resumen ya muestra los colores) y se cierra al tocar fuera de ella."""
    filas = f'<li class="titulo">{tr(TITULO_LEYENDA)}</li>'
    filas += "".join(f'<li><span class="pin" style="background:{c}"></span>{n}</li>' for n, c in colores)
    filas += f'<li><span class="pin hueco"></span>{tr("Sin serie")}</li><li class="sep" aria-hidden="true"></li>'
    if hay_excluidas:
        filas += f'<li><span class="pin fuera"></span>{tr("Excluida")}</li>'
    filas += f'<li><span class="pin duda" style="background:#9AA6BC"></span>{tr("Altitud dudosa")}</li>'
    filas += (f'<li><span class="linea" style="border-color:#35F0FF"></span>{tr("Área")}</li>'
              '<li><span class="linea" style="border-color:#FF7A1A;border-top-style:dashed"></span>Buffer</li>'
              f'<li class="nota">{tr("Relieve exagerado ×2")}</li>') if en3d else (
              f'<li><span class="linea" style="border-color:#1C6FD8"></span>{tr("Área")}</li>'
              '<li><span class="linea" style="border-color:#FAB219;border-top-style:dashed"></span>Buffer</li>')
    muestras = "".join(f'<i style="background:{c}"></i>' for _, c in colores)
    md(f'<details class="y2k-sobre lg-regular y2k-leyenda"><summary>{tr("Leyenda")}<span class="muestras" aria-hidden="true">'
       f'{muestras}</span></summary><ul>{filas}</ul></details>')


def leyenda_altura(html):
    """Leyenda de la textura "Altura" del 3D (la escala la arma terreno.leyenda_altura)."""
    md(f'<details class="y2k-sobre lg-regular y2k-leyenda"><summary>{tr("Altitud")}</summary>{html}'
       f'<p class="tit">{tr("Relieve exagerado ×2")}</p></details>')


def ficha_pildora(nombre, codigo):
    """Cabecera de la ficha de la estacion elegida: una pildora con el nombre que despliega la ficha (empieza cerrada:
    abierta tapaba el mapa) y una x que quita la seleccion."""
    md(f'<div class="y2k-ficha-pil" data-codigo="{escape(codigo)}">'
       f'<button type="button" class="abrir" data-y2k-ficha-btn aria-expanded="false" '
       f'title="{tr("Ver la ficha de la estación")}">{ICONOS["estacion"]}<span class="nom">{escape(nombre)}</span>'
       f'<span class="y2k-vh">: {tr("ficha de la estación")}</span><span class="flecha">{ICONOS["chevron"]}</span></button>'
       f'<button type="button" class="x" data-y2k-ficha-quitar aria-label="{tr("Quitar la selección")}" '
       f'title="{tr("Quitar la selección")}">'
       f'{ICONOS["cerrar"]}</button><span class="y2k-ficha-cab" hidden></span></div>')


def sobre_mapa(html, clase, material="lg-regular"):
    md(f'<div class="y2k-sobre {material} {clase}">{html}</div>')


def detalles(resumen, cuerpo, ver="Ver detalles"):
    """Resumen breve siempre visible y el detalle desplegable (<details>, accesible con teclado)."""
    md(f'<details class="y2k-det"><summary><span>{resumen}</span><span class="ver">{tr(ver)}</span></summary>'
       f'<div>{cuerpo}</div></details>')


def pie():
    """Fuente de los datos, manual y creditos de los mapas (al final del panel)."""
    f = FUENTE
    md('<footer class="y2k-pie">'
       f'<p>{tr("Datos")}: <b>{f["nombre"]}</b> · <a href="{f["url"]}" target="_blank" rel="noopener">Instituto de Hidrología, '
       'Meteorología y Estudios Ambientales</a></p>'
       f'<p>{tr("Uso personal, privado y no comercial; cita la fuente. Herramienta independiente, no oficial del IDEAM.")}</p>'
       f'<p><a href="app/static/manual.html" target="_blank" rel="noopener">{tr("Manual de usuario")}</a> · '
       f'{tr("versión")} {f["version"]}</p>'
       f'<details class="y2k-det"><summary><span class="ver">{tr("Fuentes y créditos de los mapas")}</span></summary>'
       f'<div><p>{tr(CREDITOS_MAPAS)}</p></div></details>'
       '</footer>')


# ---------------------------------------------------------------------------
# Piezas de la pantalla 3 (Exportacion)
# ---------------------------------------------------------------------------
def cabecera_exportar(titulo, estado="vivo"):
    """`estado`: "vivo" (descargando), "hecho" o "alto" (detenida o con error)."""
    punto = {"vivo": '<span class="vivo" aria-hidden="true"></span>', "hecho": '<span class="hecho" aria-hidden="true"></span>'}.get(estado, "")
    md(f'<header class="y2k-cab-export"><p class="eyebrow">{punto}{tr("Exportación")}</p><h1>{titulo}</h1>{_pasos(3)}</header>')


def progreso(fraccion, principal, meta, estado="vivo"):
    """HTML del avance real de la descarga: porcentaje, texto principal (tiempo que falta o total) y una linea de
    cifras. `estado`: "vivo", "fin" o "alto"."""
    pct = round(max(0.0, min(1.0, fraccion)) * 100)
    clase = {"fin": " fin", "alto": " alto"}.get(estado, "")
    return (f'<div class="y2k-md"><div class="y2k-prog">'
            f'<div class="y2k-prog-cifras"><b>{pct} %</b><span>{principal}</span></div>'
            f'<div class="y2k-barra{clase}" role="progressbar" aria-label="{tr("Avance de la descarga")}" aria-valuemin="0" '
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
    md(f'<dl class="y2k-recibo" aria-label="{tr("Recibo de la descarga")}">{html}</dl>')


def resumen_final(texto, reparto):
    """Resumen general de lo descargado: una frase y el reparto por clase de cobertura [(nombre, n, color)]."""
    total = sum(n for _, n, _ in reparto) or 1
    barras = "".join(f'<i style="width:{n / total * 100:.2f}%;background:{c}" title="{escape(nm)}: {n}"></i>'
                     for nm, n, c in reparto if n)
    ley = "".join(f'<li><i style="background:{c}"></i>{escape(nm)} <b>{n}</b></li>' for nm, n, c in reparto if n)
    md(f'<div class="y2k-final"><p>{texto}</p>'
       + (f'<div class="y2k-reparto" aria-hidden="true">{barras}</div>'
          f'<ul class="y2k-reparto-ley" aria-label="{tr("Estaciones guardadas por completitud real")}">{ley}</ul>' if ley else "")
       + '</div>')


def legal_exportar(texto_legal):
    md('<div class="y2k-legal-bloque">'
       f'<p>{tr("Datos del IDEAM: uso personal y no comercial; cita la fuente (el ZIP incluye CITACION.txt).")}</p>'
       f'<details class="y2k-det"><summary><span class="ver">{tr("Ver condiciones completas")}</span></summary>'
       f'<div><p>{texto_legal}</p></div></details></div>')
