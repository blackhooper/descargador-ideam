import streamlit as st

# ===========================================================================
# IDIOMA DE LA INTERFAZ (espanol o ingles)
# La app esta escrita en espanol: cada texto visible pasa por tr(), que lo devuelve tal cual en espanol o su
# traduccion de EN en ingles. Un texto sin traduccion sale en espanol (no rompe nada). El idioma se elige con el boton
# ES/EN de arriba a la derecha y viaja en la direccion (?lang=en) para que sobreviva a una recarga.
# Los nombres de variables, parametros, departamentos y estaciones vienen del IDEAM y no se traducen.
# ===========================================================================

IDIOMAS = {"es": "Español", "en": "English"}


def actual():
    """Idioma elegido ("es" o "en"). Fuera de una sesion (hilos de carga por detras) es espanol."""
    try:
        return st.session_state.get("idioma", "es")
    except Exception:
        return "es"


def tr(texto, **valores):
    """Texto en el idioma elegido. `valores` llena los huecos {asi} del texto (en los dos idiomas)."""
    if actual() == "en":
        texto = EN.get(texto, texto)
    return texto.format(**valores) if valores else texto


def num(n):
    """Cifra entera con separador de miles: 1.234 en espanol, 1,234 en ingles."""
    texto = f"{n:,.0f}"
    return texto if actual() == "en" else texto.replace(",", ".")


def traducir_js(codigo):
    """Guion del navegador con sus textos en el idioma elegido (en espanol queda igual)."""
    if actual() != "en":
        return codigo
    for es, en in JS_EN:
        codigo = codigo.replace(es, en)
    return codigo


