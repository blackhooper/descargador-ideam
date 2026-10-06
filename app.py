import io
import json
import re
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
from modules.calidad import filtrar_descargables, clasificar_calidad

st.set_page_config(page_title="Descargador IDEAM", page_icon="🌧️", layout="wide", initial_sidebar_state="collapsed")

ss = st.session_state
for clave, valor in {"paso": "inicio", "cuenca": None, "version_mapa": 0, "estacion_sel": None,
                     "_prev_sel": {}, "descarga": None, "resultado": None, "descarga_en_curso": False,
                     "saltos": 0, "tema": "oscuro" if st.query_params.get("tema") == "oscuro" else "claro"}.items():
    ss.setdefault(clave, valor)

# Para saber si el mapa 2D sigue montado en el navegador: si la corrida anterior lo dibujo, es el mismo
ss._mapa_en_run_anterior = ss.get("_mapa_en_esta_run", False)
ss._mapa_en_esta_run = False

estilo.aplicar(ss.tema)
estilo.control_tema()
# Guion que colorea el relieve en la textura "Altura": se instala desde el arranque de la pagina (no cuesta nada
# si no se usa) para que ya este puesto antes de que el visor 3D pida sus imagenes
with st.container(key="y2k_hipso"):
    components.html(terreno.HIPSOMETRICO, height=0)
PALETA = estilo.PALETAS[ss.tema]

if not all(ideam_downloader.credenciales_ideam()):
    st.error("Faltan el usuario y la clave del portal DHIME del IDEAM. En tu computador van en "
             "`.streamlit/secrets.toml`; en Streamlit Cloud, en Settings → Secrets de la app, así:\n\n"
             "```toml\n[ideam]\nusuario = \"...\"\nclave = \"...\"\n```")
    st.stop()

catalogo = ideam_catalog.load_ideam_catalog()

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
    """El navegador se quedo sin memoria grafica: visor 3D nuevo y en version liviana."""
    ss.version_3d = ss.get("version_3d", 0) + 1
    ss.modo_3d_ligero = True


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
    estilo.ventana(f"Catálogo nacional · {_num(len(catalogo))} estaciones" if catalogo is not None else "")
    estilo.pasos({1}, set())
    st.markdown('<div class="y2k-hello"><h1>¿Dónde está tu cuenca?</h1><p>Elige cómo marcar el área. Después verás '
                'las estaciones del IDEAM que caen adentro y cuántos datos tiene cada una.</p></div>',
                unsafe_allow_html=True)
    _, c1, c2, _ = st.columns([0.5, 2, 2, 0.5], gap="medium")
    with c1, st.container(border=True):
        st.markdown(f'<div class="y2k-card-head">{estilo.ICONO_DIBUJAR}<div><h2>Dibujar en el mapa</h2>'
                    '<p>Traza un rectángulo, mueve sus esquinas y bórralo cuando quieras.</p></div></div>'
                    '<div class="y2k-chips"><span class="y2k-chip">rectángulo</span>'
                    '<span class="y2k-chip">editar</span><span class="y2k-chip">buffer</span></div>', unsafe_allow_html=True)
        if st.button("Dibujar mi cuenca", type="primary", use_container_width=True):
            ss.cuenca = None
            ss.version_mapa += 1
            ss.estacion_sel = None
            _ir("estaciones")
    with c2, st.container(border=True):
        st.markdown(f'<div class="y2k-card-head">{estilo.ICONO_SUBIR}<div><h2>Subir un archivo</h2>'
                    '<p>Si no trae sistema de coordenadas te lo avisamos antes de seguir.</p></div></div>'
                    '<div class="y2k-chips"><span class="y2k-chip">shp en zip</span><span class="y2k-chip">shp suelto</span>'
                    '<span class="y2k-chip">geojson</span><span class="y2k-chip">kml</span><span class="y2k-chip">kmz</span>'
                    '<span class="y2k-chip">gpkg</span></div>', unsafe_allow_html=True)
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
                            if st.button("Continuar con esta cuenca", type="primary", use_container_width=True):
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
    avanzado = st.toggle("Descarga avanzada (cada 2, 5 o 10 minutos)", key="avanzado",
                         help="Series con muchísimos datos. El IDEAM solo entrega 1 mes por consulta.")
    if avanzado:
        st.warning("⏳ El IDEAM entrega estos datos de a **1 mes por consulta**: 10 años son 120 consultas por "
                   "estación y cada Excel puede tener cientos de miles de filas. Usa rangos cortos y pocas estaciones.")
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
    st.markdown(f'<p class="y2k-hint">Serie <b>{param["etiqueta"]}</b> · el IDEAM entrega hasta '
                f'{f"{anios:.0f} años" if anios >= 1 else str(param["dias_bloque"]) + " días"} por consulta</p>',
                unsafe_allow_html=True)
    return param


