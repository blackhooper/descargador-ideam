# Descargador IDEAM

Consulta y descarga de series hidrometeorológicas del portal **DHIME del IDEAM** (Colombia) para todas las estaciones de un área (una cuenca, un municipio o cualquier zona). Es una herramienta independiente, no oficial del IDEAM.

1. **Consulta**: eliges la serie de tiempo y el periodo, con las mismas listas que la página del IDEAM. En la serie *estándar* eliges la variable y luego el parámetro (series diarias, mensuales, anuales, horarias y de alta frecuencia; para Precipitación: día pluviométrico, total mensual y total anual). En la *especial* eliges la frecuencia (decadal o multianual), la variable y el parámetro con su cálculo, con el texto de la página: «Día pluviométrico |SUM [PTPM_CON]». Mientras tanto, el mapa y los datos del IDEAM se cargan por detrás.
2. **Área y estaciones**: en el mapa dibujas un rectángulo o subes el contorno del área (shapefile en ZIP, GeoJSON, KML/KMZ o GeoPackage). La app muestra las estaciones del IDEAM que caen adentro, y en un buffer opcional. También puedes elegirlas como en la página del IDEAM, por departamento, municipio y nombre o código, en el desplegable «Filtrar por ubicación» de la consulta: el mapa abre con solo esas estaciones, sin dibujar nada. Para cada una calcula la **cantidad probable**: qué parte del periodo consultado cubre el registro de la estación, entre su primer y su último dato. Este valor no descuenta los huecos internos. Revisas la cobertura y defines qué estaciones incluir.
3. **Descarga**: un ZIP con un Excel por estación, con el formato original del IDEAM y los bloques de años ya unidos. Antes de bajarlo eliges su nombre y si las estaciones van separadas en carpetas por completitud real del periodo. El ZIP incluye `resumen_descarga.csv` (con la **completitud real** de cada estación: los datos que llegaron frente a los que caben en el periodo) y `CITACION.txt` con la cita de la fuente.

Incluye vista 3D con relieve real y aviso de estaciones cuya altitud en el catálogo no coincide con el terreno.

