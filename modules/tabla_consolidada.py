"""
Tabla consolidada: un solo archivo con las fechas en filas y cada estacion en una columna, armado con los Excel ya
descargados (el IDEAM no se vuelve a consultar). Es opcional porque puede pesar mucho: antes de armarla se estima su
tamaño y se decide en que formatos es usable.

Reglas (de Excel: 1.048.576 filas y 16.384 columnas por hoja; mas alla de unos pocos millones de celdas tarda y se
vuelve pesado de abrir):
  - hasta LIMITE_CELDAS_XLSX celdas, con menos de MAX_FILAS_EXCEL filas: Excel o CSV;
  - si no cabe en Excel pero hasta LIMITE_CELDAS_CSV: solo CSV (no tiene tope de filas);
  - si pasa de eso: no se ofrece, con el motivo.
"""
import io
import zipfile
from datetime import date

import pandas as pd

from modules import ideam_downloader, mapa_huecos

MAX_FILAS_EXCEL = 1_000_000
MAX_COLUMNAS_EXCEL = 16_000
LIMITE_CELDAS_XLSX = 2_000_000
LIMITE_CELDAS_CSV = 60_000_000


def estimar(huecos, rango, frecuencia):
    """Tamaño probable de la tabla y formatos viables. `huecos`: {codigo: {"nombre", "anios"}} de la descarga.
    Devuelve {"filas", "columnas", "celdas", "formatos": ["xlsx", "csv"] o ["csv"] o [], "motivo"}."""
    if not huecos or not mapa_huecos.disponible(frecuencia):
        return {"filas": 0, "columnas": 0, "celdas": 0, "formatos": [],
                "motivo": "La serie multianual no tiene fechas para consolidar."}
    ini, fin = (r.date() if hasattr(r, "date") else r for r in rango)
    esperados = sum(mapa_huecos.esperados_anio(a, ini, fin, frecuencia) for a in range(ini.year, fin.year + 1))
    datos = sum(sum(h["anios"].values()) for h in huecos.values())
    filas = max(1, min(esperados, datos))   # las fechas distintas no pasan de lo que caben ni de los datos que llegaron
    columnas = len(huecos)
    celdas = filas * columnas
    formatos, motivo = [], ""
    if celdas > LIMITE_CELDAS_CSV:
        motivo = (f"La tabla tendría unas {filas:,} filas por {columnas} estaciones: es demasiado grande para un "
                  "solo archivo usable. Reduce el periodo o las estaciones.").replace(",", ".")
    elif filas > MAX_FILAS_EXCEL or columnas > MAX_COLUMNAS_EXCEL or celdas > LIMITE_CELDAS_XLSX:
        formatos = ["csv"]
        motivo = "Es demasiado grande para Excel; va en CSV."
    else:
        formatos = ["xlsx", "csv"]
    return {"filas": filas, "columnas": columnas, "celdas": celdas, "formatos": formatos, "motivo": motivo}


def _serie(libro, nombre):
    """Serie (indice = fecha, valores numericos) de un Excel del IDEAM; vacia si no se entiende."""
    filas = ideam_downloader._leer_valores_xlsx(libro)
    n = ideam_downloader.FILAS_ENCABEZADO_IDEAM
    encabezado = filas[n - 1] if len(filas) >= n else ()
    texto = [str(c or "").strip().lower() for c in encabezado]
    col = next((i for i, c in enumerate(texto) if c.startswith("valor")), 2)
    fechas, valores = [], []
    for f in filas[n:]:
        if f and f[0] not in (None, "") and len(f) > col and f[col] not in (None, ""):
            fechas.append(f[0])
            valores.append(f[col])
    serie = pd.Series(pd.to_numeric(valores, errors="coerce"), index=pd.to_datetime(fechas, errors="coerce"), name=nombre)
    serie = serie[serie.index.notna()]
    return serie[~serie.index.duplicated(keep="first")]


def construir(zip_bytes, resumen):
    """DataFrame con la fecha como indice y una columna 'NOMBRE [codigo]' por estacion guardada, ordenado por fecha."""
    series = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        for fila in resumen or []:
            if fila.get("Resultado") != "Guardada" or not fila.get("Archivo"):
                continue
            nombre = f"{str(fila.get('Nombre', '')).split('[')[0].strip()} [{fila.get('Código', '')}]"
            try:
                series.append(_serie(z.read(fila["Archivo"]), nombre))
            except (KeyError, zipfile.BadZipFile):
                continue
    if not series:
        return pd.DataFrame()
    tabla = pd.concat(series, axis=1).sort_index()
    tabla.index.name = "Fecha"
    return tabla


def a_bytes(tabla, formato):
    if formato == "xlsx":
        salida = io.BytesIO()
        tabla.to_excel(salida, sheet_name="Consolidado")
        return salida.getvalue()
    return tabla.to_csv().encode("utf-8-sig")


def nombre_archivo(formato):
    return f"tabla_consolidada.{formato}"


def agregar_al_zip(zip_bytes, tabla, formato):
    """Copia del ZIP con la tabla consolidada añadida."""
    salida = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as origen, zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as destino:
        for info in origen.infolist():
            destino.writestr(info.filename, origen.read(info.filename))
        destino.writestr(nombre_archivo(formato), a_bytes(tabla, formato))
    return salida.getvalue()
