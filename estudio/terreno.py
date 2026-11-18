"""Etapa 1. Terreno: del modelo de elevación a la cuenca y su red de drenaje.

Sigue el procedimiento que describe el IDEAM para la Evaluación Regional del Agua (IDEAM, 2013, p. 104): a partir del
modelo de elevación se calcula la dirección de flujo D8, luego la acumulación de flujo, y con un punto de cierre se
delimita la cuenca. Antes, el modelo se "acondiciona" (relleno de depresiones y zonas planas) para que el agua siempre
encuentre salida; son los pasos estándar de cualquier programa SIG, con su referencia técnica.

Todo se trabaja en Magna-Sirgas origen nacional (EPSG:9377), como piden Minambiente (Res. 940 de 2026) y el IGAC
(Res. 471 de 2020), para medir áreas y longitudes en metros reales.

Este módulo no sabe nada de la página: recibe rutas y números y devuelve resultados con sus fuentes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
import rasterio.merge
import rasterio.warp
from rasterio.transform import rowcol, xy
from shapely.geometry import Point, box, shape
from shapely.ops import unary_union

CRS_TRABAJO = "EPSG:9377"           # Magna-Sirgas origen nacional
CRS_GEOGRAFICO = "EPSG:4326"
RESOLUCION_M = 30.0                  # la de los modelos globales de 1 segundo de arco
NODATA = -9999.0
# Códigos D8 de dirección de flujo, los mismos de ArcGIS que muestra el IDEAM (2013, figura 28):
# N, NE, E, SE, S, SO, O, NO
DIRMAP = (64, 128, 1, 2, 4, 8, 16, 32)

COPERNICUS_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/{n}/{n}.tif")
_GDAL_REMOTO = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
                    GDAL_HTTP_MAX_RETRY="3", GDAL_HTTP_RETRY_DELAY="1")


class ErrorTerreno(Exception):
    """Un problema con los datos que la persona puede entender y corregir (no un error de programación)."""


# ---------------------------------------------------------------------------------------------------------------
# 1. Obtener y preparar el modelo de elevación
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class DemPreparado:
    ruta: Path
    fuente: str                    # clave en fuentes.FUENTES
    descripcion: str
    bbox_wgs84: tuple              # (oeste, sur, este, norte)
    resolucion_m: float
    filas: int
    columnas: int
    elev_min: float
    elev_max: float
    porcentaje_sin_dato: float
    notas: list[str] = field(default_factory=list)


def _validar_bbox(bbox):
    o, s, e, n = (float(v) for v in bbox)
    if not (-180 <= o < e <= 180 and -90 <= s < n <= 90):
        raise ErrorTerreno("El rectángulo del área no es válido: revisa que el oeste sea menor que el este y el sur "
                           "menor que el norte.")
    if (e - o) * (n - s) > 4.0:
        raise ErrorTerreno("El área es demasiado grande (más de unos 50.000 km²). Marca una zona más pequeña "
                           "alrededor de la cuenca.")
    return o, s, e, n


def teselas_copernicus(bbox) -> list[str]:
    """Nombres de las teselas de 1° x 1° de Copernicus GLO-30 que cubren el rectángulo."""
    o, s, e, n = _validar_bbox(bbox)
    nombres = []
    for lat in range(math.floor(s), math.ceil(n)):
        for lon in range(math.floor(o), math.ceil(e)):
            ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
            eo = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
            nombres.append(f"Copernicus_DSM_COG_10_{ns}_00_{eo}_00_DEM")
    return nombres


def _reproyectar(origen, transform_origen, crs_origen, bbox_wgs84, nodata_origen, destino: Path,
                 resolucion=RESOLUCION_M) -> DemPreparado:
    """Lleva el modelo a EPSG:9377 con celdas cuadradas de `resolucion` m (interpolación bilineal)."""
    limites = rasterio.warp.transform_bounds(CRS_GEOGRAFICO, CRS_TRABAJO, *bbox_wgs84, densify_pts=21)
    columnas = int(math.ceil((limites[2] - limites[0]) / resolucion))
    filas = int(math.ceil((limites[3] - limites[1]) / resolucion))
    transform = rasterio.transform.from_origin(limites[0], limites[3], resolucion, resolucion)
    salida = np.full((filas, columnas), NODATA, dtype="float32")
    rasterio.warp.reproject(
        origen, salida, src_transform=transform_origen, src_crs=crs_origen, src_nodata=nodata_origen,
        dst_transform=transform, dst_crs=CRS_TRABAJO, dst_nodata=NODATA,
        resampling=rasterio.warp.Resampling.bilinear)
    # Recorta al rectángulo pedido (la reproyección deja esquinas fuera del área)
    rect = rasterio.warp.transform_geom(CRS_GEOGRAFICO, CRS_TRABAJO, box(*bbox_wgs84).__geo_interface__)
    fuera = ~rasterio.features.geometry_mask([rect], (filas, columnas), transform, invert=True)
    salida[fuera] = NODATA
    validos = salida[salida != NODATA]
    if validos.size == 0:
        raise ErrorTerreno("El modelo de elevación no tiene datos en el área marcada.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(destino, "w", driver="GTiff", height=filas, width=columnas, count=1, dtype="float32",
                       crs=CRS_TRABAJO, transform=transform, nodata=NODATA, compress="deflate", tiled=True) as d:
        d.write(salida, 1)
    return DemPreparado(destino, "", "", tuple(bbox_wgs84), resolucion, filas, columnas,
                        float(validos.min()), float(validos.max()),
                        round(100 * (1 - validos.size / max(1, (~fuera).sum())), 2))


def leer_copernicus(bbox, destino: Path, abrir=rasterio.open) -> DemPreparado:
    """Lee solo la ventana del área desde Copernicus GLO-30 en línea (sin bajar la tesela completa)."""
    bbox = _validar_bbox(bbox)
    fuentes_abiertas, faltan = [], []
    with rasterio.Env(**_GDAL_REMOTO):
        try:
            for nombre in teselas_copernicus(bbox):
                try:
                    fuentes_abiertas.append(abrir("/vsicurl/" + COPERNICUS_URL.format(n=nombre)))
                except rasterio.errors.RasterioIOError:
                    faltan.append(nombre)   # tesela inexistente: mar abierto
            if not fuentes_abiertas:
                raise ErrorTerreno("No se pudo leer Copernicus para esta área. Si el problema sigue, sube tu propio "
                                   "modelo de elevación (.tif).")
            mosaico, transform = rasterio.merge.merge(fuentes_abiertas, bounds=bbox, nodata=NODATA)
        finally:
            for f in fuentes_abiertas:
                f.close()
    dem = _reproyectar(mosaico[0], transform, CRS_GEOGRAFICO, bbox, NODATA, destino)
    dem.fuente = "copernicus_glo30"
    dem.descripcion = "Copernicus GLO-30 (ESA), 30 m, leído en línea"
    if faltan:
        dem.notas.append(f"{len(faltan)} tesela(s) no existen (mar abierto) y quedan sin dato.")
    return dem


TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
TERRARIUM_ZOOM = 12      # ~38 m por píxel en Colombia: el más cercano a 30 m sin inventar detalle


def _tiles_terrarium(bbox, z):
    o, s, e, n = bbox
    def idx(lon, lat):
        k = 2 ** z
        return (int((lon + 180) / 360 * k),
                int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * k))
    x0, y0 = idx(o, n)
    x1, y1 = idx(e, s)
    return x0, y0, x1, y1


def leer_terrarium(bbox, destino: Path, z: int = TERRARIUM_ZOOM, bajar=None) -> DemPreparado:
    """Segundo modelo, independiente de Copernicus: las teselas de terreno de Mapzen en AWS, que en Colombia vienen
    del SRTM de la NASA (misión de radar de 2000). Sirve para comparar la cuenca con dos modelos distintos."""
    import io
    from concurrent.futures import ThreadPoolExecutor

    import requests
    from PIL import Image

    bbox = _validar_bbox(bbox)
    x0, y0, x1, y1 = _tiles_terrarium(bbox, z)
    if (x1 - x0 + 1) * (y1 - y0 + 1) > 400:
        raise ErrorTerreno("El área es demasiado grande para el segundo modelo. Marca una zona más pequeña.")

    def _bajar(xy_):
        r = requests.get(TERRARIUM_URL.format(z=z, x=xy_[0], y=xy_[1]), timeout=30)
        r.raise_for_status()
        return r.content
    bajar = bajar or _bajar
    claves = [(x, y) for y in range(y0, y1 + 1) for x in range(x0, x1 + 1)]
    try:
        with ThreadPoolExecutor(max_workers=8) as grupo:
            imagenes = list(grupo.map(bajar, claves))
    except Exception as e:
        raise ErrorTerreno("No se pudo leer el segundo modelo (SRTM de Mapzen). Revisa la conexión o sube tu "
                           "propio .tif para comparar.") from e
    alto, ancho = (y1 - y0 + 1) * 256, (x1 - x0 + 1) * 256
    mosaico = np.empty((alto, ancho), dtype="float32")
    for (x, y), contenido in zip(claves, imagenes):
        rgb = np.asarray(Image.open(io.BytesIO(contenido)).convert("RGB"), dtype="float32")
        # Codificación Terrarium: altura = (R·256 + G + B/256) − 32768
        mosaico[(y - y0) * 256:(y - y0 + 1) * 256, (x - x0) * 256:(x - x0 + 1) * 256] = (
            rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768)
    # Georreferencia en Web Mercator (EPSG:3857), el sistema de las teselas
    origen = 20037508.342789244
    tam = 2 * origen / 2 ** z / 256
    transform = rasterio.transform.from_origin(-origen + x0 * 256 * tam, origen - y0 * 256 * tam, tam, tam)
    dem = _reproyectar(mosaico, transform, "EPSG:3857", bbox, None, destino)
    dem.fuente = "mapzen_terrain_srtm"
    dem.descripcion = "SRTM (NASA) por las teselas de terreno de Mapzen, ~38 m remuestreado a 30 m"
    return dem


def preparar_dem_propio(ruta_tif: Path, destino: Path, bbox=None, nombre_archivo: str = "") -> DemPreparado:
    """Prepara un .tif subido por el usuario: lo reproyecta a EPSG:9377 y, si hay área, lo recorta a ella."""
    try:
        src = rasterio.open(ruta_tif)
    except rasterio.errors.RasterioIOError as e:
        raise ErrorTerreno("No se pudo abrir el archivo. Debe ser un GeoTIFF (.tif) con su sistema de "
                           "coordenadas.") from e
    with src:
        if src.crs is None:
            raise ErrorTerreno("El .tif no trae sistema de coordenadas, así que no se sabe dónde está. Expórtalo "
                               "de nuevo con su sistema de referencia.")
        limites = rasterio.warp.transform_bounds(src.crs, CRS_GEOGRAFICO, *src.bounds, densify_pts=21)
        if bbox is None:
            bbox = limites
        else:
            bbox = _validar_bbox(bbox)
            inter = (max(bbox[0], limites[0]), max(bbox[1], limites[1]),
                     min(bbox[2], limites[2]), min(bbox[3], limites[3]))
            if inter[0] >= inter[2] or inter[1] >= inter[3]:
                raise ErrorTerreno("El .tif no cubre el área marcada.")
            bbox = inter
        datos = src.read(1, masked=False).astype("float32")
        nodata = src.nodata if src.nodata is not None else NODATA
        dem = _reproyectar(datos, src.transform, src.crs, bbox, nodata, destino)
    dem.fuente = "dem_propio"
    dem.descripcion = f"Modelo de elevación propio ({nombre_archivo or Path(ruta_tif).name})"
    if "dem.tif" in (nombre_archivo or "").lower() and "ap_" in (nombre_archivo or "").lower():
        dem.notas.append("Parece un archivo ALOS PALSAR (ASF): según NASA/ASF, su terreno es SRTM de 30 m "
                         "remuestreado a 12,5 m, así que no aporta más detalle que un modelo de 30 m.")
    return dem


# ---------------------------------------------------------------------------------------------------------------
# 2. Acondicionar y calcular dirección y acumulación de flujo
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class Flujo:
    """Resultado del acondicionamiento. Guarda la grilla de pysheds para delimitar cuencas sin recalcular."""
    grid: object
    dem: object                 # elevaciones originales (pysheds Raster)
    fdir: object                # dirección de flujo D8
    acc: object                 # acumulación (número de celdas que drenan a cada celda, incluida ella)
    area_celda_km2: float
    celdas_rellenas: int
    relleno_max_m: float
    celdas_planas: int

    @property
    def transform(self):
        return self.grid.affine

    @property
    def forma(self):
        return self.grid.shape

    def acc_km2(self):
        return np.asarray(self.acc, dtype="float64") * self.area_celda_km2


def _grid_pysheds():
    """Importa pysheds (tarde, porque carga numba y tarda unos segundos).

    pysheds 0.5 todavía llama a `numpy.in1d`, que numpy 2.4 eliminó. Para arreglos de una dimensión, como los que
    usa pysheds (`fdir.ravel()`), `numpy.isin` da exactamente el mismo resultado, así que se deja ese alias."""
    if not hasattr(np, "in1d"):
        np.in1d = np.isin
    from pysheds.grid import Grid
    return Grid


def acondicionar(ruta_dem: Path) -> Flujo:
    """Relleno de pozos y depresiones, zonas planas, dirección D8 y acumulación de flujo."""
    Grid = _grid_pysheds()
    grid = Grid.from_raster(str(ruta_dem))
    dem = grid.read_raster(str(ruta_dem))
    sin_pozos = grid.fill_pits(dem)
    rellenado = grid.fill_depressions(sin_pozos)
    planas = grid.detect_flats(rellenado)
    inclinado = grid.resolve_flats(rellenado)
    fdir = grid.flowdir(inclinado, dirmap=DIRMAP)
    acc = grid.accumulation(fdir, dirmap=DIRMAP)

    base = np.asarray(dem, dtype="float64")
    valido = base != NODATA
    dif = np.where(valido, np.asarray(rellenado, dtype="float64") - base, 0.0)
    resx, resy = grid.affine.a, -grid.affine.e
    return Flujo(grid, dem, fdir, acc, area_celda_km2=resx * resy / 1e6,
                 celdas_rellenas=int((dif > 1e-6).sum()), relleno_max_m=float(dif.max(initial=0.0)),
                 celdas_planas=int(np.asarray(planas).sum()))


# ---------------------------------------------------------------------------------------------------------------
# 3. Punto de cierre y cuenca
# ---------------------------------------------------------------------------------------------------------------
@dataclass
class PuntoCierre:
    x: float                    # EPSG:9377
    y: float
    x_original: float
    y_original: float
    distancia_m: float          # cuánto se movió para caer sobre el cauce
    area_aportante_km2: float
    fila: int = -1              # celda en la grilla del flujo
    columna: int = -1


def ubicar_punto_cierre(flujo: Flujo, lon: float, lat: float, radio_m: float = 300.0,
                        area_objetivo_km2: float | None = None) -> PuntoCierre:
    """Mueve el punto a la celda de mayor acumulación dentro de `radio_m` (lo que en ArcGIS se llama "Snap Pour
    Point"). Un clic casi nunca cae justo en la celda del cauce; sin este ajuste la cuenca saldría diminuta.

    Con `area_objetivo_km2` (por ejemplo, el área obtenida con otro modelo o el área oficial de una estación), elige la
    celda del radio cuya área aportante más se parece a ese valor, como hacen Lehner (2011) para ubicar estaciones
    sobre HydroSHEDS. Evita saltar a un afluente pequeño o al río principal vecino."""
    from pyproj import Transformer
    x0, y0 = Transformer.from_crs(CRS_GEOGRAFICO, CRS_TRABAJO, always_xy=True).transform(lon, lat)
    fila, col = rowcol(flujo.transform, x0, y0)
    filas, cols = flujo.forma
    if not (0 <= fila < filas and 0 <= col < cols):
        raise ErrorTerreno("El punto de cierre está fuera del modelo de elevación.")
    r = max(1, int(round(radio_m / flujo.transform.a)))
    f0, f1, c0, c1 = max(0, fila - r), min(filas, fila + r + 1), max(0, col - r), min(cols, col + r + 1)
    ventana = np.asarray(flujo.acc)[f0:f1, c0:c1].astype("float64")
    ff, cc = np.mgrid[f0:f1, c0:c1]
    ventana[(ff - fila) ** 2 + (cc - col) ** 2 > r * r] = -1   # ventana circular
    if area_objetivo_km2:
        areas = ventana * flujo.area_celda_km2
        error = np.where(ventana >= 0, np.abs(areas - area_objetivo_km2), np.inf)
        i, j = np.unravel_index(np.argmin(error), ventana.shape)
    else:
        i, j = np.unravel_index(np.argmax(ventana), ventana.shape)
    fila_n, col_n = f0 + i, c0 + j
    x, y = xy(flujo.transform, fila_n, col_n)
    return PuntoCierre(x, y, x0, y0, distancia_m=float(math.hypot(x - x0, y - y0)),
                       area_aportante_km2=float(ventana[i, j] * flujo.area_celda_km2),
                       fila=int(fila_n), columna=int(col_n))


@dataclass
class Cuenca:
    poligono: object            # shapely, EPSG:9377
    mascara: np.ndarray         # booleana, en la grilla del flujo
    punto: PuntoCierre
    area_km2: float
    celdas: int
    elev_min: float
    elev_max: float
    cortada: bool
    lados_borde: list[str]


def delinear(flujo: Flujo, punto: PuntoCierre) -> Cuenca:
    # Se pasa la celda (fila, columna) y no la coordenada: así no hay duda de a qué celda corresponde el punto
    # (con coordenadas, pysheds puede redondear a la celda vecina y la cuenca sale diminuta)
    fila, col = (punto.fila, punto.columna) if punto.fila >= 0 else rowcol(flujo.transform, punto.x, punto.y)
    catch = flujo.grid.catchment(x=int(col), y=int(fila), fdir=flujo.fdir, dirmap=DIRMAP, xytype="index")
    mascara = np.asarray(catch).astype(bool)
    celdas = int(mascara.sum())
    if celdas < 4:
        raise ErrorTerreno("La cuenca salió casi vacía: el punto no cae sobre un cauce. Acércalo al río o aumenta "
                           "el radio de ajuste.")
    partes = [shape(g) for g, v in rasterio.features.shapes(mascara.astype("uint8"), mask=mascara,
                                                             transform=flujo.transform) if v == 1]
    poligono = unary_union(partes)
    if poligono.geom_type == "MultiPolygon":   # D8 a veces deja celdas unidas solo por una esquina
        poligono = max(poligono.geoms, key=lambda g: g.area)
    elev = np.asarray(flujo.dem, dtype="float64")[mascara]
    elev = elev[elev != NODATA]
    lados = lados_en_borde(mascara, np.asarray(flujo.dem) == NODATA)
    return Cuenca(poligono, mascara, punto, area_km2=celdas * flujo.area_celda_km2, celdas=celdas,
                  elev_min=float(elev.min()), elev_max=float(elev.max()), cortada=bool(lados), lados_borde=lados)


def lados_en_borde(mascara: np.ndarray, sin_dato: np.ndarray) -> list[str]:
    """Prueba de borde: ¿la cuenca toca el límite del modelo o una zona sin dato? Si sí, puede faltar terreno aguas
    arriba (la cuenca estaría cortada). Devuelve los lados tocados: norte, sur, este, oeste o "zona sin dato"."""
    # Se miran las dos primeras filas y columnas de cada lado: pysheds no enruta la celda del borde (la trata como
    # salida del modelo), así que una cuenca cortada llega solo hasta la segunda. Lo comprueba tests/test_estudio.py.
    lados = []
    if mascara[:2, :].any():
        lados.append("norte")
    if mascara[-2:, :].any():
        lados.append("sur")
    if mascara[:, :2].any():
        lados.append("oeste")
    if mascara[:, -2:].any():
        lados.append("este")
    if sin_dato.any():
        # una celda de la cuenca vecina (4 direcciones) de una celda sin dato
        vecino = np.zeros_like(sin_dato)
        vecino[1:, :] |= sin_dato[:-1, :]
        vecino[:-1, :] |= sin_dato[1:, :]
        vecino[:, 1:] |= sin_dato[:, :-1]
        vecino[:, :-1] |= sin_dato[:, 1:]
        if (vecino & mascara).any():
            lados.append("zona sin dato")
    return lados


def ampliar_bbox(bbox, lados: list[str], grados: float = 0.1):
    """Agranda el rectángulo hacia los lados donde la cuenca quedó cortada (0,1° ≈ 11 km)."""
    o, s, e, n = bbox
    todos = "zona sin dato" in lados
    return (o - grados if todos or "oeste" in lados else o, s - grados if todos or "sur" in lados else s,
            e + grados if todos or "este" in lados else e, n + grados if todos or "norte" in lados else n)


# ---------------------------------------------------------------------------------------------------------------
# 4. Red de drenaje
# ---------------------------------------------------------------------------------------------------------------
def red_drenaje(flujo: Flujo, cuenca: Cuenca, umbral_km2: float) -> gpd.GeoDataFrame:
    """Cauces dentro de la cuenca: celdas con área aportante de al menos `umbral_km2`. Cada tramo lleva su orden de
    Strahler y su longitud en km."""
    if umbral_km2 <= 0:
        raise ErrorTerreno("El umbral de la red debe ser mayor que cero.")
    rios = (flujo.acc_km2() >= umbral_km2) & cuenca.mascara
    columnas = ["orden", "longitud_km", "geometry"]
    if rios.sum() < 2:
        return gpd.GeoDataFrame(columns=columnas, geometry="geometry", crs=CRS_TRABAJO)
    from pysheds.sview import Raster
    rios = Raster(rios, viewfinder=flujo.fdir.viewfinder)   # pysheds exige su propio tipo de ráster
    ramas = flujo.grid.extract_river_network(flujo.fdir, rios, dirmap=DIRMAP)
    orden = np.asarray(flujo.grid.stream_order(flujo.fdir, rios, dirmap=DIRMAP))
    filas = []
    for f in ramas["features"]:
        linea = shape(f["geometry"])
        if linea.length == 0:
            continue
        # orden del tramo: el más frecuente entre sus vértices (en las uniones un vértice toca el tramo vecino)
        vals = []
        for x_, y_ in linea.coords:
            fi, co = rowcol(flujo.transform, x_, y_)
            if 0 <= fi < orden.shape[0] and 0 <= co < orden.shape[1] and orden[fi, co] > 0:
                vals.append(int(orden[fi, co]))
        filas.append({"orden": int(np.bincount(vals).argmax()) if vals else 1,
                      "longitud_km": linea.length / 1000, "geometry": linea})
    return gpd.GeoDataFrame(filas, columns=columnas, geometry="geometry", crs=CRS_TRABAJO)


# ---------------------------------------------------------------------------------------------------------------
# 5. Comparar con un segundo modelo y exportar
# ---------------------------------------------------------------------------------------------------------------
def comparar_cuencas(a: Cuenca, b: Cuenca) -> dict:
    """Diferencia de área y coincidencia espacial (intersección / unión) entre dos delimitaciones."""
    inter = a.poligono.intersection(b.poligono).area
    union = a.poligono.union(b.poligono).area
    return {"area_a_km2": a.area_km2, "area_b_km2": b.area_km2,
            "diferencia_pct": 100 * (b.area_km2 - a.area_km2) / a.area_km2,
            "coincidencia_pct": 100 * inter / union if union else 0.0}


def capas(cuenca: Cuenca, red: gpd.GeoDataFrame | None, fuente_dem: str, umbral_km2: float | None):
    """Las tres capas del resultado, en EPSG:9377, con áreas en hectáreas (2 decimales) y longitudes (1 decimal)
    como pide la Res. 940 de 2026."""
    gc = gpd.GeoDataFrame([{"area_ha": round(cuenca.area_km2 * 100, 2), "area_km2": round(cuenca.area_km2, 2),
                            "elev_min_m": round(cuenca.elev_min, 1), "elev_max_m": round(cuenca.elev_max, 1),
                            "cortada": cuenca.cortada, "fuente_dem": fuente_dem, "geometry": cuenca.poligono}],
                          geometry="geometry", crs=CRS_TRABAJO)
    p = cuenca.punto
    gp = gpd.GeoDataFrame([{"x_m": round(p.x, 1), "y_m": round(p.y, 1), "ajuste_m": round(p.distancia_m, 1),
                            "geometry": Point(p.x, p.y)}], geometry="geometry", crs=CRS_TRABAJO)
    salida = {"cuenca": gc, "punto_cierre": gp}
    if red is not None and len(red):
        gr = red.copy()
        gr["longitud_km"] = gr["longitud_km"].round(3)
        gr["umbral_km2"] = umbral_km2
        salida["red_drenaje"] = gr
    return salida


def exportar_gpkg(capas_: dict, destino: Path) -> Path:
    """GeoPackage con una capa por resultado (formato aceptado por la Res. 940 de 2026; se abre en QGIS)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        destino.unlink()
    for nombre, gdf in capas_.items():
        gdf.to_file(destino, layer=nombre, driver="GPKG")
    return destino


def exportar_kml(capas_: dict, destino: Path) -> Path:
    """KML para Google Earth. El formato KML solo admite coordenadas geográficas WGS84, así que se convierte."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        destino.unlink()
    for nombre, gdf in capas_.items():
        g = gdf.to_crs(CRS_GEOGRAFICO)
        g.to_file(destino, layer=nombre, driver="KML", append=destino.exists())
    return destino
