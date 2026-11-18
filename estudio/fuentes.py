"""Registro de fuentes del estudio hidrológico.

Cada cálculo o decisión del estudio apunta a una o varias claves de este registro. Así la página puede mostrar la
fuente junto a cada resultado y el informe (etapa 8) arma la bibliografía en APA 7 sin escribirla dos veces.

Cada fuente lleva una **marca** que dice qué tan oficial es su respaldo, en el orden de prioridad acordado con el
usuario el 17 nov 2026: primero entidades ambientales, luego otras entidades oficiales, y lo demás se declara.
"""
from __future__ import annotations

from dataclasses import dataclass

# Marcas visibles en la página y en el informe. El orden es el de prioridad.
MARCAS = {
    "ambiental": "Fuente ambiental oficial",
    "oficial": "Otra entidad oficial",
    "literatura": "Referencia técnica (sin norma colombiana)",
    "hidrologo": "Decisión del hidrólogo",
    "sin_fuente": "Sin fuente oficial",
}

MARCAS_DESCRIPCION = {
    "ambiental": "Lo respalda una entidad ambiental colombiana: IDEAM, CAR u otra corporación, Minambiente o ANLA.",
    "oficial": "Lo respalda otra entidad oficial colombiana (IGAC, SGC, INVÍAS…), porque las ambientales no lo traen "
               "escrito.",
    "literatura": "Es un método publicado en la literatura técnica internacional. Ninguna norma colombiana lo fija; "
                  "se usa porque es el estándar del método que sí pide la norma.",
    "hidrologo": "Lo decide el hidrólogo responsable del estudio. La página propone un valor y lo deja editable.",
    "sin_fuente": "Es un control o una decisión de esta herramienta, sin respaldo oficial. Se declara para que el "
                  "revisor lo sepa.",
}


@dataclass(frozen=True)
class Fuente:
    clave: str
    cita: str          # referencia completa en APA 7
    corta: str         # cita en el texto, p. ej. "IDEAM (2013)"
    marca: str         # clave de MARCAS
    url: str = ""
    nota: str = ""     # qué se toma de esta fuente (página, tabla, ecuación)

    @property
    def marca_texto(self) -> str:
        return MARCAS[self.marca]


