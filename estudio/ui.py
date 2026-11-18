"""Piezas visuales de la página del estudio, con el mismo sistema Liquid Glass del descargador (modules/estilo.py).

Lo común (tokens de color, vidrio, botón azul, Ajustes, temas, Lite) viene de `modules.estilo`; aquí solo está lo
propio del estudio: tarjetas sobre fondo ambiental, ayudas «i» con fuentes, chips de marca y cifras.
"""
from __future__ import annotations

from html import escape

import streamlit as st

from modules import estilo, guion

from . import fuentes, pasos

# Tarjetas del estudio: vidrio regular (superficies con texto). Se agregan a la lista de vidrio del descargador.
TARJETAS = ".st-key-est_entrada,.st-key-est_mapa,.st-key-est_resultado,.st-key-est_fuentes"

CSS = """
/* fondo ambiental: el vidrio necesita algo detrás (gradiente suave con halos de color) */
.stApp{background:
  radial-gradient(900px 520px at 12% -6%,color-mix(in srgb,var(--y2k-accent) 22%,transparent),transparent 70%),
  radial-gradient(760px 520px at 96% 8%,color-mix(in srgb,var(--y2k-accent-2) 18%,transparent),transparent 70%),
  radial-gradient(900px 640px at 50% 110%,color-mix(in srgb,var(--y2k-ok-luz) 12%,transparent),transparent 70%),
  var(--y2k-bg) !important;background-attachment:fixed !important}
.stMainBlockContainer{max-width:1240px;padding:28px 24px 64px !important}
/* el botón de idioma del descargador no aplica aquí: el estudio está solo en español */
.st-key-y2k_idioma{display:none !important}
.st-key-y2k_ajustes{position:fixed !important;top:12px;right:12px;z-index:60;border-radius:999px;padding:4px !important;width:auto !important}

/* tarjetas */
:is(__TARJETAS__){position:relative;border-radius:30px !important;padding:22px 24px !important;gap:14px !important}
.st-key-est_mapa{padding:10px !important}
.st-key-est_mapa iframe{border-radius:22px !important}

/* cabecera */
.est-cab{margin:6px 0 4px}
.est-cab .eyebrow{font-size:12px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--y2k-accent-texto);margin:0 0 6px}
.est-cab h1{font-size:30px;line-height:1.15;margin:0 0 6px;font-weight:700}
.est-cab p{margin:0;color:var(--y2k-ink-2);font-size:15px;max-width:70ch}
.est-etapas{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px;padding:0;list-style:none}
.est-etapas li{font-size:12.5px;font-weight:600;color:var(--y2k-ink-3);padding:5px 11px;border-radius:999px;
  box-shadow:0 0 0 1px var(--y2k-line) inset;background:var(--y2k-campo)}
.est-etapas li[aria-current="step"]{color:var(--y2k-sobre-acento);background:var(--y2k-boton-tinte);box-shadow:var(--y2k-boton-canto)}

/* título de sección con su botón «i» a la derecha */
[class*="st-key-est_sec_"]{align-items:center !important;gap:8px !important}
.est-sec{font-size:15px;font-weight:700;color:var(--y2k-ink);margin:0;display:flex;align-items:center;gap:8px}
.est-sec .num{display:inline-grid;place-items:center;width:22px;height:22px;border-radius:50%;font-size:12px;
  background:var(--y2k-pista);color:var(--y2k-ink-2);flex:none}
/* botón «i»: cápsula circular pequeña con el ícono centrado */
[class*="st-key-est_sec_"] .stPopover button{width:30px;min-width:30px;height:30px;min-height:30px !important;padding:0 !important;
  border-radius:999px !important;position:relative !important;background:var(--y2k-campo) !important;
  box-shadow:0 0 0 1px var(--y2k-campo-borde) inset !important;border:0 !important}
[class*="st-key-est_sec_"] [data-testid="stPopoverButton"] > div{margin:0 !important}
[class*="st-key-est_sec_"] [data-testid="stPopoverButton"] > div > div[aria-hidden="true"]{display:none !important}
[class*="st-key-est_sec_"] .stPopover button [data-testid="stIconMaterial"]{position:absolute !important;left:50%;top:50%;
  transform:translate(-50%,-50%);margin:0 !important;font-size:18px !important;color:var(--y2k-accent-texto)}
[class*="st-key-est_sec_"] .stPopover button [data-testid="stMarkdownContainer"]{position:absolute !important;width:1px;height:1px;
  overflow:hidden;clip:rect(0 0 0 0)}
[class*="st-key-est_sec_"] [data-testid="stElementContainer"]:has(.est-sec){flex:1 1 auto;min-width:0}

/* contenido de la ayuda */
.est-ayuda{max-width:440px;font-size:13.5px;line-height:1.5}
.est-ayuda h4{font-size:15px;margin:0 0 8px}
.est-ayuda .r{font-size:11.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--y2k-ink-3);margin:12px 0 4px}
.est-ayuda p{margin:0 0 6px;color:var(--y2k-ink-2)}
.est-ayuda ol{margin:4px 0 0;padding-left:18px}
.est-ayuda li{margin:0 0 8px;color:var(--y2k-ink-2)}
.est-ayuda li .n{display:block;font-size:12.5px;color:var(--y2k-ink-3)}

/* marca de la fuente: punto de color + texto */
.est-marca{display:inline-flex;align-items:center;gap:6px;font-size:12px;font-weight:700;color:var(--y2k-ink-2);
  padding:3px 10px 3px 8px;border-radius:999px;background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;white-space:nowrap}
.est-marca::before{content:"";width:8px;height:8px;border-radius:50%;background:var(--m,var(--y2k-line-2));flex:none}
.est-marca[data-m="ambiental"]{--m:var(--y2k-ok-luz)}
.est-marca[data-m="oficial"]{--m:var(--y2k-accent)}
.est-marca[data-m="literatura"]{--m:var(--y2k-accent-2)}
.est-marca[data-m="hidrologo"]{--m:#B27DFF}
.est-marca[data-m="sin_fuente"]{--m:var(--y2k-alerta-borde)}
.est-fuentes-linea{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin:2px 0 0;font-size:12.5px;color:var(--y2k-ink-3)}
/* Streamlit da 1rem a todo párrafo de markdown: dentro de las tarjetas, el texto secundario vuelve a su tamaño */
:is(__TARJETAS__) [data-testid="stMarkdownContainer"] :is(p.est-fuentes-linea,p.y2k-aviso,details.y2k-aviso summary){
  font-size:12.5px !important;line-height:1.45}
:is(__TARJETAS__) [data-testid="stMarkdownContainer"] p.est-fuentes-linea{color:var(--y2k-ink-3) !important}
:is(__TARJETAS__) [data-testid="stMarkdownContainer"] p.est-sec{font-size:15px !important}

/* cifras */
.est-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.est-kpi{background:var(--y2k-campo);box-shadow:0 0 0 1px var(--y2k-campo-borde) inset;border-radius:14px;padding:11px 12px 10px;min-width:0}
.est-kpi .v{font-size:21px;font-weight:700;color:var(--y2k-ink);line-height:1.1;font-variant-numeric:tabular-nums;letter-spacing:-.02em;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.est-kpi .l{font-size:12px;font-weight:700;color:var(--y2k-ink-2);margin-top:5px}
.est-kpi .s{font-size:12px;color:var(--y2k-ink-3);line-height:1.35}
.est-ref{font-size:12.5px;color:var(--y2k-ink-3);margin:2px 0 0}

/* bibliografía */
.est-biblio{margin:0;padding-left:0;list-style:none;display:grid;gap:10px}
.est-biblio li{font-size:13px;line-height:1.5;color:var(--y2k-ink-2);padding-left:1.6em;text-indent:-1.6em}
.est-biblio .est-marca{text-indent:0;margin-left:8px;vertical-align:1px;font-size:11.5px;padding:1px 8px 1px 7px}
.est-biblio a{word-break:break-all}

/* celular: una sola columna y tarjetas con margen */
@media (max-width: 760px){
  .stMainBlockContainer{padding:64px 10px 48px !important}
  :is(__TARJETAS__){border-radius:22px !important;padding:16px 14px !important}
  .est-cab h1{font-size:24px}
  .est-kpis{grid-template-columns:1fr;gap:6px}
  /* en el celular cada cifra va en una línea (valor y etiqueta) con el detalle debajo: ocupa la mitad */
  .est-kpi{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:10px;padding:9px 12px}
  .est-kpi .v{font-size:18px}
  .est-kpi .l{margin:0}
  .est-kpi .s{flex-basis:100%}
}
"""


