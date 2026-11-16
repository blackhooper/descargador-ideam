"""Buscador de lugares: de un nombre ("Zipaquira", "Rio Teusaca", "Paipa, Boyaca") a un punto del mapa.

Usa Nominatim (el buscador de OpenStreetMap), limitado a Colombia. Politica de uso de Nominatim: maximo una consulta
por segundo, sin autocompletar (se busca al pulsar Enter) y un User-Agent que identifique la aplicacion. Solo sale
a la red el texto que la persona escribe; no se manda nada mas. Datos © colaboradores de OpenStreetMap (ODbL).
"""
import math

import requests
import streamlit as st

URL = "https://nominatim.openstreetmap.org/search"
AGENTE = "descargador-ideam/1.0 (herramienta de consulta de datos del IDEAM)"
MAX_RESULTADOS = 5
ZOOM_MIN, ZOOM_MAX = 6, 16


class ErrorBusqueda(Exception):
    """El buscador no respondio (sin red, servicio caido o demasiadas consultas)."""


def zoom_para(caja):
    """Zoom de Leaflet para que quepa una caja (sur, norte, oeste, este) en una ventana de unos 900 px."""
    sur, norte, oeste, este = caja
    ancho, alto = abs(este - oeste), abs(norte - sur)
    grande = max(ancho, alto, 1e-4)
    # a zoom z, 256*2^z px dan 360 grados: 900 px abarcan 360 * 900 / (256 * 2^z) grados
    z = math.floor(math.log2(360 * 900 / (256 * grande)))
    return max(ZOOM_MIN, min(ZOOM_MAX, z))


def _lugar(fila):
    caja = [float(v) for v in fila["boundingbox"]]
    return {"nombre": fila["display_name"], "lat": float(fila["lat"]), "lon": float(fila["lon"]),
            "tipo": fila.get("type", ""), "zoom": zoom_para(caja)}


@st.cache_data(ttl=3600, show_spinner=False)
def buscar(texto, limite=MAX_RESULTADOS):
    """Lugares de Colombia que coinciden con el texto, del mas al menos relevante: lista de dicts con nombre, lat,
    lon, tipo y zoom. Lista vacia si no hay coincidencias; ErrorBusqueda si el servicio no responde."""
    texto = " ".join(str(texto or "").split())
    if len(texto) < 3:
        return []
    try:
        r = requests.get(URL, params={"q": texto, "countrycodes": "co", "format": "jsonv2", "limit": limite,
                                      "accept-language": "es"},
                         headers={"User-Agent": AGENTE}, timeout=8)
        r.raise_for_status()
        return [_lugar(f) for f in r.json()]
    except (requests.RequestException, ValueError, KeyError) as e:
        raise ErrorBusqueda(str(e)) from e
