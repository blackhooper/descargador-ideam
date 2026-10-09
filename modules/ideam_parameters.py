import math
import re
import time
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from modules import ideam_downloader
from modules.calidad import clasificar_calidad

# ===========================================================================
# CATALOGO DE VARIABLES Y PARAMETROS DEL IDEAM
# ---------------------------------------------------------------------------
# Se lee de los mismos servicios que usa la pagina del IDEAM y se ofrece igual que ella:
#   - Estandar: variable y luego parametro. Los parametros salen de GestionDatos/ConsultarInformacionSeriesTiempoGD
#     y solo se ofrecen los que la pagina muestra al publico (Visible = true; de los ~950 que existen, el resto son
#     internos o de prueba), en su mismo orden. Incluye los de alta frecuencia (cada pocos minutos), que el IDEAM
#     entrega de a un mes por consulta.
#   - Especial: frecuencia (Decadal o Multianual), variable y parametro. Son calculos del IDEAM sobre una serie
#     base (suma, maximo, minimo o promedio de cada decada; minimo, media y maximo de cada mes en todo el periodo)
#     y salen de la tabla SERIESTIEMPOCALCULO_VIEW del servicio de mapas de DHIME, con el texto de la pagina:
#     "Dia pluviometrico |SUM [PTPM_CON]".
# Solo se ofrecen las variables que tienen parametros en la serie (y frecuencia) elegida.
# ===========================================================================

# Frecuencias de la serie especial, en el orden de la pagina (es una lista fija en ella)
FRECUENCIAS_ESPECIALES = ["Decadal", "Multianual"]
# Datos cada pocos minutos: el IDEAM solo entrega 1 mes por consulta
FRECUENCIAS_AVANZADAS = ["Cada 10 Minutos", "Cada 05 Minutos", "Cada 02 Minutos", "Minutal"]

# Segundos entre datos de cada frecuencia (para estimar cuantos datos caben)
SEGUNDOS_POR_FRECUENCIA = {
    "Anual": 365 * 86400, "Mensual": 30 * 86400, "Decadal": 10 * 86400, "Diario": 86400,
    "03 Veces al Día": 8 * 3600, "02 Veces al Día": 12 * 3600, "Horario": 3600,
    "Cada 10 Minutos": 600, "Cada 05 Minutos": 300, "Cada 02 Minutos": 120, "Minutal": 60,
}
# Una serie multianual trae siempre 36 datos: minimo, media y maximo de cada mes del ano en el periodo
FILAS_MULTIANUAL = 36


def segundos_de(frecuencia):
    """Segundos entre datos de una frecuencia (por defecto, un dia)."""
    return SEGUNDOS_POR_FRECUENCIA.get(frecuencia, 86400)

# Excel no admite mas de 1.048.576 filas por hoja
MAX_FILAS_EXCEL = 1_000_000


def _inferir_frecuencia(etiqueta, periodicidad, defecto="Diario"):
    """Algunos parametros no traen periodicidad; se deduce del final de la etiqueta."""
    if periodicidad and periodicidad != "Desconocida":
        return periodicidad
    sufijo = re.search(r"_([DMAH])$", etiqueta or "")
    return {"D": "Diario", "M": "Mensual", "A": "Anual", "H": "Horario"}.get(
        sufijo.group(1) if sufijo else "", defecto
    )


