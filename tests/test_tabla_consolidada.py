import io
import zipfile
from datetime import date

import openpyxl

from modules import tabla_consolidada as t


def _libro(filas):
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(7):
        ws.append([None] * 3)
    ws.append(["Fecha", None, "Valor:"])
    for f, v in filas:
        ws.append([f, None, v])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def _zip():
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("A.xlsx", _libro([("2020-01-01 00:00", 1.0), ("2020-01-02 00:00", 2.0)]))
        z.writestr("B.xlsx", _libro([("2020-01-02 00:00", 5.0), ("2020-01-03 00:00", 6.0), ("2020-01-04 00:00", None)]))
    return b.getvalue()


RESUMEN = [{"Código": "1", "Nombre": "UNO [1]", "Resultado": "Guardada", "Archivo": "A.xlsx"},
           {"Código": "2", "Nombre": "DOS [2]", "Resultado": "Guardada", "Archivo": "B.xlsx"},
           {"Código": "3", "Nombre": "TRES [3]", "Resultado": "Omitida", "Archivo": ""}]


def test_construir_une_por_fecha():
    tabla = t.construir(_zip(), RESUMEN)
    assert list(tabla.columns) == ["UNO [1]", "DOS [2]"] and len(tabla) == 3
    assert tabla.loc["2020-01-02", "UNO [1]"] == 2.0 and tabla.loc["2020-01-02", "DOS [2]"] == 5.0
    assert tabla["UNO [1]"].isna().sum() == 1   # el 3 de enero no tiene dato de UNO
    assert t.construir(_zip(), []).empty


def test_formatos_en_bytes_y_zip():
    tabla = t.construir(_zip(), RESUMEN)
    assert b"UNO [1]" in t.a_bytes(tabla, "csv")
    assert t.a_bytes(tabla, "xlsx")[:2] == b"PK"
    assert "tabla_consolidada.csv" in zipfile.ZipFile(io.BytesIO(t.agregar_al_zip(_zip(), tabla, "csv"))).namelist()


def test_estimar_decide_formato():
    rango = (date(2020, 1, 1), date(2020, 12, 31))
    chico = {"1": {"nombre": "x", "anios": {2020: 300}}}
    assert t.estimar(chico, rango, "Diario")["formatos"] == ["xlsx", "csv"]
    # 40 estaciones horarias de 30 años: ~263 mil filas x 40 = 10 millones de celdas -> solo CSV
    grande = {str(i): {"nombre": "x", "anios": {a: 8000 for a in range(1990, 2020)}} for i in range(40)}
    est = t.estimar(grande, (date(1990, 1, 1), date(2019, 12, 31)), "Horario")
    assert est["formatos"] == ["csv"] and est["filas"] < t.MAX_FILAS_EXCEL and est["celdas"] > t.LIMITE_CELDAS_XLSX
    # de 10 minutos y 30 años: mas de un millon de filas, tampoco cabe en Excel
    sub = {"1": {"nombre": "x", "anios": {a: 50000 for a in range(1990, 2020)}}}
    assert t.estimar(sub, (date(1990, 1, 1), date(2019, 12, 31)), "Cada 10 Minutos")["filas"] > t.MAX_FILAS_EXCEL
    # enorme: no se ofrece
    enorme = {str(i): {"nombre": "x", "anios": {a: 500000 for a in range(1990, 2020)}} for i in range(400)}
    assert t.estimar(enorme, (date(1990, 1, 1), date(2019, 12, 31)), "Minutal")["formatos"] == []
    assert t.estimar(chico, rango, "Multianual")["formatos"] == []
