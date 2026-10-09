import json
import math
import os
import re
import threading
import time
from datetime import date

import geopandas as gpd
import pandas as pd
import shapely
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from modules import (escaner, estilo, geo_input, geo_utils, map_view, ideam_catalog, ideam_parameters,
                     ideam_downloader, panel_estadisticas, terreno)
from modules.calidad import CLASES_CALIDAD, filtrar_descargables, clasificar_calidad

st.set_page_config(page_title="Descargador IDEAM", page_icon="🌧️", layout="wide", initial_sidebar_state="collapsed")

# ===========================================================================
# TRES PANTALLAS SOBRE UN MISMO MAPA
#   parametros -> mapa -> descarga ("Exportacion")
# El mapa 2D va siempre en el mismo lugar del arbol de Streamlit (el escenario), asi no se vuelve a cargar al
# cambiar de pantalla: en Parametros se carga por detras mientras la persona elige que descargar.
# ===========================================================================
ss = st.session_state
# Preferencias de apariencia y rendimiento: viajan en la direccion (?tema=, ?contraste=, ?lite=) para que sobrevivan
# a una recarga. Sin parametro = lo que pida el equipo (tema y contraste) y calidad completa.
_q = st.query_params
for clave, valor in {"paso": "parametros", "vista": "2D", "cuenca": None, "version_mapa": 0, "version_subida": 0,
                     "estacion_sel": None, "_prev_sel": {}, "consulta": None, "descarga": None, "resultado": None,
                     "estado_descarga": None, "excluidas": set(), "version_lista": 0, "subida_abierta": False,
                     "saltos": 0,
                     "tema": _q.get("tema") if _q.get("tema") in estilo.TEMAS else "sistema",
                     "contraste": _q.get("contraste") if _q.get("contraste") in estilo.CONTRASTES else "sistema",
                     "lite": _q.get("lite") == "1"}.items():
    ss.setdefault(clave, valor)
if (ss.paso not in ("parametros", "mapa", "descarga") or (ss.paso == "mapa" and not ss.consulta)
        or (ss.paso == "descarga" and not ss.descarga)):
    ss.paso = "parametros"
PANTALLA = {"parametros": "parametros", "mapa": "mapa", "descarga": "exportar"}[ss.paso]

# Para saber si el mapa 2D sigue montado en el navegador. Lo monta la corrida que lo dibuja (aunque luego se
# interrumpa o pida otra con st.rerun: lo enviado ya llego). Solo una corrida que TERMINA sin dibujarlo lo quita (ver
# el final del guion); una corrida interrumpida antes de llegar al mapa no lo toca, el navegador lo sigue mostrando.
# Antes se miraba solo la corrida anterior: si esa se interrumpia, el mapa se rehacia sin necesidad (y perdia el zoom)
ss._mapa_en_run_anterior = ss.get("_mapa_montado", False)
ss._mapa_en_esta_run = False



def _en_streamlit_cloud():
    """True en Streamlit Community Cloud, que pone su boton ("Manage app" o su logo) abajo a la derecha, fuera de la
    app: esa esquina se deja libre. Y2K_SELLO=1 simula ese boton para revisar la disposicion en otro servidor."""
    if os.environ.get("Y2K_SELLO") == "1" or os.getcwd().startswith("/mount/src"):
        return True
    try:
        h = st.context.headers
        return any(".streamlit.app" in (h.get(k) or "") for k in ("Host", "Origin", "X-Forwarded-Host"))
    except Exception:
        return False


estilo.aplicar(ss.tema, ss.contraste, ss.lite, sello=_en_streamlit_cloud())
estilo.guiones_globales(PANTALLA)
# Guion que colorea el relieve en la textura "Altura": se instala desde el arranque de la pagina (no cuesta nada
# si no se usa) para que ya este puesto antes de que el visor 3D pida sus imagenes
with st.container(key="y2k_hipso"):
    components.html(terreno.HIPSOMETRICO, height=0)
# Aqui (arriba, sin alto) se pone despues el CSS que tapa el visor 3D mientras arranca la secuencia de entrada
velo_3d = st.container(key="y2k_velo")
PALETA = estilo.paleta(ss.tema)
# Ajustes (arriba a la derecha, en todas las pantallas). Durante una descarga se bloquean: cambiar algo recargaria
# la pagina y la detendria
estilo.ajustes(bloqueado=ss.paso == "descarga" and ss.estado_descarga in ("pendiente", "en_curso"))

if not all(ideam_downloader.credenciales_ideam()):
    st.error("Faltan el usuario y la clave del portal DHIME del IDEAM. En tu computador van en "
             "`.streamlit/secrets.toml`; en Streamlit Cloud, en Settings → Secrets de la app, así:\n\n"
             "```toml\n[ideam]\nusuario = \"...\"\nclave = \"...\"\n```")
    st.stop()

catalogo = ideam_catalog.load_ideam_catalog()
# El mapa vive aqui, en la misma posicion en las tres pantallas (no mover esta linea por debajo de nada condicional)
escenario = st.container(key="y2k_escenario")
# Los huecos de las tres pantallas van siempre, en este orden (vacios los de las otras pantallas). Asi cada uno
# conserva su lugar en la pagina: al cambiar de pantalla, lo de la anterior no aparece dentro de la nueva mientras
# Streamlit termina la corrida (y el CSS lo oculta enseguida por su clave). Lo condicional va despues de todos.
hueco_inicio = st.container(key="y2k_inicio")
hueco_panel = st.container(key="y2k_panel")
hueco_abrir = st.container(key="y2k_abrir")
hueco_herr = st.container(key="y2k_herr")
hueco_filtro = st.container(key="y2k_filtro")
hueco_dock = st.container(key="y2k_dock", horizontal=True, gap=None)
hueco_ficha = st.container(key="y2k_ficha")
hueco_exportar = st.container(key="y2k_exportar")
hueco_ocultos = st.container(key="y2k_ocultos")


# ===========================================================================
# Cargas por detras: lista de parametros (al arrancar el servidor) y series de cada parametro (al elegirlo)
# ===========================================================================
@st.cache_resource(show_spinner=False)
def _iniciar_precarga_servidor():
    """La lista de parametros del IDEAM tarda unos segundos (decenas de consultas). Se pide por detras apenas arranca
    el servidor; mientras tanto la pantalla de Parametros muestra su desplegable en gris.
    Devuelve el estado compartido: {"listo": bool, "error": str | None}."""
    estado = {"listo": False, "error": None}

    def trabajo():
        try:
            ideam_parameters.obtener_catalogo_parametros()
        except Exception as e:  # sin red o IDEAM caido: se ofrece reintentar
            estado["error"] = str(e)
        finally:
            estado["listo"] = True

    threading.Thread(target=trabajo, daemon=True, name="precarga-ideam").start()
    return estado


@st.cache_resource(show_spinner=False)
def _registro_series():
    return {"candado": threading.Lock(), "estado": {}}


def _precargar_series(etiqueta):
    """Pide por detras que estaciones tienen la serie `etiqueta` (lo que necesita el mapa para evaluar). Compartido
    entre sesiones; si fallo, se reintenta a los 30 s. Devuelve {"listo": bool, "error": str | None}."""
    reg = _registro_series()
    with reg["candado"]:
        e = reg["estado"].get(etiqueta)
        vigente = e and (not e["listo"] or (e["error"] is None and time.time() - e["t"] < 6 * 3600 - 120)
                         or (e["error"] and time.time() - e["t"] < 30))
        if vigente:
            return e
        e = {"listo": False, "error": None, "t": time.time()}
        reg["estado"][etiqueta] = e

    def trabajo():
        try:
            ideam_downloader.obtener_series_disponibles(etiqueta)
        except Exception as ex:
            e["error"] = str(ex)
        finally:
            e["listo"] = True

    threading.Thread(target=trabajo, daemon=True, name=f"series-{etiqueta}").start()
    return e


def _reintentar_catalogo():
    _iniciar_precarga_servidor.clear()
    ideam_parameters.limpiar_catalogo()


_precarga = _iniciar_precarga_servidor()

# Condiciones de uso de los datos (terminos del portal DHIME)
TEXTO_LEGAL = ("Los datos provienen del IDEAM y su descarga está autorizada para uso personal, privado y no "
               "comercial. No pueden comercializarse ni venderse. Todo trabajo que los utilice debe citar la "
               "fuente (el ZIP incluye la cita en CITACION.txt). El IDEAM no se hace responsable del uso de los "
               "datos ni de las interpretaciones o inferencias derivadas de ellos. Esta es una herramienta "
               "independiente, no oficial del IDEAM.")