def _descripcion(texto, etiqueta):
    """Descripcion del IDEAM; algunas vienen vacias o con el texto "null" (la pagina lo muestra asi): la etiqueta."""
    texto = str(texto or "").strip()
    return etiqueta if texto in ("", "null") else texto


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def obtener_limites_por_frecuencia():
    """
    Años maximos por consulta segun la frecuencia (ej. Diario 30, Horario 10,
    cada 10 minutos 0.083 = 1 mes). Si una frecuencia aparece dos veces se
    toma el limite mas bajo.
    """
    limites = {}
    for restriccion in ideam_downloader.consultar_api("Restricciones/GestionDatos"):
        nombre, anios = restriccion["descripcion"], float(restriccion["nroAnual"])
        limites[nombre] = min(anios, limites.get(nombre, anios))
    return limites


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _parametros_del_portal():
    """Variables del portal (en su orden, por nombre) y todos los parametros de cada una, visibles o no:
    ([variable, ...], {IdVariable: [parametro, ...]})."""
    token = ideam_downloader.obtener_token()
    variables = ideam_downloader.consultar_api("PortalDescargas/obtenerVariables", token=token)

    def parametros_de(variable):
        return variable["IdVariable"], ideam_downloader.consultar_api(
            "GestionDatos/ConsultarInformacionSeriesTiempoGD", {"idparametro": variable["IdVariable"]}, token=token
        ) or []

    with ThreadPoolExecutor(max_workers=6) as pool:
        return variables, dict(pool.map(parametros_de, variables))


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _series_especiales():
    return ideam_downloader.obtener_series_calculo()


# Si el servicio de mapas del IDEAM no responde, la serie especial queda vacia y se vuelve a intentar a los 5 minutos
# (la estandar sigue funcionando: no depende de ese servicio)
_FALLO_ESPECIALES = {"t": 0.0}


def _series_especiales_o_nada():
    if time.time() - _FALLO_ESPECIALES["t"] < 300:
        return []
    try:
        return _series_especiales()
    except Exception as e:
        print(f"[catalogo] Sin la serie especial: {e}", flush=True)
        _FALLO_ESPECIALES["t"] = time.time()
        return []


def limpiar_catalogo():
    """Olvida la lista guardada (boton "Reintentar" de la pantalla de Parametros)."""
    for funcion in (_parametros_del_portal, _series_especiales, obtener_limites_por_frecuencia):
        funcion.clear()
    _FALLO_ESPECIALES["t"] = 0.0


