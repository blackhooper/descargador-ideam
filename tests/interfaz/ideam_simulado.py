"""IDEAM de mentira para probar la interfaz sin red: variables, parametros, series, descargas y relieve inventados
(siempre los mismos: salen de una semilla), con el catalogo real de estaciones del repositorio.

`instalar()` cambia las funciones de `modules` que salen a internet. Lo usa `app_simulada.py`.
Variables de entorno: `SIMULADO_ESPERA` (segundos por bloque descargado, 0.3) y `SIMULADO_API` (segundos por
consulta, 0.2).
"""
import datetime
import io
import json
import os
import random
import time

import openpyxl
from PIL import Image

from modules import dhime_enriquecimiento, ideam_downloader, terreno

ESPERA_BLOQUE = float(os.environ.get("SIMULADO_ESPERA", "0.3"))
ESPERA_API = float(os.environ.get("SIMULADO_API", "0.2"))

DEPARTAMENTOS = {5: "Antioquia", 11: "Bogota D.C.", 15: "Boyaca", 25: "Cundinamarca"}
VARIABLES = [{"IdVariable": "PRECIPITACION", "Nombre": "Precipitación"},
             {"IdVariable": "TEMPERATURA", "Nombre": "Temperatura"},
             {"IdVariable": "CAUDAL", "Nombre": "Caudal"}]
PARAMETROS = {
    "PRECIPITACION": [("PTPM_CON", "Día pluviométrico (convencional)", "mm", "Diario"),
                      ("PTPM_TT_M", "Precipitación total mensual", "mm", "Mensual"),
                      ("PT_10_TT_D", "Precipitación acumulada 10 minutos", "mm", "Cada 10 Minutos")],
    "TEMPERATURA": [("TMX_CON", "Temperatura máxima diaria", "°C", "Diario")],
    "CAUDAL": [("Q_MEDIA_D", "Caudal medio diario", "m3/s", "Diario")],
}
LIMITES = {"Diario": 30, "Mensual": 50, "Anual": 50, "Horario": 10, "Cada 10 Minutos": 0.083}
CALCULOS = [
    {"idparametro": "PRECIPITACION", "etiqueta": "PTPM_CON", "descripcion": "Día pluviométrico", "calculo": "SUM",
     "frecuencia": "Decadal"},
    {"idparametro": "PRECIPITACION", "etiqueta": "PTPM_TT_M", "descripcion": "Precipitación total mensual",
     "calculo": "NA", "frecuencia": "Multianual"},
]

_catalogo = None


def _estaciones():
    global _catalogo
    if _catalogo is None:
        with open("data/ideam_catalogo_completo.geojson", encoding="utf-8") as f:
            _catalogo = [e["properties"] for e in json.load(f)["features"]]
    return _catalogo


def _series(etiqueta):
    """Estaciones con esa serie: algo mas de la mitad del catalogo, cada una con sus años de registro."""
    azar, filas = random.Random(etiqueta), []
    for p in _estaciones():
        if azar.random() < .45:
            continue
        inicio = azar.randint(1950, 2012)
        fin = min(2026, inicio + azar.randint(3, 60))
        filas.append({"IdEstacion": p["idestacion"], "Nombre": p["nombre"], "InicioData": f"{inicio}-01-01T00:00:00",
                      "FinData": f"{fin}-06-30T00:00:00", "Periodo": 86400, "IdDepartamento": p["iddepartamento"],
                      "Departamento": DEPARTAMENTOS.get(p["iddepartamento"], f"Departamento {p['iddepartamento']}"),
                      "IdMunicipio": p["idmunicipio"], "Municipio": f"Municipio {p['idmunicipio']}"})
    return filas


def consultar_api(ruta, params=None, token=None):
    time.sleep(ESPERA_API)
    if ruta.startswith("PortalDescargas"):
        return VARIABLES
    if ruta.startswith("GestionDatos/Consultar"):
        return [{"Etiqueta": e, "Descripcion": d, "Unidad": u, "Periodicidad": f, "Visible": True}
                for e, d, u, f in PARAMETROS[params["idparametro"]]]
    if ruta.startswith("Restricciones"):
        return [{"descripcion": k, "nroAnual": v} for k, v in LIMITES.items()]
    if ruta.startswith("Reportes/ObtenerEstacionesSerieTiempo"):
        return _series(params["idEtiqueta"])
    raise RuntimeError(f"El IDEAM simulado no conoce la ruta {ruta}")


def descargar_excel(fecha_ini, fecha_fin, token, param, codigo, inicio_serie=None, fin_serie=None,
                    al_terminar_bloque=None, detener=None):
    """Excel con el formato del IDEAM (siete filas de encabezado y la tabla), con huecos; una de cada ocho estaciones
    no trae datos."""
    bloques = ideam_downloader.bloques_de(param, fecha_ini, fecha_fin, inicio_serie, fin_serie)
    azar = random.Random(codigo)
    if azar.random() < .12:
        for _ in bloques:
            if al_terminar_bloque:
                al_terminar_bloque(1)
        return None, "Sin datos (simulado)"
    libro = openpyxl.Workbook()
    hoja = libro.active
    for i in range(7):
        hoja.append([f"Meta {i}", "x"])
    hoja.append(["Fecha", "Grado", "Valor", "Calificador", "Nivel de Aprobación"])
    for desde, hasta in bloques:
        if detener is not None and detener.is_set():
            return None, "Descarga detenida"
        time.sleep(ESPERA_BLOQUE)
        dia = desde
        while dia <= hasta:
            if azar.random() > .2 and dia.year % 7 != azar.randint(0, 6):
                hoja.append([datetime.datetime(dia.year, dia.month, dia.day), 50, round(azar.random() * 30, 1), "",
                             azar.choice(["Definitivo", "Preliminar"])])
            dia += datetime.timedelta(days=1)
        if al_terminar_bloque:
            al_terminar_bloque(1)
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue(), "OK simulado"


def _tesela(z, x, y):
    """Tesela de relieve (formato Terrarium) con una altitud lisa entre 500 y 3.000 m."""
    valor = 500 + (x * 37 + y * 91) % 2500 + 32768
    return Image.new("RGB", (256, 256), (valor // 256, valor % 256, 0))


def instalar():
    """Cambia las salidas a internet por las simuladas (una sola vez por servidor)."""
    if getattr(ideam_downloader, "_simulado", False):
        return
    ideam_downloader._simulado = True
    ideam_downloader.obtener_token = lambda: "token-simulado"
    ideam_downloader.consultar_api = consultar_api
    ideam_downloader.obtener_series_calculo = lambda: CALCULOS
    ideam_downloader.descargar_excel_ideam = descargar_excel
    ideam_downloader.registrar_descargas_ideam = lambda *a, **k: None
    terreno._tile = _tesela
    dhime_enriquecimiento.cargar_tablas = lambda *a, **k: None