# ===========================================================================
# Utilidades
# ===========================================================================
def _num(n):
    return f"{n:,.0f}".replace(",", ".")


def _firma(gdf):
    """Huella de una geometria para saber si la cuenca cambio de verdad."""
    if gdf is None or gdf.empty:
        return None
    return shapely.normalize(shapely.set_precision(gdf.union_all(), 1e-5)).wkt


def _area_km2(gdf):
    """Area de la cuenca en km² (en la proyeccion de Colombia que usa tambien el buffer)."""
    try:
        return float(gdf[["geometry"]].to_crs(epsg=3116).area.sum()) / 1e6
    except Exception:
        return None


def _periodo(ini, fin):
    """Periodo corto para los textos: "2000–2020" si son anos completos; si no, las fechas."""
    if (ini.month, ini.day, fin.month, fin.day) == (1, 1, 12, 31):
        return f"{ini.year}–{fin.year}" if ini.year != fin.year else str(ini.year)
    return f"{ini:%d/%m/%Y} – {fin:%d/%m/%Y}"


def _frecuencia_txt(frecuencia):
    """Frecuencia para una frase ("frecuencia diaria", "frecuencia cada 10 minutos")."""
    f = re.sub(r"^0(\d)", r"\1", frecuencia.lower())
    return {"diario": "diaria", "horario": "horaria"}.get(f, f)


def _por_defecto(opciones, *preferidas):
    """Posicion de la primera opcion preferida que este en la lista (si ninguna esta, la primera)."""
    claves = list(opciones)
    return next((claves.index(c) for c in preferidas if c in opciones), 0)


def _clave_widget(texto):
    return re.sub(r"\W+", "_", str(texto))


def _desplegable(titulo, opciones, clave, espera, defecto=0, punto=None, buscar="Escribe para buscar"):
    """Desplegable con su etiqueta visible; devuelve el valor elegido. opciones: {valor: texto}. Sin opciones
    (mientras carga la lista del IDEAM o si fallo) va en gris y no se puede abrir, con otra clave: asi el de verdad
    nace con su valor por defecto. defecto=None: empieza sin nada elegido (con `buscar` como texto)."""
    estilo.etiqueta(titulo, punto=punto)
    if not opciones:
        st.selectbox(titulo, [], index=None, key=f"espera_{_clave_widget(titulo)}", label_visibility="collapsed",
                     disabled=True, placeholder=espera)
        return None
    return st.selectbox(titulo, list(opciones), index=defecto, key=clave, label_visibility="collapsed",
                        format_func=lambda v: opciones.get(v, v), placeholder=buscar,
                        persist_state="session")


def _vigente(clave, opciones, multiple=False):
    """Olvida lo elegido en un campo si ya no esta entre sus opciones (otra serie u otro departamento)."""
    valor = ss.get(clave)
    if multiple and valor:
        ss[clave] = [v for v in valor if v in opciones]
    elif not multiple and valor is not None and valor not in opciones:
        del ss[clave]


def _filtro_ubicacion(etiqueta, cargada):
    """Desplegable «Filtrar por ubicación» de Parametros (como «Datos Estación» de la pagina del IDEAM):
    departamento, municipio y estaciones de la serie elegida. Es otra forma de elegir las estaciones y reemplaza al
    area del mapa. Va cerrado para no llenar la tarjeta (abierto si ya hay un filtro). Devuelve el filtro
    ({"codigos", "texto"}) o None si no se eligio departamento. `cargada`: las estaciones de la serie ya llegaron."""
    series = ideam_downloader.obtener_series_disponibles(etiqueta) if cargada else {}
    deps = ideam_parameters.departamentos_de(series)
    _vigente("ubic_dep", deps)
    with st.container(key="y2k_ubicacion"), st.expander("Filtrar por ubicación · opcional", icon=":material/location_on:",
                                                        expanded=ss.get("ubic_dep") is not None):
        # sin departamento no hay filtro (la × del campo lo quita): se olvidan tambien municipio y estaciones
        dep = _desplegable("Departamento", deps, "ubic_dep", "Departamento", defecto=None,
                           buscar="Elige un departamento")
        if dep is None:
            ss.pop("ubic_mun", None)
            ss.pop("ubic_est", None)
            return None
        municipios = ideam_parameters.municipios_de(series, dep)
        _vigente("ubic_mun", municipios)
        mun = _desplegable("Municipio", municipios, "ubic_mun", "Municipio")
        estaciones = ideam_parameters.estaciones_de(series, dep, mun)
        _vigente("ubic_est", estaciones, multiple=True)
        estilo.etiqueta("Estaciones")
        elegidas = st.multiselect("Estaciones", list(estaciones), key="ubic_est", label_visibility="collapsed",
                                  format_func=lambda c: estaciones.get(c, c), persist_state="session",
                                  placeholder="Todas · nombre o código")
    return ideam_parameters.filtro_ubicacion(series, dep, mun, elegidas)


@st.cache_resource(show_spinner=False)
def _codigos_catalogo():
    """Codigo IDEAM de cada estacion del catalogo (mismo indice), para elegirlas por codigo sin recorrerlo cada vez."""
    return pd.Series([ideam_downloader.codigo_de_estacion(r, i) for i, r in catalogo.iterrows()], index=catalogo.index)


def _estaciones_del_filtro(filtro):
    """Estaciones del catalogo elegidas por ubicacion, con zona = "filtro"."""
    zona = catalogo[_codigos_catalogo().reindex(catalogo.index).isin(set(filtro["codigos"])).values].copy()
    zona["zona"] = "filtro"
    return zona


def _marco(zona):
    """Recuadro de las estaciones con unos 2 km de margen: encuadra el 3D y mide el relieve (no se dibuja)."""
    minx, miny, maxx, maxy = zona.total_bounds
    return gpd.GeoDataFrame(geometry=[shapely.box(minx - .02, miny - .02, maxx + .02, maxy + .02)], crs=4326)


def _encuadre(zona):
    """Centro y zoom del mapa 2D para que quepan todas las estaciones (pantalla de ~1000 x 600 px; en el celular
    ~340 x 520). El desfase minusculo hace que el mapa se mueva aunque se repita el mismo encuadre."""
    minx, miny, maxx, maxy = zona.total_bounds
    ancho_px, alto_px = (340, 520) if _es_celular() else (1000, 600)
    zoom = min(math.log2(ancho_px * 360 / (256 * max(maxx - minx, .01))),
               math.log2(alto_px * 360 / (256 * max(maxy - miny, .01))))
    ss.saltos += 1
    return ((miny + maxy) / 2 + ss.saltos * 1e-9, (minx + maxx) / 2), min(13, max(5, int(zoom))) + (ss.saltos % 2) * 1e-4


def _param_de(clave):
    """Parametro del catalogo por su clave (None si la lista no esta o ya no lo trae)."""
    try:
        catalogo_param = ideam_parameters.obtener_catalogo_parametros()
    except Exception:
        return None
    return next((p for p in catalogo_param if p["clave"] == clave), None)


def _sincronizar(fuente, valor, a_codigo):
    """Marca como seleccionada la estacion que se eligio en `fuente` (si esa fuente cambio)."""
    firma = json.dumps(valor, sort_keys=True, default=str)
    if ss._prev_sel.get(fuente) == firma:
        return False
    ss._prev_sel[fuente] = firma
    codigo = a_codigo(valor)
    if codigo:
        ss.estacion_sel = str(codigo)
        return True
    return False


def _estacion_cercana(zona, clic):
    if zona is None or zona.empty or not clic:
        return None
    d = (zona.geometry.x - clic["lng"]) ** 2 + (zona.geometry.y - clic["lat"]) ** 2
    idx = d.idxmin()
    return ideam_downloader.codigo_de_estacion(zona.loc[idx], idx) if d.min() < 1e-6 else None


def _nombre_archivo(texto, respaldo):
    """Nombre de archivo valido en Windows a partir de lo que escribio el usuario."""
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (texto or "").strip())
    limpio = re.sub(r"\.zip$", "", limpio, flags=re.IGNORECASE).strip(" .")
    return limpio or respaldo


