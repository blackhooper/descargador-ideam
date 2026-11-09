import io

import openpyxl

from modules import ideam_downloader as d


def _libro(filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    for fila in filas:
        ws.append(fila)
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


# Mismo orden que los Excel reales del IDEAM: 7 filas de encabezado, la 8 con los titulos y luego los datos
ENCABEZADO = [[None] * 6 for _ in range(7)] + [["Fecha", None, "Valor:", None, "Nivel de Aprobación", None]]
DATOS = [
    ["2020-01-01 00:00", None, 20.1, None, "Definitivo", None],
    ["2020-01-02 00:00", None, 21.0, None, "Definitivo", None],
    ["2020-01-03 00:00", None, 19.5, None, "En revisión", None],
    ["2020-01-04 00:00", None, None, None, "Preliminar", None],   # sin valor: no cuenta
    ["2020-01-05 00:00", None, 22.0, None, "Preliminar", None],
]


def test_cuenta_datos_y_niveles():
    datos, niveles = d.analizar_excel(_libro(ENCABEZADO + DATOS))
    assert datos == 4
    assert niveles == {"Definitivo": 2, "En revisión": 1, "Preliminar": 1}
    assert d.contar_datos(_libro(ENCABEZADO + DATOS)) == 4


def test_porcentajes():
    p = d.porcentajes_nivel({"Definitivo": 2, "En revisión": 1, "Preliminar": 1})
    assert p == {"Definitivo (%)": 50.0, "En revisión (%)": 25.0, "Preliminar (%)": 25.0}
    assert d.porcentajes_nivel({}) == {"Definitivo (%)": "", "En revisión (%)": "", "Preliminar (%)": ""}


def test_archivo_ilegible():
    assert d.analizar_excel(b"no es un excel") == (None, {})
