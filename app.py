import io
import json
import re
import threading
import time
import zipfile
from datetime import date

import pandas as pd
import shapely
import streamlit as st
import streamlit.components.v1 as components
from streamlit_folium import st_folium

from modules import (escaner, estilo, geo_input, geo_utils, map_view, ideam_catalog, ideam_parameters,
                     ideam_downloader, panel_estadisticas, terreno, escena_descarga)
from modules.calidad import CLASES_CALIDAD, filtrar_descargables, clasificar_calidad

st.set_page_config(page_title="Descargador IDEAM", page_icon="🌧️", layout="wide", initial_sidebar_state="collapsed")

ss = st.session_state
# Preferencias de apariencia y rendimiento: viajan en la direccion (?tema=, ?contraste=, ?lite=) para que sobrevivan
# a una recarga. Sin parametro = "Sistema" (sigue la configuracion del equipo) y calidad completa.
_q = st.query_params
for clave, valor in {"paso": "inicio", "cuenca": None, "version_mapa": 0, "estacion_sel": None,
                     "_prev_sel": {}, "descarga": None, "resultado": None, "descarga_en_curso": False,
                     "saltos": 0,
                     "tema": _q.get("tema") if _q.get("tema") in estilo.TEMAS else "sistema",
                     "contraste": _q.get("contraste") if _q.get("contraste") in estilo.CONTRASTES else "sistema",
                     "lite": _q.get("lite") == "1"}.items():
    ss.setdefault(clave, valor)

# Para saber si el mapa 2D sigue montado en el navegador: si la corrida anterior lo dibujo, es el mismo
ss._mapa_en_run_anterior = ss.get("_mapa_en_esta_run", False)
ss._mapa_en_esta_run = False

estilo.aplicar(ss.tema, ss.contraste, ss.lite)
estilo.control_tema()
estilo.guiones_globales()
# Guion que colorea el relieve en la textura "Altura": se instala desde el arranque de la pagina (no cuesta nada
# si no se usa) para que ya este puesto antes de que el visor 3D pida sus imagenes
with st.container(key="y2k_hipso"):
    components.html(terreno.HIPSOMETRICO, height=0)
# Aqui (arriba, sin alto) se pone despues el CSS que tapa el visor 3D mientras arranca la secuencia de entrada
velo_3d = st.container(key="y2k_velo")
PALETA = estilo.paleta(ss.tema)

if not all(ideam_downloader.credenciales_ideam()):
    st.error("Faltan el usuario y la clave del portal DHIME del IDEAM. En tu computador van en "
             "`.streamlit/secrets.toml`; en Streamlit Cloud, en Settings → Secrets de la app, así:\n\n"
             "```toml\n[ideam]\nusuario = \"...\"\nclave = \"...\"\n```")
    st.stop()

catalogo = ideam_catalog.load_ideam_catalog()


@st.cache_resource(show_spinner=False)
def _iniciar_precarga_servidor():
    """Lo que tarda al pasar a la pantalla de estaciones (~4,6 s) es la lista de parametros del IDEAM (decenas de
    consultas). Se pide por detras apenas arranca el servidor, para que ya este en cache cuando el usuario pulse
    "Dibujar mi cuenca". Devuelve el estado compartido: {"listo": bool, "error": str | None}."""
    estado = {"listo": False, "error": None}

    def trabajo():
        try:
            ideam_parameters.obtener_catalogo_parametros()
        except Exception as e:  # sin red o IDEAM caido: el usuario vera el error de siempre en la pantalla siguiente
            estado["error"] = str(e)
        finally:
            estado["listo"] = True

    threading.Thread(target=trabajo, daemon=True, name="precarga-ideam").start()
    return estado


_precarga = _iniciar_precarga_servidor()

# Condiciones de uso de los datos (terminos del portal DHIME), junto al boton de extraccion
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


def _recargar_3d():
    """«Seguir intentando» tras un fallo del 3D: visor nuevo en el mismo modo (la camara la repone el navegador)."""
    ss.version_3d = ss.get("version_3d", 0) + 1


def _lite_reintentar():
    """«Activar Lite y reintentar»: solo cuando el usuario lo elige en un aviso de fallo."""
    ss.lite = True
    st.query_params["lite"] = "1"
    ss.version_3d = ss.get("version_3d", 0) + 1


def _pasar_a_2d():
    ss.vista = "2D"


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
    revision =[terreno.revisar_altitud(r.get("altitud"), r.geometry.x, r.geometry.y) for _, r in zona.iterrows()]
    zona["terreno"] = [t for t, _ in revision]
    zona["altitud_dudosa"] = [d for _, d in revision]


