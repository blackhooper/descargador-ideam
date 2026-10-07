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
for clave, valor in {"paso": "mapa", "vista": "2D", "cuenca": None, "version_mapa": 0, "version_subida": 0, "estacion_sel": None,
                     "_prev_sel": {}, "descarga": None, "resultado": None, "descarga_en_curso": False,
                     "saltos": 0,
                     "tema": _q.get("tema") if _q.get("tema") in estilo.TEMAS else "sistema",
                     "contraste": _q.get("contraste") if _q.get("contraste") in estilo.CONTRASTES else "sistema",
                     "lite": _q.get("lite") == "1"}.items():
    ss.setdefault(clave, valor)
if ss.paso != "descarga":
    ss.paso = "mapa"   # antes habia una pantalla de inicio y otra de estaciones; ahora todo pasa sobre el mapa

# Para saber si el mapa 2D sigue montado en el navegador: si la corrida anterior lo dibujo, es el mismo
ss._mapa_en_run_anterior = ss.get("_mapa_en_esta_run", False)
ss._mapa_en_esta_run = False

estilo.aplicar(ss.tema, ss.contraste, ss.lite)
estilo.guiones_globales()
# Guion que colorea el relieve en la textura "Altura": se instala desde el arranque de la pagina (no cuesta nada
# si no se usa) para que ya este puesto antes de que el visor 3D pida sus imagenes
with st.container(key="y2k_hipso"):
    components.html(terreno.HIPSOMETRICO, height=0)
# Aqui (arriba, sin alto) se pone despues el CSS que tapa el visor 3D mientras arranca la secuencia de entrada
velo_3d = st.container(key="y2k_velo")
PALETA = estilo.paleta(ss.tema)
# Capsulas de arriba (vidrio): marca y utilidades (Lite, Apariencia, Manual)
estilo.marca("descarga" if ss.paso == "descarga" else "mapa")
estilo.control_tema()

if not all(ideam_downloader.credenciales_ideam()):
    st.error("Faltan el usuario y la clave del portal DHIME del IDEAM. En tu computador van en "
             "`.streamlit/secrets.toml`; en Streamlit Cloud, en Settings → Secrets de la app, así:\n\n"
             "```toml\n[ideam]\nusuario = \"...\"\nclave = \"...\"\n```")
    st.stop()

catalogo = ideam_catalog.load_ideam_catalog()


@st.cache_resource(show_spinner=False)
def _iniciar_precarga_servidor():
    """La lista de parametros del IDEAM tarda unos segundos (decenas de consultas). Se pide por detras apenas arranca
    el servidor; mientras tanto el mapa ya se puede usar y "Consulta" avisa que la lista esta cargando.
    Devuelve el estado compartido: {"listo": bool, "error": str | None}."""
    estado = {"listo": False, "error": None}

    def trabajo():
        try:
            ideam_parameters.obtener_catalogo_parametros()
        except Exception as e:  # sin red o IDEAM caido: el error se muestra al pedir la lista de nuevo
            estado["error"] = str(e)
        finally:
            estado["listo"] = True

    threading.Thread(target=trabajo, daemon=True, name="precarga-ideam").start()
    return estado


_precarga = _iniciar_precarga_servidor()

# Condiciones de uso de los datos (terminos del portal DHIME), junto al boton de descarga
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


def _borrar_cuenca():
    ss.cuenca = None
    ss.version_mapa += 1
    ss.estacion_sel = None


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
    revision = [terreno.revisar_altitud(r.get("altitud"), r.geometry.x, r.geometry.y) for _, r in zona.iterrows()]
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
            "alerta": f"⚠ Altitud dudosa: el relieve marca {_num(r['terreno'])} m" if dudosa else "",
            "terreno": r.get("terreno"),
            "dudosa": dudosa,
        })
    return salida


def _ir(paso):
    ss.paso = paso
    st.rerun()