def _es_celular():
    """True si la pagina se abrio desde un celular o tablet (segun el navegador)."""
    try:
        agente = st.context.headers.get("User-Agent", "")
    except Exception:
        return False
    return any(marca in agente for marca in ("Mobi", "Android", "iPhone", "iPad"))


def _hex_a_rgb(color):
    color = color.lstrip("#")
    return [int(color[i:i + 2], 16) for i in (0, 2, 4)]


def _revisar_altitudes(zona):
    """Compara la altitud del catalogo con el terreno real (columnas 'terreno' y 'altitud_dudosa')."""
    terreno.precargar(list(zip(zona.geometry.x, zona.geometry.y)))
    revision = [terreno.revisar_altitud(r.get("altitud"), r.geometry.x, r.geometry.y) for _, r in zona.iterrows()]
    zona["terreno"] = [t for t, _ in revision]
    zona["altitud_dudosa"] = [d for _, d in revision]


def _estaciones_3d(zona, excluidas):
    salida = []
    for idx, r in zona.iterrows():
        codigo = ideam_downloader.codigo_de_estacion(r, idx)
        # En 3D solo las que tienen serie en DHIME (salvo la seleccionada): las demas no se
        # pueden descargar y llenan el relieve de pines
        if r.get("Serie DHIME") == "No" and codigo != ss.estacion_sel:
            continue
        pct = r.get("Porcentaje (%)")
        evaluada = pct is not None and pd.notna(pct)
        tiene = bool(evaluada and r.get("Serie DHIME") == "Sí" and r.get("Cantidad Probable", 0) > 0)
        ok = tiene and codigo not in excluidas
        try:
            altitud = float(r.get("altitud"))
        except (TypeError, ValueError):
            altitud = None
        dudosa = bool(r.get("altitud_dudosa")) and r.get("terreno") is not None
        salida.append({
            "codigo": codigo,
            "nombre": str(r.get("nombre", "")),
            "lon": float(r.geometry.x), "lat": float(r.geometry.y),
            "altitud": altitud,
            "altitud_txt": f"{_num(altitud)} m" if altitud else "altitud sin dato",
            "pct_txt": (f"{pct:.0f} %" + (" · excluida" if tiene and not ok else "")) if evaluada else "sin evaluar",
            "color": _hex_a_rgb(clasificar_calidad(pct)["color"]) if ok else [150, 160, 180],
            "ok": ok,
            "zona": {"cuenca": "En el área", "buffer": "En el buffer"}.get(r.get("zona"), ""),
            "alerta": f"⚠ Altitud dudosa: el relieve marca {_num(r['terreno'])} m" if dudosa else "",
            "terreno": r.get("terreno"),
            "dudosa": dudosa,
        })
    return salida


# ===========================================================================
# Acciones (callbacks: corren antes del guion, asi la pantalla nueva aparece en la misma recarga)
# ===========================================================================
def _ir_mapa(clave_param, listo, filtro=None):
    if not listo:   # el navegador ya lo impide (el boton parpadea en rojo); esto es por si el guion no cargo
        return
    nueva = {"clave": ss.get(clave_param), "ini": ss.get("f_ini"), "fin": ss.get("f_fin"), "filtro": filtro}
    if nueva != ss.consulta:
        ss.excluidas = set()   # otro parametro, otro periodo u otras estaciones: las quitadas antes no aplican
    if filtro:
        # Las estaciones elegidas por ubicacion reemplazan al area: si habia una, se quita (el mapa se arma de nuevo,
        # sin el rectangulo) y el mapa se encuadra en las estaciones
        if ss.cuenca is not None:
            ss.cuenca = None
            ss.version_mapa += 1
        ss._encuadrar = True
    ss.consulta = nueva
    ss.paso = "mapa"


# Campos del filtro por ubicacion (Parametros)
UBICACION = ("ubic_dep", "ubic_mun", "ubic_est")


def _quitar_ubicacion():
    """Los tres campos del filtro por ubicacion vuelven a vacio."""
    for clave in UBICACION:
        ss.pop(clave, None)


def _quitar_filtro_mapa():
    """«Quitar filtro» del panel: vuelve al modo area (dibujar o subir un area). Tambien se vacia en Parametros."""
    if ss.consulta:
        ss.consulta = {**ss.consulta, "filtro": None}
    _quitar_ubicacion()
    ss.estacion_sel = None
    ss.excluidas = set()


def _volver_parametros():
    ss.paso = "parametros"


def _borrar_cuenca():
    ss.cuenca = None
    ss.version_mapa += 1
    ss.estacion_sel = None
    ss.excluidas = set()


def _abrir_subida():
    ss.subida_abierta = True


def _cerrar_subida():
    ss.subida_abierta = False


def _recargar_3d():
    """«Seguir intentando» tras un fallo del 3D: visor nuevo en el mismo modo (la camara la repone el navegador)."""
    ss.version_3d = ss.get("version_3d", 0) + 1


def _lite_reintentar():
    """«Activar Lite y reintentar»: solo cuando el usuario lo elige en un aviso de fallo."""
    estilo.poner_lite(True)
    ss.version_3d = ss.get("version_3d", 0) + 1


def _pasar_a_2d():
    ss.vista = "2D"


def _repetir_intro():
    ss._repetir_intro = True


def _poner(clave, valor):
    """Opciones del menu de capas del 3D (textura y escala): las pulsan sus botones ocultos."""
    ss[clave] = valor


def _quitar_filtro():
    ss.filtro_cob = (0, 100)


TEXTURAS = ["Satélite", "Topográfico", "Altura"]
ESCALAS = ["Rango de la zona", "Rango de Colombia"]


def _preparar(datos):
    ss.descarga = datos
    ss.resultado = None
    ss.estado_descarga = "pendiente"
    ss.pop("nombre_zip", None)  # cada descarga nueva arranca con su nombre sugerido
    ss.paso = "descarga"


def _detener():
    ss.estado_descarga = "detenida"


def _reintentar_descarga():
    ss.resultado = None
    ss.estado_descarga = "pendiente"


def _volver_mapa():
    ss.paso = "mapa"


def _nueva_consulta():
    _borrar_cuenca()
    ss.descarga = None
    ss.resultado = None
    ss.estado_descarga = None
    ss.paso = "parametros"


def _vigia(pendiente):
    """Mientras algo carga por detras, este fragmento revisa cada segundo y, al terminar, recarga la pagina una vez."""
    @st.fragment(run_every=1.0)
    def _vigilar():
        if not pendiente():
            st.rerun()
    _vigilar()


# ===========================================================================
# Mapa 2D (escenario): el mismo en las tres pantallas
# ===========================================================================
def _capa_catalogo():
    """Capa del catalogo nacional agrupado (sin area marcada). Se arma de nuevo en cada corrida: folium no deja
    volver a dibujar el mismo objeto (el agrupador quedaria sin definir)."""
    return map_view.capa_dinamica(catalogo=catalogo)


def mapa_2d(capa, centro=None, zoom=None):
    """Mapa base de Leaflet a pantalla completa. El mapa base solo lleva la cuenca cuando se monta de cero (archivo,
    vuelta del 3D, "Borrar"). Un rectangulo recien dibujado ya vive en el navegador: meterlo al mapa base cambiaria
    el componente y Streamlit lo reconstruiria (pantalla en blanco y salto de zoom). Estaciones y buffer van aparte."""
    viva = ss._mapa_en_run_anterior and ss.get("_mapa_version") == ss.version_mapa
    if not viva:
        ss._base_cuenca = ss.cuenca
        ss._mapa_version = ss.version_mapa
    base = map_view.mapa_base(ss.get("_base_cuenca"), ss.tema)
    # El alto real lo pone el CSS (llena la ventana); 650 es solo el valor inicial del componente
    with st.container(key="y2k_mapa2d"):
        retorno = st_folium(base, key=f"mapa2d_{ss.version_mapa}", height=650, use_container_width=True,
                            feature_group_to_add=capa, center=centro, zoom=zoom,
                            returned_objects=["all_drawings", "last_object_clicked"])
    ss._mapa_en_esta_run = ss._mapa_montado = True
    return retorno


def mapa_de_fondo(nuevo_permitido=True):
    """Mapa detras de Parametros y Exportacion: el de la pantalla del mapa, quieto y velado. Si no estaba montado y
    `nuevo_permitido` es False (durante una descarga), no se monta: al cargar podria recargar la pagina."""
    if not nuevo_permitido and not (ss._mapa_en_run_anterior and ss.get("_mapa_version") == ss.version_mapa):
        return
    args = ss.get("_capa_args")
    hay_zona = ss.cuenca is not None or bool((ss.consulta or {}).get("filtro"))
    capa = map_view.capa_dinamica(*args) if hay_zona and args is not None else _capa_catalogo()
    with escenario:
        mapa_2d(capa)