def _estaciones_3d(zona, umbral):
    salida = []
    for idx, r in zona.iterrows():
        codigo = ideam_downloader.codigo_de_estacion(r, idx)
        # En 3D solo las que tienen serie en DHIME (salvo la seleccionada): las demas no se
        # pueden descargar y llenan el relieve de pines
        if r.get("Serie DHIME") == "No" and codigo != ss.estacion_sel:
            continue
        pct = r.get("Porcentaje (%)")
        evaluada = pct is not None and pd.notna(pct)
        ok = bool(evaluada and r.get("Serie DHIME") == "Sí" and r.get("Cantidad Probable", 0) > 0 and pct >= umbral)
        # Con un minimo de cantidad probable, las descartadas se quitan del mapa (salvo la seleccionada)
        if evaluada and umbral > 0 and not ok and codigo != ss.estacion_sel:
            continue
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
            "pct_txt": f"{pct:.0f} %" if evaluada else "sin evaluar",
            "color": _hex_a_rgb(clasificar_calidad(pct)["color"]) if ok else [150, 160, 180],
            "ok": ok,
            "zona": "En la cuenca" if r.get("zona") == "cuenca" else "En el buffer",
            "alerta": f"⚠ Altitud inconsistente: el terreno mide {_num(r['terreno'])} m" if dudosa else "",
            "terreno": r.get("terreno"),
            "dudosa": dudosa,
        })
    return salida


def _ir(paso):
    ss.paso = paso
    st.rerun()


# ===========================================================================
# Pantalla 1: elegir como marcar la cuenca
# ===========================================================================
def pantalla_inicio():
    estilo.barra("", {1}, set(), pantalla="inicio")
    total = (f'<span class="y2k-chip-dato"><i aria-hidden="true"></i>{_num(len(catalogo))} estaciones en el catálogo '
             'nacional</span>' if catalogo is not None else "")
    st.html('<div class="y2k-hello"><h1>¿Dónde está tu cuenca?</h1><p>Marca el área y verás las estaciones del IDEAM '
            f'que caen adentro y cuántos datos tiene cada una.</p>{total}</div>')
    # Se baja por detras lo que necesita el mapa 2D; "Dibujar" espera a que termine para abrirlo sin esperas
    with st.container(key="y2k_precal_mapa"):
        components.html(terreno.precargar_mapa_2d(map_view.recursos_mapa()), height=0)
        st.html(terreno.CSS_DIBUJAR_ESPERA)
        if not _precarga["listo"]:
            # ...y tambien espera a que el servidor tenga la lista de parametros del IDEAM. Este fragmento se repite
            # cada segundo hasta que termina; entonces recarga la pagina una vez (y deja de repetirse)
            @st.fragment(run_every=1.0)
            def _vigilar_precarga():
                if _precarga["listo"]:
                    st.rerun()
                st.html(terreno.CSS_DIBUJAR_ESPERA_SERVIDOR)
            _vigilar_precarga()
    _, c1, c2, _ = st.columns([0.25, 2, 2, 0.25], gap="medium")
    with c1, st.container(key="y2k_card_dibujar"):
        estilo.md(f'<div class="y2k-card-head">{estilo.ICONO_DIBUJAR}<div><h2>Dibujar en el mapa</h2>'
                  '<p>Traza un rectángulo; después puedes mover sus esquinas o borrarlo.</p></div></div>')
        if st.button("Dibujar mi cuenca", type="primary", width="stretch", key="y2k_dibujar"):
            ss.cuenca = None
            ss.version_mapa += 1
            ss.estacion_sel = None
            _ir("estaciones")
        st.html('<p class="y2k-hint y2k-preparando" role="status">Preparando el mapa…</p>')
    with c2, st.container(key="y2k_card_subir"):
        estilo.md(f'<div class="y2k-card-head">{estilo.ICONO_SUBIR}<div><h2>Subir un archivo</h2>'
                  '<p>El contorno de tu cuenca. Si no trae sistema de coordenadas, te avisamos.</p></div></div>'
                  '<p class="y2k-formatos">SHP (en ZIP o suelto) · GeoJSON · KML · KMZ · GPKG</p>')
        archivos = st.file_uploader("Archivo de la cuenca", type=geo_input.EXTENSIONES_ACEPTADAS,
                                    accept_multiple_files=True, label_visibility="collapsed")
        if archivos:
            gdf_raw = geo_input.load_vector_file(archivos)
            if gdf_raw is not None:
                valido, mensaje = geo_utils.validate_geometry(gdf_raw)
                if not valido:
                    st.error(mensaje)
                else:
                    try:
                        gdf = geo_utils.reproject_to_epsg4326(gdf_raw)
                    except ValueError as e:
                        st.error(str(e))
                        gdf = None
                    if gdf is not None:
                        poligonos = gdf[gdf.geom_type.isin(["Polygon", "MultiPolygon"])]
                        if poligonos.empty:
                            st.error("El archivo no trae polígonos (solo puntos o líneas). Sube el contorno de la cuenca.")
                        else:
                            if mensaje != "Geometría válida.":
                                st.warning(mensaje)
                            st.success(f"Cuenca lista ({len(poligonos)} polígono(s)).")
                            if st.button("Continuar con esta cuenca", type="primary", width="stretch"):
                                ss.cuenca = poligonos[["geometry"]].reset_index(drop=True)
                                ss.version_mapa += 1
                                ss.estacion_sel = None
                                _ir("estaciones")
    if catalogo is None:
        st.error("No se pudo cargar el catálogo de estaciones del IDEAM. Revisa tu conexión y recarga la página.")