EN = {
    # ---- Parametros ----
    "Consulta y descarga de datos hidrometeorológicos": "Hydrometeorological data query and download",
    "Serie de tiempo y frecuencia": "Time series and frequency",
    "Estándar": "Standard",
    "Especial": "Special",
    "**Estándar:** se elige la variable y luego el parámetro (series diarias, mensuales, anuales, horarias y de alta "
    "frecuencia).\n\n**Especial:** se elige la frecuencia (decadal o multianual), la variable y el parámetro con su "
    "cálculo: suma, máximo, mínimo o promedio de cada década, o el mínimo, la media y el máximo de cada mes en todo el "
    "periodo.":
        "**Standard:** choose the variable and then the parameter (daily, monthly, annual, hourly and high-frequency "
        "series).\n\n**Special:** choose the frequency (decadal or multi-year), the variable and the parameter with its "
        "aggregation: sum, maximum, minimum or mean of each 10-day period, or the minimum, mean and maximum of each "
        "month over the whole period.",
    "Frecuencia": "Frequency",
    "Variable": "Variable",
    "Parámetro": "Parameter",
    "Escribe para buscar": "Type to search",
    "No disponible": "Not available",
    "No disponible por ahora": "Not available yet",
    "Sin variables": "No variables",
    "Sin parámetros": "No parameters",
    "No se pudo cargar la lista de variables del IDEAM.": "The IDEAM variable list could not be loaded.",
    "Reintentar": "Retry",
    "Serie de alta frecuencia: un mes por consulta.": "High-frequency series: one month per request.",
    "El IDEAM entrega estas series de a un mes por consulta: diez años son 120 consultas por estación. Conviene usar "
    "periodos cortos y pocas estaciones.":
        "IDEAM serves these series one month per request: ten years means 120 requests per station. Short periods and "
        "a few stations work best.",
    "Desde": "From",
    "Hasta": "To",
    "La fecha inicial debe ser anterior a la final.": "The start date must be earlier than the end date.",
    "El periodo es demasiado largo para un Excel.": "The period is too long for a single Excel file.",
    "Con frecuencia {f}, daría hasta {n} filas por estación y Excel admite alrededor de un millón por hoja. Acorta el "
    "periodo.":
        "Frequency: {f}. This would produce up to {n} rows per station, and Excel supports about one million rows per "
        "sheet. Please shorten the period.",
    "Con frecuencia {f}, daría hasta {n} filas por estación y Excel admite alrededor de un millón por hoja. Acorta el "
    "periodo en Parámetros.":
        "Frequency: {f}. This would produce up to {n} rows per station, and Excel supports about one million rows per "
        "sheet. Please shorten the period under Parameters.",
    "El periodo es demasiado largo para una serie multianual.": "The period is too long for a multi-year series.",
    "El IDEAM calcula los valores multianuales de una sola vez y para esta serie acepta hasta {n} años por consulta. "
    "Acorta el periodo.":
        "IDEAM computes multi-year values in a single pass and accepts up to {n} years per request for this series. "
        "Please shorten the period.",
    "Filtrar por ubicación · opcional": "Filter by location · optional",
    "Departamento": "Department",
    "Municipio": "Municipality",
    "Estaciones": "Stations",
    "Elige un departamento": "Choose a department",
    "Todas · nombre o código": "All · name or code",
    "Ver {n} {estaciones} en el mapa": "View {n} {estaciones} on the map",
    "Seleccionar área en el mapa": "Select area on the map",
    "Pasos de la consulta": "Query steps",
    "Establecer parámetros": "Set parameters",
    "Serie, variable y periodo.": "Series, variable and period.",
    "Delimitar el área de análisis": "Define the study area",
    "Zona de estudio y cobertura de cada estación.": "Study area and data coverage of each station.",
    "Preparar la descarga": "Prepare the download",
    "Nombre del ZIP y organización de los archivos.": "ZIP name and file organization.",
    "Datos del IDEAM: uso personal y no comercial; cita la fuente.":
        "IDEAM data: personal, non-commercial use; cite the source.",
    "Ver condiciones": "View terms",
    "Ver condiciones completas": "View full terms",
    "Herramienta independiente, no oficial del IDEAM": "Independent tool, not affiliated with IDEAM",
    "Manual de usuario": "User manual",
    "se abre en otra pestaña": "opens in a new tab",
    "Los datos provienen del IDEAM y su descarga está autorizada para uso personal, privado y no comercial. No pueden "
    "comercializarse ni venderse. Todo trabajo que los utilice debe citar la fuente (el ZIP incluye la cita en "
    "CITACION.txt). El IDEAM no se hace responsable del uso de los datos ni de las interpretaciones o inferencias "
    "derivadas de ellos. Esta es una herramienta independiente, no oficial del IDEAM.":
        "The data come from IDEAM (Colombia's Institute of Hydrology, Meteorology and Environmental Studies) and may be "
        "downloaded for personal, private and non-commercial use only. They may not be commercialized or sold. Any "
        "work that uses them must cite the source (the ZIP includes the citation in CITACION.txt). IDEAM is not "
        "responsible for the use of the data or for any interpretation or inference derived from them. This is an "
        "independent tool, not affiliated with IDEAM.",
    "Faltan el usuario y la clave del portal DHIME del IDEAM. En tu computador van en `.streamlit/secrets.toml`; en "
    "Streamlit Cloud, en Settings → Secrets de la app, así:":
        "The IDEAM DHIME portal username and password are missing. Locally they go in `.streamlit/secrets.toml`; on "
        "Streamlit Cloud, in the app's Settings → Secrets, like this:",
    "Lista de variables del IDEAM: pendiente": "IDEAM variable list: loading",
    "Lista de variables del IDEAM: disponible": "IDEAM variable list: ready",
    "Lista de variables del IDEAM: no disponible": "IDEAM variable list: unavailable",
    "opcional": "optional",
    "Ver más": "More",
    "Ver detalles": "Details",
    # frecuencias (en minuscula, dentro de una frase) y las de la serie especial
    "anual": "annual", "mensual": "monthly", "decadal": "10-day (decadal)", "diaria": "daily", "horaria": "hourly",
    "3 veces al día": "3 times a day", "2 veces al día": "twice a day", "cada 10 minutos": "every 10 minutes",
    "cada 5 minutos": "every 5 minutes", "cada 05 minutos": "every 5 minutes", "cada 02 minutos": "every 2 minutes", "cada 2 minutos": "every 2 minutes", "minutal": "every minute",
    "multianual": "multi-year",
    "Decadal": "Decadal (10-day)", "Multianual": "Multi-year",

    # ---- Ajustes ----
    "Ajustes": "Settings",
    "Apariencia": "Appearance",
    "Tema": "Theme",
    "Claro": "Light",
    "Oscuro": "Dark",
    "Alto contraste": "High contrast",
    "Superficies opacas, bordes nítidos y foco más grueso. Si tu equipo pide más contraste, se aplica solo.":
        "Opaque surfaces, crisp borders and a thicker focus ring. Applied automatically if your system requests more "
        "contrast.",
    "Rendimiento": "Performance",
    "Modo Lite": "Lite mode",
    "Modo Lite activado": "Lite mode on",
    "Menos efectos visuales (sin desenfoque ni animaciones) y un 3D más liviano. Los datos y las funciones son los "
    "mismos.":
        "Fewer visual effects (no blur or animations) and a lighter 3D view. Same data and features.",
    "Las animaciones respetan la opción de reducir el movimiento de tu equipo.":
        "Animations follow your system's reduced-motion setting.",
    "Durante la descarga los ajustes quedan bloqueados": "Settings are locked while a download is running",

    # ---- Mapa: panel ----
    "Consulta": "Query",
    "Ocultar la consulta": "Hide the query panel",
    "Mostrar la consulta": "Show the query panel",
    "Cerrar la consulta": "Close the query panel",
    "Cerrar": "Close",
    "Estaciones elegidas": "Selected stations",
    "Área de estudio": "Study area",
    "Sin definir": "Not defined",
    "Calidad de los datos": "Data quality",
    "Pulsa para cambiar la variable o el periodo": "Click to change the variable or period",
    "Cambiar la variable o el periodo": "Change the variable or period",
    "Para cambiar el área, vuelve a la vista 2D.": "To change the area, go back to the 2D view.",
    "Ver en 2D": "View in 2D",
    "Ver en 3D": "View in 3D",
    "Dibujar otro rectángulo": "Draw another rectangle",
    "Dibujar un rectángulo": "Draw a rectangle",
    "Redibujar": "Redraw",
    "Ajustar las esquinas": "Adjust the corners",
    "Ajustar": "Adjust",
    "Borrar el área": "Delete the area",
    "Borrar": "Delete",
    "Elegir las estaciones con un área del mapa": "Choose stations with an area on the map instead",
    "Quitar filtro": "Clear filter",
    "Sin buffer": "No buffer",
    "Franja alrededor del área para incluir las estaciones cercanas":
        "Margin around the area to include nearby stations",
    "Incluir estaciones cercanas": "Include nearby stations",
    "Agrega una franja alrededor del área para tener en cuenta las estaciones cercanas.":
        "Adds a margin around the area so nearby stations are taken into account.",
    "Ancho del buffer (km)": "Buffer width (km)",
    "No se pudo consultar el IDEAM": "IDEAM could not be reached",
    "No se pudo consultar el IDEAM.": "IDEAM could not be reached.",
    "Delimita el área de estudio para evaluar la disponibilidad de datos de cada estación.":
        "Define the study area to assess the data availability of each station.",
    "Ninguna estación tiene una cobertura entre {a} y {b} %.": "No station has a coverage between {a} and {b} %.",
    "Amplía el rango en el filtro de estaciones (arriba a la izquierda del mapa).":
        "Widen the range in the station filter (top left of the map).",
    "No hay estaciones del IDEAM en esta zona. Activa o amplía el buffer.":
        "There are no IDEAM stations in this area. Turn on or widen the buffer.",
    "Ninguna estación de la zona tiene datos de esta variable en el periodo.":
        "No station in this area has data for this variable in the period.",
    "Cambia la variable o el periodo, o amplía el buffer.": "Change the variable or the period, or widen the buffer.",
    "Estaciones encontradas": "Stations found",
    "{n} {estaciones} sin información": "{n} {estaciones} without data",
    "Todas con información": "All with data",
    "Estaciones con esta serie en {u}.": "Stations with this series in {u}.",
    "Estaciones del IDEAM en el área y el buffer.": "IDEAM stations in the area and the buffer.",
    " {n} tienen datos de esta variable en el periodo.": " {n} have data for this variable in the period.",
    "Cobertura media del periodo": "Mean coverage of the period",
    "Promedio de la cantidad probable de las estaciones seleccionadas: qué parte del periodo consultado cubre su "
    "registro (no descuenta los huecos internos).":
        "Average expected record count of the selected stations: how much of the requested period their record spans "
        "(internal gaps are not subtracted).",
    "Tamaño del ZIP": "ZIP size",
    "{t} aprox.": "≈ {t}",
    "Estimación para {n} {estaciones} y {r} registros probables. La descarga hace {b} consultas al IDEAM ":
        "Estimate for {n} {estaciones} and {r} expected records. The download makes {b} requests to IDEAM ",
    "(una por estación: la serie multianual se pide de una vez).":
        "(one per station: the multi-year series is requested in a single pass).",
    "de hasta {d} días.": "of up to {d} days each.",
    "{n} {estaciones} con altitud dudosa": "{n} {estaciones} with questionable elevation",
    "En el catálogo, su altitud difiere en más de {m} m del relieve en su punto. ":
        "Their catalog elevation differs by more than {m} m from the terrain at their location. ",
    "En esta zona el relieve va de <b>{a} a {b} m</b>. ": "In this area the terrain ranges from <b>{a} to {b} m</b>. ",
    "La mayor diferencia es la de <b>{e}</b>: el catálogo indica {c} m y el relieve, {t} m. Elige una fila para verla "
    "en el mapa 3D.":
        "The largest difference is at <b>{e}</b>: the catalog says {c} m and the terrain {t} m. Pick a row to see it on "
        "the 3D map.",
    "Estación": "Station",
    "Catálogo": "Catalog",
    "Relieve": "Terrain",
    "Diferencia": "Difference",
    "Catálogo menos relieve": "Catalog minus terrain",
    "Serie de alta frecuencia: {b} consultas al IDEAM.": "High-frequency series: {b} requests to IDEAM.",
    "El IDEAM entrega estas series de a {d} días por consulta (≈ {n} por estación), así que la descarga tarda más.":
        "IDEAM serves these series {d} days per request (≈ {n} per station), so the download takes longer.",
    "Estaciones a descargar": "Stations to download",
    "de": "of",
    "Color de su clase de cobertura (ver la leyenda)": "Color of its coverage class (see the legend)",
    "Cobertura": "Coverage",
    "Cantidad probable: qué parte del periodo cubre el registro de la estación":
        "Expected record count: how much of the period the station's record spans",
    "{n} en el área": "{n} in the area",
    " · {n} en el buffer": " · {n} in the buffer",
    "{n} con datos en el último año": "{n} with data in the last year",
    "Los datos recientes pueden ser preliminares.": "Recent data may be preliminary.",
    "Cada dato del IDEAM tiene un nivel de aprobación (preliminar, en revisión o definitivo); los preliminares pueden "
    "cambiar. Cada Excel lo indica en la columna «Nivel de Aprobación».":
        "Every IDEAM value has an approval level (preliminary, under review or final); preliminary values may change. "
        "Each Excel file shows it in the “Nivel de Aprobación” (approval level) column.",
    "Datos": "Data",
    "Uso personal, privado y no comercial; cita la fuente. Herramienta independiente, no oficial del IDEAM.":
        "Personal, private, non-commercial use; cite the source. Independent tool, not affiliated with IDEAM.",
    "versión": "version",
    "Fuentes y créditos de los mapas": "Map sources and credits",

    # ---- Mapa: herramientas, capas y leyenda ----
    "Herramientas del mapa": "Map tools",
    "Dibujo del área": "Area drawing",
    "Haz clic y arrastra sobre el mapa": "Click and drag on the map",
    "Usar el área visible": "Use the visible area",
    "Primero acércate a tu zona": "Zoom in to your area first",
    "Subir un archivo": "Upload a file",
    "SHP, GeoJSON, KML, KMZ o GPKG": "SHP, GeoJSON, KML, KMZ or GPKG",
    "Arrastra los vértices y pulsa «Guardar»": "Drag the vertices and click “Save”",
    "Mapa base": "Basemap",
    "Satélite con nombres": "Satellite with labels",
    "Satélite": "Satellite",
    "Calles": "Streets",
    "Satélite de noche": "Night satellite",
    "Topográfico": "Topographic",
    "Altura": "Elevation",
    "Rango de la zona": "Area range",
    "Rango de Colombia": "Colombia range",
    "Escala de la zona": "Area scale",
    "Escala de Colombia": "Colombia scale",
    "escala de la zona": "area scale",
    "escala de Colombia": "Colombia scale",
    "Escala de colores": "Color scale",
    "Acercar": "Zoom in",
    "Alejar": "Zoom out",
    "Herramientas del 3D": "3D tools",
    "Cámara: girar, inclinar y acercar": "Camera: rotate, tilt and zoom",
    "Cámara": "Camera",
    "Textura del relieve": "Terrain texture",
    "Inclinar más": "Tilt more",
    "Girar a la izquierda": "Rotate left",
    "Orientar al norte": "Reset to north",
    "Girar a la derecha": "Rotate right",
    "Inclinar menos": "Tilt less",
    "Gestos del mapa 3D": "3D map gestures",
    "Arrastrar": "Drag",
    "Mover el mapa": "Pan the map",
    "Clic derecho y arrastrar": "Right-click and drag",
    "Girar e inclinar": "Rotate and tilt",
    "Rueda": "Scroll wheel",
    "Acercar o alejar": "Zoom in or out",
    "Un dedo": "One finger",
    "Dos dedos": "Two fingers",
    "Girar; deslizar arriba o abajo inclina; pellizcar acerca": "Rotate; swipe up or down to tilt; pinch to zoom",
    "Disponibilidad estimada de datos en el periodo": "Estimated data availability in the period",
    "Alta": "High", "Media": "Medium", "Baja": "Low", "Crítica": "Critical",
    "Sin serie": "No series",
    "Excluida": "Excluded",
    "Altitud dudosa": "Questionable elevation",
    "Área": "Area",
    "Relieve exagerado ×2": "Terrain exaggerated ×2",
    "Leyenda": "Legend",
    "Altitud": "Elevation",
    "Relieve: Terrarium (Mapzen · AWS · SRTM/USGS) · Imagen: Esri": "Terrain: Terrarium (Mapzen · AWS · SRTM/USGS) · Imagery: Esri",
    "Buscando estaciones": "Searching for stations",
    "Filtrar estaciones": "Filter stations",
    "Cobertura del periodo": "Period coverage",
    "{a} de {b} {estaciones} en el rango. Las demás no se ven en el mapa ni se descargan.":
        "{a} of {b} {estaciones} in range. The rest are hidden from the map and not downloaded.",
    "Quitar el filtro": "Clear the filter",
    "estaciones": "stations",
    "estación": "station",
    "estaciones con datos": "stations with data",
    "estación con datos": "station with data",
    "No hay estaciones aquí · amplía el buffer": "No stations here · widen the buffer",
    "Ninguna estación tiene datos en el periodo": "No station has data in the period",
    "Delimita el área en la vista 2D para verla en relieve.": "Define the area in the 2D view to see it in 3D.",
    "No hay estaciones en esta zona. Activa o amplía el buffer.":
        "There are no stations in this area. Turn on or widen the buffer.",
    "Tu equipo pide reducir el movimiento, así que la animación de entrada no se reproduce sola. Puedes verla con el "
    "botón ↻ de abajo.":
        "Your system requests reduced motion, so the intro animation does not play automatically. You can play it with "
        "the ↻ button below.",
    "Vista del mapa": "Map view",
    "Repetir animación": "Replay animation",
    "En modo Lite no hay animación de entrada. Desactívalo en Ajustes para verla.":
        "Lite mode has no intro animation. Turn it off in Settings to see it.",
    "Repetir la animación de entrada al 3D": "Replay the 3D intro animation",
    "Preparar descarga": "Prepare download",
    "Delimita el área de estudio": "Define the study area",
    "El periodo es demasiado largo para Excel": "The period is too long for Excel",
    "Selecciona al menos una estación": "Select at least one station",
    "No hay estaciones con datos en esta zona": "No stations with data in this area",

    # ---- Ficha de la estacion y tooltips ----
    "Ver la ficha de la estación": "View the station details",
    "ficha de la estación": "station details",
    "Quitar la selección": "Clear the selection",
    "Quitar selección": "Clear selection",
    "Código": "Code",
    "altitud sin dato": "no elevation data",
    "sin evaluar": "not assessed",
    " · excluida": " · excluded",
    "En el área": "In the area",
    "en el área": "in the area",
    "En el buffer": "In the buffer",
    "en el buffer": "in the buffer",
    "En la cuenca": "In the area",
    "⚠ Altitud dudosa: el relieve marca {m} m": "⚠ Questionable elevation: the terrain shows {m} m",
    "Cobertura **{p} %** ({clase}) · serie {a}–{b}": "Coverage **{p} %** ({clase}) · series {a}–{b}",
    "Sin serie de esta variable en DHIME": "No series for this variable in DHIME",
    "Sin serie de este parámetro en DHIME": "No series for this parameter in DHIME",
    "Incluir en la descarga": "Include in the download",
    "Altitud dudosa · Ver detalles": "Questionable elevation · Details",
    "Según el relieve, el terreno en ese punto está a <b>{t} m</b>, pero el catálogo del IDEAM sitúa la estación a "
    "<b>{a} m</b>: <b>{d} m más {lado}</b>.":
        "According to the terrain model, the ground at that point is at <b>{t} m</b>, but the IDEAM catalog places the "
        "station at <b>{a} m</b>: <b>{d} m {lado}</b>.",
    "arriba": "higher",
    "abajo": "lower",
    " En toda la zona el terreno va de {a} a {b} m, así que esa altitud no es posible aquí.":
        " Across the area the terrain ranges from {a} to {b} m, so that elevation is not possible here.",
    " En toda la zona el terreno llega como máximo a {b} m, así que esa altitud no es posible aquí.":
        " Across the area the terrain reaches at most {b} m, so that elevation is not possible here.",
    " En toda la zona el terreno va de {a} a {b} m, así que la altitud podría ser correcta y el error estar en las "
    "coordenadas de la estación.":
        " Across the area the terrain ranges from {a} to {b} m, so the elevation may be right and the error may be in "
        "the station's coordinates.",
    " En el mapa 3D, la marca naranja muestra dónde quedaría con la altitud del catálogo.":
        " On the 3D map, the orange marker shows where it would sit at the catalog elevation.",
    "Excluida de la descarga": "Excluded from the download",
    "Cantidad probable": "Expected records",
    "Cantidad probable <b>{p} %</b> · cobertura {clase}": "Expected records <b>{p} %</b> · {clase} coverage",
    "Serie": "Series",

    # ---- Subir un area ----
    "Subir el contorno del área": "Upload the area boundary",
    "SHP (en ZIP o suelto), GeoJSON, KML, KMZ o GPKG. Si el archivo no trae sistema de coordenadas, te avisaremos.":
        "SHP (zipped or loose), GeoJSON, KML, KMZ or GPKG. If the file has no coordinate system, we will let you know.",
    "Archivo del área": "Area file",
    "El archivo solo tiene puntos o líneas. Sube el contorno (polígono) del área.":
        "The file only has points or lines. Please upload the area boundary (polygon).",
    "Archivo válido: {n} {poligonos}.": "Valid file: {n} {poligonos}.",
    "polígonos": "polygons",
    "polígono": "polygon",
    "Usar esta área": "Use this area",
    "El archivo o conjunto de datos está vacío.": "The file or dataset is empty.",
    "El archivo no trae ninguna geometría.": "The file has no geometry.",
    "El archivo contiene geometrías inválidas que no se pudieron reparar.":
        "The file contains invalid geometries that could not be repaired.",
    "Había geometrías inválidas y se repararon automáticamente.":
        "Some geometries were invalid and were repaired automatically.",

    # ---- Exportacion ----
    "Exportación": "Export",
    "Descargando datos del IDEAM": "Downloading IDEAM data",
    "Descarga lista": "Download ready",
    "No se pudo descargar": "The download failed",
    "Descarga detenida": "Download stopped",
    "Preparando…": "Preparing…",
    "Terminando…": "Finishing…",
    "Faltan ≈ {t}": "≈ {t} left",
    "Faltan unos segundos": "A few seconds left",
    "<span>Estaciones <b>{a} de {b}</b></span>": "<span>Stations <b>{a} of {b}</b></span>",
    "Puedes seguir mirando esta pantalla; si cierras la pestaña, la descarga se detiene.":
        "You can keep this screen open; closing the tab stops the download.",
    "Detener la descarga": "Stop the download",
    "Sin terminar": "Not finished",
    "No se guardó nada": "Nothing was saved",
    "Puedes reintentarla o volver al mapa para cambiar la selección.":
        "You can retry it or go back to the map to change the selection.",
    "Volver al mapa": "Back to the map",
    "Completada en {t}": "Completed in {t}",
    "<span>Guardadas <b>{g}</b></span><span>Omitidas <b>{o}</b></span>":
        "<span>Saved <b>{g}</b></span><span>Skipped <b>{o}</b></span>",
    "Separar en carpetas por cobertura": "Split into folders by coverage",
    "Alta (70–100 %), media (50–70 %), baja (25–50 %) y crítica (0–25 %) del periodo consultado. Sin marcar, todos los "
    "Excel van juntos.":
        "High (70–100 %), medium (50–70 %), low (25–50 %) and critical (0–25 %) coverage of the requested period. "
        "Unchecked, all Excel files go together.",
    "Nombre del archivo ZIP": "ZIP file name",
    "Por ejemplo: descarga 1. La extensión .zip se añade sola.": "For example: download 1. The .zip extension is added "
                                                                "automatically.",
    "Descargar el ZIP": "Download the ZIP",
    "Nueva consulta": "New query",
    "Periodo": "Period",
    "Archivo": "File",
    "Fuente": "Source",
    "Frecuencia {f}": "Frequency: {f}",
    " · cálculo {c}": " · aggregation {c}",
    "Un Excel por estación": "One Excel file per station",
    "Carpetas por cobertura": "Folders by coverage",
    "Alta, media, baja y crítica": "High, medium, low and critical",
    "Cobertura y resultado por estación": "Coverage and result per station",
    "Cita de la fuente": "Source citation",
    "Avance de la descarga": "Download progress",
    "Recibo de la descarga": "Download receipt",
    "Estaciones guardadas por cobertura": "Saved stations by coverage",
    "Datos del IDEAM: uso personal y no comercial; cita la fuente (el ZIP incluye CITACION.txt).":
        "IDEAM data: personal, non-commercial use; cite the source (the ZIP includes CITACION.txt).",
    "en ≈ {t}": "in ≈ {t}",
    "en cualquier momento": "at any moment",
    "El servidor está ocupado: hay {n} descargas en curso. Eres el número {p} en la fila y la tuya empezará sola "
    "{cuando} (llevas {t}).":
        "The server is busy: {n} downloads are running. You are number {p} in the queue and yours will start "
        "automatically {cuando} (waiting for {t}).",
    "No se pudo completar la descarga.": "The download could not be completed.",
    # mensajes de acceso al portal (ideam_downloader.mensaje_acceso)
    "La aplicación no tiene configurado el acceso al portal del IDEAM.":
        "The app is not configured to access the IDEAM portal.",
    "El portal del IDEAM no respondió. Revisa tu conexión a internet o inténtalo en unos minutos.":
        "The IDEAM portal did not respond. Check your internet connection or try again in a few minutes.",
    "El portal del IDEAM rechazó el acceso de la herramienta. Lo más probable es que el portal haya cambiado su forma "
    "de acceso y el Descargador necesite actualizarse. Si el problema continúa, la herramienta necesita una "
    "actualización.":
        "The IDEAM portal rejected the tool's access. Most likely the portal changed its access method and the "
        "downloader needs an update. If the problem persists, the tool needs an update.",
    "No se pudo acceder al portal del IDEAM. Si el problema continúa, la herramienta necesita una actualización.":
        "The IDEAM portal could not be accessed. If the problem persists, the tool needs an update.",
}

