"""
Enriquecimiento del catalogo de estaciones con tres servicios de la API de DHIME que el mapa (CNE) no trae:

  1. Listas/ConsultarProgramasEstaciones           -> que mide realmente cada estacion (niveles, caudal, sedimentos...)
  2. CatalogoNacionalEstaciones/ConsultarSubRedes  -> a que red/subred regional pertenece (util para estaciones vecinas)
  3. CatalogoNacionalEstaciones/HomologacionEstaciones -> pares de codigos que son la MISMA estacion (no partir su historico)

Columnas que agrega al catalogo (todas texto, vacio si no hay dato):
  programas, tipos_programa, subredes, homologa_con, grupo_homologacion

Si el IDEAM no responde, el catalogo se devuelve tal cual (sin esas columnas): nada de la app depende de ellas.
Las tablas ya procesadas se guardan en data/dhime_enriquecimiento.json y se renuevan cada 7 dias.
"""
import json
import os
import re
import time

import pandas as pd


RUTA_CACHE = os.path.join("data", "dhime_enriquecimiento.json")
VIGENCIA_SEGUNDOS = 7 * 24 * 3600
COLUMNAS = ("programas", "tipos_programa", "subredes", "homologa_con", "grupo_homologacion")


def _codigo(valor):
    """Codigo de estacion como texto sin decimales, o None."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip().split(".")[0]
    return texto if texto.isdigit() else None


def _filas(respuesta):
    """Las respuestas vienen como lista o como {"Data": lista}."""
    if isinstance(respuesta, dict):
        respuesta = respuesta.get("Data") or []
    return respuesta if isinstance(respuesta, list) else []


# ---------------------------------------------------------------------------
# Procesamiento (funciones puras: reciben el JSON del IDEAM, devuelven diccionarios)
# ---------------------------------------------------------------------------
def procesar_programas(respuesta):
    """{codigo: {"programas": [descripcion...], "tipos": [tipo...]}} sin repetidos y en orden alfabetico."""
    acumulado = {}
    for fila in _filas(respuesta):
        codigo = _codigo(fila.get("IDESTACION"))
        if not codigo:
            continue
        item = acumulado.setdefault(codigo, {"programas": set(), "tipos": set()})
        descripcion = str(fila.get("DESCRIPCION") or "").strip()
        tipo = str(fila.get("TIPO") or "").strip()
        if descripcion:
            item["programas"].add(descripcion)
        if tipo:
            item["tipos"].add(tipo)
    return {c: {"programas": sorted(v["programas"]), "tipos": sorted(v["tipos"])} for c, v in acumulado.items()}


def _codigo_de_estacion_subred(item):
    """El codigo dentro de un elemento de `Estaciones` de una subred. No se conoce el nombre exacto del campo,
    asi que se prueban los habituales y, de ultimas, cualquier campo con 'estacion' o un '[12345678]' en un nombre."""
    if not isinstance(item, dict):
        return _codigo(item)
    for clave in ("IdEstacion", "IDESTACION", "CodigoEstacion", "Codigo", "Id"):
        if clave in item and _codigo(item[clave]):
            return _codigo(item[clave])
    for clave, valor in item.items():
        if "estacion" in clave.lower() and _codigo(valor):
            return _codigo(valor)
    for valor in item.values():
        match = re.search(r"\[(\d{6,9})\]", str(valor))
        if match:
            return match.group(1)
    return None


def procesar_subredes(respuesta):
    """{codigo: [nombre de subred, ...]} (una estacion puede estar en varias)."""
    resultado = {}
    for subred in _filas(respuesta):
        nombre = str(subred.get("Nombre") or "").strip()
        if not nombre:
            continue
        for item in subred.get("Estaciones") or []:
            codigo = _codigo_de_estacion_subred(item)
            if codigo and nombre not in resultado.setdefault(codigo, []):
                resultado[codigo].append(nombre)
    return {c: sorted(v) for c, v in resultado.items()}


def procesar_homologacion(respuesta):
    """{codigo: {"homologa_con": [otros codigos], "grupo": codigo menor del grupo}}.
    Las parejas se tratan sin direccion y se unen en grupos (A=B y B=C -> A, B y C son la misma estacion)."""
    padre = {}

    def raiz(x):
        padre.setdefault(x, x)
        while padre[x] != x:
            padre[x] = padre[padre[x]]
            x = padre[x]
        return x

    pares = set()
    for fila in _filas(respuesta):
        a, b = _codigo(fila.get("IdEstacionOrigen")), _codigo(fila.get("IdEstacionDestino"))
        if a and b and a != b:
            pares.add((a, b))
            padre[raiz(a)] = raiz(b)
    grupos = {}
    for codigo in list(padre):
        grupos.setdefault(raiz(codigo), []).append(codigo)
    resultado = {}
    for miembros in grupos.values():
        grupo = min(miembros, key=lambda c: (len(c), c))
        for codigo in miembros:
            resultado[codigo] = {"homologa_con": sorted(m for m in miembros if m != codigo), "grupo": grupo}
    return resultado


# ---------------------------------------------------------------------------
# Descarga y cache en disco
# ---------------------------------------------------------------------------
def descargar_tablas():
    """Pide los tres servicios (un solo token) y devuelve las tablas procesadas. Lanza excepcion si falla alguno."""
    from modules import ideam_downloader   # aqui y no arriba: asi las funciones puras no necesitan Streamlit
    token = ideam_downloader.obtener_token()
    if not token:
        raise ideam_downloader.error_acceso()
    consultar = ideam_downloader.consultar_api
    return {
        "creado": time.time(),
        "programas": procesar_programas(consultar("Listas/ConsultarProgramasEstaciones", token=token)),
        "subredes": procesar_subredes(consultar("CatalogoNacionalEstaciones/ConsultarSubRedes", token=token)),
        "homologacion": procesar_homologacion(consultar("CatalogoNacionalEstaciones/HomologacionEstaciones", token=token)),
    }


def cargar_tablas(ruta=RUTA_CACHE, vigencia=VIGENCIA_SEGUNDOS, descargar=descargar_tablas):
    """Tablas del cache en disco si estan vigentes; si no, las descarga y las guarda. Si la descarga falla y hay un
    cache viejo, usa el viejo; si no hay nada, devuelve None."""
    viejo = None
    try:
        with open(ruta, encoding="utf-8") as f:
            viejo = json.load(f)
        if time.time() - viejo.get("creado", 0) < vigencia:
            return viejo
    except (OSError, ValueError):
        pass
    try:
        nuevo = descargar()
    except Exception:
        return viejo
    try:
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(nuevo, f, ensure_ascii=False)
    except OSError:
        pass
    return nuevo


# ---------------------------------------------------------------------------
# Union con el catalogo
# ---------------------------------------------------------------------------
def enriquecer_catalogo(catalogo, tablas):
    """Copia del catalogo con las columnas de COLUMNAS. `tablas` es lo que devuelve cargar_tablas (o None)."""
    if catalogo is None or not tablas:
        return catalogo
    codigos = catalogo["idestacion"].map(_codigo)
    programas, subredes, homologacion = tablas["programas"], tablas["subredes"], tablas["homologacion"]
    salida = catalogo.copy()
    salida["programas"] = codigos.map(lambda c: "; ".join(programas.get(c, {}).get("programas", [])))
    salida["tipos_programa"] = codigos.map(lambda c: "; ".join(programas.get(c, {}).get("tipos", [])))
    salida["subredes"] = codigos.map(lambda c: "; ".join(subredes.get(c, [])))
    salida["homologa_con"] = codigos.map(lambda c: ", ".join(homologacion.get(c, {}).get("homologa_con", [])))
    salida["grupo_homologacion"] = codigos.map(lambda c: homologacion.get(c, {}).get("grupo", ""))
    return salida


def mide(catalogo, texto):
    """Filtro: estaciones cuyo listado de programas contiene `texto` (sin distinguir mayusculas), p. ej. mide(cat, 'caudal')."""
    if "programas" not in catalogo.columns:
        return catalogo.iloc[0:0]
    return catalogo[catalogo["programas"].str.contains(texto, case=False, regex=False, na=False)]