# ===========================================================================
# Pantalla 2: estaciones, parametro, fechas y filtro
# ===========================================================================
def selector_parametro():
    try:
        with st.spinner("Cargando parámetros del IDEAM..."):
            catalogo_param = ideam_parameters.obtener_catalogo_parametros()
    except ideam_downloader.ErrorAccesoIDEAM as e:
        st.error(str(e))
        return None
    except Exception as e:
        st.error(f"No se pudo cargar la lista de parámetros del IDEAM: {e}")
        return None
    avanzado = st.toggle("Series cada 2, 5 o 10 minutos", key="avanzado",
                         help="Descarga avanzada: series con muchísimos datos. El IDEAM solo entrega 1 mes por consulta.")
    if avanzado:
        st.warning("El IDEAM entrega estos datos de a **1 mes por consulta** (10 años = 120 consultas por estación). "
                   "Usa rangos cortos y pocas estaciones.", icon=":material/hourglass_top:")
    variables = ideam_parameters.variables_disponibles(catalogo_param, avanzado)
    ids = list(variables)
    variable = st.selectbox("Variable", ids, format_func=variables.get, key=f"var_{avanzado}",
                            index=ids.index("PRECIPITACION") if "PRECIPITACION" in ids else 0)
    frecuencia = st.selectbox("Frecuencia", ideam_parameters.frecuencias_disponibles(catalogo_param, variable, avanzado),
                              key=f"frec_{variable}")
    parametros = ideam_parameters.parametros_disponibles(catalogo_param, variable, frecuencia)
    etiqueta = st.selectbox("Parámetro", list(parametros), key=f"par_{variable}_{frecuencia}",
                            format_func=lambda e: f"{parametros[e]['descripcion']} ({parametros[e]['unidad']})")
    param = parametros[etiqueta]
    anios = param["dias_bloque"] / 360
    st.html(f'<p class="y2k-hint">Serie <b>{param["etiqueta"]}</b> · hasta '
            f'{f"{anios:.0f} años" if anios >= 1 else str(param["dias_bloque"]) + " días"} por consulta</p>')
    return param