# ===========================================================================
# Piezas del panel "Consulta"
# ===========================================================================
def subir_cuenca():
    """Contorno de la cuenca desde un archivo (desplegable dentro del paso 1)."""
    with st.container(key="y2k_subida"), st.expander("Subir un archivo", icon=":material/upload_file:"):
        st.html('<p class="y2k-hint">Contorno de la cuenca en SHP (en ZIP o suelto), GeoJSON, KML, KMZ o GPKG. '
                'Si el archivo no trae sistema de coordenadas, te avisaremos.</p>')
        # la clave cambia al usar el archivo: asi el cargador queda vacio para la siguiente vez
        archivos = st.file_uploader("Archivo de la cuenca", type=geo_input.EXTENSIONES_ACEPTADAS,
                                    accept_multiple_files=True, label_visibility="collapsed",
                                    key=f"subida_{ss.version_subida}")
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
            st.error("El archivo solo tiene puntos o líneas. Sube el contorno (polígono) de la cuenca.")
            return
        if mensaje != "Geometría válida.":
            st.warning(mensaje)
        st.success(f"Archivo válido: {len(poligonos)} {'polígonos' if len(poligonos) != 1 else 'polígono'}.")
        if st.button("Usar esta cuenca", type="primary", width="stretch", key="usar_subida"):
            ss.cuenca = poligonos[["geometry"]].reset_index(drop=True)
            ss.version_mapa += 1
            ss.version_subida += 1
            ss.estacion_sel = None
            st.rerun()


def selector_parametro():
    if not _precarga["listo"]:
        # La lista se pide por detras al arrancar el servidor: el mapa no espera por ella
        st.html('<p class="y2k-hint" role="status">Cargando la lista de parámetros del IDEAM…</p>')
        return None
    try:
        catalogo_param = ideam_parameters.obtener_catalogo_parametros()
    except ideam_downloader.ErrorAccesoIDEAM as e:
        st.error(str(e))
        return None
    except Exception as e:
        st.error(f"No se pudo cargar la lista de parámetros del IDEAM: {e}")
        return None
    avanzado = st.toggle("Series cada 2, 5 o 10 minutos", key="avanzado",
                         help="Descarga avanzada: series con muchísimos datos. El IDEAM entrega solo un mes por consulta.")
    if avanzado:
        st.warning("El IDEAM entrega estos datos de **un mes por consulta** (10 años = 120 consultas por estación). "
                   "Usa periodos cortos y pocas estaciones.", icon=":material/hourglass_top:")
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