def aplicar_css():
    css = CSS.replace("__TARJETAS__", TARJETAS)
    # mismo material que las superficies regulares del descargador
    css += (f":is({TARJETAS}){{background:radial-gradient(240px 150px at var(--mx,22%) var(--my,-40%),var(--lg-especular),"
            "transparent 70%),var(--lg-brillo),var(--lg-regular);-webkit-backdrop-filter:var(--lg-filtro-regular);"
            "backdrop-filter:var(--lg-filtro-regular);isolation:isolate;color:var(--y2k-ink);"
            "box-shadow:inset 0 1px 0 var(--lg-luz),inset 0 -1px 0 var(--lg-borde),0 0 0 .5px var(--lg-filo),var(--lg-sombra)}")
    st.html("<style>" + css.replace("<", "\\3c ") + "</style>")


def cabecera(eyebrow: str, titulo: str, texto: str, etapas: list[str], actual: int):
    items = "".join(f'<li{" aria-current=step" if i == actual else ""}>{i + 1}. {escape(e)}</li>'
                    for i, e in enumerate(etapas))
    estilo.md(f'<header class="est-cab"><p class="eyebrow">{escape(eyebrow)}</p><h1>{escape(titulo)}</h1>'
              f'<p>{escape(texto)}</p><ol class="est-etapas" aria-label="Etapas del estudio">{items}</ol></header>')