def pantalla_estaciones():
    cuenca = ss.cuenca
    # Disposicion: el mapa ocupa la pantalla (escenario). En escritorio "Consulta" y "Resumen" son paneles plegables
    # a los lados; en el celular van en pestanas dentro de una hoja inferior contraible (y2k_hoja). Plegar y
    # desplegar lo hace el navegador (estilo.instalar_ui), sin recargar la pagina.
    with st.container(key="y2k_hoja"):
        # cabecera de la hoja (celular): se llena al final, pero en un contenedor (no st.empty) para que las pestanas
        # sigan a la vista mientras Streamlit recalcula
        cab_hoja = st.container()
        col_ctrl = st.container(key="y2k_consulta")
        col_res = st.container(key="y2k_resumen")
    escenario = st.container(key="y2k_escenario")
    # Botones ocultos: los pulsan los avisos de fallo del navegador (siempre por eleccion del usuario)
    with st.container(key="y2k_ocultos"):
        st.button("Activar Lite y reintentar", key="y2k_lite_reintentar", on_click=_lite_reintentar)
        st.button("Seguir intentando", key="y2k_reintentar3d", on_click=_recargar_3d)
        st.button("Ver en 2D", key="y2k_pasar2d", on_click=_pasar_a_2d)

    # ---------------- controles ----------------
    with col_ctrl:
        estilo.cabecera_panel("Consulta", "izq")
        estilo.seccion("Cuenca")
        ayuda_mapa = ("<p>La herramienta de dibujo está arriba a la izquierda del mapa: con el <b>lápiz</b> mueves las "
                      "esquinas y con la <b>papelera</b> borras. Un rectángulo nuevo reemplaza al anterior.</p>"
                      "<p>Pasa el cursor por una estación para ver su ficha y haz clic para seleccionarla. El botón de "
                      "capas (arriba a la derecha) cambia el mapa base.</p>")
        if cuenca is None:
            estilo.detalles("Dibuja un <b>rectángulo</b> sobre el mapa.", ayuda_mapa, ver="Cómo dibujar")
        else:
            estilo.detalles("Cuenca marcada; puedes ajustarla en el mapa.", ayuda_mapa, ver="Cómo usar el mapa")
        buffer_on = st.toggle("Buffer alrededor de la cuenca", value=True, key="buf_on")
        buffer_km = st.slider("Distancia del buffer (km)", 0.5, 15.0, 2.0, 0.5, key="buf_km", disabled=not buffer_on)
        with st.container(horizontal=True, gap="small"):
            if st.button("Borrar cuenca", width="stretch", disabled=cuenca is None, icon=":material/delete:"):
                ss.cuenca = None
                ss.version_mapa += 1
                ss.estacion_sel = None
                st.rerun()
            if st.button("Inicio", width="stretch", icon=":material/arrow_back:"):
                _ir("inicio")
        estilo.seccion("Parámetro")
        param = selector_parametro()
        f1, f2 = st.columns(2)
        fecha_ini = f1.date_input("Desde", date(2000, 1, 1), min_value=date(1920, 1, 1), key="f_ini", format="DD/MM/YYYY")
        fecha_fin = f2.date_input("Hasta", date(2020, 12, 31), min_value=date(1920, 1, 1), key="f_fin", format="DD/MM/YYYY")
        fechas_ok = fecha_ini < fecha_fin
        if not fechas_ok:
            st.error("La fecha de inicio debe ser anterior a la final.")
        estilo.seccion("Filtro")
        umbral = st.slider("Cantidad probable mínima", 0, 100, 0, 5, format="%d%%", key="umbral",
                           help="Qué parte del periodo consultado debe cubrir el registro de la estación "
                                "(entre su primer y su último dato). No descuenta los huecos internos.")
        carpetas = st.checkbox("Carpetas por cobertura en el ZIP", value=True, key="carpetas",
                               help="Alta 70-100 %, Media 50-70 %, Baja 25-50 %, Crítica 0-25 % "
                                    "del periodo consultado")
        # La accion principal queda siempre a la vista al final del panel
        zona_boton = st.container(key="y2k_accion")
        estilo.pie()

    # ---------------- estaciones de la cuenca + evaluacion ----------------
    zona = area = None
    seleccion = None
    evaluada = False
    if cuenca is not None and catalogo is not None:
        area = geo_utils.create_buffer(cuenca, buffer_km if buffer_on else 0)
        zona = geo_utils.filter_stations(catalogo, area)
        union = cuenca.union_all()
        zona["zona"] = ["cuenca" if union.covers(g) else "buffer" for g in zona.geometry]
        if not zona.empty:
            with st.spinner("Revisando la altitud de las estaciones contra el relieve..."):
                _revisar_altitudes(zona)
        if param is not None and fechas_ok and not zona.empty:
            try:
                calidad = ideam_parameters.get_metadata_availability(zona, param, fecha_ini, fecha_fin)
                for columna in ["Cantidad Probable", "Esperados", "Porcentaje (%)", "Clase calidad",
                                "Serie DHIME", "Inicio serie", "Fin serie"]:
                    zona[columna] = calidad[columna].values
                evaluada = True
            except ideam_downloader.ErrorAccesoIDEAM as e:
                with col_ctrl:
                    st.error(str(e))
            except Exception as e:
                with col_ctrl:
                    st.error(f"No se pudo consultar el IDEAM: {e}")
        seleccion = filtrar_descargables(zona, umbral) if evaluada else zona.iloc[0:0]
    tabla = panel_estadisticas.tabla_estaciones(seleccion)

    # ---------------- estacion seleccionada (lista, grafica o 3D) ----------------
    v = ss.get("tabla_est") or {}
    filas = (v.get("selection") or {}).get("rows", [])
    cambio_sel = _sincronizar("tabla", filas, lambda f: tabla.iloc[f[0]]["Código"] if f and f[0] < len(tabla) else None)
    v = ss.get("graf_alt") or {}
    puntos = (v.get("selection") or {}).get("punto", [])
    cambio_sel |= _sincronizar("grafica", puntos, lambda p: p[0].get("Código") if p else None)
    v = ss.get(f"mapa3d_{ss.get('version_3d', 0)}") or {}
    objetos = ((v.get("selection") or {}).get("objects") or {}).get("estaciones", [])
    cambio_sel |= _sincronizar("3d", objetos, lambda o: o[0].get("codigo") if o else None)
    # Lista de altitudes dudosas: al elegir una se muestra en el mapa 3D
    dudosas = panel_estadisticas.tabla_dudosas(zona)
    v = ss.get("tabla_dudosas") or {}
    filas = (v.get("selection") or {}).get("rows", [])
    if _sincronizar("dudosas", filas, lambda f: dudosas.iloc[f[0]]["Código"] if f and f[0] < len(dudosas) else None):
        cambio_sel = True
        ss.vista = "3D"
    rango = terreno.rango_terreno(area) if zona is not None and not zona.empty else None
    # Intro satelital: con la cuenca ya confirmada (no se va a mover) se precalienta por detras, asi al pasar a 3D no hay
    # espera. No en celulares; en modo Lite tampoco se precalienta ni se reproduce (es lo mas costoso para la tarjeta
    # grafica), pero `usar_intro` no depende de Lite para que activarlo no cambie el guion de la camara
    bbox_intro, est_intro, usar_intro = None, [], False
    if zona is not None and not zona.empty and terreno.SATELITE_ACTIVO and not _es_celular():
        usar_intro = True
        bbox_intro = list((cuenca if cuenca is not None else area).total_bounds)
        est_intro = _estaciones_3d(zona, umbral)
    if usar_intro and not ss.lite:
        with st.container(key="y2k_precal"):
            components.html(terreno.precalentar_satelite(bbox_intro, est_intro, buffer_on), height=0)
            st.html(terreno.css_boton_3d_espera(bbox_intro, est_intro))   # el boton 3D espera a que todo este listo

    # ---------------- mapa (escenario a pantalla completa) ----------------
    with escenario:
        vista = st.segmented_control("Vista", ["2D", "3D"], default="2D", key="vista",
                                     label_visibility="collapsed") or "2D"
        if vista == "3D":
            with st.container(key="y2k_tex3d", horizontal=True, gap="small"):
                textura = st.segmented_control("Textura", ["Satélite", "Topográfico", "Altura"], default="Satélite",
                                               key="textura", label_visibility="collapsed") or "Satélite"
                # Textura "Altura": colores segun la altitud, con la escala de la zona o la de todo Colombia
                altura, escala_alt = None, None
                if textura == "Altura":
                    escala_alt = st.segmented_control("Escala de altura", ["Rango de la zona", "Rango de Colombia"],
                                                      default="Rango de la zona", key="escala_altura",
                                                      format_func=lambda e: e.replace("Rango de la", "Escala:").replace("Rango de", "Escala:"),
                                                      label_visibility="collapsed") or "Rango de la zona"
                    altura = rango if (escala_alt == "Rango de la zona" and rango and rango[1] > rango[0]) else terreno.ALTURA_COLOMBIA
            if zona is None or zona.empty:
                estilo.sobre_mapa("Dibuja tu cuenca en el mapa 2D para verla en 3D.", "y2k-vacio")
            else:
                ligero = _es_celular() or ss.lite
                with st.container(key="y2k_visor3d"):
                    deck, orbita = terreno.construir_deck(cuenca, area if buffer_on else None,
                                                          _estaciones_3d(zona, umbral), ss.estacion_sel, textura,
                                                          PALETA, ligero=ligero, altura=altura)
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
                        ss._apex_aplicado = ss.get("apex_factor", 1.7)   # el control temporal solo vale en la siguiente animacion
                    # Secuencia de entrada (lasers, caida de pines, alertas): una sola vez por cuenca/buffer.
                    # Se ata al turno de la vuelta para que el guion no cambie entre una recarga y otra.
                    # En modo Lite el guion no la corre (se muestra el resultado final de una vez)
                    firma_intro = json.dumps([[round(float(c), 5) for c in area.total_bounds], bool(buffer_on)])
                    if disparar and (ss.get("_intro_firma") != firma_intro or repetir):
                        ss._intro_firma = firma_intro
                        ss._intro_turno = ss.orbita
                    intro = ss.get("_intro_turno") == ss.get("orbita")
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
                    components.html(terreno.orbitar(orbita, ss.get("orbita", 0), intro, satelite,
                                                    ss.get("_apex_aplicado", 1.7)), height=0)
                    if satelite and not ss.lite:
                        components.html(terreno.intro_satelital(ss.get("orbita", 0), bbox_intro, est_intro, buffer_on), height=0)
                    components.html(terreno.AVISO_NAVEGADOR, height=0)
                    components.html(terreno.EXTRAS_3D, height=0)
                estilo.controles_camara()
                if altura:
                    estilo.sobre_mapa(terreno.leyenda_altura(altura[0], altura[1],
                                                             "escala de Colombia" if altura == terreno.ALTURA_COLOMBIA
                                                             else "escala de la zona")
                                      + '<p class="tit" style="font-weight:500;padding-top:0">Relieve ×2 · Ctrl + arrastrar gira e inclina</p>',
                                      "y2k-leyenda y2k-leyenda-alt en3d")
                else:
                    estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD], en3d=True)
                estilo.sobre_mapa(estilo.ATRIB_RELIEVE_3D_CORTO, "y2k-atrib3d")
        else:
            # El mapa base solo lleva la cuenca cuando el mapa se monta de cero (archivo, volver del 3D,
            # "Borrar cuenca"). Un rectangulo recien dibujado ya vive en el navegador: meterlo al mapa
            # base cambiaria el hash del componente y Streamlit lo reconstruiria (pantalla en blanco y
            # salto de zoom), ademas de llevarse el escaner. Las estaciones y el buffer van aparte.
            viva = ss._mapa_en_run_anterior and ss.get("_mapa_version") == ss.version_mapa
            if not viva:
                ss._base_cuenca = cuenca
                ss._mapa_version = ss.version_mapa
            base = map_view.mapa_base(ss.get("_base_cuenca"), ss.tema)
            capa = map_view.capa_dinamica(area if (buffer_on and cuenca is not None) else None, zona, umbral,
                                          ss.estacion_sel, catalogo if cuenca is None else None)
            centro = zoom = None
            if cambio_sel and zona is not None and ss.estacion_sel:
                elegida = zona[[ideam_downloader.codigo_de_estacion(r, i) == ss.estacion_sel for i, r in zona.iterrows()]]
                if not elegida.empty:
                    # El mapa solo se mueve si centro/zoom cambian respecto a la vez anterior: un
                    # desfase minusculo (invisible) garantiza que vuelva aunque se elija la misma estacion
                    ss.saltos += 1
                    centro = (elegida.geometry.iloc[0].y + ss.saltos * 1e-9, elegida.geometry.iloc[0].x)
                    zoom = 14 + (ss.saltos % 2) * 1e-4
            # El alto real lo pone el CSS (llena el escenario); 650 es solo el valor inicial del componente
            with st.container(key="y2k_mapa2d"):
                retorno = st_folium(base, key=f"mapa2d_{ss.version_mapa}", height=650, use_container_width=True,
                                    feature_group_to_add=capa, center=centro, zoom=zoom,
                                    returned_objects=["all_drawings", "last_object_clicked"])
            ss._mapa_en_esta_run = True
            if retorno and retorno.get("all_drawings") is not None:
                nueva = map_view.cuenca_desde_dibujos(retorno["all_drawings"])
                if _firma(nueva) != _firma(cuenca):
                    ss.cuenca = nueva
                    ss.estacion_sel = None
                    st.rerun()
            # Escaner del mapa: el controlador se instala una vez y, al terminar el calculo, se le avisa
            with st.container(key="y2k_escaner"):
                escaner.instalar()
                if cuenca is not None and zona is not None:
                    hay = len(seleccion) if evaluada and seleccion is not None else len(zona)
                    if hay:
                        texto = f"{hay} {'estaciones encontradas' if hay != 1 else 'estación encontrada'}"
                    elif zona.empty:
                        texto = "Sin estaciones aquí · prueba ampliar el buffer"
                    else:
                        texto = "Ninguna estación cumple el filtro"
                    escaner.listo(hay, texto)
            clic = (retorno or {}).get("last_object_clicked")
            if _sincronizar("mapa2d", clic, lambda c: _estacion_cercana(zona, c)):
                st.rerun()
            if cuenca is not None:
                estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD])
        ss._vista_prev = vista

    # ---------------- resumen ----------------
    with col_res:
        n_sel = len(seleccion) if evaluada and seleccion is not None else None
        estilo.cabecera_panel("Resumen", "der", extra=f"{n_sel} para descargar" if n_sel is not None else "")
        if cuenca is not None and param is not None and fechas_ok and zona is not None and not evaluada and not zona.empty:
            st.info("Consultando el IDEAM...")
        elif param is not None and fechas_ok:
            panel_estadisticas.mostrar_panel(zona, seleccion if seleccion is not None else None, param,
                                             fecha_ini, fecha_fin, umbral, ss.estacion_sel, tabla, PALETA,
                                             dudosas, rango, vista)
        else:
            st.html('<p class="y2k-hint">El resumen aparece al elegir un parámetro y fechas válidas.</p>')
        if vista == "3D" and zona is not None and not zona.empty:
            # TEMPORAL: para ver la animacion de entrada otra vez mientras se ajusta (quitar antes de presentar)
            with st.expander("Ajustes de la animación 3D (temporal)", icon=":material/tune:"):
                st.button("Repetir animación", key="y2k_repetir_intro", icon=":material/replay:",
                          on_click=lambda: ss.update(_repetir_intro=True), disabled=ss.lite,
                          help="En modo Lite no hay animación de entrada." if ss.lite else None)
                st.slider("Altura de salida de láseres y estaciones (× distancia de la cámara)",
                          0.5, 4.0, 1.7, 0.1, key="apex_factor",
                          help="Más bajo = salen de más cerca y caen más inclinados; más alto = caen casi rectos. "
                               "Se aplica al pulsar «Repetir animación».")

    # ---------------- boton de descarga ----------------
    with zona_boton:
        n = 0 if seleccion is None else len(seleccion)
        excede = False
        if param is not None and fechas_ok:
            filas_estacion = ideam_parameters.filas_estimadas(param, fecha_ini, fecha_fin)
            excede = filas_estacion > ideam_parameters.MAX_FILAS_EXCEL
            if excede:
                st.error(f"Con frecuencia '{param['frecuencia']}' este rango daría hasta {_num(filas_estacion)} filas "
                         f"por estación y Excel solo admite ~1.000.000. Acorta el rango de fechas.")
        if st.button(f"Iniciar extracción · {n} estaciones", type="primary", width="stretch",
                     icon=":material/download:", disabled=n == 0 or excede or param is None):
            ss.descarga = {"estaciones": seleccion.copy(), "param": param, "ini": fecha_ini, "fin": fecha_fin,
                           "carpetas": carpetas}
            ss.resultado = None
            ss.descarga_en_curso = False
            ss.pop("nombre_zip", None)  # cada descarga nueva arranca con su nombre sugerido
            _ir("descarga")
        # El portal obliga a aceptar sus terminos antes de cada descarga; la herramienta se salta
        # esa pantalla, asi que muestra lo esencial aqui, junto al boton (no en un modal)
        estilo.aviso_legal(TEXTO_LEGAL)

    # ---------------- cabecera de la hoja inferior (celular) ----------------
    if cuenca is None:
        estado = "Dibuja un rectángulo en el mapa"
    elif zona is None or zona.empty:
        estado = "Sin estaciones en la zona"
    elif n_sel is not None:
        estado = ""   # la pestana "Resumen (n)" ya lo dice
    else:
        estado = f"{len(zona)} estaciones en la zona"
    with cab_hoja:
        estilo.cabecera_hoja(estado, n_sel)

    return "", cuenca is not None, evaluada