# ===========================================================================
# PANTALLA 1: PARAMETROS
# ===========================================================================
def pantalla_parametros():
    mapa_de_fondo()
    pendientes = []
    with hueco_inicio:
        # la tarjeta de vidrio no se desplaza: lo hace este cuerpo (asi el brillo y el canto de luz quedan fijos)
        cuerpo = st.container(key="y2k_inicio_cuerpo")
    with cuerpo:
        estilo.cabecera_inicio()
        # Serie de tiempo y frecuencia, como en la pagina del IDEAM
        serie = st.segmented_control(
            "Serie de tiempo y frecuencia", ["Estándar", "Especial"], default="Estándar", key="serie", required=True,
            width="stretch", persist_state="session",
            help="**Estándar:** se elige la variable y luego el parámetro (series diarias, mensuales, anuales, horarias "
                 "y de alta frecuencia).\n\n**Especial:** se elige la frecuencia (decadal o multianual), la variable y "
                 "el parámetro con su cálculo: suma, máximo, mínimo o promedio de cada década, o el mínimo, la media y "
                 "el máximo de cada mes en todo el periodo.")
        especial = serie == "Especial"

        # Lista de variables del IDEAM: los desplegables quedan en gris hasta que carga (el punto se enciende)
        estado_cat = "cargando" if not _precarga["listo"] else ("error" if _precarga["error"] else "listo")
        catalogo_param = []
        if estado_cat == "listo":
            try:
                catalogo_param = ideam_parameters.obtener_catalogo_parametros()
            except Exception as e:
                estado_cat, _precarga["error"] = "error", str(e)
        if estado_cat == "cargando":
            pendientes.append(lambda: not _precarga["listo"])
        vacio = "No disponible" if estado_cat == "error" else None
        cargada = estado_cat == "listo"

        # Como en la pagina: [Frecuencia (solo Especial)] -> Variable -> Parametro, cada uno con su lista
        frecuencia = None
        if especial:
            frecuencias = ideam_parameters.frecuencias_especiales(catalogo_param)
            frecuencia = _desplegable("Frecuencia", {f: f for f in frecuencias}, "frec_especial",
                                      vacio or ("No disponible por ahora" if cargada else "Frecuencia"))
        sufijo = f"esp_{frecuencia}" if especial else "est"
        variables = ideam_parameters.variables_de(catalogo_param, especial, frecuencia)
        variable = _desplegable("Variable", variables, f"var_{sufijo}", vacio or ("Sin variables" if cargada else "Variable"),
                                defecto=_por_defecto(variables, "PRECIPITACION"), punto=estado_cat)
        params = ideam_parameters.parametros_de(catalogo_param, variable, especial, frecuencia) if variable else {}
        clave_param = f"par_{sufijo}_{_clave_widget(variable)}"
        clave = _desplegable("Parámetro", {c: p["nombre"] for c, p in params.items()}, clave_param,
                             vacio or ("Sin parámetros" if cargada else "Parámetro"), defecto=_por_defecto(params, "PRECIPITACION|PTPM_CON"))
        param = params.get(clave) if clave else None
        if estado_cat == "error":
            st.error(f"No se pudo cargar la lista de variables del IDEAM. {_precarga['error'] or ''}".strip(),
                     icon=":material/cloud_off:")
            st.button("Reintentar", key="reintentar_catalogo", icon=":material/replay:", on_click=_reintentar_catalogo)
        if param and param.get("avanzado"):
            estilo.aviso("Serie de alta frecuencia: un mes por consulta.",
                         "El IDEAM entrega estas series de a un mes por consulta: diez años son 120 consultas por "
                         "estación. Conviene usar periodos cortos y pocas estaciones.", tono="info")

        c1, c2 = st.container(key="y2k_fechas").columns(2, gap="small")   # en una fila tambien en el celular
        with c1:
            estilo.etiqueta("Desde")
            fecha_ini = st.date_input("Desde", date(2000, 1, 1), min_value=date(1920, 1, 1), max_value=date.today(),
                                      key="f_ini", format="DD/MM/YYYY", label_visibility="collapsed", persist_state="session")
        with c2:
            estilo.etiqueta("Hasta")
            fecha_fin = st.date_input("Hasta", date(2020, 12, 31), min_value=date(1920, 1, 1), max_value=date.today(),
                                      key="f_fin", format="DD/MM/YYYY", label_visibility="collapsed", persist_state="session")
        fechas_ok = fecha_ini < fecha_fin
        if not fechas_ok:
            estilo.aviso("La fecha inicial debe ser anterior a la final.", tono="error")
        filas = ideam_parameters.filas_estimadas(param, fecha_ini, fecha_fin) if param and fechas_ok else 0
        excede = filas > ideam_parameters.MAX_FILAS_EXCEL
        if excede:
            estilo.aviso("El periodo es demasiado largo para un Excel.",
                         f"Con frecuencia {_frecuencia_txt(param['frecuencia'])}, daría hasta {_num(filas)} filas por "
                         "estación y Excel admite alrededor de un millón por hoja. Acorta el periodo.")
        # La serie multianual no se puede partir en bloques (cada bloque daria otros minimos, medias y maximos)
        anios_max = ideam_parameters.periodo_excedido(param, fecha_ini, fecha_fin) if param and fechas_ok else None
        if anios_max:
            estilo.aviso("El periodo es demasiado largo para una serie multianual.",
                         f"El IDEAM calcula los valores multianuales de una sola vez y para esta serie acepta hasta "
                         f"{_num(anios_max)} años por consulta. Acorta el periodo.")

        # Estaciones con la serie elegida: se piden por detras mientras la persona termina de elegir. El boton es
        # siempre azul: si se pulsa antes de que todo este listo no avanza y parpadea en rojo (lo hace el navegador,
        # que sabe ademas si el mapa ya cargo); la unica senal de la carga es el punto de "Variable"
        series = _precargar_series(param["etiqueta"]) if param else None
        if series and not series["listo"]:
            pendientes.append(lambda s=series: not s["listo"])
        # Otra forma de elegir las estaciones (departamento, municipio, estaciones), en un desplegable al final
        filtro = _filtro_ubicacion(param["etiqueta"], bool(series and series["listo"] and not series["error"])) \
            if param else None
        listo = bool(param and fechas_ok and not excede and not anios_max and series and series["listo"])
        estilo.marca_listo(listo)
        n_filtro = len(filtro["codigos"]) if filtro else 0
        st.button(f"Ver {n_filtro} {'estaciones' if n_filtro != 1 else 'estación'} en el mapa" if filtro
                  else "Seleccionar área en el mapa", type="primary", key="ir_mapa", icon=":material/arrow_forward:",
                  icon_position="right", width="stretch", on_click=_ir_mapa, args=(clave_param, listo, filtro))
        estilo.como_funciona()
        estilo.pie_inicio(TEXTO_LEGAL)
    with hueco_ocultos:
        if pendientes:
            _vigia(lambda: any(p() for p in pendientes))


# ===========================================================================
# PANTALLA 2: MAPA
# ===========================================================================
@st.dialog("Subir el contorno del área", width="medium", on_dismiss=_cerrar_subida)
def dialogo_subida():
    st.html('<p class="y2k-hint">SHP (en ZIP o suelto), GeoJSON, KML, KMZ o GPKG. Si el archivo no trae sistema de '
            'coordenadas, te avisaremos.</p>')
    # la clave cambia al usar el archivo: asi el cargador queda vacio para la siguiente vez
    archivos = st.file_uploader("Archivo del área", type=geo_input.EXTENSIONES_ACEPTADAS, accept_multiple_files=True,
                                label_visibility="collapsed", key=f"subida_{ss.version_subida}")
    if not archivos:
        return
    gdf_raw = geo_input.load_vector_file(archivos)
    if gdf_raw is None:
        return
    valido, mensaje = geo_utils.validate_geometry(gdf_raw)
    if not valido:
        st.error(mensaje)
        return
    try:
        gdf = geo_utils.reproject_to_epsg4326(gdf_raw)
    except ValueError as e:
        st.error(str(e))
        return
    poligonos = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
    if poligonos.empty:
        st.error("El archivo solo tiene puntos o líneas. Sube el contorno (polígono) del área.")
        return
    if mensaje != "Geometría válida.":
        st.warning(mensaje)
    st.success(f"Archivo válido: {len(poligonos)} {'polígonos' if len(poligonos) != 1 else 'polígono'}.")
    if st.button("Usar esta área", type="primary", width="stretch", key="usar_subida", icon=":material/check:"):
        ss.cuenca = poligonos[["geometry"]].reset_index(drop=True)
        _quitar_filtro_mapa()   # un area reemplaza a las estaciones elegidas por ubicacion
        ss.version_mapa += 1
        ss.version_subida += 1
        ss.estacion_sel = None
        ss.excluidas = set()
        ss.subida_abierta = False
        st.rerun()


