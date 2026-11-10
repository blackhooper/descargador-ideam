import numpy as np
from modules import dhime_extras as x

# Forma real de la respuesta (valores como texto), recortada de una estacion con aforos
AFOROS = [
    {"No": "1", "Fecha": "24/07/2017 00:00", "Hora": None, "NivelMedio": "820", "AnchoSeccion": "207",
     "AreaSeccion": "2463.8150", "ProfundidadMedia": "11.902", "VelocidadMedia": "0.84", "CaudalTotal": "2070.8710",
     "PerimetroMojado": "213.255", "RadioHidraulico": "11.553"},
    {"No": "2", "Fecha": "29/01/2017 00:00", "Hora": None, "NivelMedio": "341", "AnchoSeccion": "165.4",
     "AreaSeccion": "1488.7060", "ProfundidadMedia": "9", "VelocidadMedia": "0.209", "CaudalTotal": "311.61",
     "PerimetroMojado": "169.525", "RadioHidraulico": "8.781"},
    {"No": "3", "Fecha": "01/01/2016 00:00", "NivelMedio": None, "CaudalTotal": "5"},   # sin nivel: se descarta
]


def test_aforos_ordenados_y_numericos():
    df = x.procesar_aforos(AFOROS)
    assert len(df) == 2
    assert list(df["nivel_cm"]) == [341.0, 820.0]            # ordenado por fecha
    assert df["caudal_m3s"].iloc[1] == 2070.871
    assert str(df["fecha"].iloc[0].date()) == "2017-01-29"


def test_vacio_no_es_error():
    assert x.procesar_aforos([]).empty and list(x.procesar_aforos([]).columns)[0] == "fecha"
    assert x.procesar_perfiles([]).empty
    assert x.procesar_detalle_perfil({}).empty


def test_perfiles_y_detalle():
    df = x.procesar_perfiles([
        {"idPerfilT": 2, "Fecha": "2024-02-14T00:00:00", "CotaBM": 23.863, "CotaCeroLM": 18.72, "LecturaNivel": 361.0},
        {"idPerfilT": 1, "Fecha": "2023-10-07T00:00:00", "CotaBM": 23.863, "CotaCeroLM": 15.716, "LecturaNivel": 417.0}])
    assert list(df["id_perfil"]) == [1, 2]
    det = x.procesar_detalle_perfil({"DetalleCarteras": [
        {"Abscisado": 2.0, "Cota": 24.18, "Profundidad": 24.7, "Tipo": "TAPT01", "ObservacionesNombre": "S/ TERRENO"},
        {"Abscisado": 0.0, "Cota": 24.06, "Profundidad": 24.7, "Tipo": "TAPT01", "ObservacionesNombre": "PR OD"}]})
    assert list(det["abscisa_m"]) == [0.0, 2.0]


def test_curva_recupera_parametros():
    h = np.linspace(0.5, 4, 12)
    df = x.procesar_aforos([{"Fecha": f"01/01/{2000 + i} 00:00", "NivelMedio": str(h[i] * 100),
                             "CaudalTotal": str(3.0 * h[i] ** 1.6)} for i in range(12)])
    c = x.ajustar_curva(df)
    assert abs(c["a"] - 3.0) < 0.01 and abs(c["b"] - 1.6) < 0.01 and c["r2"] > 0.999
    q = x.caudal_desde_nivel(c, [200.0, 0.0])
    assert abs(q[0] - 3.0 * 2.0 ** 1.6) < 0.05 and np.isnan(q[1])
    assert x.ajustar_curva(df.head(3)) is None