def obtener_catalogo_parametros():
    """
    Lista de parametros del IDEAM que ofrece la pagina, cada uno como dict:
    clave (unica: "PRECIPITACION|PTPM_CON" en la serie estandar; "Decadal|PRECIPITACION|SUM|PTPM_CON" en la especial;
    una misma etiqueta puede estar en dos variables), nombre (el texto de la
    lista de la pagina), variable, variable_nombre, orden_variable, etiqueta, descripcion, unidad, frecuencia,
    frecuencia_base (la de la serie de la que sale el calculo), tipo_serie y calculo (lo que se manda al descargar),
    avanzado (True si es de datos cada pocos minutos), especial (True si va en la serie "Especial"), anios_max y
    dias_bloque (años y dias maximos por consulta; el servidor rechaza consultas mas largas).
    Las partes que vienen del IDEAM se guardan 24 h; esto solo las arma.
    """
    variables, parametros = _parametros_del_portal()
    limites = obtener_limites_por_frecuencia()
    orden = {v["IdVariable"]: i for i, v in enumerate(variables)}
    nombres_var = {v["IdVariable"]: v["Nombre"].strip() for v in variables}

    def entrada(variable, etiqueta, descripcion, unidad, frecuencia, frecuencia_base, **extra):
        # La pagina del IDEAM mide los años como dias / 360; se usa lo mismo
        anios = limites.get(frecuencia_base, 10)
        return {"clave": f"{variable}|{etiqueta}", "nombre": descripcion, "variable": variable, "variable_nombre": nombres_var[variable],
                "orden_variable": orden[variable], "etiqueta": etiqueta, "descripcion": descripcion,
                "unidad": unidad or "", "frecuencia": frecuencia, "frecuencia_base": frecuencia_base,
                "tipo_serie": "Estandard", "calculo": "", "avanzado": frecuencia in FRECUENCIAS_AVANZADAS,
                "especial": False, "anios_max": anios, "dias_bloque": max(1, int(anios * 360)), **extra}

    catalogo = []
    for variable in orden:
        visibles = [p for p in parametros.get(variable, []) if p.get("Visible")]
        descripciones = [_descripcion(p.get("Descripcion"), p["Etiqueta"]) for p in visibles]
        for p, descripcion in zip(visibles, descripciones):
            frecuencia = _inferir_frecuencia(p["Etiqueta"], p.get("Periodicidad"))
            # dos con el mismo texto en la misma variable: se distinguen por la etiqueta, como hacia la pagina
            nombre = descripcion + (f" [{p['Etiqueta']}]" if descripciones.count(descripcion) > 1 else "")
            catalogo.append(entrada(variable, p["Etiqueta"], descripcion, p.get("Unidad"), frecuencia, frecuencia,
                                    nombre=nombre))

    # Serie especial: la unidad y la frecuencia de la serie base salen de su parametro en GestionDatos (aunque no
    # sea visible). Sin ese dato, la frecuencia se deduce de la etiqueta. Las variables que la pagina no ofrece se
    # omiten (REC VIENTO tiene filas en la tabla, pero no esta entre las variables del portal)
    base = {(v, p["Etiqueta"]): p for v, lista in parametros.items() for p in lista}
    for fila in _series_especiales_o_nada():
        variable, etiqueta, frecuencia = fila["idparametro"], fila["etiqueta"], fila["frecuencia"]
        if variable not in orden or frecuencia not in FRECUENCIAS_ESPECIALES:
            continue
        p = base.get((variable, etiqueta), {})
        descripcion = _descripcion(fila.get("descripcion"), etiqueta)
        calculo = str(fila.get("calculo") or "").strip()
        # el texto de la pagina; sin descripcion, la pagina pone solo la etiqueta y el calculo
        nombre = f"{descripcion} |{calculo}" + (f" [{etiqueta}]" if descripcion != etiqueta else "")
        frecuencia_base = _inferir_frecuencia(etiqueta, p.get("Periodicidad"),
                                              "Mensual" if frecuencia == "Multianual" else "Diario")
        catalogo.append(entrada(variable, etiqueta, descripcion, p.get("Unidad"), frecuencia, frecuencia_base,
                                clave=f"{frecuencia}|{variable}|{calculo}|{etiqueta}", nombre=nombre,
                                tipo_serie=frecuencia, calculo=calculo, especial=True))
    return catalogo


def frecuencias_especiales(catalogo):
    """Frecuencias de la serie "Especial" que trae el catalogo, en el orden de la pagina."""
    presentes = {p["frecuencia"] for p in catalogo if p["especial"]}
    return [f for f in FRECUENCIAS_ESPECIALES if f in presentes]


def _de_la_serie(catalogo, especial, frecuencia):
    return [p for p in catalogo if p["especial"] == especial and (not especial or p["frecuencia"] == frecuencia)]


def variables_de(catalogo, especial=False, frecuencia=None):
    """{IdVariable: nombre} de las variables con parametros en la serie elegida (y su frecuencia, en la especial),
    en el orden de la pagina."""
    params = sorted(_de_la_serie(catalogo, especial, frecuencia), key=lambda p: p["orden_variable"])
    return {p["variable"]: p["variable_nombre"] for p in params}


def parametros_de(catalogo, variable, especial=False, frecuencia=None):
    """{clave: parametro} de una variable en la serie elegida, en el orden de la pagina."""
    return {p["clave"]: p for p in _de_la_serie(catalogo, especial, frecuencia) if p["variable"] == variable}


def periodo_excedido(param, fecha_ini, fecha_fin):
    """Años maximos si el periodo no cabe en una sola consulta de una serie multianual (que no se puede partir en
    bloques); None si cabe o si la serie se puede partir. Medido: con N años de limite el IDEAM acepta unos dias mas
    de N años de calendario, asi que se permite hasta N x 365,25 dias."""
    if param["frecuencia"] != "Multianual":
        return None
    anios = param["anios_max"]
    return anios if (fecha_fin - fecha_ini).days > int(anios * 365.25) else None