def _km_txt(valor):
    """Cifra corta en km o km²: "2", "2,5", "0,8", "1.234"."""
    if valor < 10:
        return f"{valor:.1f}".rstrip("0").rstrip(".").replace(".", ",")
    return _num(valor)


def _control_buffer():
    """Buffer en una pildora pequena: al pulsarla se activa o desactiva y se cambia el ancho (de 0,5 en 0,5 km)."""
    activo = bool(ss.get("buf_on", True))
    km = float(ss.get("buf_km") or 2.0)
    with st.container(key="y2k_buffer"):
        with st.popover(f"Buffer · {_km_txt(km)} km" if activo else "Sin buffer", icon=":material/radar:",
                        key="pop_buffer", help="Franja alrededor del área para incluir las estaciones cercanas"):
            buffer_on = st.toggle("Incluir estaciones cercanas", value=True, key="buf_on", persist_state="session",
                                  help="Agrega una franja alrededor del área para tener en cuenta las estaciones cercanas.")
            buffer_km = st.number_input("Ancho del buffer (km)", min_value=0.5, max_value=15.0, value=2.0, step=0.5,
                                        format="%.1f", key="buf_km", disabled=not buffer_on, persist_state="session")
    return buffer_on, buffer_km


def pantalla_mapa():
    consulta = ss.consulta
    param = _param_de(consulta.get("clave"))
    if param is None:   # la lista del IDEAM no esta (servidor reiniciado o sin red): de vuelta a Parametros
        ss.paso = "parametros"
        st.rerun()
    fecha_ini, fecha_fin = consulta["ini"], consulta["fin"]
    cuenca = ss.cuenca
    # Estaciones elegidas por ubicacion en Parametros: reemplazan al area (sin rectangulo ni buffer)
    filtro = consulta.get("filtro")
    encuadrar = ss.pop("_encuadrar", False)
    vista = ss.get("vista") or "2D"   # el selector 2D/3D se dibuja abajo, en las pildoras
    excluidas = set(ss.excluidas)

    # Disposicion: el mapa ocupa la ventana (escenario). Encima flotan, en vidrio: el panel (area, buffer y calidad),
    # la capsula de herramientas, las pildoras de abajo y la ficha de la estacion elegida
    with hueco_panel:
        with st.container(key="y2k_panel_cab"):
            estilo.cabecera_panel()
        cuerpo = st.container(key="y2k_cuerpo")
    with hueco_abrir:
        estilo.boton_abrir_panel()

    # ---------------- area y buffer ----------------
    with cuerpo:
        if filtro:
            estilo.seccion("Estaciones elegidas")
            estilo.ubicacion_elegida(filtro["texto"])
            buffer_on, buffer_km = False, 0
        else:
            area_km2 = _area_km2(cuenca) if cuenca is not None else None
            estilo.seccion("Área de estudio", capsula=f"≈ {_km_txt(area_km2)} km²" if area_km2 else None,
                           valor="" if cuenca is not None else "Sin definir")
            estilo.acciones_area(cuenca is not None, vista)
            buffer_on, buffer_km = _control_buffer()
        # la variable consultada, en corto (sin fechas): al pulsarla se vuelve a Parametros
        estilo.seccion("Calidad de los datos", chip=(
            param["variable_nombre"], f"{param['nombre']} · {_periodo(fecha_ini, fecha_fin)}. "
                                      "Pulsa para cambiar la variable o el periodo"))
        caja_calidad = st.container()
        estilo.pie()

    # ---------------- estaciones del area + evaluacion ----------------
    ss.setdefault("filtro_cob", (0, 100))   # el deslizador del filtro toma su valor de aqui (sin valor por defecto propio)
    rango_cob = tuple(ss.filtro_cob)
    filtro_activo = rango_cob != (0, 100)
    n_zona_total = 0
    zona = area = None
    descargables = seleccion = None
    evaluada = False
    error_ideam = None
    if catalogo is not None and filtro:
        zona = _estaciones_del_filtro(filtro)
        area = _marco(zona) if not zona.empty else None
    elif cuenca is not None and catalogo is not None:
        area = geo_utils.create_buffer(cuenca, buffer_km if buffer_on else 0)
        zona = geo_utils.filter_stations(catalogo, area)
        union = cuenca.union_all()
        zona["zona"] = ["cuenca" if union.covers(g) else "buffer" for g in zona.geometry]
    if zona is not None:
        if not zona.empty:
            # sin textos de carga: mientras se calcula, el escaner recorre el area en el mapa
            _revisar_altitudes(zona)
            try:
                calidad = ideam_parameters.get_metadata_availability(zona, param, fecha_ini, fecha_fin)
                for columna in ["Cantidad Probable", "Esperados", "Porcentaje (%)", "Clase calidad",
                                "Serie DHIME", "Inicio serie", "Fin serie"]:
                    zona[columna] = calidad[columna].values
                evaluada = True
            except ideam_downloader.ErrorAccesoIDEAM as e:
                error_ideam = str(e)
            except Exception as e:
                error_ideam = f"No se pudo consultar el IDEAM: {e}"
        # Filtro de cobertura (boton de arriba a la izquierda): lo que queda fuera del rango no se ve ni se descarga
        n_zona_total = len(zona)
        if evaluada and filtro_activo:
            pct = pd.to_numeric(zona["Porcentaje (%)"], errors="coerce").fillna(0)
            zona = zona[(pct >= rango_cob[0]) & (pct <= rango_cob[1])]
        if evaluada:
            descargables = filtrar_descargables(zona, 0)
            codigos = [ideam_downloader.codigo_de_estacion(r, i) for i, r in descargables.iterrows()]
            seleccion = descargables[[c not in excluidas for c in codigos]]
    codigos_desc = (set(ideam_downloader.codigo_de_estacion(r, i) for i, r in descargables.iterrows())
                    if descargables is not None else set())

    # ---------------- estacion seleccionada (mapa 2D, 3D o lista) ----------------
    v = ss.get(f"mapa3d_{ss.get('version_3d', 0)}") or {}
    objetos = ((v.get("selection") or {}).get("objects") or {}).get("estaciones", [])
    cambio_sel = _sincronizar("3d", objetos, lambda o: o[0].get("codigo") if o else None)
    cambio_sel |= bool(ss.pop("_centrar", False))   # elegida en la lista del panel: el mapa va a ella
    dudosas = panel_estadisticas.tabla_dudosas(zona)
    v = ss.get("tabla_dudosas") or {}
    filas = (v.get("selection") or {}).get("rows", [])
    cambio_sel |= _sincronizar("dudosas", filas, lambda f: dudosas.iloc[f[0]]["Código"] if f and f[0] < len(dudosas) else None)
    rango = terreno.rango_terreno(area) if zona is not None and not zona.empty else None
    # Intro satelital: con el area ya confirmada (no se va a mover) se precalienta por detras, asi al pasar a 3D no hay
    # espera. No en celulares; en modo Lite tampoco se precalienta ni se reproduce (es lo mas costoso para la tarjeta
    # grafica), pero `usar_intro` no depende de Lite para que activarlo no cambie el guion de la camara
    bbox_intro, est_intro, usar_intro = None, [], False
    if zona is not None and not zona.empty and terreno.SATELITE_ACTIVO and not _es_celular():
        usar_intro = True
        bbox_intro = list((cuenca if cuenca is not None else area).total_bounds)
        est_intro = _estaciones_3d(zona, excluidas)

    # ---------------- mapa (escenario a pantalla completa) ----------------
    textura = ss.get("textura") if ss.get("textura") in TEXTURAS else "Satélite"
    escala_alt = ss.get("escala_altura") if ss.get("escala_altura") in ESCALAS else "Rango de la zona"
    repetir = False
    with escenario:
        if vista == "3D":
            if zona is None or zona.empty:
                estilo.sobre_mapa("Delimita el área en la vista 2D para verla en relieve." if cuenca is None else
                                  "No hay estaciones en esta zona. Activa o amplía el buffer.", "y2k-vacio")
            else:
                altura = None
                if textura == "Altura":
                    altura = (rango if (escala_alt == "Rango de la zona" and rango and rango[1] > rango[0])
                              else terreno.ALTURA_COLOMBIA)
                ligero = _es_celular() or ss.lite
                with st.container(key="y2k_visor3d"):
                    deck, orbita = terreno.construir_deck(cuenca, area if buffer_on else None,
                                                          _estaciones_3d(zona, excluidas), ss.estacion_sel, textura,
                                                          PALETA, ligero=ligero, altura=altura, celular=_es_celular(),
                                                          marco_gdf=area)
                    # Vuelta de camara: alrededor de la estacion recien elegida o, sin seleccion, alrededor
                    # del centro de las estaciones (al abrir el 3D, al cambiar las estaciones o al quitar la seleccion)
                    pedida = ss.pop("_orbitar", False)
                    repetir = ss.pop("_repetir_intro", False)   # boton temporal "Repetir animacion"
                    entro_3d = ss.get("_vista_prev") != "3D"
                    if ss.estacion_sel:
                        disparar = cambio_sel or pedida or entro_3d
                    else:
                        firma = json.dumps([orbita["lon"], orbita["lat"], orbita["zoom"], orbita["pivote"]])
                        disparar = entro_3d or firma != ss.get("_orbita_firma") or ss.get("_sel_prev") is not None
                        ss._orbita_firma = firma
                    ss._sel_prev = ss.estacion_sel
                    disparar = disparar or repetir
                    if disparar:
                        ss.saltos += 1
                        ss.orbita = ss.saltos
                    # Secuencia de entrada (lasers, caida de pines, alertas): una sola vez por area/buffer (o al
                    # pulsar "Repetir animacion"). Se ata al turno de la vuelta para que el guion no cambie entre una
                    # recarga y otra. En modo Lite el guion no la corre (se muestra el resultado final de una vez)
                    firma_intro = json.dumps([[round(float(c), 5) for c in area.total_bounds], bool(buffer_on)])
                    if disparar and (ss.get("_intro_firma") != firma_intro or repetir):
                        ss._intro_firma = firma_intro
                        ss._intro_turno = ss.orbita
                        ss._intro_forzada = repetir
                    intro = ss.get("_intro_turno") == ss.get("orbita")
                    forzar = bool(intro and ss.get("_intro_forzada"))
                    # Mientras corre la secuencia el visor se tapa (CSS) hasta que el guion de terreno.py esconde las capas
                    # y lo marca con este turno. Se manda en todas las corridas del turno (no solo la primera): si Streamlit
                    # repite el script al entrar al 3D, el velo no puede desaparecer. Si algo falla, se destapa solo a los 12 s
                    if intro and not ss.lite:
                        with velo_3d:
                            st.html('<style>.st-key-y2k_visor3d:not([data-mostrar="' + str(ss.orbita) + '"]) '
                                    '[data-testid="stDeckGlJsonChart"]{visibility:hidden;animation:y2k-mostrar 0s linear 12s forwards}'
                                    '@keyframes y2k-mostrar{to{visibility:visible}}</style>')
                    # La clave cambia con "Seguir intentando" / "Activar Lite y reintentar": visor nuevo desde cero
                    st.pydeck_chart(deck, height=terreno.ALTO_VISOR, on_select="rerun", selection_mode="single-object",
                                    key=f"mapa3d_{ss.get('version_3d', 0)}")
                # Intro satelital (del mapa 2D al 3D): no en celulares ni en modo Lite
                satelite = bool(intro and usar_intro)
                with st.container(key="y2k_orbita"):
                    components.html(terreno.orbitar(orbita, ss.get("orbita", 0), intro, satelite, 1.7, forzar), height=0)
                    if satelite and not ss.lite:
                        components.html(terreno.intro_satelital(ss.get("orbita", 0), bbox_intro, est_intro, buffer_on,
                                                                forzar), height=0)
                    components.html(terreno.AVISO_NAVEGADOR, height=0)
                    components.html(terreno.EXTRAS_3D, height=0)
                if altura:
                    estilo.leyenda_altura(terreno.leyenda_altura(
                        altura[0], altura[1], "escala de Colombia" if altura == terreno.ALTURA_COLOMBIA else "escala de la zona"))
                else:
                    estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD], en3d=True,
                                              hay_excluidas=bool(excluidas & codigos_desc))
                estilo.sobre_mapa(estilo.ATRIB_RELIEVE_3D_CORTO, "y2k-atrib3d", "lg-claro")
                if intro and not forzar and not ss.lite and usar_intro:
                    estilo.sobre_mapa("Tu equipo pide reducir el movimiento, así que la animación de entrada no se "
                                      "reproduce sola. Puedes verla con el botón ↻ de abajo.", "y2k-nota-mov")
        else:
            if cuenca is None and not filtro:
                capa = _capa_catalogo()
            else:
                ss._capa_args = (area if buffer_on else None, zona, ss.estacion_sel, None, excluidas & codigos_desc)
                capa = map_view.capa_dinamica(*ss._capa_args)
            centro = zoom = None
            if encuadrar and zona is not None and not zona.empty:
                centro, zoom = _encuadre(zona)   # recien llegadas las estaciones elegidas por ubicacion
            if cambio_sel and zona is not None and ss.estacion_sel:
                elegida = zona[[ideam_downloader.codigo_de_estacion(r, i) == ss.estacion_sel for i, r in zona.iterrows()]]
                if not elegida.empty:
                    # El mapa solo se mueve si centro/zoom cambian respecto a la vez anterior: un
                    # desfase minusculo (invisible) garantiza que vuelva aunque se elija la misma estacion
                    ss.saltos += 1
                    centro = (elegida.geometry.iloc[0].y + ss.saltos * 1e-9, elegida.geometry.iloc[0].x)
                    zoom = 14 + (ss.saltos % 2) * 1e-4
            retorno = mapa_2d(capa, centro, zoom)
            if retorno and retorno.get("all_drawings") is not None:
                nueva = map_view.cuenca_desde_dibujos(retorno["all_drawings"])
                if _firma(nueva) != _firma(cuenca):
                    ss.cuenca = nueva
                    if filtro:
                        _quitar_filtro_mapa()   # un area reemplaza a las estaciones elegidas por ubicacion
                    ss.estacion_sel = None
                    ss.excluidas = set()
                    st.rerun()
            # Escaner del mapa: el controlador se instala una vez y, al terminar el calculo, se le avisa
            with st.container(key="y2k_escaner"):
                escaner.instalar()
                if cuenca is not None and zona is not None:
                    hay = len(descargables) if evaluada and descargables is not None else len(zona)
                    if hay:
                        texto = f"{hay} {'estaciones con datos' if hay != 1 else 'estación con datos'}"
                    elif zona.empty:
                        texto = "No hay estaciones aquí · amplía el buffer"
                    else:
                        texto = "Ninguna estación tiene datos en el periodo"
                    escaner.listo(hay, texto)
            clic = (retorno or {}).get("last_object_clicked")
            if _sincronizar("mapa2d", clic, lambda c: _estacion_cercana(zona, c)):
                st.rerun()
            if cuenca is not None or filtro:
                estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD],
                                          hay_excluidas=bool(excluidas & codigos_desc))
        ss._vista_prev = vista

    # ---------------- tablero de calidad ----------------
    n_sel = len(seleccion) if seleccion is not None else 0
    cifras = panel_estadisticas.cifras_seleccion(seleccion, param, fecha_ini, fecha_fin) if evaluada else None
    filas_estacion = ideam_parameters.filas_estimadas(param, fecha_ini, fecha_fin)
    excede = filas_estacion > ideam_parameters.MAX_FILAS_EXCEL
    with caja_calidad:
        if error_ideam:
            estilo.aviso("No se pudo consultar el IDEAM.", error_ideam, tono="error")
        elif cuenca is None and not filtro:
            st.html('<p class="y2k-hint">Delimita el área de estudio para evaluar la disponibilidad de datos de cada '
                    'estación.</p>')
        elif zona is not None and zona.empty and n_zona_total:
            estilo.aviso(f"Ninguna estación tiene una cobertura entre {rango_cob[0]} y {rango_cob[1]} %.",
                         "Amplía el rango en el filtro de estaciones (arriba a la izquierda del mapa).")
        elif zona is not None and zona.empty:
            estilo.aviso("No hay estaciones del IDEAM en esta zona. Activa o amplía el buffer.")
        elif excede:
            estilo.aviso("El periodo es demasiado largo para un Excel.",
                         f"Con frecuencia {_frecuencia_txt(param['frecuencia'])}, daría hasta {_num(filas_estacion)} filas "
                         "por estación y Excel admite alrededor de un millón por hoja. Acorta el periodo en Parámetros.")
        elif evaluada and descargables.empty:
            estilo.aviso("Ninguna estación de la zona tiene datos de esta variable en el periodo.",
                         "Cambia la variable o el periodo, o amplía el buffer.")
        elif evaluada:
            panel_estadisticas.tablero(zona, descargables, seleccion, param, cifras, dudosas, rango,
                                       ubicacion=filtro["texto"] if filtro else None)

    # ---------------- capsula de herramientas (derecha) ----------------
    with hueco_herr:
        if vista == "3D":
            if zona is not None and not zona.empty:
                estilo.herramientas_3d(textura, escala_alt)
        else:
            estilo.herramientas_2d(cuenca is not None)

    # ---------------- filtro de estaciones por cobertura (arriba a la izquierda) ----------------
    with hueco_filtro:
        if evaluada and n_zona_total:
            with st.popover(f"{rango_cob[0]}–{rango_cob[1]} %" if filtro_activo else "Filtrar estaciones",
                            icon=":material/filter_alt:", key="pop_filtro"):
                st.html('<p class="y2k-menu-tit">Cobertura del periodo</p>')
                st.slider("Cobertura del periodo", 0, 100, step=5, key="filtro_cob", format="%d %%",
                          label_visibility="collapsed", persist_state="session")
                st.caption(f"{len(zona)} de {n_zona_total} {'estaciones' if n_zona_total != 1 else 'estación'} en el rango. "
                           "Las demás no se ven en el mapa ni se descargan.")
                if filtro_activo:
                    st.button("Quitar el filtro", key="quitar_filtro", icon=":material/filter_alt_off:",
                              on_click=_quitar_filtro, width="stretch")
            if filtro_activo:
                estilo.marca_filtro()   # despues del boton: asi no lo mueve de lugar (y no se cierra al filtrar)

    # ---------------- pildoras de abajo: 2D/3D y "Preparar descarga" ----------------
    listo = evaluada and n_sel > 0 and not excede
    if listo:
        razon = (f"{n_sel} {'estaciones' if n_sel != 1 else 'estación'} · "
                 f"{panel_estadisticas.duracion_aprox(cifras['segundos'])}")
    elif cuenca is None and not filtro:
        razon = "Delimita el área de estudio"
    elif error_ideam:
        razon = "No se pudo consultar el IDEAM"
    elif excede:
        razon = "El periodo es demasiado largo para Excel"
    elif evaluada and descargables is not None and not descargables.empty:
        razon = "Selecciona al menos una estación"
    else:
        razon = "No hay estaciones con datos en esta zona"
    with hueco_dock:
        with st.container(key="y2k_dock_izq", horizontal=True, gap=None, vertical_alignment="center"):
            estilo.boton_consulta()   # celular: abre y cierra la tarjeta de la consulta
            st.segmented_control("Vista del mapa", ["2D", "3D"], key="vista", required=True,
                                 label_visibility="collapsed", persist_state="session")
            if vista == "3D" and zona is not None and not zona.empty:
                # TEMPORAL: para ver la animacion de entrada otra vez mientras se ajusta
                if usar_intro:
                    st.button("Repetir animación", key="y2k_repetir_intro", icon=":material/replay:", on_click=_repetir_intro,
                              disabled=ss.lite,
                              help="En modo Lite no hay animación de entrada. Desactívalo en Ajustes para verla." if ss.lite
                              else "Repetir la animación de entrada al 3D")
        with st.container(key="y2k_dock_der"):
            datos = {"estaciones": seleccion.copy(), "param": param, "ini": fecha_ini, "fin": fecha_fin,
                     "ubicacion": filtro["texto"] if filtro else None} if listo else None
            st.button("Preparar descarga", type="primary", key="preparar", icon=":material/arrow_forward:",
                      icon_position="right", disabled=not listo, help=razon, on_click=_preparar, args=(datos,))

    # ---------------- ficha de la estacion elegida (flotante) ----------------
    with hueco_ficha:
        if ss.estacion_sel and zona is not None and not zona.empty:
            fila = zona[[ideam_downloader.codigo_de_estacion(r, i) == ss.estacion_sel for i, r in zona.iterrows()]]
            if not fila.empty:
                panel_estadisticas.tarjeta_seleccionada(fila.iloc[0], rango, vista,
                                                        descargable=ss.estacion_sel in codigos_desc)

    # Botones ocultos: los pulsan los menus y los avisos de fallo del navegador (siempre por eleccion del usuario)
    with hueco_ocultos:
        st.button("Activar Lite y reintentar", key="y2k_lite_reintentar", on_click=_lite_reintentar)
        st.button("Seguir intentando", key="y2k_reintentar3d", on_click=_recargar_3d)
        st.button("Ver en 2D", key="y2k_pasar2d", on_click=_pasar_a_2d)
        st.button("Borrar el área", key="y2k_borrar", on_click=_borrar_cuenca)
        st.button("Quitar filtro", key="y2k_quitar_ubicacion", on_click=_quitar_filtro_mapa)
        st.button("Subir un archivo", key="y2k_subir", on_click=_abrir_subida)
        st.button("Cambiar la variable", key="chip_param", on_click=_volver_parametros)
        for i, t in enumerate(TEXTURAS):   # menu de capas del 3D
            st.button(t, key=f"y2k_tex_{i}", on_click=_poner, args=("textura", t))
        for i, e in enumerate(ESCALAS):
            st.button(e, key=f"y2k_esc_{i}", on_click=_poner, args=("escala_altura", e))

    # Lo condicional va al final, para no mover de lugar (y rehacer) lo de arriba
    if usar_intro and not ss.lite:
        with st.container(key="y2k_precal"):
            components.html(terreno.precalentar_satelite(bbox_intro, est_intro, buffer_on), height=0)
            st.html(terreno.css_boton_3d_espera(bbox_intro, est_intro))   # el boton 3D espera a que todo este listo
    if ss.subida_abierta:
        if vista == "2D":
            dialogo_subida()
        else:
            ss.subida_abierta = False