def pantalla_estaciones():
    cuenca = ss.cuenca
    col_ctrl, col_mapa, col_res = st.columns([1.05, 2.35, 1.25], gap="medium")

    # ---------------- controles ----------------
    with col_ctrl, st.container(border=True):
        st.markdown("### CUENCA")
        if cuenca is None:
            st.markdown('<p class="y2k-hint">Dibuja tu cuenca con el <b>rectángulo</b> (arriba a la izquierda del mapa). '
                        'Con el <b>lápiz</b> mueves sus esquinas y con la <b>basurita</b> la borras.</p>',
                        unsafe_allow_html=True)
        buffer_on = st.toggle("Buffer alrededor de la cuenca", value=True, key="buf_on")
        buffer_km = st.slider("Distancia del buffer (km)", 0.5, 15.0, 2.0, 0.5, key="buf_km", disabled=not buffer_on)
        b1, b2 = st.columns(2)
        if b1.button("Borrar cuenca", use_container_width=True, disabled=cuenca is None):
            ss.cuenca = None
            ss.version_mapa += 1
            ss.estacion_sel = None
            st.rerun()
        if b2.button("← Inicio", use_container_width=True):
            _ir("inicio")
        st.divider()
        st.markdown("### PARÁMETRO")
        param = selector_parametro()
        f1, f2 = st.columns(2)
        fecha_ini = f1.date_input("Desde", date(2000, 1, 1), min_value=date(1920, 1, 1), key="f_ini", format="DD/MM/YYYY")
        fecha_fin = f2.date_input("Hasta", date(2020, 12, 31), min_value=date(1920, 1, 1), key="f_fin", format="DD/MM/YYYY")
        fechas_ok = fecha_ini < fecha_fin
        if not fechas_ok:
            st.error("La fecha de inicio debe ser anterior a la final.")
        st.divider()
        st.markdown("### FILTRO")
        umbral = st.slider("Cantidad probable mínima", 0, 100, 0, 5, format="%d%%", key="umbral",
                           help="Qué parte del periodo consultado debe cubrir el registro de la estación "
                                "(entre su primer y su último dato). No descuenta los huecos internos.")
        carpetas = st.checkbox("Carpetas por cobertura en el ZIP", value=True, key="carpetas",
                               help="Alta 70-100 %, Media 50-70 %, Baja 25-50 %, Crítica 0-25 % "
                                    "del periodo consultado")
        zona_boton = st.container()

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

    # ---------------- mapa ----------------
    with col_mapa:
        c_vista, c_tex = st.columns([1, 1])
        vista = c_vista.segmented_control("Vista", ["2D", "3D"], default="2D", key="vista",
                                          label_visibility="collapsed") or "2D"
        if vista == "3D":
            textura = c_tex.segmented_control("Textura", ["Satélite", "Topográfico", "Altura"], default="Satélite",
                                              key="textura", label_visibility="collapsed") or "Satélite"
            # Textura "Altura": colores segun la altitud, con la escala de la zona o la de todo Colombia
            altura, escala_alt = None, None
            if textura == "Altura":
                escala_alt = st.segmented_control("Escala de altura", ["Rango de la zona", "Rango de Colombia"],
                                                  default="Rango de la zona", key="escala_altura",
                                                  label_visibility="collapsed") or "Rango de la zona"
                altura = rango if (escala_alt == "Rango de la zona" and rango and rango[1] > rango[0]) else terreno.ALTURA_COLOMBIA
            if zona is None or zona.empty:
                st.info("Dibuja tu cuenca para verla en 3D.")
            else:
                # La cubierta "Alistando las estaciones" se ve mientras el servidor arma la escena y el
                # navegador baja el relieve; el guion de terreno.py la levanta cuando el relieve esta listo
                with st.container(key="y2k_visor3d"):
                    # (sin cubierta de carga: la espera ya la cubre el escaner; la animacion arranca sola cuando llega el relieve)
                    deck, orbita = terreno.construir_deck(cuenca, area if buffer_on else None,
                                                          _estaciones_3d(zona, umbral), ss.estacion_sel, textura,
                                                          PALETA, ligero=_es_celular() or ss.get("modo_3d_ligero", False),
                                                          altura=altura)
                    # La clave cambia con "Recargar vista 3D": asi Streamlit crea un visor nuevo desde cero
                    st.pydeck_chart(deck, height=terreno.ALTO_VISOR, on_select="rerun", selection_mode="single-object",
                                    key=f"mapa3d_{ss.get('version_3d', 0)}")
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
                # Secuencia de entrada (lasers, caida de pines, alertas): una sola vez por cuenca/buffer.
                # Se ata al turno de la vuelta para que el guion no cambie entre una recarga y otra
                firma_intro = json.dumps([[round(float(c), 5) for c in area.total_bounds], bool(buffer_on)])
                if disparar and (ss.get("_intro_firma") != firma_intro or repetir):
                    ss._intro_firma = firma_intro
                    ss._intro_turno = ss.orbita
                intro = ss.get("_intro_turno") == ss.get("orbita")
                with st.container(key="y2k_orbita"):
                    components.html(terreno.orbitar(orbita, ss.get("orbita", 0), intro), height=0)
                    components.html(terreno.AVISO_NAVEGADOR, height=0)
                    components.html(terreno.EXTRAS_3D, height=0)
                    # Botones ocultos: los pulsa el aviso de "sin memoria grafica" que pone EXTRAS_3D
                    st.button("Recargar vista 3D", key="y2k_recargar3d", on_click=_recargar_3d)
                    st.button("Ver en 2D", key="y2k_pasar2d", on_click=_pasar_a_2d)
                # TEMPORAL: para ver la animacion de entrada otra vez mientras se ajusta
                st.button("▶ Repetir animación (temporal)", key="y2k_repetir_intro",
                          on_click=lambda: ss.update(_repetir_intro=True))
                if altura:
                    st.markdown(terreno.leyenda_altura(altura[0], altura[1],
                                                       "escala de Colombia" if altura == terreno.ALTURA_COLOMBIA
                                                       else "escala de la zona"), unsafe_allow_html=True)
                st.caption("Relieve ×2 · toca el mapa para detener la vuelta · Ctrl + arrastrar para girar e inclinar")
                st.markdown(f'<p class="y2k-hint" style="margin-top:10px !important;text-align:right">'
                            f'{estilo.ATRIB_RELIEVE_3D_CORTO}</p>', unsafe_allow_html=True)
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
                        texto = f"{hay} estación{'es' if hay != 1 else ''} encontrada{'s' if hay != 1 else ''}"
                    elif zona.empty:
                        texto = "Sin estaciones aquí · prueba ampliar el buffer"
                    else:
                        texto = "Ninguna estación cumple el filtro"
                    escaner.listo(hay, texto)
            clic = (retorno or {}).get("last_object_clicked")
            if _sincronizar("mapa2d", clic, lambda c: _estacion_cercana(zona, c)):
                st.rerun()
            st.caption("Pasa el cursor por una estación para ver su ficha · clic para seleccionarla · "
                       "cambia el mapa base con el botón de capas (arriba a la derecha)")
        ss._vista_prev = vista

    # ---------------- resumen ----------------
    with col_res, st.container(border=True):
        if cuenca is not None and param is not None and fechas_ok and zona is not None and not evaluada and not zona.empty:
            st.info("Consultando el IDEAM...")
        elif param is not None and fechas_ok:
            panel_estadisticas.mostrar_panel(zona, seleccion if seleccion is not None else None, param,
                                             fecha_ini, fecha_fin, umbral, ss.estacion_sel, tabla, ss.tema,
                                             dudosas, rango, vista)

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
        if st.button(f"Iniciar extracción · {n} estaciones", type="primary", use_container_width=True,
                     disabled=n == 0 or excede or param is None):
            ss.descarga = {"estaciones": seleccion.copy(), "param": param, "ini": fecha_ini, "fin": fecha_fin,
                           "carpetas": carpetas}
            ss.resultado = None
            ss.descarga_en_curso = False
            ss.pop("nombre_zip", None)  # cada descarga nueva arranca con su nombre sugerido
            _ir("descarga")
        # El portal obliga a aceptar sus terminos antes de cada descarga; la herramienta se salta
        # esa pantalla, asi que muestra lo esencial aqui, junto al boton (no en un modal)
        estilo.aviso_legal(TEXTO_LEGAL)

    return "", cuenca is not None, evaluada