# Textos del guion del navegador (estilo._UI): literales completos, con sus comillas, para no tocar otra cosa. Los de
# Streamlit que el guion pasaba al espanol vuelven a su ingles original.
JS_EN = [
    ('"Ocultar la consulta"', '"Hide the query panel"'), ('"Mostrar la consulta"', '"Show the query panel"'),
    ('n.nodeValue = "Elegir todas"', 'n.nodeValue = "Select all"'),
    ('n.nodeValue = "Sin resultados"', 'n.nodeValue = "No results"'),
    ('"Elegir las $1 coincidencias"', '"Select $1 matches"'),
    ('b.setAttribute("aria-label", "Borrar")', 'b.setAttribute("aria-label", "Clear value")'),
    ('b.setAttribute("aria-label", "Quitar todas")', 'b.setAttribute("aria-label", "Clear all")'),
    ('"Arrastra los archivos aquí"', '"Drag and drop files here"'),
    ('"Arrastra el archivo aquí"', '"Drag and drop file here"'),
    ('"Browse files": "Elegir archivos", "Upload": "Elegir archivos"', '"Browse files": "Browse files", "Upload": "Upload"'),
    ('"Hasta $1 MB por archivo"', '"Limit $1 MB per file"'),
    ('{title: "Cancelar el dibujo", text: "Cancelar"}', '{title: "Cancel drawing", text: "Cancel"}'),
    ('{title: "Terminar el dibujo", text: "Terminar"}', '{title: "Finish drawing", text: "Finish"}'),
    ('{title: "Borrar el último punto", text: "Deshacer"}', '{title: "Delete last point", text: "Undo"}'),
    ('{rectangle: "Dibujar un rectángulo"}', '{rectangle: "Draw a rectangle"}'),
    ('"Haz clic y arrastra para dibujar el rectángulo."', '"Click and drag to draw the rectangle."'),
    ('"Suelta para terminar."', '"Release to finish."'),
    ('{title: "Guardar los cambios", text: "Guardar"}', '{title: "Save changes", text: "Save"}'),
    ('{title: "Descartar los cambios", text: "Cancelar"}', '{title: "Discard changes", text: "Cancel"}'),
    ('{title: "Borrar todo", text: "Borrar todo"}', '{title: "Clear all", text: "Clear all"}'),
    ('edit: "Ajustar las esquinas"', 'edit: "Adjust the corners"'),
    ('"No hay nada que ajustar"', '"Nothing to adjust"'), ('remove: "Borrar el área"', 'remove: "Delete the area"'),
    ('"No hay nada que borrar"', '"Nothing to delete"'),
    ('"Arrastra los vértices para ajustar el área."', '"Drag the vertices to adjust the area."'),
    ('"Pulsa «Guardar» al terminar o «Cancelar» para deshacer."', '"Click “Save” when done or “Cancel” to undo."'),
    ('"Haz clic en el área para borrarla."', '"Click the area to delete it."'),
    ('"Mapa. Con el teclado: flechas para moverte, + y − para acercar o alejar"',
     '"Map. With the keyboard: arrows to pan, + and − to zoom in or out"'),
    ('"Disponible en la vista 2D"', '"Available in the 2D view"'),
    ('"Lo que ves ahora en el mapa"', '"What you see on the map right now"'),
    ('"Primero acércate a tu zona"', '"Zoom in to your area first"'),
    ('"Rumbo " + Math.round(((n.bearing', '"Bearing " + Math.round(((n.bearing'),
    ('"°, inclinación "', '"°, tilt "'),
    ('txt = "Rumbo " + rumbo + "° · Inclinación "', 'txt = "Bearing " + rumbo + "° · Tilt "'),
    ('tipo: "Fallo gráfico"', 'tipo: "Graphics failure"'),
    ('"Se perdió el contexto gráfico (WebGL)"', '"The graphics context (WebGL) was lost"'),
    ('"La vista 3D se detuvo. Suele ocurrir cuando el navegador se queda sin memoria gráfica. "',
     '"The 3D view stopped. This usually happens when the browser runs out of graphics memory. "'),
    ('"El modo Lite ya está activo."', '"Lite mode is already on."'),
    ('"El modo Lite usa menos memoria y muestra los mismos datos."', '"Lite mode uses less memory and shows the same data."'),
    ('etiqueta: "Activar Lite y reintentar"', 'etiqueta: "Turn on Lite and retry"'),
    ('etiqueta: "Seguir intentando"', 'etiqueta: "Keep trying"'),
    ('etiqueta: "Ver en 2D"', 'etiqueta: "View in 2D"'),
    ('tipo: "Problema de red"', 'tipo: "Network problem"'),
    ('"No cargan los datos del relieve 3D"', '"The 3D terrain data is not loading"'),
    ('"No cargan las imágenes del 3D"', '"The 3D imagery is not loading"'),
    ('"Fallaron " + falla.malos + " descargas de teselas en los últimos segundos. Suele deberse a la conexión o al '
     'servidor de mapas, no a tu equipo."',
     '"" + falla.malos + " tile downloads failed in the last few seconds. This is usually the connection or the map '
     'server, not your computer."'),
    ('tipo: "Carga lenta"', 'tipo: "Slow loading"'),
    ('"El relieve 3D no termina de cargar"', '"The 3D terrain is taking too long to load"'),
    ('"En 40 s llegó muy poco relieve y no hubo errores de red claros. Puede ser una conexión lenta o un equipo con '
     'pocos recursos gráficos."',
     '"Very little terrain arrived in 40 s and there were no clear network errors. It may be a slow connection or a '
     'computer with limited graphics resources."'),
    ('"El mapa base no está cargando"', '"The basemap is not loading"'),
    ('"Fallan las teselas de «" + nombre + "». Suele deberse a la conexión o al servidor de mapas. Tu área y las '
     'estaciones siguen en el mapa; prueba otro mapa base en Capas."',
     '"Tiles for “" + nombre + "” are failing. This is usually the connection or the map server. Your area and the '
     'stations are still on the map; try another basemap under Layers."'),
]