# ===========================================================================
# PANTALLA 3: EXPORTACION
# ===========================================================================
def _recibo(d):
    n = len(d["estaciones"])
    en_area = int((d["estaciones"]["zona"] == "cuenca").sum()) if "zona" in d["estaciones"].columns else n
    lugar = d.get("ubicacion") or (f"{en_area} en el área" + (f" · {n - en_area} en el buffer" if n - en_area else ""))
    p = d["param"]
    unidad = f" ({p['unidad']})" if p.get("unidad") else ""
    estilo.recibo([
        ("Variable", p["descripcion"] + unidad, f"Frecuencia {_frecuencia_txt(p['frecuencia'])}"
         + (f" · cálculo {p['calculo']}" if p["especial"] and p["calculo"] not in ("", "NA") else "")),
        ("Periodo", f"{d['ini']:%d/%m/%Y} – {d['fin']:%d/%m/%Y}", ""),
        ("Estaciones", f"{n}", lugar),
        ("Archivo", [("Un Excel por estación", "excel", "")]
         + ([("Carpetas por cobertura", "carpeta", "Alta, media, baja y crítica")] if ss.get("carpetas", True) else [])
         + [("resumen_descarga.csv", "tabla", "Cobertura y resultado por estación"),
            ("CITACION.txt", "cita", "Cita de la fuente")], ""),
        ("Fuente", "IDEAM · DHIME", ""),
    ])