# ===========================================================================
# Pantalla del mapa: buscar, marcar la cuenca, revisar las estaciones y descargar
# ===========================================================================
def pantalla_mapa():
    cuenca = ss.cuenca
    # Disposicion: el mapa ocupa la ventana (escenario). Encima flotan, en vidrio: la capsula 2D/3D (y las texturas
    # del 3D), el panel con las pestanas "Consulta" y "Resumen" (en el celular, una hoja inferior), la isla de accion
    # con el siguiente paso y la ficha de la estacion elegida. Plegar el panel, cambiar de pestana o mover la hoja lo
    # hace el navegador (estilo.instalar_ui), sin recargar la pagina.
    with st.container(key="y2k_modo"):
        # sin "default": el valor sale de la sesion (lo cambian tambien la ficha, la lista de altitudes y los avisos)
        vista = st.segmented_control("Vista del mapa", ["2D", "3D"], key="vista", required=True,
                                     label_visibility="collapsed") or "2D"
    textura, escala_alt = "Satélite", None
    with st.container(key="y2k_tex3d", horizontal=True, gap=None, vertical_alignment="center",
                      horizontal_alignment="center"):
        if vista == "3D":
            textura = st.segmented_control("Textura del relieve", ["Satélite", "Topográfico", "Altura"], default="Satélite",
                                           key="textura", required=True, label_visibility="collapsed") or "Satélite"
            # Textura "Altura": colores segun la altitud, con la escala de la zona o la de todo Colombia
            if textura == "Altura":
                escala_alt = st.segmented_control("Escala de colores", ["Rango de la zona", "Rango de Colombia"],
                                                  default="Rango de la zona", key="escala_altura", required=True,
                                                  format_func=lambda e: e.replace("Rango", "Escala"),
                                                  label_visibility="collapsed") or "Rango de la zona"
    with st.container(key="y2k_panel"):
        cab_panel = st.container(key="y2k_panel_cab")
        col_ctrl = st.container(key="y2k_consulta")
        col_res = st.container(key="y2k_resumen")
    with st.container(key="y2k_dock"):
        dock_fila = st.container(key="y2k_dock_fila", horizontal=True, gap="small", wrap=False,
                                 vertical_alignment="center")
        dock_avisos = st.container()
        dock_carga = st.container()
    escenario = st.container(key="y2k_escenario")
    # Botones ocultos: los pulsan los avisos de fallo del navegador (siempre por eleccion del usuario)
    with st.container(key="y2k_ocultos"):
        st.button("Activar Lite y reintentar", key="y2k_lite_reintentar", on_click=_lite_reintentar)
        st.button("Seguir intentando", key="y2k_reintentar3d", on_click=_recargar_3d)
        st.button("Ver en 2D", key="y2k_pasar2d", on_click=_pasar_a_2d)
        if not _precarga["listo"]:
            # Este fragmento se repite cada segundo hasta que el servidor tiene la lista de parametros; entonces
            # recarga la pagina una vez (y deja de repetirse)
            @st.fragment(run_every=1.0)
            def _vigilar_precarga():
                if _precarga["listo"]:
                    st.rerun()
            _vigilar_precarga()

    # ---------------- Consulta: tres pasos ----------------
    with col_ctrl:
        area_km2 = _area_km2(cuenca) if cuenca is not None else None
        estilo.paso(1, "Cuenca", hecho=cuenca is not None, estado=f"≈ {_num(area_km2)} km²" if area_km2 else "")
        if vista == "3D":
            st.html('<p class="y2k-hint">Para marcar o cambiar la cuenca, vuelve a la vista 2D.</p>')
        else:
            estilo.opciones_cuenca(cuenca is not None)
            estilo.detalles("", "<p>Pulsa <b>Dibujar un rectángulo</b> (o la herramienta del mapa, arriba a la izquierda) "
                                "y arrastra sobre el mapa. Con el <b>lápiz</b> ajustas las esquinas y con la "
                                "<b>papelera</b> borras la cuenca; un rectángulo nuevo reemplaza al anterior.</p>"
                                "<p>Con el teclado: lleva el foco al mapa, muévete con las flechas, acerca con + y "
                                "pulsa <b>Usar el área visible</b>.</p>"
                                "<p>Pasa el cursor sobre una estación para ver sus datos y haz clic para seleccionarla. "
                                "El botón de capas (arriba a la derecha) cambia el mapa base.</p>",
                            ver="Cómo usar el mapa")
        subir_cuenca()
        buffer_on = st.toggle("Buffer alrededor de la cuenca", value=True, key="buf_on",
                              help="Incluye también las estaciones cercanas a la cuenca.")
        buffer_km = st.slider("Distancia del buffer (km)", 0.5, 15.0, 2.0, 0.5, key="buf_km", disabled=not buffer_on)
        if cuenca is not None:
            st.button("Borrar la cuenca", key="borrar_cuenca", icon=":material/delete:", width="stretch",
                      on_click=_borrar_cuenca)
        cab_paso2 = st.container()
        param = selector_parametro()
        f1, f2 = st.columns(2)
        fecha_ini = f1.date_input("Desde", date(2000, 1, 1), min_value=date(1920, 1, 1), key="f_ini", format="DD/MM/YYYY")
        fecha_fin = f2.date_input("Hasta", date(2020, 12, 31), min_value=date(1920, 1, 1), key="f_fin", format="DD/MM/YYYY")
        fechas_ok = fecha_ini < fecha_fin
        if not fechas_ok:
            st.error("La fecha inicial debe ser anterior a la final.")
        with cab_paso2:
            estilo.paso(2, "Parámetro y fechas", hecho=param is not None and fechas_ok)
        estilo.paso(3, "Filtro y archivo", estado="Opcional")
        umbral = st.slider("Cantidad probable mínima", 0, 100, 0, 5, format="%d %%", key="umbral",
                           help="Qué parte del periodo consultado debe cubrir el registro de la estación "
                                "(entre su primer y su último dato). No descuenta los huecos internos.")
        carpetas = st.checkbox("Separar en carpetas por cobertura", value=True, key="carpetas",
                               help="Alta (70–100 %), media (50–70 %), baja (25–50 %) y crítica (0–25 %) del periodo "
                                    "consultado.")
        estilo.pie()

    # ---------------- estaciones de la cuenca + evaluacion ----------------
    zona = area = None
    seleccion = None
    evaluada = False
    error_ideam = None
    if cuenca is not None and catalogo is not None:
        area = geo_utils.create_buffer(cuenca, buffer_km if buffer_on else 0)
        zona = geo_utils.filter_stations(catalogo, area)
        union = cuenca.union_all()
        zona["zona"] = ["cuenca" if union.covers(g) else "buffer" for g in zona.geometry]
        if not zona.empty:
            with dock_carga, st.spinner("Comparando la altitud de las estaciones con el relieve…"):
                _revisar_altitudes(zona)
        if param is not None and fechas_ok and not zona.empty:
            try:
                with dock_carga, st.spinner("Consultando en el IDEAM qué datos tiene cada estación…"):
                    calidad = ideam_parameters.get_metadata_availability(zona, param, fecha_ini, fecha_fin)
                for columna in ["Cantidad Probable", "Esperados", "Porcentaje (%)", "Clase calidad",
                                "Serie DHIME", "Inicio serie", "Fin serie"]:
                    zona[columna] = calidad[columna].values
                evaluada = True
            except ideam_downloader.ErrorAccesoIDEAM as e:
                error_ideam = str(e)
            except Exception as e:
                error_ideam = f"No se pudo consultar el IDEAM: {e}"
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
    # Lista de altitudes dudosas: al elegir una se muestra en el mapa 3D (el cambio a 3D lo hace el callback de la
    # tabla, antes de dibujar el selector 2D/3D)
    dudosas = panel_estadisticas.tabla_dudosas(zona)
    v = ss.get("tabla_dudosas") or {}
    filas = (v.get("selection") or {}).get("rows", [])
    cambio_sel |= _sincronizar("dudosas", filas, lambda f: dudosas.iloc[f[0]]["Código"] if f and f[0] < len(dudosas) else None)
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
        if vista == "3D":
            if zona is None or zona.empty:
                estilo.sobre_mapa("Marca tu cuenca en la vista 2D para verla en relieve." if cuenca is None else
                                  "No hay estaciones en esta zona. Activa o amplía el buffer.", "y2k-vacio")
            else:
                altura = None
                if textura == "Altura":
                    altura = (rango if (escala_alt == "Rango de la zona" and rango and rango[1] > rango[0])
                              else terreno.ALTURA_COLOMBIA)
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
                    estilo.leyenda_altura(terreno.leyenda_altura(
                        altura[0], altura[1], "escala de Colombia" if altura == terreno.ALTURA_COLOMBIA else "escala de la zona"))
                else:
                    estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD], en3d=True)
                estilo.sobre_mapa(estilo.ATRIB_RELIEVE_3D_CORTO, "y2k-atrib3d", "lg-claro")
        else:
            # El mapa base solo lleva la cuenca cuando el mapa se monta de cero (archivo, volver del 3D,
            # "Borrar la cuenca"). Un rectangulo recien dibujado ya vive en el navegador: meterlo al mapa
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
            # El alto real lo pone el CSS (llena la ventana); 650 es solo el valor inicial del componente
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
                        texto = "No hay estaciones aquí · amplía el buffer"
                    else:
                        texto = "Ninguna estación cumple el filtro"
                    escaner.listo(hay, texto)
            clic = (retorno or {}).get("last_object_clicked")
            if _sincronizar("mapa2d", clic, lambda c: _estacion_cercana(zona, c)):
                st.rerun()
            if cuenca is not None:
                estilo.leyenda_estaciones([(f"{c[1]} {c[2]}", c[4]) for c in CLASES_CALIDAD])
        ss._vista_prev = vista

    # ---------------- Resumen ----------------
    n_sel = len(seleccion) if evaluada and seleccion is not None else None
    cifras = (panel_estadisticas.cifras_seleccion(seleccion, param, fecha_ini, fecha_fin)
              if evaluada and n_sel else None)
    with col_res:
        if error_ideam:
            st.error(error_ideam)
        elif cuenca is None:
            st.html('<p class="y2k-hint">Marca tu cuenca para ver aquí cuántas estaciones hay y qué datos tienen.</p>')
        elif param is None or not fechas_ok:
            st.html('<p class="y2k-hint">Elige un parámetro y fechas válidas para ver el resumen.</p>')
        else:
            panel_estadisticas.mostrar_panel(zona, seleccion, param, fecha_ini, fecha_fin, umbral, ss.estacion_sel,
                                             tabla, PALETA, dudosas, rango, cifras)
        if vista == "3D" and zona is not None and not zona.empty:
            # TEMPORAL: para ver la animacion de entrada otra vez mientras se ajusta (quitar antes de presentar)
            with st.expander("Ajustes de la animación 3D (temporal)", icon=":material/tune:"):
                st.button("Repetir animación", key="y2k_repetir_intro", icon=":material/replay:",
                          on_click=lambda: ss.update(_repetir_intro=True), disabled=ss.lite,
                          help="En modo Lite no hay animación de entrada." if ss.lite else None)
                st.slider("Altura de salida de láseres y estaciones (× distancia de la cámara)",
                          0.5, 4.0, 1.7, 0.1, key="apex_factor",
                          help="Más bajo: salen más cerca y caen más inclinados. Más alto: caen casi verticales. "
                               "Se aplica al pulsar «Repetir animación».")
    with cab_panel:
        estilo.pestanas(n_sel)

    # ---------------- isla de accion: estado y siguiente paso ----------------
    n = 0 if seleccion is None else len(seleccion)
    filas_estacion = (ideam_parameters.filas_estimadas(param, fecha_ini, fecha_fin)
                      if param is not None and fechas_ok else 0)
    excede = filas_estacion > ideam_parameters.MAX_FILAS_EXCEL
    listo = evaluada and n > 0 and not excede
    with dock_fila:
        if cuenca is None:
            if vista == "3D":
                estilo.estado_accion("Marca tu cuenca para empezar", "Vuelve a la vista 2D para dibujarla o sube un archivo.")
                st.button("Ir a 2D", key="dock_2d", type="primary", on_click=_pasar_a_2d)
            else:
                estilo.estado_accion("Marca tu cuenca para empezar", "Dibuja un rectángulo en el mapa o sube un archivo.")
                estilo.botones_inicio()
        elif zona is not None and zona.empty:
            estilo.estado_accion("No hay estaciones en esta zona", "Activa o amplía el buffer en", ("Consulta", "consulta"),
                                 alerta=True)
        elif error_ideam:
            estilo.estado_accion("No se pudo consultar el IDEAM", "El detalle está en", ("Resumen", "resumen"), alerta=True)
        elif param is None:
            estilo.estado_accion(f"{len(zona)} estaciones en la zona" if zona is not None else "Cuenca marcada",
                                 "Cargando la lista de parámetros del IDEAM…" if not _precarga["listo"] else
                                 "Elige el parámetro en", None if not _precarga["listo"] else ("Consulta", "consulta"))
        elif not fechas_ok:
            estilo.estado_accion("Revisa las fechas", "La fecha inicial debe ser anterior a la final.",
                                 ("Ir a Consulta", "consulta"), alerta=True)
        elif excede:
            estilo.estado_accion("El periodo es demasiado largo",
                                 f"Con frecuencia {param['frecuencia'].lower()}, daría hasta {_num(filas_estacion)} filas "
                                 "por estación y Excel admite alrededor de un millón por hoja. Acorta el periodo.",
                                 alerta=True)
        elif n == 0:
            estilo.estado_accion("Ninguna estación cumple el filtro",
                                 "Baja la cantidad probable mínima o cambia las fechas en", ("Consulta", "consulta"),
                                 alerta=True)
        else:
            estilo.estado_accion(f"{n} {'estaciones listas' if n != 1 else 'estación lista'}"
                                 '<span class="y2k-ancho"> para descargar</span>',
                                 f"{param['descripcion']} · {_periodo(fecha_ini, fecha_fin)} · "
                                 f"{panel_estadisticas.duracion_aprox(cifras['segundos'])}",
                                 ("Ver resumen", "resumen"), sep=" · ")
        if cuenca is not None and evaluada:
            if st.button("Iniciar descarga", type="primary", icon=":material/download:", key="iniciar_descarga",
                         disabled=not listo):
                ss.descarga = {"estaciones": seleccion.copy(), "param": param, "ini": fecha_ini, "fin": fecha_fin,
                               "carpetas": carpetas}
                ss.resultado = None
                ss.descarga_en_curso = False
                ss.pop("nombre_zip", None)  # cada descarga nueva arranca con su nombre sugerido
                _ir("descarga")
    if cuenca is not None and evaluada:
        # El portal obliga a aceptar sus terminos antes de cada descarga; la herramienta se salta esa pantalla,
        # asi que muestra lo esencial aqui, junto al boton
        with dock_avisos:
            estilo.aviso_legal(TEXTO_LEGAL)

    # ---------------- ficha de la estacion elegida (flotante) ----------------
    with st.container(key="y2k_ficha"):
        if ss.estacion_sel and zona is not None and not zona.empty:
            fila = zona[[ideam_downloader.codigo_de_estacion(r, i) == ss.estacion_sel for i, r in zona.iterrows()]]
            if not fila.empty:
                panel_estadisticas.tarjeta_seleccionada(fila.iloc[0], rango, vista)


