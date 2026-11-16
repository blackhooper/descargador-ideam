import json
import os

import pytest

from modules import historia_estacion as h

DATOS = os.path.join(os.path.dirname(__file__), "datos", "historia_estacion")


def _json(endpoint, codigo):
    with open(os.path.join(DATOS, f"{endpoint}_{codigo}.json"), encoding="utf-8") as f:
        return json.load(f)


def _tipos(eventos):
    return [(e["fecha"], e["tipo"], e["antes"], e["despues"]) for e in eventos]


def test_estacion_sin_cambios_solo_trae_el_inicio():
    """Guayabo: tres registros, dos de ellos solo ruido ("LM" vs "LM   "): queda el inicio de la bitacora."""
    ev = h.procesar_historia(_json("historico", "21117080"))
    assert [e["tipo"] for e in ev] == ["inicio"]
    assert ev[0]["fecha"] == "2020-12-18" and ev[0]["detalle"]["estado"] == "Suspendida"
    assert ev[0]["detalle"]["instalacion"] == "1976-10-15"


def test_acapulco_cambio_de_categoria_estado_y_traslado():
    ev = h.procesar_historia(_json("historico", "21206280"))
    tipos = _tipos(ev)
    assert ev[0]["tipo"] == "inicio" and ev[0]["fecha"] == "2018-03-09"
    assert ("2022-04-26", "categoria", "CO", "CP") in tipos           # CO -> CP
    assert ("2022-04-26", "tecnologia", "Convencional", "Automática con Telemetría") in tipos   # pasa por un vacio
    traslado = next(e for e in ev if e["tipo"] == "traslado")
    assert traslado["fecha"] == "2022-11-16" and 1000 < traslado["antes"] < 3000   # ~1,4 km
    assert ("2022-11-16", "altitud", 2650, 2680) in tipos
    assert ("2023-03-21", "estado", "Activa", "En Mantenimiento") in tipos
    assert ("2024-06-19", "estado", "En Mantenimiento", "Activa") in tipos
    # el cambio de nombre y el "CP   " no son eventos, y no hay eventos repetidos
    assert len(tipos) == len(set(tipos))
    assert not any(e["tipo"] == "categoria" and e["fecha"].startswith("2024-04") for e in ev)


def test_ajuste_pequeno_de_coordenadas_no_es_traslado():
    reg = lambda f, lat: {"IdLogCambio": f, "FechaLog": f"2024-01-0{f}T00:00:00", "Latitud": lat, "Longitud": -74.0,
                          "Altitud": 100, "Categoria": "X", "EstadoEstacion": "Activa"}
    assert [e["tipo"] for e in h.procesar_historia([reg(1, 4.00000), reg(2, 4.00010)])] == ["inicio"]
    assert [e["tipo"] for e in h.procesar_historia([reg(1, 4.0), reg(2, 4.01)])] == ["inicio", "traslado"]


def test_informacion_observadores_y_visitas():
    assert h.procesar_informacion(_json("informacion", "21117080")) == {"instalacion": "1976-10-15",
                                                                         "suspension": "2020-12-18"}
    assert h.procesar_informacion(_json("informacion", "21206280"))["suspension"] is None
    obs = h.procesar_observadores(_json("observadores", "21206280"))
    assert obs == [{"desde": "2018-09-01", "hasta": None, "activo": True},
                   {"desde": "2017-01-01", "hasta": "2018-01-01", "activo": False}]
    assert "Nombre" not in str(obs) and "Cedula" not in str(obs)          # sin datos personales
    assert h.procesar_visitas(_json("visitas", "21117080")) == {"n": 6, "primera": "2018-01-22", "ultima": "2019-05-17"}
    assert h.procesar_visitas(_json("visitas", "21201410"))["n"] == 0


@pytest.mark.parametrize("entrada", [None, [], {}, "x", [{"sin": "fecha"}]])
def test_respuestas_vacias_o_raras_no_rompen(entrada):
    assert h.procesar_historia(entrada) == []
    assert h.procesar_observadores(entrada) == []
    assert h.procesar_visitas(entrada)["n"] == 0
    assert set(h.procesar_informacion(entrada)) == {"instalacion", "suspension"}
