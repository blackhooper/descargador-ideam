import io
import zipfile
from datetime import date

import openpyxl
from PIL import Image

from modules import ideam_downloader as d, mapa_huecos as m


def _libro(fechas):
    wb = openpyxl.Workbook()
    ws = wb.active
    for _ in range(7):
        ws.append([None] * 3)
    ws.append(["Fecha", None, "Valor:"])
    for f, v in fechas:
        ws.append([f, None, v])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def test_datos_por_anio():
    libro = _libro([("2019-12-31 00:00", 1.0), ("2020-01-01 00:00", 2.0), ("2020-01-02 00:00", None),
                    ("2020-01-03 00:00", 3.0)])
    datos, niveles, por_anio = d.analizar_excel_detalle(libro)
    assert datos == 3 and por_anio == {2019: 1, 2020: 2}
    assert d.analizar_excel(libro)[0] == 3   # la funcion de siempre sigue igual


def test_esperados():
    assert m.esperados_anio(2020, date(2020, 1, 1), date(2020, 12, 31), "Diario") == 366
    assert m.esperados_anio(2020, date(2020, 7, 1), date(2021, 6, 30), "Mensual") == 6
    assert m.esperados_anio(2019, date(2020, 7, 1), date(2021, 6, 30), "Anual") == 0
    assert m.esperados_anio(2020, date(2020, 1, 1), date(2020, 1, 2), "Horario") == 48


def test_tabla_y_png_y_zip():
    huecos = {"1": {"nombre": "UNO [1]", "anios": {2020: 366, 2021: 100}},
              "2": {"nombre": "DOS [2]", "anios": {2020: 10}}}
    t = m.tabla_huecos(huecos, (date(2020, 1, 1), date(2022, 12, 31)), "Diario")
    assert t.loc[("1", "UNO [1]"), 2020] == 100.0 and t.loc[("1", "UNO [1]"), 2022] == 0.0
    assert round(t.loc[("1", "UNO [1]"), 2021], 1) == round(100 / 365 * 100, 1)
    img = Image.open(io.BytesIO(m.png(t, "Prueba")))
    assert img.width > 100 and img.height > 100
    base = io.BytesIO()
    with zipfile.ZipFile(base, "w") as z:
        z.writestr("a.txt", "x")
    nombres = zipfile.ZipFile(io.BytesIO(m.agregar_al_zip(base.getvalue(), t))).namelist()
    assert nombres == ["a.txt", "mapa_de_huecos.png", "mapa_de_huecos.csv"]
    assert not m.disponible("Multianual") and m.disponible("Diario")


def test_texto_sin_tildes_para_fuente_basica():
    assert m._sin_tildes("Precipitación – año · Cabaña") == "Precipitacion - ano | Cabana"