def marca(clave_marca: str) -> str:
    return (f'<span class="est-marca" data-m="{clave_marca}" title="{escape(fuentes.MARCAS_DESCRIPCION[clave_marca])}">'
            f'{escape(fuentes.MARCAS[clave_marca])}</span>')


def _contenido_ayuda(p: pasos.Paso) -> str:
    lis = []
    for c in p.fuentes:
        f = fuentes.fuente(c)
        enlace = f' <a href="{escape(f.url)}" target="_blank" rel="noopener">Abrir</a>' if f.url else ""
        lis.append(f'<li>{marca(f.marca)}<br>{escape(f.cita)}{enlace}<span class="n">{escape(f.nota)}</span></li>')
    decision = (f'<p class="r">A decisión del hidrólogo</p><p>{escape(p.decision)}</p>') if p.decision else ""
    return (f'<div class="est-ayuda"><h4>{escape(p.titulo)}</h4>'
            f'<p class="r">Qué hace</p><p>{escape(p.que_hace)}</p>'
            f'<p class="r">Por qué</p><p>{escape(p.por_que)}</p>{decision}'
            f'<p class="r">Fuentes</p><ol>{"".join(lis)}</ol></div>')


def _punto(estado: str | None, que: str) -> str:
    """Punto de estado: gris mientras carga, azul cuando está listo, rojo si falló. Es la única señal de carga."""
    if not estado:
        return ""
    titulo = {"cargando": f"{que}: en preparación", "listo": f"{que}: listo", "error": f"{que}: no disponible"}[estado]
    return (f'<span class="y2k-punto" data-estado="{estado}" role="img" aria-label="{escape(titulo)}" '
            f'title="{escape(titulo)}"></span>')