# ===========================================================================
# Pantalla 3: la descarga
# ===========================================================================
def pantalla_descarga():
    d = ss.descarga
    lista = bool(ss.resultado) and "error" not in ss.resultado
    estilo.ventana((f"Descarga lista · {d['param']['etiqueta']} · Fuente: IDEAM" if lista
                    else f"Descargando {d['param']['etiqueta']} · Fuente: IDEAM") if d else "")
    estilo.pasos({4}, {1, 2, 3})
    if d is None:
        st.info("No hay ninguna descarga preparada.")
        if st.button("← Volver a estaciones"):
            _ir("estaciones")
        return

    col_esc, col_con = st.columns([1.6, 1], gap="medium")
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
                    aviso.info(f"⏳ Hay {ideam_downloader.MAX_DESCARGAS_SIMULTANEAS} descargas en curso en el servidor "
                               f"y la tuya es la número {puesto} en la fila. Empieza sola {cuando} "
                               f"(llevas {ideam_downloader.formatear_duracion(time.time() - inicio_espera)} esperando).")
            finally:
                with turnos["candado"]:
                    if turno in turnos["fila"]:
                        turnos["fila"].remove(turno)
        with turnos["candado"]:
            turnos["en_curso"][turno] = (time.time(), segundos)
        try:
            espera.empty()
            with col_esc:
                escena_descarga.mostrar("vivo", total=len(d["estaciones"]), segundos_estimados=segundos)
                ui = {"barra": st.empty(), "estado": st.empty(), "oculto": st.empty()}
                st.button("🛑 Detener descarga", key="detener")
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
        st.warning("Descarga detenida. Puedes volver a intentarlo o cambiar la selección.")
        c1, c2 = st.columns(2)
        if c1.button("Reintentar", type="primary", use_container_width=True):
            st.rerun()
        if c2.button("← Volver a estaciones", use_container_width=True):
            _ir("estaciones")
        return

    if "error" in resultado:
        st.error(resultado["error"])
        if st.button("← Volver a estaciones"):
            _ir("estaciones")
        return

    with col_esc:
        escena_descarga.mostrar("final", total=len(resultado["colores"]), colores_finales=resultado["colores"],
                                subtitulo=f"{resultado['guardadas']} estaciones · {resultado['omitidas']} omitidas"
                                          f" · Fuente: IDEAM · DHIME")
        st.markdown(estilo.barra_pixel(1.0), unsafe_allow_html=True)
        st.markdown(f'<div class="y2k-pmeta"><span><b>100 %</b> · listo en <b>{resultado["duracion"]}</b></span>'
                    f'<span>Guardadas <b>{resultado["guardadas"]}</b> · Omitidas <b>{resultado["omitidas"]}</b></span></div>',
                    unsafe_allow_html=True)
        ini, fin = resultado["rango"]
        predeterminado = f"IDEAM_{resultado['etiqueta']}_{ini:%Y%m%d}-{fin:%Y%m%d}"
        nombre = st.text_input("Nombre del archivo ZIP", value=predeterminado, key="nombre_zip", max_chars=120,
                               help="Por ejemplo: descarga 1. La extensión .zip se añade sola.")
        st.markdown('<p class="y2k-hint">Escribe el nombre y presiona <b>Enter</b> antes de descargar.</p>',
                    unsafe_allow_html=True)
        st.download_button("⬇️ Descargar ZIP con los Excel", data=resultado["zip"], type="primary",
                           file_name=f"{_nombre_archivo(nombre, predeterminado)}.zip",
                           mime="application/zip", use_container_width=True)
        # Recordatorio de las condiciones de uso del IDEAM en el momento de la entrega
        estilo.aviso_legal(TEXTO_LEGAL)
        c1, c2 = st.columns(2)
        if c1.button("← Volver a estaciones", use_container_width=True):
            _ir("estaciones")
        if c2.button("Nueva cuenca", use_container_width=True):
            ss.cuenca = None
            ss.version_mapa += 1
            _ir("inicio")
    with col_con, st.container(border=True):
        st.markdown("### RESUMEN")
        try:
            with zipfile.ZipFile(io.BytesIO(resultado["zip"])) as z:
                resumen = pd.read_csv(io.BytesIO(z.read("resumen_descarga.csv")))
            columnas = [c for c in ["Nombre", "Cobertura", "Clase", "Resultado", "Detalle"] if c in resumen.columns]
            st.dataframe(resumen[columnas], hide_index=True,
                         use_container_width=True, height=380)
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
        estilo.ventana(meta)
        estilo.pasos({2, 3} if hay_cuenca else {1}, {1} if hay_cuenca else set())

estilo.pie()
