"""
Datos auxiliares de hidrologia de la API de DHIME que la descarga de series no trae:

  - Aforos liquidos       Hidrologia/ConsultarAforoLiquidoPorEstacion?IdEstacion=...
  - Perfiles transversales  Hirologia/ObtenerPerfilesTrasnversalesExistentes?IdEstacion=...   (sic: "Hirologia")
                            Hidrologia/ConsultarDetallesPerfilTrasnversalUri?idPerfilT=...

Validado contra la API real (9 nov 2026, cuenta publica del portal): de 25 estaciones con programa de aforos al azar,
17 devolvieron entre 58 y 370 aforos; la ruta con la ortografia correcta ("Hidrologia/ObtenerPerfiles...") da 404.
Una estacion sin aforos responde 200 con una lista vacia (no es un error).

Las funciones `procesar_*` son puras (reciben el JSON del IDEAM y devuelven DataFrames) para poder probarlas sin red.
"""
import pandas as pd

from modules import ideam_downloader

CAMPOS_AFORO = {
    "NivelMedio": "nivel_cm", "AnchoSeccion": "ancho_m", "AreaSeccion": "area_m2", "ProfundidadMedia": "profundidad_m",
    "VelocidadMedia": "velocidad_ms", "CaudalTotal": "caudal_m3s", "PerimetroMojado": "perimetro_m",
    "RadioHidraulico": "radio_hidraulico_m",
}


def procesar_aforos(respuesta):
    """Aforos liquidos como DataFrame ordenado por fecha. Los valores del IDEAM llegan como texto; el nivel va en cm
    y el caudal en m3/s. Las filas sin nivel o sin caudal numerico se descartan."""
    filas = respuesta if isinstance(respuesta, list) else []
    columnas = ["fecha", *CAMPOS_AFORO.values()]
    if not filas:
        return pd.DataFrame(columns=columnas)
    df = pd.DataFrame(filas)
    salida = pd.DataFrame({"fecha": pd.to_datetime(df.get("Fecha"), format="%d/%m/%Y %H:%M", errors="coerce")})
    for origen, destino in CAMPOS_AFORO.items():
        salida[destino] = pd.to_numeric(df.get(origen), errors="coerce")
    salida = salida.dropna(subset=["nivel_cm", "caudal_m3s"])
    return salida.sort_values("fecha").reset_index(drop=True)[columnas]


def procesar_perfiles(respuesta):
    """Lista de perfiles de una estacion (uno por visita): id, fecha, cota del banco de marca y cota cero de la regla."""
    filas = respuesta if isinstance(respuesta, list) else []
    columnas = ["id_perfil", "fecha", "cota_bm", "cota_cero", "lectura_nivel_cm", "tecnico", "observaciones"]
    if not filas:
        return pd.DataFrame(columns=columnas)
    df = pd.DataFrame(filas)
    salida = pd.DataFrame({
        "id_perfil": df.get("idPerfilT"),
        "fecha": pd.to_datetime(df.get("Fecha"), errors="coerce"),
        "cota_bm": pd.to_numeric(df.get("CotaBM"), errors="coerce"),
        "cota_cero": pd.to_numeric(df.get("CotaCeroLM"), errors="coerce"),
        "lectura_nivel_cm": pd.to_numeric(df.get("LecturaNivel"), errors="coerce"),
        "tecnico": df.get("Tecnico"),
        "observaciones": df.get("Observaciones"),
    })
    return salida.sort_values("fecha").reset_index(drop=True)[columnas]


def procesar_detalle_perfil(respuesta):
    """Puntos de un perfil: distancia desde la orilla (abscisa, m) y cota del fondo (m), en orden de medicion."""
    puntos = (respuesta or {}).get("DetalleCarteras") if isinstance(respuesta, dict) else None
    columnas = ["abscisa_m", "cota_m", "profundidad_m", "tipo", "descripcion"]
    if not puntos:
        return pd.DataFrame(columns=columnas)
    df = pd.DataFrame(puntos)
    salida = pd.DataFrame({
        "abscisa_m": pd.to_numeric(df.get("Abscisado"), errors="coerce"),
        "cota_m": pd.to_numeric(df.get("Cota"), errors="coerce"),
        "profundidad_m": pd.to_numeric(df.get("Profundidad"), errors="coerce"),
        "tipo": df.get("Tipo"),
        "descripcion": df.get("ObservacionesNombre"),
    })
    return salida.dropna(subset=["abscisa_m"]).sort_values("abscisa_m", kind="stable").reset_index(drop=True)[columnas]


# ---------------------------------------------------------------------------
# Consultas (usan el token y la API ya configurados en ideam_downloader)
# ---------------------------------------------------------------------------
def aforos_de(codigo, token=None):
    return procesar_aforos(ideam_downloader.consultar_api(
        "Hidrologia/ConsultarAforoLiquidoPorEstacion", {"IdEstacion": codigo}, token=token))


def perfiles_de(codigo, token=None):
    return procesar_perfiles(ideam_downloader.consultar_api(
        "Hirologia/ObtenerPerfilesTrasnversalesExistentes", {"IdEstacion": codigo}, token=token))


def detalle_perfil(id_perfil, token=None):
    return procesar_detalle_perfil(ideam_downloader.consultar_api(
        "Hidrologia/ConsultarDetallesPerfilTrasnversalUri", {"idPerfilT": id_perfil}, token=token))
