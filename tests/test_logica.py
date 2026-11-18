"""Logica de la app sin Streamlit (`modules/logica.py`): fechas, encuadre del mapa, tabla y variantes del ZIP."""
import io
import zipfile
from datetime import date

import geopandas as gpd
import pytest
from shapely.geometry import Point

from modules import logica


def _zona(puntos):
    return gpd.GeoDataFrame({"nombre": [f"E{i}" for i in range(len(puntos))]},
                            geometry=[Point(x, y) for x, y in puntos], crs=4326)


def test_periodo_anios_completos_y_fechas_sueltas():
    assert logica.periodo(date(2000, 1, 1), date(2020, 12, 31)) == "2000–2020"
    assert logica.periodo(date(2010, 1, 1), date(2010, 12, 31)) == "2010"
    assert logica.periodo(date(2000, 3, 1), date(2020, 12, 31)) == "01/03/2000 – 31/12/2020"


def test_atajo_periodo():
    hoy = date(2026, 11, 11)
    assert logica.atajo_periodo(10, hoy) == (date(2016, 11, 11), hoy)
    assert logica.atajo_periodo(None, hoy) == (logica.INICIO_REGISTRO, hoy)
    # 29 de febrero: diez años atras no es bisiesto
    assert logica.atajo_periodo(10, date(2024, 2, 29))[0] == date(2014, 2, 28)


def test_por_defecto():
    assert logica.por_defecto(["a", "b", "c"], "z", "c", "b") == 2
    assert logica.por_defecto(["a", "b"], "z") == 0


@pytest.mark.parametrize("texto, esperado", [
    ("descarga 1", "descarga 1"), ("mi:zip?.ZIP", "mi_zip_"), ("  ", "respaldo"), (None, "respaldo"), ("...", "respaldo"),
])
def test_nombre_archivo(texto, esperado):
    assert logica.nombre_archivo(texto, "respaldo") == esperado


def test_hex_a_rgb():
    assert logica.hex_a_rgb("#FFE08A") == [255, 224, 138]


def test_encuadre_ignora_una_estacion_lejana():
    cerca = [(-74.0 + i * .01, 4.6 + (i % 5) * .01) for i in range(120)]
    (lat, lon), zoom = logica.encuadre(_zona(cerca + [(-83.0, 4.6)]))
    (lat0, lon0), zoom0 = logica.encuadre(_zona(cerca))
    assert abs(lon - lon0) < .05 and abs(lat - lat0) < .05
    assert zoom == zoom0 and zoom >= 8


def test_encuadre_limites_y_medio_nivel():
    (_, _), zoom = logica.encuadre(_zona([(-74.0, 4.6)]))
    assert zoom == 13                                   # una sola estacion: el maximo
    (_, _), zoom = logica.encuadre(_zona([(-95, -20), (-50, 30)]))
    assert zoom == 5                                    # medio continente: el minimo
    _, zoom = logica.encuadre(_zona([(-74.0, 4.6), (-73.7, 4.9)]))
    assert zoom * 2 == int(zoom * 2)
    assert logica.encuadre(_zona([(-74.0, 4.6), (-73.7, 4.9)]), celular=True)[1] < zoom


def test_estacion_cercana():
    zona = _zona([(-74.0, 4.6), (-73.9, 4.7)])
    zona["codigo"] = ["21205012", "21205013"]
    assert logica.estacion_cercana(zona, {"lat": 4.7, "lng": -73.9}) == "21205013"
    assert logica.estacion_cercana(zona, {"lat": 5.5, "lng": -73.9}) is None
    assert logica.estacion_cercana(zona, None) is None


def test_tabla_completitud_ordena_por_caida():
    resultado = {"resumen": [
        {"Nombre": "A [1]", "Resultado": "Guardada", "Cobertura estimada (%)": 90, "Completitud real (%)": 88},
        {"Nombre": "B [2]", "Resultado": "Guardada", "Cobertura estimada (%)": 80, "Completitud real (%)": 40},
        {"Nombre": "C [3]", "Resultado": "Sin datos", "Cobertura estimada (%)": 70, "Completitud real (%)": ""},
    ]}
    t = logica.tabla_completitud(resultado)
    assert list(t["Estación"]) == ["B", "A"]
    assert list(t["Diferencia"]) == [-40, -2]
    assert logica.tabla_completitud({"resumen": []}) is None


def _zip(nombres):
    s = io.BytesIO()
    with zipfile.ZipFile(s, "w") as z:
        for n in nombres:
            z.writestr(n, "x")
    return s.getvalue()


def test_zip_final_guarda_una_sola_variante(monkeypatch):
    plano, carpetas = _zip(["a.xlsx"]), _zip(["1_Excelente/a.xlsx"])
    llamadas = []
    monkeypatch.setattr(logica.ideam_downloader, "zip_con_carpetas", lambda r: llamadas.append(1) or carpetas)
    resultado = {"zip": plano}
    assert logica.zip_final(resultado, True) is carpetas
    assert logica.zip_final(resultado, True) is carpetas and len(llamadas) == 1   # no se rearma
    assert logica.zip_final(resultado, False) is plano
    assert "_zip_variante" not in resultado


def test_anio_de_fechas_del_catalogo():
    assert logica.anio_de(-1505761200000.0) == 1922     # las anteriores a 1970 vienen en negativo
    assert logica.anio_de(1502740303000) == 2017
    assert logica.anio_de(None) is None and logica.anio_de(float("nan")) is None and logica.anio_de("x") is None
    assert logica.operacion({"fechainstalacion": -1505761200000.0, "fechasuspension": None}) == (1922, None)


def test_lista_de_celdas_con_varios_valores():
    assert logica.lista_de("Caudal; Nivel;Caudal") == ["Caudal", "Nivel"]
    assert logica.lista_de("2120, 2121") == ["2120", "2121"]
    assert logica.lista_de(None) == [] and logica.lista_de(float("nan")) == [] and logica.lista_de("") == []


def test_la_ficha_tiene_nombre_y_simbolo_para_todo_lo_que_mide_una_estacion():
    from modules import dhime_enriquecimiento, estilo, idioma
    for variable in set(dhime_enriquecimiento.VARIABLE_POR_CODIGO.values()):
        nombre, simbolo = logica.VARIABLES_FICHA[variable]
        assert simbolo in estilo.ICONOS, variable
        assert nombre in idioma.EN, nombre
    assert logica.variables_ficha({"programas": "Precipitacion; Otra cosa"}) == [("Precipitación", "lluvia"),
                                                                                ("Otra cosa", "punto")]
    assert all(nombre in idioma.EN for nombre in logica.CATEGORIAS.values())
