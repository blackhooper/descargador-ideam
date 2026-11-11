"""Logica de la app que no depende de Streamlit: cuentas, textos y tablas que `app.py` solo llama.

Vive aparte para poder probarla (ver `tests/test_logica.py`): aqui no se lee `st.session_state` ni se dibuja nada.
"""
import math
import re
from datetime import date

import geopandas as gpd
import pandas as pd
import shapely

from modules import ideam_downloader, mapa_huecos

INICIO_REGISTRO = date(1920, 1, 1)   # "Todo": antes de esta fecha el IDEAM no tiene series


def firma(gdf):
    """Huella de una geometria para saber si la cuenca cambio de verdad."""
    if gdf is None or gdf.empty:
        return None
    return shapely.normalize(shapely.set_precision(gdf.union_all(), 1e-5)).wkt


def area_km2(gdf):
    """Area de la cuenca en km² (en la proyeccion de Colombia que usa tambien el buffer)."""
    try:
        return float(gdf[["geometry"]].to_crs(epsg=3116).area.sum()) / 1e6
    except Exception:
        return None


def periodo(ini, fin):
    """Periodo corto para los textos: "2000–2020" si son anos completos; si no, las fechas."""
    if (ini.month, ini.day, fin.month, fin.day) == (1, 1, 12, 31):
        return f"{ini.year}–{fin.year}" if ini.year != fin.year else str(ini.year)
    return f"{ini:%d/%m/%Y} – {fin:%d/%m/%Y}"


def atajo_periodo(anios, hoy=None):
    """Fechas (desde, hasta) de los atajos de Parametros: los ultimos `anios` años hasta hoy, o todo el registro
    (None). El dia se limita a 28 para que un 29 de febrero no de una fecha que no existe."""
    hoy = hoy or date.today()
    if anios is None:
        return INICIO_REGISTRO, hoy
    return date(hoy.year - anios, hoy.month, min(hoy.day, 28)), hoy


def por_defecto(opciones, *preferidas):
    """Posicion de la primera opcion preferida que este en la lista (si ninguna esta, la primera)."""
    claves = list(opciones)
    return next((claves.index(c) for c in preferidas if c in opciones), 0)


def clave_widget(texto):
    return re.sub(r"\W+", "_", str(texto))


def nombre_archivo(texto, respaldo):
    """Nombre de archivo valido en Windows a partir de lo que escribio el usuario."""
    limpio = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", (texto or "").strip())
    limpio = re.sub(r"\.zip$", "", limpio, flags=re.IGNORECASE).strip(" .")
    return limpio or respaldo


def hex_a_rgb(color):
    color = color.lstrip("#")
    return [int(color[i:i + 2], 16) for i in (0, 2, 4)]


def marco(zona):
    """Recuadro de las estaciones con unos 2 km de margen: encuadra el 3D y mide el relieve (no se dibuja)."""
    minx, miny, maxx, maxy = zona.total_bounds
    return gpd.GeoDataFrame(geometry=[shapely.box(minx - .02, miny - .02, maxx + .02, maxy + .02)], crs=4326)


def encuadre(zona, celular=False):
    """Centro (lat, lon) y zoom del mapa 2D para que quepan las estaciones (pantalla de ~1000 x 600 px; en el
    celular ~340 x 520)."""
    # Con muchas estaciones se encuadra entre los percentiles 1 y 99: una sola estacion con coordenadas erradas
    # (hay una de Cundinamarca en la longitud -83) alejaba el mapa hasta dejar el departamento diminuto
    if len(zona) >= 20:
        xs, ys = zona.geometry.x, zona.geometry.y
        minx, maxx, miny, maxy = xs.quantile(.01), xs.quantile(.99), ys.quantile(.01), ys.quantile(.99)
    else:
        minx, miny, maxx, maxy = zona.total_bounds
    ancho_px, alto_px = (340, 520) if celular else (1000, 600)
    zoom = min(math.log2(ancho_px * 360 / (256 * max(maxx - minx, .01))),
               math.log2(alto_px * 360 / (256 * max(maxy - miny, .01))))
    # medio nivel de zoom (el mapa lo admite): redondear siempre hacia abajo dejaba el encuadre pequeno
    return ((miny + maxy) / 2, (minx + maxx) / 2), min(13, max(5, math.floor(zoom * 2) / 2))


def estacion_cercana(zona, clic):
    """Codigo de la estacion que esta justo donde se hizo clic en el mapa (None si no hay ninguna)."""
    if zona is None or zona.empty or not clic:
        return None
    d = (zona.geometry.x - clic["lng"]) ** 2 + (zona.geometry.y - clic["lat"]) ** 2
    idx = d.idxmin()
    return ideam_downloader.codigo_de_estacion(zona.loc[idx], idx) if d.min() < 1e-6 else None


def nombre_limpio(nombre):
    """Nombre de la estacion sin el codigo entre corchetes del final."""
    return re.sub(r"\s*\[\d+\]\s*$", "", str(nombre)).strip()


def tabla_completitud(resultado):
    """Completitud real de cada estacion guardada frente a su cobertura estimada, de la mayor caida a la menor: es el
    dato nuevo de la descarga (antes solo estaba dentro de resumen_descarga.csv)."""
    filas = [f for f in resultado.get("resumen") or [] if f.get("Resultado") == "Guardada"
             and f.get("Completitud real (%)") not in ("", None)]
    if not filas:
        return None
    t = pd.DataFrame({
        "Estación": [nombre_limpio(f["Nombre"]) for f in filas],
        "Estimada": [float(f["Cobertura estimada (%)"]) for f in filas],
        "Real": [float(f["Completitud real (%)"]) for f in filas],
    })
    t["Diferencia"] = t["Real"] - t["Estimada"]
    return t.sort_values(["Diferencia", "Estación"]).reset_index(drop=True)


def titulo_huecos(resultado):
    ini, fin = resultado["rango"]
    return f"{resultado['rotulo']} · {ini:%d/%m/%Y} – {fin:%d/%m/%Y}"


def tabla_huecos(resultado):
    """Tabla del mapa de huecos de la descarga (se arma una vez y se guarda)."""
    if resultado.get("_tabla_huecos") is None:
        resultado["_tabla_huecos"] = mapa_huecos.tabla_huecos(resultado["huecos"], resultado["rango"],
                                                              resultado.get("frecuencia"))
    return resultado["_tabla_huecos"]


def zip_final(resultado, carpetas, huecos=False):
    """El ZIP tal como se descarga: plano o en carpetas por completitud, con el mapa de huecos si se pidio. Solo se
    guarda la variante elegida (ademas del ZIP plano de la descarga): antes quedaban hasta cuatro copias en memoria
    por sesion, y un ZIP grande pesa decenas de MB."""
    clave = (bool(carpetas), bool(huecos))
    if clave == (False, False):
        resultado.pop("_zip_variante", None)
        return resultado["zip"]
    guardada = resultado.get("_zip_variante")
    if guardada is None or guardada[0] != clave:
        base = ideam_downloader.zip_con_carpetas(resultado) if carpetas else resultado["zip"]
        if huecos:
            base = mapa_huecos.agregar_al_zip(base, tabla_huecos(resultado), titulo_huecos(resultado))
        guardada = resultado["_zip_variante"] = (clave, base)
    return guardada[1]
