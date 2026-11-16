from unittest import mock

import pytest
import requests

from modules import buscador_lugares as bl


def test_zoom_segun_el_tamano_del_lugar():
    assert bl.zoom_para((4.0, 4.001, -74.0, -73.999)) == bl.ZOOM_MAX      # un punto: de cerca
    assert bl.zoom_para((-4.0, 13.0, -79.0, -66.0)) == bl.ZOOM_MIN        # el pais: de lejos
    assert bl.zoom_para((4.96, 5.16, -74.09, -73.90)) in (11, 12)         # un municipio


def _respuesta(datos, estado=200):
    r = mock.Mock(status_code=estado)
    r.json.return_value = datos
    r.raise_for_status.side_effect = None if estado == 200 else requests.HTTPError("x")
    return r


def test_buscar_devuelve_lugares_y_ignora_textos_cortos():
    fila = {"display_name": "Zipaquirá, Cundinamarca, Colombia", "lat": "5.02", "lon": "-74.00", "type": "administrative",
            "boundingbox": ["4.96", "5.16", "-74.09", "-73.90"]}
    with mock.patch.object(bl.requests, "get", return_value=_respuesta([fila])) as get:
        lugares = bl.buscar.__wrapped__("Zipaquirá")
        assert lugares[0]["lat"] == 5.02 and lugares[0]["lon"] == -74.0 and lugares[0]["nombre"].startswith("Zipaquirá")
        assert get.call_args.kwargs["params"]["countrycodes"] == "co"
        assert "descargador-ideam" in get.call_args.kwargs["headers"]["User-Agent"]
    with mock.patch.object(bl.requests, "get") as get:
        assert bl.buscar.__wrapped__("ab") == []
        get.assert_not_called()


def test_buscar_avisa_si_el_servicio_falla():
    with mock.patch.object(bl.requests, "get", side_effect=requests.ConnectionError("sin red")):
        with pytest.raises(bl.ErrorBusqueda):
            bl.buscar.__wrapped__("Paipa")
    with mock.patch.object(bl.requests, "get", return_value=_respuesta([], 429)):
        with pytest.raises(bl.ErrorBusqueda):
            bl.buscar.__wrapped__("Paipa")