> **Portfolio (English).** A GIS case study of this project, with the spatial analysis behind it and how it applies to land and site-feasibility work, is at [blackhooper.github.io/descargador-ideam](https://blackhooper.github.io/descargador-ideam/) (source: `docs/index.html`). In short: the app takes a national catalog of 9,857 stations, cuts it to any study area with metric buffers and spatial joins (Shapefile, GeoJSON, KML/KMZ or GeoPackage input, with CRS checks and geometry repair), screens each station's data coverage and cross-checks its catalog altitude against a terrain model, and delivers a sourced, organized package (merged Excel, summary CSV, citation).

## Acceso por clave y modos (cliente / desarrollador)

La app pide una clave al entrar, y la clave decide el modo: la del **cliente** abre la app tal como está (esa clave es temporal, solo para mantener la página privada por ahora) y la del **desarrollador** abre el **modo desarrollador**: la misma app más un apartado «Herramientas» (en Ajustes → Acceso → Vista) donde se irán sumando las herramientas nuevas (`modules/herramientas.py`). La clave se pide una sola vez por navegador: queda guardada en una cookie de un año y las recargas entran solas. «Cerrar sesión» está en Ajustes.

Las claves van como secretos, junto a las del IDEAM (en `.streamlit/secrets.toml` o en Settings → Secrets de Streamlit Cloud):

```toml
[acceso]
cliente = "..."
desarrollador = "..."
```

La pantalla de la clave usa el mismo vidrio y los mismos tokens que el resto (`.st-key-y2k_acceso` en `estilo.py`) y trae el botón de idioma. Tras 5 claves erradas seguidas (entre todos los visitantes) hay que esperar 30 s para volver a probar, y la espera se duplica en cada tanda hasta 5 minutos (`acceso.INTENTOS_POR_TANDA`, `ESPERA_BASE_S`).

Cambiar una clave cierra las sesiones guardadas con la anterior. **Ojo: no es seguridad real.** Es una puerta para que no entre cualquiera por curiosidad; no protege datos sensibles.

## Contenido

- [Portafolio (inglés)](https://blackhooper.github.io/descargador-ideam/): caso de estudio SIG del proyecto
- [Usarla en tu computador](#usarla-en-tu-computador) · [Publicarla](#publicarla-en-streamlit-community-cloud)
- [Cómo probar cambios](#cómo-probar-cambios) · [Convenciones](#convenciones)
- [Uso de los datos](#uso-de-los-datos) · [Fuentes y créditos de los mapas](#fuentes-y-créditos-de-los-mapas)

Cada cosa se explica en un solo sitio: este README dice qué es la app, cómo instalarla y sus reglas; el [manual](static/manual.html) explica cómo se usa, con los nombres de los botones; y para quien modifica la app hay dos documentos aparte:

- [Arquitectura](documentacion/ARQUITECTURA.md): las tres capas y los archivos, las tres pantallas con sus planos, cómo se arma la página en cada corrida, los avisos de fallo, el mapa 2D, la vista 3D, la intro satelital y las pruebas.
- [Estilo](documentacion/ESTILO.md): el sistema visual (tokens, materiales y el contrato de lo que no hay que tocar), el guion de la interfaz del navegador y los temas, el contraste, el modo Lite y el movimiento.

## Usarla en tu computador

Necesitas Python 3.12 o superior.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Antes de arrancar, crea el archivo `.streamlit/secrets.toml` con el usuario y la clave de acceso del portal DHIME. No se trata de una cuenta personal: son las credenciales públicas que el propio portal entrega a cualquier visitante. Se guardan como secreto para no dejarlas escritas en el código.

```toml
[ideam]
usuario = "..."
clave = "..."
```

En Windows con poca memoria virtual conviene arrancar con `OPENBLAS_NUM_THREADS=1`.

## Publicarla en Streamlit Community Cloud

Conecta este repositorio en [share.streamlit.io](https://share.streamlit.io), con `app.py` como archivo principal. En **Advanced settings** elige Python 3.12 o 3.13. En **Secrets** pega el mismo bloque `[ideam]` de arriba. Cada reinicio borra las cachés en memoria (relieve, series), así que la primera consulta tras un reinicio es la más lenta.

`requirements.txt` fija las versiones con las que se probó (Streamlit 1.64). La interfaz usa funciones recientes de Streamlit (contenedores con `key`, contenedores horizontales, `segmented_control`): con versiones anteriores no se verá bien.

## Cómo probar cambios

- **Pruebas automáticas:** `python -m pytest -q tests`. Las de lógica no abren la app; las de `tests/interfaz/` la arrancan contra un IDEAM simulado y la recorren con un navegador (necesitan `pip install playwright` y `playwright install chromium`; sin Playwright se saltan). En GitHub corren en cada PR. El detalle está en [Arquitectura · Pruebas](documentacion/ARQUITECTURA.md#pruebas).
- **Ver la app sin el IDEAM:** con la app simulada de las pruebas (el comando está en el mismo apartado de Arquitectura). Streamlit no recarga los módulos de `modules/` al cambiarlos: reinicia el servidor.
- **Lo visual (3D, escáner, vidrio):** las pruebas no miran el aspecto. Hay que abrir la app y sacar capturas. Para el mapa 2D hay que probar con **ratón real** (eventos de ratón del navegador): disparar eventos de Leaflet a mano no detecta, por ejemplo, un canvas que intercepta los clics.
- **Contraste:** medirlo sobre píxeles reales (captura de cada texto: fondo = mediana de la caja, tinta = el píxel más alejado), sobre el mapa y con un fondo negro o blanco bajo el vidrio.
- Conviene probar con una cuenca grande, con muchas estaciones, con el modo Lite, en un celular, con los tres temas y con movimiento reducido (Lite y movimiento reducido por separado y juntos).
- **Trampas de Streamlit:** `st.html` quita los SVG en línea (por eso el HTML propio va con `estilo.md`, que usa `st.markdown`); un `<style>` cuyo texto contenga `<` seguido de una letra (aunque sea en un comentario CSS) lo descarta el sanitizador entero (por eso `estilo.aplicar` escapa todo `<` del CSS); los contenedores horizontales traen un margen negativo (las cápsulas lo anulan); Streamlit pinta los captions al 60 % de opacidad (el CSS lo devuelve a 1); los botones con ayuda y los popover traen una copia oculta en el DOM (en las pruebas, usa `:visible`); `st.dataframe` no acepta `args` (el callback va con `functools.partial`); y al cambiar de pantalla deja los elementos viejos hasta terminar la corrida, por eso las tres pantallas tienen [huecos fijos](documentacion/ARQUITECTURA.md#pantallas).

## Convenciones

- Interfaz y textos en español. Hay dos nombres y solo dos: **cobertura estimada** (antes de descargar; es la «cantidad probable» del IDEAM) y **completitud real** (después, con los datos que llegaron). En la interfaz no se usa «calidad» ni «cantidad probable» (los nombres internos `calidad` y `Cantidad Probable` se conservan en el código). Una estación que no tiene la serie es «sin serie», y la zona dibujada es «el área».
- Colores solo a través de tokens (`estilo.TOKENS`); los colores de datos y de mapa, en sus módulos (ver [Colores que viven fuera de `estilo.py`](documentacion/ESTILO.md#colores-que-viven-fuera-de-estilopy)).
- La app no lleva datos personales de sus autores. Se conservan las marcas de que los datos son del IDEAM y los avisos legales.
- No agregar créditos ni enlaces personales sin hablarlo antes.

## Uso de los datos

- Los datos son del IDEAM y están protegidos por derechos de autor. Su descarga está autorizada para uso personal, privado y no comercial, y no pueden comercializarse ni venderse.
- Todo trabajo que los utilice debe citar la fuente con el formato de los términos de uso del portal; el ZIP trae la cita armada en `CITACION.txt`.
- Esta herramienta automatiza consultas que cualquiera puede hacer en el portal DHIME. No almacena ni redistribuye los datos por su cuenta.
- Como hace el portal, cada serie descargada se registra de forma anónima en las estadísticas de descargas del IDEAM.
- El servidor permite como máximo 4 descargas a la vez para no saturar el servicio del IDEAM. Las demás esperan turno.

## Fuentes y créditos de los mapas

Las capas de mapa no son del IDEAM y pertenecen a sus proveedores:

- **Satélite, Satélite con nombres y Relieve:** Esri (Maxar, Earthstar Geographics, HERE, Garmin, FAO, NOAA, USGS, OpenStreetMap y la comunidad de usuarios de GIS). Se consultan por el punto de acceso público `server.arcgisonline.com`, sin clave. Esri lo considera un servicio antiguo y recomienda uno con clave; conviene revisar sus términos antes de un uso amplio.
- **Calles:** © colaboradores de OpenStreetMap.
- **Satélite de noche:** NASA EOSDIS GIBS.
- **Relieve 3D:** modelo de elevación Terrarium (Mapzen, AWS Open Data), construido con datos SRTM y GMTED2010, cortesía del U.S. Geological Survey, entre otras fuentes.

La aplicación muestra estos créditos al final del panel del mapa y, más cortos, en el borde de cada mapa.