# ===========================================================================
# Pantalla de la descarga
# ===========================================================================
def pantalla_descarga():
    d = ss.descarga
    with st.container(key="y2k_descarga"):
        if d is None:
            st.info("No hay ninguna descarga preparada.")
            if st.button("Volver al mapa", icon=":material/arrow_back:"):
                _ir("mapa")
            return
        lista = bool(ss.resultado) and "error" not in ss.resultado
        n = len(d["estaciones"])
        estilo.md(f'<div class="y2k-encabezado"><h1>{"Descarga lista" if lista else "Descargando datos del IDEAM"}</h1>'
                  f'<p>{d["param"]["descripcion"]} · {_periodo(d["ini"], d["fin"])} · {n} '
                  f'{"estaciones" if n != 1 else "estación"} · Fuente: IDEAM · DHIME</p></div>')
        col_esc, col_con = st.columns([1.6, 1], gap="medium")
        col_esc = col_esc.container(key="y2k_card_descarga")
        resultado = ss.resultado

        if resultado is None and not ss.descarga_en_curso:
            if ss.get("cancelar_espera"):
                _ir("mapa")
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
                        cuando = (f"en ≈ {ideam_downloader.formatear_duracion(falta)}" if falta >= 5
                                  else "en cualquier momento")
                        aviso.info(f"El servidor está ocupado: hay {ideam_downloader.MAX_DESCARGAS_SIMULTANEAS} descargas "
                                   f"en curso. Eres el número {puesto} en la fila y la tuya empezará sola {cuando} "
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
                    st.button("Detener la descarga", key="detener", icon=":material/stop_circle:")
                with col_con, st.container(key="y2k_card_consola"):
                    st.html('<p class="y2k-titulo-seccion">Registro</p>')
                    ui["consola"] = st.empty()
                ss.descarga_en_curso = True
                resultado = ideam_downloader.procesar_descargas(d["estaciones"], d["carpetas"], d["ini"], d["fin"],
                                                                d["param"], ui)
                ss.descarga_en_curso = False
                ss.resultado = resultado or {"error": "No se pudo completar la descarga."}
            finally:
                # Se libera el turno siempre: al terminar, al pulsar "Detener" o si se cierra la pestaña
                with turnos["candado"]:
                    turnos["en_curso"].pop(turno, None)
                cupos.release()
            st.rerun()

        if resultado is None:
            # Se pulso "Detener" a mitad de la descarga
            ss.descarga_en_curso = False
            with col_esc:
                st.warning("Descarga detenida. Puedes reintentarla o volver al mapa para cambiar la selección.")
                c1, c2 = st.columns(2)
                if c1.button("Reintentar", type="primary", width="stretch", icon=":material/replay:"):
                    st.rerun()
                if c2.button("Volver al mapa", width="stretch", icon=":material/arrow_back:"):
                    _ir("mapa")
            return

        if "error" in resultado:
            with col_esc:
                st.error(resultado["error"])
                if st.button("Volver al mapa", icon=":material/arrow_back:"):
                    _ir("mapa")
            return

        with col_esc:
            escena_descarga.mostrar("final", total=len(resultado["colores"]), colores_finales=resultado["colores"],
                                    subtitulo=f"{resultado['guardadas']} estaciones · {resultado['omitidas']} omitidas"
                                              f" · Fuente: IDEAM · DHIME", lite=ss.lite)
            st.markdown(estilo.barra_pixel(1.0), unsafe_allow_html=True)
            st.markdown(f'<div class="y2k-pmeta"><span><b>100 %</b> · lista en <b>{resultado["duracion"]}</b></span>'
                        f'<span>Guardadas <b>{resultado["guardadas"]}</b> · Omitidas <b>{resultado["omitidas"]}</b></span></div>',
                        unsafe_allow_html=True)
            ini, fin = resultado["rango"]
            predeterminado = f"IDEAM_{resultado['etiqueta']}_{ini:%Y%m%d}-{fin:%Y%m%d}"
            nombre = st.text_input("Nombre del archivo ZIP", value=predeterminado, key="nombre_zip", max_chars=120,
                                   help="Por ejemplo: descarga 1. La extensión .zip se añade sola.")
            st.html('<p class="y2k-hint">Si cambias el nombre, pulsa <b>Enter</b> antes de descargar.</p>')
            st.download_button("Descargar el ZIP con los Excel", data=resultado["zip"], type="primary",
                               file_name=f"{_nombre_archivo(nombre, predeterminado)}.zip", icon=":material/download:",
                               mime="application/zip", width="stretch")
            # Recordatorio de las condiciones de uso del IDEAM en el momento de la entrega
            estilo.aviso_legal(TEXTO_LEGAL)
            c1, c2 = st.columns(2)
            if c1.button("Volver al mapa", width="stretch", icon=":material/arrow_back:"):
                _ir("mapa")
            if c2.button("Nueva cuenca", width="stretch", icon=":material/add_location_alt:"):
                ss.cuenca = None
                ss.version_mapa += 1
                ss.estacion_sel = None
                _ir("mapa")
        with col_con, st.container(key="y2k_card_resumen_zip"):
            st.html('<p class="y2k-titulo-seccion">Resumen por estación</p>')
            try:
                with zipfile.ZipFile(io.BytesIO(resultado["zip"])) as z:
                    resumen = pd.read_csv(io.BytesIO(z.read("resumen_descarga.csv")))
                columnas = [c for c in ["Nombre", "Cobertura", "Clase", "Resultado", "Detalle"] if c in resumen.columns]
                st.dataframe(resumen[columnas].fillna(""), hide_index=True, width="stretch", height=380)
            except Exception:
                st.caption("El detalle está en resumen_descarga.csv, dentro del ZIP.")
        estilo.pie()


# ===========================================================================
if ss.paso == "descarga":
    pantalla_descarga()
else:
    pantalla_mapa()