def seccion(clave_paso: str, numero: int | None = None, titulo: str | None = None, estado: str | None = None):
    """Título de una sección con su botón «i»: qué hace, por qué y sus fuentes, cada una con su marca.
    `estado` ("cargando", "listo", "error") pone el punto de carga junto al título."""
    p = pasos.paso(clave_paso)
    with st.container(key=f"est_sec_{clave_paso.replace('.', '_')}_{numero or 0}", horizontal=True,
                      vertical_alignment="center", wrap=False):
        num = f'<span class="num" aria-hidden="true">{numero}</span>' if numero else ""
        estilo.md(f'<p class="est-sec" role="heading" aria-level="2">{num}<span>{escape(titulo or p.titulo)}</span>'
                  f'{_punto(estado, titulo or p.titulo)}</p>')
        with st.popover(f"Qué hace «{p.titulo}» y sus fuentes", icon=":material/info:"):
            estilo.md(_contenido_ayuda(p))


def linea_fuentes(claves: list[str], prefijo: str = "Fuente:"):
    """Fuente de un resultado, en una línea, con la marca más fuerte."""
    cortas = " · ".join(dict.fromkeys(fuentes.fuente(c).corta for c in claves))
    estilo.md(f'<p class="est-fuentes-linea">{marca(fuentes.marca_principal(claves))}'
              f'<span>{escape(prefijo)} {escape(cortas)}</span></p>')


def kpis(items: list[tuple[str, str, str]]):
    """Cifras en tarjetas 3 × 1: (valor, etiqueta, detalle)."""
    html = "".join(f'<div class="est-kpi"><div class="v">{escape(v)}</div><div class="l">{escape(l)}</div>'
                   f'<div class="s">{escape(s)}</div></div>' for v, l, s in items)
    estilo.md(f'<div class="est-kpis">{html}</div>')


def etiqueta(texto: str, estado: str | None = None, que: str = ""):
    """Etiqueta de un campo con el punto de estado (gris mientras carga, azul cuando está listo)."""
    estilo.md(f'<p class="y2k-etq"><span>{escape(texto)}</span>{_punto(estado, que or texto)}</p>')


def bibliografia(claves: list[str]):
    filas = []
    for c in sorted(set(claves), key=lambda k: fuentes.fuente(k).cita.lower()):
        f = fuentes.fuente(c)
        filas.append(f'<li>{escape(f.cita)}{marca(f.marca)}</li>')   # sangría francesa, como pide APA 7
    estilo.md(f'<ol class="est-biblio">{"".join(filas)}</ol>')


# Guiones de la página. No se usa `estilo.guiones_globales`: su interfaz es la del descargador (oculta la barra de
# dibujo y el zoom de Leaflet para manejarlos desde su cápsula de herramientas), y aquí el mapa usa los controles de
# Leaflet tal cual. Se reutiliza solo la sincronización del tema de Streamlit.
_LUZ = """
<script>
(function () {
  var w = window.parent, d = w.document;
  if (w.__estLuz) return; w.__estLuz = true;
  // luz especular de las tarjetas: sigue al puntero (sin efecto en Lite ni con movimiento reducido, lo apaga el CSS)
  d.addEventListener("pointermove", function (e) {
    var t = e.target && e.target.closest && e.target.closest("__TARJETAS__");
    if (!t) return;
    var r = t.getBoundingClientRect();
    t.style.setProperty("--mx", ((e.clientX - r.left) / r.width * 100).toFixed(1) + "%");
    t.style.setProperty("--my", ((e.clientY - r.top) / r.height * 100).toFixed(1) + "%");
  }, {passive: true});
})();
</script>
"""


def guiones(pantalla: str = "estudio"):
    with st.container(key="y2k_guiones"):
        estilo.md(f'<span class="y2k-pantalla" data-p="{pantalla}" hidden></span>')
        quiero = {"claro": "Light", "oscuro": "Dark"}.get(st.session_state.get("tema", "sistema"), "System")
        guion.inyectar(estilo._SINCRONIZAR_TEMA.replace("__TEMA__", quiero) + _LUZ.replace("__TARJETAS__", TARJETAS))