def filas_estimadas(param, fecha_ini, fecha_fin):
    """Cuantos datos (filas de Excel) puede traer una estacion en ese rango."""
    if param["frecuencia"] == "Multianual":
        return FILAS_MULTIANUAL
    segundos = segundos_de(param["frecuencia"])
    return int(((fecha_fin - fecha_ini).days + 1) * 86400 // segundos)


def get_metadata_availability(estaciones_df, param, fecha_ini, fecha_fin):
    """
    Calcula la "Cantidad Probable" de cada estacion dentro del rango elegido,
    igual que la pagina del IDEAM: cuantos datos caben entre el primer y el
    ultimo registro de la serie, recortado al rango.
    OJO: no descuenta huecos intermedios (dias sin dato dentro de la serie);
    eso solo se sabe al descargar.
    Las estaciones que no tienen la serie en DHIME quedan con 0 y "Serie DHIME" = "No".
    En la serie especial, como la pagina, se miran las estaciones de la serie base (la de la etiqueta): el
    porcentaje es el de esa serie y la cantidad, la de datos calculados (uno por decada; 36 en la multianual).
    """
    if estaciones_df is None or estaciones_df.empty: return None

    series = ideam_downloader.obtener_series_disponibles(param["etiqueta"])
    periodo_nominal = segundos_de(param["frecuencia_base"])

    # Rango pedido: desde fecha_ini 00:00 hasta el final del dia fecha_fin
    rango_ini = datetime.combine(fecha_ini, datetime.min.time())
    rango_fin = datetime.combine(fecha_fin, datetime.min.time()) + timedelta(days=1)

    resultados = []
    for idx, row in estaciones_df.iterrows():
        codigo = ideam_downloader.codigo_de_estacion(row, idx)
        nombre = str(row["nombre"]) if "nombre" in row.index else f"Estación {idx}"
        serie = series.get(codigo)

        # Periodo = segundos entre datos de la serie (86400 = diario, 3600 = horario...)
        periodo = (serie or {}).get("Periodo") or periodo_nominal
        esperados = max(1, int((rango_fin - rango_ini).total_seconds() // periodo))

        cantidad_probable = 0
        if serie and serie.get("InicioData") and serie.get("FinData"):
            inicio = max(rango_ini, datetime.fromisoformat(serie["InicioData"]))
            fin = min(rango_fin, datetime.fromisoformat(serie["FinData"]))
            if fin > inicio:
                cantidad_probable = int((fin - inicio).total_seconds() // periodo)

        porcentaje = round(min(100.0, cantidad_probable / esperados * 100), 1)
        if param["especial"]:
            cubierto = cantidad_probable * periodo
            esperados = filas_estimadas(param, fecha_ini, fecha_fin)
            if param["frecuencia"] == "Multianual":
                cantidad_probable = esperados if cantidad_probable else 0
            else:
                cantidad_probable = min(esperados, math.ceil(cubierto / segundos_de(param["frecuencia"])))

        resultados.append({
            "Código": codigo,
            "Nombre": nombre,
            "FechaIni": fecha_ini.strftime("%Y-%m-%d"),
            "FechaFin": fecha_fin.strftime("%Y-%m-%d"),
            "Cantidad Probable": cantidad_probable,
            "Esperados": esperados,
            "Porcentaje (%)": porcentaje,
            "Clase calidad": clasificar_calidad(porcentaje)["nombre"],
            "Serie DHIME": "Sí" if serie else "No",
            # Primer y ultimo dato de toda la serie (sirven para no pedir bloques vacios)
            "Inicio serie": (serie.get("InicioData") or "")[:10] if serie else "",
            "Fin serie": (serie.get("FinData") or "")[:10] if serie else ""
        })

    return pd.DataFrame(resultados)
