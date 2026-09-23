import re
import pandas as pd
import streamlit as st
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from modules import ideam_downloader
from modules.calidad import clasificar_calidad

# ===========================================================================
# CATALOGO DE VARIABLES Y PARAMETROS DEL IDEAM
# ---------------------------------------------------------------------------
# Se lee de los mismos servicios que usa la pagina del IDEAM. De los ~950
# parametros que existen solo se ofrecen los que la pagina muestra al
# publico (Visible = true); el resto son internos o de prueba.
# ===========================================================================

# Frecuencias en el orden en que se muestran
FRECUENCIAS_NORMALES = ["Diario", "Mensual", "Anual", "Horario", "03 Veces al Día", "02 Veces al Día"]
# Datos cada pocos minutos: el IDEAM solo entrega 1 mes por consulta
FRECUENCIAS_AVANZADAS = ["Cada 10 Minutos", "Cada 05 Minutos", "Cada 02 Minutos", "Minutal"]

# Segundos entre datos de cada frecuencia (para estimar cuantos datos caben)
SEGUNDOS_POR_FRECUENCIA = {
    "Anual": 365 * 86400, "Mensual": 30 * 86400, "Diario": 86400,
    "03 Veces al Día": 8 * 3600, "02 Veces al Día": 12 * 3600, "Horario": 3600,
    "Cada 10 Minutos": 600, "Cada 05 Minutos": 300, "Cada 02 Minutos": 120, "Minutal": 60,
}

# Excel no admite mas de 1.048.576 filas por hoja
MAX_FILAS_EXCEL = 1_000_000


def _inferir_frecuencia(etiqueta, periodicidad):
    """Algunos parametros no traen periodicidad; se deduce del final de la etiqueta."""
    if periodicidad and periodicidad != "Desconocida":
        return periodicidad
    sufijo = re.search(r"_([DMAH])$", etiqueta or "")
    return {"D": "Diario", "M": "Mensual", "A": "Anual", "H": "Horario"}.get(
        sufijo.group(1) if sufijo else "", "Diario"
    )


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
def obtener_catalogo_parametros():
    """
    Lista de parametros publicos del IDEAM, cada uno como dict:
    variable, variable_nombre, etiqueta, descripcion, unidad, frecuencia,
    avanzado (True si es de datos cada pocos minutos) y dias_bloque
    (dias maximos por consulta; el servidor rechaza consultas mas largas).
    """
    token = ideam_downloader.obtener_token()
    variables = ideam_downloader.consultar_api("PortalDescargas/obtenerVariables", token=token)
    limites = obtener_limites_por_frecuencia()

    def parametros_de(variable):
        return variable, ideam_downloader.consultar_api(
            "GestionDatos/ConsultarInformacionSeriesTiempoGD", {"idparametro": variable["IdVariable"]}, token=token
        )

    catalogo = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for variable, parametros in pool.map(parametros_de, variables):
            for p in parametros or []:
                if not p.get("Visible"):
                    continue
                frecuencia = _inferir_frecuencia(p["Etiqueta"], p.get("Periodicidad"))
                # La pagina del IDEAM mide los años como dias / 360; se usa lo mismo
                anios = limites.get(frecuencia, 10)
                catalogo.append({
                    "variable": variable["IdVariable"],
                    "variable_nombre": variable["Nombre"].strip(),
                    "etiqueta": p["Etiqueta"],
                    "descripcion": (p.get("Descripcion") or p["Etiqueta"]).strip(),
                    "unidad": p.get("Unidad") or "",
                    "frecuencia": frecuencia,
                    "avanzado": frecuencia in FRECUENCIAS_AVANZADAS,
                    "dias_bloque": max(1, int(anios * 360)),
                })
    return catalogo


def variables_disponibles(catalogo, avanzado=False):
    """{IdVariable: nombre} de las variables con parametros en el modo elegido."""
    variables = {p["variable"]: p["variable_nombre"] for p in catalogo if p["avanzado"] == avanzado}
    return dict(sorted(variables.items(), key=lambda v: v[1]))


def frecuencias_disponibles(catalogo, variable, avanzado=False):
    orden = FRECUENCIAS_AVANZADAS if avanzado else FRECUENCIAS_NORMALES
    presentes = {p["frecuencia"] for p in catalogo if p["variable"] == variable and p["avanzado"] == avanzado}
    return [f for f in orden if f in presentes] + sorted(presentes - set(orden))


def parametros_disponibles(catalogo, variable, frecuencia):
    """{etiqueta: parametro} de una variable y frecuencia, ordenados por descripcion."""
    params = [p for p in catalogo if p["variable"] == variable and p["frecuencia"] == frecuencia]
    return {p["etiqueta"]: p for p in sorted(params, key=lambda p: p["descripcion"])}


def filas_estimadas(param, fecha_ini, fecha_fin):
    """Cuantos datos (filas de Excel) puede traer una estacion en ese rango."""
    segundos = SEGUNDOS_POR_FRECUENCIA.get(param["frecuencia"], 86400)
    return int(((fecha_fin - fecha_ini).days + 1) * 86400 // segundos)


def get_metadata_availability(estaciones_df, param, fecha_ini, fecha_fin):
    """
    Calcula la "Cantidad Probable" de cada estacion dentro del rango elegido,
    igual que la pagina del IDEAM: cuantos datos caben entre el primer y el
    ultimo registro de la serie, recortado al rango.
    OJO: no descuenta huecos intermedios (dias sin dato dentro de la serie);
    eso solo se sabe al descargar.
    Las estaciones que no tienen la serie en DHIME quedan con 0 y "Serie DHIME" = "No".
    """
    if estaciones_df is None or estaciones_df.empty: return None

    series = ideam_downloader.obtener_series_disponibles(param["etiqueta"])
    periodo_nominal = SEGUNDOS_POR_FRECUENCIA.get(param["frecuencia"], 86400)

    # Rango pedido: desde fecha_ini 00:00 hasta el final del dia fecha_fin
    rango_ini = datetime.combine(fecha_ini, datetime.min.time())
    rango_fin = datetime.combine(fecha_fin, datetime.min.time()) + timedelta(days=1)

    resultados = []
    for idx, row in estaciones_df.iterrows():
        codigo = ideam_downloader.codigo_de_estacion(row, idx)
        nombre = str(row["nombre"]) if "nombre" in row.index else f"Estación {idx}"
        serie = series.get(codigo)

        # Periodo = segundos entre datos (86400 = diario, 3600 = horario...)
        periodo = (serie or {}).get("Periodo") or periodo_nominal
        esperados = max(1, int((rango_fin - rango_ini).total_seconds() // periodo))

        cantidad_probable = 0
        if serie and serie.get("InicioData") and serie.get("FinData"):
            inicio = max(rango_ini, datetime.fromisoformat(serie["InicioData"]))
            fin = min(rango_fin, datetime.fromisoformat(serie["FinData"]))
            if fin > inicio:
                cantidad_probable = int((fin - inicio).total_seconds() // periodo)

        porcentaje = round(min(100.0, cantidad_probable / esperados * 100), 1)

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