# ===========================================================================
# Pantalla 3: la descarga
# ===========================================================================
def pantalla_descarga():
    d = ss.descarga
    lista = bool(ss.resultado) and "error" not in ss.resultado
    estilo.barra((f"Descarga lista · {d['param']['etiqueta']} · Fuente: IDEAM" if lista
                  else f"Descargando {d['param']['etiqueta']} · Fuente: IDEAM") if d else "", {4}, {1, 2, 3},
                 pantalla="descarga")
    if d is None:
        st.info("No hay ninguna descarga preparada.")
        if st.button("Volver a estaciones", icon=":material/arrow_back:"):
            _ir("estaciones")
        return

    col_esc, col_con = st.columns([1.6, 1], gap="medium")
    col_esc = col_esc.container(key="y2k_card_descarga")
    resultado = ss.resultado

    if resultado is None and not ss.descarga_en_curso:
        if ss.get("cancelar_espera"):
            _ir("estaciones")
        # Turno: como mucho MAX_DESCARGAS_SIMULTANEAS descargas a la vez en el servidor (entre
        # todos los usuarios), para no saturar al IDEAM. Si no hay cupo, se espera con aviso.
        cupos = ideam_downloader.cupos_descarga()
        turnos = ideam_downloader.turnos_descarga()
        _, _, segundos = ideam_downloader.plan_descarga(d["estaciones"], d["ini"], d["fin"], d["param"])
        turno = object()
        with col_esc:
            espera = st.empty()
        if not cupos.acquire(blocking=False):
            with turnos["candado"]:
                turnos["fila"].append(turno)
            try:
                with espera.container():
                    aviso = st.empty()
                    st.button("Cancelar y volver", key="cancelar_espera")
                inicio_espera = time.time()
                while not cupos.acquire(timeout=2):
                    puesto, falta = ideam_downloader.espera_estimada(turno)
                    cuando = (f"≈ {ideam_downloader.formatear_duracion(falta)}" if falta >= 5
                              else "en cualquier momento")
                    aviso.info(f"Servidor ocupado: {ideam_downloader.MAX_DESCARGAS_SIMULTANEAS} descargas en curso. "
                               f"Vas de número {puesto} en la fila y empieza sola {cuando} "
                               f"(llevas {ideam_downloader.formatear_duracion(time.time() - inicio_espera)}).",
                               icon=":material/hourglass_top:")
            finally:
                with turnos["candado"]:
                    if turno in turnos["fila"]:
                        turnos["fila"].remove(turno)
        with turnos["candado"]:
            turnos["en_curso"][turno] = (time.time(), segundos)
        try:
            espera.empty()
            with col_esc:
                escena_descarga.mostrar("vivo", total=len(d["estaciones"]), segundos_estimados=segundos, lite=ss.lite)
                ui = {"barra": st.empty(), "estado": st.empty(), "oculto": st.empty()}
                st.button("Detener descarga", key="detener", icon=":material/stop_circle:")
            with col_con:
                ui["consola"] = st.empty()
            ss.descarga_en_curso = True
            resultado = ideam_downloader.procesar_descargas(d["estaciones"], d["carpetas"], d["ini"], d["fin"],
                                                            d["param"], ui)
            ss.descarga_en_curso = False
            ss.resultado = resultado or {"error": "No se pudo completar la descarga."}
        finally:
            # Se libera el turno siempre: al terminar, al oprimir "Detener" o si se cierra la pestaña
            with turnos["candado"]:
                turnos["en_curso"].pop(turno, None)
            cupos.release()
        st.rerun()

    if resultado is None:
        # Se oprimio "Detener" a mitad de la descarga
        ss.descarga_en_curso = False
        st.warning("Descarga detenida. Puedes reintentar o cambiar la selección.")
        c1, c2 = st.columns(2)
        if c1.button("Reintentar", type="primary", width="stretch", icon=":material/replay:"):
            st.rerun()
        if c2.button("Volver a estaciones", width="stretch", icon=":material/arrow_back:"):
            _ir("estaciones")
        return

    if "error" in resultado:
        st.error(resultado["error"])
        if st.button("Volver a estaciones", icon=":material/arrow_back:"):
            _ir("estaciones")
        return

    with col_esc:
        escena_descarga.mostrar("final", total=len(resultado["colores"]), colores_finales=resultado["colores"],
                                subtitulo=f"{resultado['guardadas']} estaciones · {resultado['omitidas']} omitidas"
                                          f" · Fuente: IDEAM · DHIME", lite=ss.lite)
        st.markdown(estilo.barra_pixel(1.0), unsafe_allow_html=True)
        st.markdown(f'<div class="y2k-pmeta"><span><b>100 %</b> · listo en <b>{resultado["duracion"]}</b></span>'
                    f'<span>Guardadas <b>{resultado["guardadas"]}</b> · Omitidas <b>{resultado["omitidas"]}</b></span></div>',
                    unsafe_allow_html=True)
        ini, fin = resultado["rango"]
        predeterminado = f"IDEAM_{resultado['etiqueta']}_{ini:%Y%m%d}-{fin:%Y%m%d}"
        nombre = st.text_input("Nombre del archivo ZIP", value=predeterminado, key="nombre_zip", max_chars=120,
                               help="Por ejemplo: descarga 1. La extensión .zip se añade sola.")
        st.html('<p class="y2k-hint">Si cambias el nombre, presiona <b>Enter</b> antes de descargar.</p>')
        st.download_button("Descargar ZIP con los Excel", data=resultado["zip"], type="primary",
                           file_name=f"{_nombre_archivo(nombre, predeterminado)}.zip", icon=":material/download:",
                           mime="application/zip", width="stretch")
        # Recordatorio de las condiciones de uso del IDEAM en el momento de la entrega
        estilo.aviso_legal(TEXTO_LEGAL)
        c1, c2 = st.columns(2)
        if c1.button("Volver a estaciones", width="stretch", icon=":material/arrow_back:"):
            _ir("estaciones")
        if c2.button("Nueva cuenca", width="stretch", icon=":material/add_location_alt:"):
            ss.cuenca = None
            ss.version_mapa += 1
            _ir("inicio")
    with col_con, st.container(key="y2k_card_resumen_zip"):
        st.html('<h3 class="y2k-titulo-seccion">Resumen</h3>')
        try:
            with zipfile.ZipFile(io.BytesIO(resultado["zip"])) as z:
                resumen = pd.read_csv(io.BytesIO(z.read("resumen_descarga.csv")))
            columnas = [c for c in ["Nombre", "Cobertura", "Clase", "Resultado", "Detalle"] if c in resumen.columns]
            st.dataframe(resumen[columnas].fillna(""), hide_index=True, width="stretch", height=380)
        except Exception:
            st.caption("El detalle está en resumen_descarga.csv dentro del ZIP.")


# ===========================================================================
if ss.paso == "inicio":
    pantalla_inicio()
elif ss.paso == "descarga":
    pantalla_descarga()
else:
    cabecera = st.container()
    meta, hay_cuenca, evaluada = pantalla_estaciones()
    with cabecera:
        estilo.barra(meta, {2, 3} if hay_cuenca else {1}, {1} if hay_cuenca else set(), pantalla="estaciones")

if ss.paso != "estaciones":
    estilo.pie()   # en la pantalla del mapa el pie va al final del panel "Consulta"