def _zip_final(resultado, carpetas):
    """El ZIP tal como se descarga: plano o en carpetas por cobertura (se arma una vez y se guarda)."""
    if not carpetas:
        return resultado["zip"]
    if resultado.get("_zip_carpetas") is None:
        resultado["_zip_carpetas"] = ideam_downloader.zip_con_carpetas(resultado)
    return resultado["_zip_carpetas"]


@st.fragment
def _entrega(resultado, carpetas):
    """Nombre del ZIP y boton de descarga (en un fragmento: escribir el nombre no recarga la tarjeta entera)."""
    ini, fin = resultado["rango"]
    predeterminado = f"IDEAM_{resultado['rotulo']}_{ini:%Y%m%d}-{fin:%Y%m%d}"
    nombre = st.text_input("Nombre del archivo ZIP", value=predeterminado, key="nombre_zip", max_chars=120, live=True,
                           help="Por ejemplo: descarga 1. La extensión .zip se añade sola.")
    st.download_button("Descargar el ZIP", data=_zip_final(resultado, carpetas), type="primary", width="stretch",
                       file_name=f"{_nombre_archivo(nombre, predeterminado)}.zip", icon=":material/download:",
                       mime="application/zip", key="bajar_zip")


def pantalla_descarga():
    d = ss.descarga
    if ss.estado_descarga == "en_curso":
        # La corrida anterior se corto a mitad de la descarga ("Detener" u otra recarga): no se puede retomar
        ss.estado_descarga = "detenida"
    estado = ss.estado_descarga
    if estado not in ("pendiente", "detenida", "error", "lista") or (estado == "lista" and not ss.resultado):
        estado = ss.estado_descarga = "detenida"
    # el mapa queda detras (velado); no se monta de cero si se va a descargar: al cargar podria recargar la pagina
    mapa_de_fondo(nuevo_permitido=estado not in ("pendiente",))
    n = len(d["estaciones"])
    resultado = ss.resultado
    # Tarjeta de vidrio: a la izquierda el avance y lo que se hace con la descarga; a la derecha el recibo y las
    # condiciones de uso (en el celular, una debajo de la otra)
    # la tarjeta de vidrio no se desplaza: lo hace su cuerpo (el brillo y el borde quedan fijos)
    with hueco_exportar, st.container(key="y2k_exportar_cuerpo"):
        if estado == "pendiente":
            titulo, tono = "Descargando datos del IDEAM", "vivo"
        elif estado == "lista":
            titulo, tono = "Descarga lista", "hecho"
        else:
            titulo, tono = ("No se pudo descargar" if (resultado or {}).get("error") else "Descarga detenida"), "alto"
        estilo.cabecera_exportar(titulo, tono)
        izq, der = st.columns([1.12, 1], gap="large")
        with der:
            _recibo(d)
            estilo.legal_exportar(TEXTO_LEGAL)

        if estado == "pendiente":
            with izq:
                progreso = st.empty()
                progreso.markdown(estilo.progreso(0, "Preparando…", f"<span>Estaciones <b>0 de {n}</b></span>"),
                                  unsafe_allow_html=True)
                aviso = st.empty()
                st.html('<p class="y2k-hint">Puedes seguir mirando esta pantalla; si cierras la pestaña, la descarga '
                        'se detiene.</p>')
                st.button("Detener la descarga", key="detener", icon=":material/stop_circle:", width="stretch",
                          on_click=_detener)
            _descargar(d, progreso, aviso)
            st.rerun()

        if estado in ("detenida", "error"):
            error = (resultado or {}).get("error")
            with izq:
                st.markdown(estilo.progreso(0, "Sin terminar", "<span>No se guardó nada</span>", "alto"),
                            unsafe_allow_html=True)
                if error:
                    st.error(error, icon=":material/cloud_off:")
                else:
                    st.html('<p class="y2k-hint">Puedes reintentarla o volver al mapa para cambiar la selección.</p>')
                with st.container(horizontal=True, gap="small"):
                    st.button("Reintentar", type="primary", width="stretch", icon=":material/replay:", key="reintentar",
                              on_click=_reintentar_descarga)
                    st.button("Volver al mapa", width="stretch", icon=":material/arrow_back:", key="volver_mapa",
                              on_click=_volver_mapa)
            return

        # Descarga lista
        guardadas, omitidas = resultado["guardadas"], resultado["omitidas"]
        with izq:
            st.markdown(estilo.progreso(1.0, f"Completada en {resultado['duracion']}",
                                        f"<span>Guardadas <b>{guardadas}</b></span><span>Omitidas <b>{omitidas}</b></span>",
                                        "fin"), unsafe_allow_html=True)
            frase = (f"Se {'guardaron' if guardadas != 1 else 'guardó'} <b>{guardadas}</b> de {guardadas + omitidas} "
                     f"{'estaciones' if guardadas + omitidas != 1 else 'estación'}."
                     + (f" {'Una' if omitidas == 1 else omitidas} no {'tenía' if omitidas == 1 else 'tenían'} datos en el "
                        "periodo o el IDEAM no respondió; el detalle está en resumen_descarga.csv, dentro del ZIP."
                        if omitidas else ""))
            estilo.resumen_final(frase, panel_estadisticas.reparto_cobertura(resultado["colores"]))
            # Antes de descargar: si el ZIP va en carpetas por cobertura (el recibo de la derecha lo refleja)
            carpetas = st.checkbox("Separar en carpetas por cobertura", value=True, key="carpetas", persist_state="session",
                                   help="Alta (70–100 %), media (50–70 %), baja (25–50 %) y crítica (0–25 %) del "
                                        "periodo consultado. Sin marcar, todos los Excel van juntos.")
            _entrega(resultado, carpetas)
            with st.container(horizontal=True, gap="small"):
                st.button("Volver al mapa", width="stretch", icon=":material/arrow_back:", key="volver_mapa",
                          on_click=_volver_mapa)
                st.button("Nueva consulta", width="stretch", icon=":material/add_location_alt:", key="nueva_consulta",
                          on_click=_nueva_consulta)