_FUENTES = [
    # --- Entidades ambientales ---
    Fuente("ideam_era_2013",
           "Instituto de Hidrología, Meteorología y Estudios Ambientales [IDEAM]. (2013). Lineamientos conceptuales y "
           "metodológicos para la Evaluación Regional del Agua. IDEAM.",
           "IDEAM (2013)", "ambiental",
           "https://www.minambiente.gov.co/wp-content/uploads/2021/10/Anexo-42.-Lineamientos-Conceptuales-y-"
           "Metodologicos-para-las-Evaluacion-Regional-del-Agua-2013.pdf",
           "p. 104 y figura 28: la red y las cuencas se sacan del modelo de elevación con dirección de flujo D8 "
           "(códigos 1 a 128), acumulación de flujo y puntos de cierre."),
    Fuente("ideam_protocolo_2018",
           "Instituto de Hidrología, Meteorología y Estudios Ambientales [IDEAM]. (2018). Protocolo de modelación "
           "hidrológica e hidráulica. IDEAM.",
           "IDEAM (2018)", "ambiental", "",
           "Calidad de los datos de entrada, evaluación de incertidumbre y documento síntesis (anexo 9)."),
    Fuente("minambiente_res940_2026",
           "Ministerio de Ambiente y Desarrollo Sostenible. (2026). Resolución 940 de 2026, anexo: Metodología general "
           "para la elaboración y presentación de estudios ambientales.",
           "Minambiente (2026)", "ambiental", "",
           "Numeral 3.2: información geográfica en Magna-Sirgas origen nacional; áreas en hectáreas con al menos "
           "dos decimales; longitudes con al menos un decimal; formatos Shapefile, GeoPackage o geodatabase."),
    Fuente("mads_rondas_2018",
           "Ministerio de Ambiente y Desarrollo Sostenible. (2018). Guía técnica de criterios para el acotamiento de "
           "las rondas hídricas en Colombia. MADS.",
           "MADS (2018)", "ambiental", "",
           "La densidad de drenaje depende de la escala de la red; hay que declarar cómo se obtuvo la red y "
           "compararla con la red oficial del IGAC 1:25.000."),
    Fuente("car_pomca_bogota_2019",
           "Corporación Autónoma Regional de Cundinamarca [CAR]. (2019). Actualización del Plan de Ordenación y "
           "Manejo de la Cuenca Hidrográfica del río Bogotá. Volumen I: caracterización física. CAR.",
           "CAR (2019)", "ambiental", "",
           "Tabla 5.9 (pp. 314-315): morfometría oficial de la subcuenca del río Teusacá, usada para validar."),
    # --- Otras entidades oficiales ---
    Fuente("igac_res471_2020",
           "Instituto Geográfico Agustín Codazzi [IGAC]. (2020). Resolución 471 de 2020, por medio de la cual se "
           "establecen las especificaciones técnicas mínimas de la cartografía básica oficial de Colombia "
           "(modificada por la Resolución 529 de 2020).",
           "IGAC (2020)", "oficial", "",
           "Adopta el sistema de proyección cartográfica Origen Nacional (CTM12), EPSG:9377."),
    # --- Datos de terreno ---
    Fuente("copernicus_glo30",
           "European Space Agency. (2021). Copernicus DEM: Copernicus Digital Elevation Model GLO-30 [Conjunto de "
           "datos]. https://doi.org/10.5270/ESA-c5d3d65",
           "ESA (2021)", "literatura",
           "https://registry.opendata.aws/copernicus-dem/",
           "Modelo de elevación global de 30 m (1 segundo de arco), de libre uso, leído en línea desde el registro "
           "de datos abiertos de AWS. No es un producto colombiano: el informe lo declara."),
    Fuente("mapzen_terrain_srtm",
           "Mapzen. (2017). Terrain Tiles [Conjunto de datos]. Registry of Open Data on AWS. "
           "https://registry.opendata.aws/terrain-tiles/",
           "Mapzen (2017)", "literatura", "https://github.com/tilezen/joerd/blob/master/docs/data-sources.md",
           "Teselas de elevación cuyo origen en Colombia es el SRTM de la NASA (misión de radar del año 2000). Se "
           "usan como segundo modelo, independiente de Copernicus, para comparar la cuenca."),
    Fuente("dem_propio",
           "Modelo de elevación suministrado por el usuario.",
           "Modelo propio", "hidrologo", "",
           "El hidrólogo sube su propio GeoTIFF y responde por su origen; el informe muestra el nombre del archivo."),
    Fuente("esri_snap_pour_point",
           "Esri. (s. f.). Snap Pour Point (Spatial Analyst). ArcGIS Pro documentation. "
           "https://pro.arcgis.com/en/pro-app/latest/tool-reference/spatial-analyst/snap-pour-point.htm",
           "Esri (s. f.)", "literatura", "",
           "Ajuste del punto de cierre a la celda de mayor acumulación dentro de un radio; es la herramienta que el "
           "IDEAM (2013) usa como referencia para su procedimiento en ArcGIS."),
    # --- Algoritmos (literatura técnica) ---
    Fuente("ocallaghan_mark_1984",
           "O'Callaghan, J. F., & Mark, D. M. (1984). The extraction of drainage networks from digital elevation "
           "data. Computer Vision, Graphics, and Image Processing, 28(3), 323-344. "
           "https://doi.org/10.1016/S0734-189X(84)80011-0",
           "O'Callaghan y Mark (1984)", "literatura", "",
           "Método D8: cada celda drena hacia la vecina de mayor pendiente, de las 8 que la rodean."),
    Fuente("barnes_2014_priority_flood",
           "Barnes, R., Lehman, C., & Mulla, D. (2014). Priority-flood: An optimal depression-filling and "
           "watershed-labeling algorithm for digital elevation models. Computers & Geosciences, 62, 117-127. "
           "https://doi.org/10.1016/j.cageo.2013.04.024",
           "Barnes et al. (2014a)", "literatura", "",
           "Relleno de depresiones: sube cada hueco hasta el nivel por donde se desborda."),
    Fuente("barnes_2014_flats",
           "Barnes, R., Lehman, C., & Mulla, D. (2014). An efficient assignment of drainage direction over flat "
           "surfaces in raster digital elevation models. Computers & Geosciences, 62, 128-135. "
           "https://doi.org/10.1016/j.cageo.2013.01.009",
           "Barnes et al. (2014b)", "literatura", "",
           "Zonas planas: les da una pendiente mínima ficticia para que el agua sepa hacia dónde salir."),
    Fuente("strahler_1957",
           "Strahler, A. N. (1957). Quantitative analysis of watershed geomorphology. Eos, Transactions American "
           "Geophysical Union, 38(6), 913-920. https://doi.org/10.1029/TR038i006p00913",
           "Strahler (1957)", "literatura", "",
           "Orden de los cauces: los nacimientos son orden 1; dos cauces del mismo orden forman uno de orden mayor."),
    Fuente("bartos_2020_pysheds",
           "Bartos, M. (2020). pysheds: Simple and fast watershed delineation in Python (Versión 0.5) "
           "[Software]. Zenodo. https://doi.org/10.5281/zenodo.3822494",
           "Bartos (2020)", "literatura", "https://github.com/mdbartos/pysheds",
           "Librería de código abierto que implementa los algoritmos anteriores."),
    Fuente("lehner_2011_snapping",
           "Lehner, B. (2011). Derivation of watershed boundaries for GRDC gauging stations based on the HydroSHEDS "
           "drainage network (GRDC Report Series, Report 41). Global Runoff Data Centre, Federal Institute of "
           "Hydrology (BfG).",
           "Lehner (2011)", "literatura", "",
           "Para ubicar una estación sobre la red de un modelo de elevación se busca, dentro de un radio, la celda "
           "cuya área aportante coincide mejor con el área conocida."),
    # --- Controles propios ---
    Fuente("herramienta_control_borde",
           "Control de esta herramienta: prueba de borde del área aportante.",
           "Control propio", "sin_fuente", "",
           "Si la cuenca toca el borde del modelo de elevación, puede estar cortada: falta terreno aguas arriba."),
    Fuente("herramienta_comparar_dem",
           "Control de esta herramienta: comparación de la cuenca delimitada con dos modelos de elevación.",
           "Control propio", "sin_fuente", "",
           "Responde a la evaluación de calidad e incertidumbre de los datos que pide el IDEAM (2018); la forma "
           "de compararlos (diferencia de área y coincidencia) es de esta herramienta."),
]

FUENTES: dict[str, Fuente] = {f.clave: f for f in _FUENTES}


def fuente(clave: str) -> Fuente:
    try:
        return FUENTES[clave]
    except KeyError as e:  # una clave mal escrita es un error de programación, no del usuario
        raise KeyError(f"Fuente desconocida: {clave!r}") from e


def marca_principal(claves: list[str]) -> str:
    """La marca más fuerte entre varias fuentes (la primera en el orden de MARCAS)."""
    orden = list(MARCAS)
    return min((fuente(c).marca for c in claves), key=orden.index)


def bibliografia(claves) -> list[str]:
    """Referencias APA 7 sin repetir, ordenadas alfabéticamente, como pide la norma."""
    return sorted({fuente(c).cita for c in claves}, key=str.lower)
