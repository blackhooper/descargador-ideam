"""Qué hace cada paso, por qué, y con qué fuentes.

Es el texto de las ayudas (los botones «i» de la página) y, más adelante, de la memoria de cálculo del informe
(etapa 8). Está en un solo lugar para que la página y el informe digan exactamente lo mismo.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import fuentes


@dataclass(frozen=True)
class Paso:
    clave: str
    titulo: str
    que_hace: str
    por_que: str
    fuentes: tuple[str, ...]
    decision: str = ""      # qué queda a criterio del hidrólogo, si algo
    calidad: str = ""       # qué tan bueno es el dato y qué lo respalda, si hace falta explicarlo

    @property
    def marca(self) -> str:
        return fuentes.marca_principal(list(self.fuentes))


_PASOS = [
    Paso("terreno.area", "Área de trabajo",
         "Marca un rectángulo que contenga toda la cuenca, con algo de margen alrededor. El modelo de elevación se "
         "recorta a esa zona.",
         "Trabajar solo la zona necesaria hace el cálculo rápido. Si la cuenca que resulta toca el borde del "
         "rectángulo, puede faltar terreno aguas arriba: la página lo detecta y ofrece ampliar el área. La marca "
         "«Sin fuente oficial» es solo de esa prueba de borde. La calidad del terreno y sus fuentes están en "
         "«Modelo de elevación».",
         ("herramienta_control_borde",)),
    Paso("terreno.dem", "Modelo de elevación",
         "Por defecto se lee en línea Copernicus GLO-30 (Agencia Espacial Europea, 30 m), solo para el área "
         "marcada. También puedes subir tu propio GeoTIFF. Luego se lleva a Magna-Sirgas origen nacional "
         "(EPSG:9377) con celdas de 30 m, interpolando de forma bilineal.",
         "Minambiente exige la información geográfica en Magna-Sirgas origen nacional, el sistema que adoptó el "
         "IGAC. En coordenadas planas las áreas y longitudes salen en metros reales.",
         ("copernicus_glo30", "minambiente_res940_2026", "igac_res471_2020", "capachero_2015_srtm",
          "buitrago_martinez_2016", "velez_suarez_2025", "nasa_alos_rtc", "car_pomca_bogota_2019_dem"),
         calidad=(
             "Es la altura del terreno en cada celda, no una foto satelital. Para Colombia no hay un modelo gratuito "
             "más fino que 30 m. El de 12,5 m de ALOS PALSAR, el «alta resolución» de la NASA, no lo es en altura: "
             "la NASA aclara que su elevación es el SRTM de 30 m remuestreado. Estudios colombianos respaldan "
             "trabajar a 30 m: con alturas del IGAC, el SRTM de 30 m tiene un error medio cuadrático de 9,5 m, y "
             "menos de 5 m en terreno plano (Capachero et al., 2015). En Boyacá, ALOS de 12,5 m y SRTM fueron los "
             "que mejor se ajustaron a puntos de GPS (Buitrago y Martínez, 2016). En una cuenca de la cordillera "
             "Central, la divisoria salió mejor con un modelo de 30 m que con el de 12,5 m (Vélez y Suárez, 2025). "
             "No encontramos estudios colombianos sobre Copernicus. Por eso cada cuenca se compara con el SRTM, y "
             "en el río Teusacá el área difiere 0,06 % de la del POMCA de la CAR (2019), que contaba con un modelo "
             "de 12,5 m.")),
    Paso("terreno.flujo", "Dirección y acumulación de flujo",
         "Primero se rellenan los pozos y las depresiones del modelo y se da una pendiente mínima a las zonas "
         "planas, para que el agua siempre tenga salida. Después cada celda drena hacia la vecina de mayor pendiente "
         "(método D8) y se cuenta cuántas celdas llegan a cada una (acumulación).",
         "Es el procedimiento que describe el IDEAM para delimitar unidades hidrográficas con un modelo de "
         "elevación. Las depresiones suelen ser errores del modelo; sin rellenarlas, el agua quedaría atrapada y la "
         "cuenca saldría partida.",
         ("ideam_era_2013", "barnes_2014_priority_flood", "barnes_2014_flats", "ocallaghan_mark_1984",
          "bartos_2020_pysheds")),
    Paso("terreno.punto", "Punto de cierre",
         "Es el sitio del río donde termina la cuenca: haz clic en el mapa, elige una estación hidrológica del IDEAM "
         "o escribe sus coordenadas. La página lo mueve a la celda del cauce con más acumulación dentro del radio "
         "de ajuste.",
         "Un clic casi nunca cae justo sobre la celda del cauce en el modelo. Sin el ajuste, la cuenca saldría de "
         "unas pocas celdas. Un radio muy grande puede saltar al río vecino: la página muestra cuánto se movió el "
         "punto y el área resultante para que lo revises.",
         ("ideam_era_2013", "esri_snap_pour_point"),
         "El radio de ajuste (300 m por defecto) y la ubicación del punto."),
    Paso("terreno.cuenca", "Cuenca",
         "Se marcan todas las celdas que drenan al punto de cierre y se convierten en un polígono. El área sale del "
         "número de celdas por el área de cada una.",
         "Es la unidad de análisis de todo el estudio: la lluvia, los suelos y el caudal se calculan sobre ella.",
         ("ideam_era_2013", "herramienta_control_borde")),
    Paso("terreno.red", "Red de drenaje",
         "Son cauces las celdas cuya área aportante supera el umbral. Cada tramo lleva su orden de Strahler y su "
         "longitud.",
         "La guía de rondas hídricas advierte que la densidad de drenaje depende de cómo se obtuvo la red. Por eso el "
         "umbral queda declarado en los resultados y en el informe, para compararlo con la red oficial.",
         ("mads_rondas_2018", "strahler_1957", "ideam_era_2013"),
         "El umbral de área para la red (1 km² por defecto)."),
    Paso("terreno.comparacion", "Comparación con un segundo modelo",
         "La cuenca se delimita también con el SRTM de la NASA, un modelo independiente de Copernicus, y se comparan "
         "el área y la coincidencia de los dos polígonos. El punto se ubica en el SRTM buscando el área que más se "
         "parece a la de Copernicus.",
         "El IDEAM pide evaluar la calidad y la incertidumbre de los datos de entrada. Si dos modelos distintos dan "
         "cuencas parecidas, la delimitación es confiable; si difieren mucho, hay que revisar el punto o el terreno.",
         ("ideam_protocolo_2018", "herramienta_comparar_dem", "mapzen_terrain_srtm", "lehner_2011_snapping")),
    Paso("terreno.exportar", "Exportar",
         "Cuenca, punto de cierre y red en GeoPackage (Magna-Sirgas origen nacional) para QGIS o ArcGIS, y en KML "
         "para Google Earth. Las áreas van en hectáreas con dos decimales y las longitudes con al menos un decimal.",
         "Son los formatos y la precisión que pide Minambiente para la información geográfica de los estudios "
         "ambientales. El KML va en coordenadas geográficas porque Google Earth solo lee ese sistema.",
         ("minambiente_res940_2026", "igac_res471_2020")),
]

PASOS: dict[str, Paso] = {p.clave: p for p in _PASOS}


def paso(clave: str) -> Paso:
    return PASOS[clave]