def _descargar(d, progreso, aviso):
    """Corre la descarga en esta misma corrida (la barra se actualiza en vivo) y deja el resultado en la sesion."""
    # Turno: como mucho MAX_DESCARGAS_SIMULTANEAS descargas a la vez en el servidor (entre todos los usuarios), para
    # no saturar al IDEAM. Si no hay cupo, se espera con aviso
    cupos = ideam_downloader.cupos_descarga()
    turnos = ideam_downloader.turnos_descarga()
    _, _, segundos = ideam_downloader.plan_descarga(d["estaciones"], d["ini"], d["fin"], d["param"])
    turno = object()
    ss.estado_descarga = "en_curso"
    if not cupos.acquire(blocking=False):
        with turnos["candado"]:
            turnos["fila"].append(turno)
        try:
            inicio_espera = time.time()
            while not cupos.acquire(timeout=2):
                puesto, falta = ideam_downloader.espera_estimada(turno)
                cuando = (f"en ≈ {ideam_downloader.duracion_texto(falta)}" if falta >= 5 else "en cualquier momento")
                aviso.info(f"El servidor está ocupado: hay {ideam_downloader.MAX_DESCARGAS_SIMULTANEAS} descargas en curso. "
                           f"Eres el número {puesto} en la fila y la tuya empezará sola {cuando} "
                           f"(llevas {ideam_downloader.duracion_texto(time.time() - inicio_espera)}).",
                           icon=":material/hourglass_top:")
        finally:
            with turnos["candado"]:
                if turno in turnos["fila"]:
                    turnos["fila"].remove(turno)
    aviso.empty()
    with turnos["candado"]:
        turnos["en_curso"][turno] = (time.time(), segundos)
    try:
        # el ZIP sale plano: las carpetas por cobertura se eligen al final, antes de descargarlo
        resultado = ideam_downloader.procesar_descargas(d["estaciones"], False, d["ini"], d["fin"],
                                                        d["param"], {"progreso": progreso})
        ss.resultado = resultado or {"error": "No se pudo completar la descarga."}
        ss.estado_descarga = "error" if "error" in ss.resultado else "lista"
    finally:
        # Se libera el turno siempre: al terminar, al pulsar "Detener" o si se cierra la pestaña
        with turnos["candado"]:
            turnos["en_curso"].pop(turno, None)
        cupos.release()


# ===========================================================================
if ss.paso == "descarga":
    pantalla_descarga()
elif ss.paso == "mapa":
    pantalla_mapa()
else:
    pantalla_parametros()
# Corrida completa sin el mapa 2D: Streamlit lo quita del navegador
if not ss._mapa_en_esta_run:
    ss._mapa_montado = False
