# Descargador IDEAM

Descarga automática de series hidrometeorológicas del portal **DHIME del IDEAM** (Colombia) para todas las estaciones de una cuenca. Es una herramienta independiente, no oficial del IDEAM.

1. Dibujas un rectángulo sobre el mapa o subes el contorno de tu cuenca (shapefile en ZIP, GeoJSON, KML/KMZ o GeoPackage).
2. La app muestra las estaciones del IDEAM que caen adentro, y en un buffer opcional. Para cada una calcula la **cantidad probable**: qué parte del periodo consultado cubre el registro de la estación, entre su primer y su último dato. Este valor no descuenta los huecos internos.
3. Filtras por cantidad probable mínima y descargas todo en un ZIP: un Excel por estación, con el formato original del IDEAM y los bloques de años ya unidos. Si quieres, las estaciones van separadas en carpetas por cobertura del periodo. El ZIP incluye `CITACION.txt` con la cita de la fuente.

Incluye vista 3D con relieve real y aviso de estaciones cuya altitud en el catálogo no coincide con el terreno.

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

## Estructura

| Archivo | Para qué sirve |
|---|---|
| `app.py` | Pantallas (inicio, estaciones, descarga), estado de sesión y cola de descarga |
| `modules/ideam_downloader.py` | Token, consultas por bloques de años, fusión de los Excel, cupos y turnos, `CITACION.txt` |
| `modules/ideam_parameters.py` | Variables y parámetros visibles del portal, límites de años por frecuencia |
| `modules/ideam_catalog.py` | Catálogo de estaciones (caché en `data/ideam_catalogo_completo.geojson`) |
| `modules/calidad.py` | Clases de cobertura (alta ≥ 70 %, media ≥ 50 %, baja ≥ 25 %, crítica) |
| `modules/map_view.py` | Mapa 2D (Leaflet vía `streamlit-folium`) |
| `modules/escaner.py`, `modules/scan_overlay.js` | Escáner del mapa 2D: animación mientras se calculan las estaciones y aparición de los pines en orden |
| `modules/terreno.py` | Vista 3D: relieve, textura por altura, pines, cámara, secuencia de entrada y guiones de la intro satelital |
| `static/intro_satelital/` | Intro satelital (del mapa 2D al 3D): escena Three.js, reproductor, mosaico de satélite |
| `modules/panel_estadisticas.py` | Tablas, gráficas y lista de altitudes dudosas |
| `modules/escena_descarga.py` | Animación pixel art de la descarga |
| `modules/estilo.py` | Estilo "liquid glass": tokens de tema (claro, oscuro, alto contraste), modo Lite, barra superior, menú Apariencia, guion de la interfaz del navegador (paneles, hoja inferior, cámara 3D, avisos de fallo), pie y créditos |
| `modules/geo_input.py`, `geo_utils.py` | Lectura de archivos, buffer y filtro espacial |
| `static/manual.html` | Manual de usuario, servido en `app/static/manual.html` |

## Interfaz (mapa primero)

- **Pantalla de estaciones:** el mapa (2D o 3D) ocupa la pantalla. En escritorio, **Consulta** (izquierda) y **Resumen** (derecha) son paneles de vidrio plegables a un riel; el mapa crece al plegarlos. Entre 761 y 1279 px de ancho cabe un panel abierto a la vez. En el celular (≤ 760 px, o pantallas bajas en horizontal) ambos van en pestañas dentro de una **hoja inferior** con tres alturas (mínima, media, máxima): se arrastra solo desde el asa (no compite con mover el mapa), y también responde a clic y a las flechas del teclado.
- Plegar y desplegar lo hace el navegador (`estilo.instalar_ui`), sin recargar la página: guarda el estado en atributos de `<html>` (`data-y2k-izq`, `data-y2k-der`, `data-y2k-hoja`, `data-y2k-tab`) y la elección en `localStorage`. Los botones de los paneles llevan `aria-expanded`.
- Las herramientas del mapa van sobre él en vidrio pequeño: 2D/3D arriba al centro (no tapa los controles de Leaflet de las esquinas), texturas arriba a la izquierda en 3D, leyenda desplegable abajo a la izquierda (abierta en escritorio, cerrada en el celular) y, en 3D, **botones de cámara** (acercar, alejar, girar, inclinar, norte) como alternativa a los gestos.
- La acción principal ("Iniciar extracción") queda fija al final del panel Consulta, con el aviso legal en una línea y su texto completo desplegable.
- **Apariencia** (barra superior): Tema *Sistema / Claro / Oscuro* y Contraste *Sistema / Normal / Alto*, independientes. "Sistema" sigue `prefers-color-scheme` y `prefers-contrast` con media queries (sin destello). La elección viaja en la dirección (`?tema=`, `?contraste=`). Con `forced-colors` se respetan los colores del sistema y solo se reponen bordes y señales.
- **Modo Lite** (botón "Lite" de la barra, `?lite=1`): mismos datos, controles y funciones con menos coste gráfico: sin desenfoque, sombras ni transiciones; 3D liviano (menos detalle de malla, caché menor, 1 píxel de dibujo por píxel CSS), sin intro satelital, sin secuencia de entrada ni vuelta de cámara (la cámara queda de una vez en el encuadre final), escáner 2D sin rejilla ni destellos y escena de descarga a 5 cuadros/s. Es independiente de "movimiento reducido": cada uno se puede tener sin el otro. El guion de la cámara lee Lite en el navegador (variable CSS `--y2k-lite`), así activarlo no mueve la cámara ni repite animaciones.
- **Avisos de fallo** (nunca cambian de modo por su cuenta; ofrecen elegir): pérdida del contexto gráfico WebGL del 3D ("Fallo gráfico": *Activar Lite y reintentar*, *Seguir intentando*, *Ver en 2D*); teselas del 3D o del mapa base 2D que fallan una y otra vez ("Problema de red", se cuenta por tipo: relieve o imagen); relieve que no avanza en 40 s sin errores claros ("Carga lenta"). Reintentar rehace el visor 3D y repone la cámara y la selección; en 2D vuelve a pedir las teselas sin mover el mapa. Los textos no afirman falta de memoria gráfica cuando solo falló una descarga.
- Al cambiar de pantalla, Streamlit deja un momento los elementos viejos: el CSS esconde lo fijo del mapa cuando ya hay una barra superior nueva de otra pantalla (`data-pantalla` + `data-stale`).
- Trampas: `st.html` quita los SVG en línea (por eso el HTML propio va con `estilo.md`, que usa `st.markdown`), y un `<style>` cuyo texto contenga `<` seguido de una letra (aunque sea en un comentario CSS) lo descarta el sanitizador entero.

## Mapa 2D

- Solo se puede dibujar un **rectángulo** (con lápiz para mover sus esquinas y basurita para borrarlo). Un rectángulo nuevo reemplaza al anterior. La cuenca subida desde archivo puede tener cualquier forma.
- Al soltar (o editar) el rectángulo corre un **escáner** sobre él mientras el servidor calcula las estaciones; al terminar se desvanece, muestra "N estaciones encontradas" y los pines aparecen de norte a sur con un pequeño rebote. Mientras corre, el mapa no se mueve ni hace zoom; la barra de dibujo sigue activa y dibujar otra vez reinicia el escáner. Tope de 30 s por si algo falla; con `prefers-reduced-motion` no corre y en modo Lite se dibuja sin rejilla ni destellos y los pines aparecen sin animación.
- Aún no hay animación para la cuenca subida desde archivo (el mapa todavía no existe mientras se calcula).
- Al abrir la pantalla de inicio se **precarga por detrás** (1) en el navegador, las librerías de Leaflet y las teselas de satélite de Colombia (`map_view.recursos_mapa`, `terreno.precargar_mapa_2d`) y (2) en el servidor, la lista de parámetros del IDEAM (`app._iniciar_precarga_servidor`, un hilo que llena la caché de `ideam_parameters.obtener_catalogo_parametros`; sin ella, pasar a la pantalla de estaciones tardaba ~5 s). El botón "Dibujar mi cuenca" queda gris hasta que ambas terminan (un fragmento de Streamlit consulta cada segundo).

**Contratos que no hay que romper** (si cambias `app.py`, `map_view.py` o `escaner.py`):

1. **El mapa base no debe cambiar al dibujar.** `st_folium` identifica el componente por un hash del mapa base; si cambia, Streamlit destruye el mapa y lo crea de nuevo (pantalla en blanco, salto de zoom, y se pierde el escáner). Por eso `mapa_base` solo recibe la cuenca cuando el mapa se monta de cero (archivo, volver del 3D, "Borrar cuenca"). La guardia está en `app.py`: `ss._mapa_en_run_anterior`, `ss._base_cuenca` y `ss._mapa_version`. Las estaciones y el buffer van aparte, en `feature_group_to_add`, que se actualiza sin reconstruir el mapa.
2. **Los pines llevan `options.y2k = "pin"`** (`map_view._marca`). folium descarta los argumentos que no conoce; la marca se escribe directo en `marcador.options`.
3. **Los pines deben ir en el mismo canvas que el rectángulo.** No les pongas un panel propio: con `prefer_canvas` cada panel tiene un canvas del tamaño del mapa y el de encima se come los clics del lápiz y la basurita (se comprobó con ratón real).
4. **`escaner.listo(n, texto)` debe llamarse después de calcular las estaciones** (hoy, justo después del `st_folium`, dentro de `st.container(key="y2k_escaner")`). Es lo que cierra el escáner. Si se llama antes, el escáner termina con el mapa vacío.
5. El controlador se inyecta en la página principal (no en el iframe de un `components.html`, que muere en cada recarga) y llega al mapa por `iframe.contentWindow.map` (el iframe de `st_folium` es del mismo origen). Su listener de `draw:created` se mueve al principio de la cola de Leaflet para quitar los demás rectángulos **antes** de que `streamlit-folium` lea `drawnItems`.

## Vista 3D (guía para quien la modifique)

Está en `modules/terreno.py` y en el bloque `vista == "3D"` de `app.py`. Usa `pydeck` (deck.gl 9) con un `TerrainLayer` alimentado por tiles **Terrarium** (altura = R·256 + G + B/256 − 32768).

**Contrato de capas.** La secuencia de entrada (JavaScript en `_ORBITA`) busca las capas por `id` y por la forma de sus datos. Si cambias alguno, actualiza también el guion:

| `id` | Tipo | Datos que el guion lee |
|---|---|---|
| `terreno` | `TerrainLayer` | `isLoaded`, para saber cuándo se levanta la cubierta de carga |
| `cuenca`, `buffer` | `PathLayer` | `[{path: [[lon, lat, z], …]}]`, se dibujan de a poco como láser |
| `tallos` | `LineLayer` | `{desde, hasta}` por estación, en el mismo orden que `estaciones` |
| `estaciones` | `ScatterplotLayer` | `{pos, …}`; los pines caen uno tras otro |
| `saltos`, `fantasmas`, `fantasmas_texto` | `LineLayer`, `ScatterplotLayer`, `TextLayer` | Altitudes dudosas; sobre `saltos` suben los haces naranjas |

**Cámara y secuencia.**
- Streamlit maneja la vista como estado de React (controlado), así que `deck.setProps({viewState})` no mueve nada. El guion busca el `deck` por dentro de React (`__reactFiber$`) y llama a `deck.props.onViewStateChange` en cada cuadro.
- La cámara gira alrededor de un punto en `z = 0`; para orbitar una estación a otra altura se usa `position: [0, 0, altura]`.
- La secuencia de entrada se esconde y anima las capas con `layer.clone()` y al final devuelve las originales. Corre una sola vez por cuenca y buffer (`ss._intro_firma` / `ss._intro_turno` en `app.py`) y se ata al turno de la vuelta para que el HTML no cambie entre recargas. Respeta `prefers-reduced-motion`.
- Mientras corre la secuencia, un CSS (que manda Python) tapa el visor hasta que el guion escondió las capas y marcó `data-mostrar="<turno>"`; se destapa solo a los 12 s si algo falla. Ya no hay cubierta de "Alistando las estaciones": la intro satelital cubre la espera.
- Cada ejecución del guion lleva un número (`__y2kOrbitaId`): si arranca otra, la anterior se detiene.

**Escena.** Toda la escena se baja la altura del terreno en el centro de la cuenca (la cámara apunta a nivel 0). Contornos, pines y relieve usan esa misma base. `EXAGERACION = 2`.

**Memoria gráfica (lo más delicado).** Se llegó a perder el contexto WebGL (3D en blanco). Valores que se probaron estables:
- Vista de conjunto: `tile_size` 512, `mesh_max_error` 8, `far_z_multiplier` 2. Cerca de una estación: 256, 4 y 3. Modo ligero (celular o modo Lite): 10 y 1,8.
- `max_cache_size` 50–100, `refinement_strategy="'no-overlap'"` y `useDevicePixels` ≤ 1,5 puesto desde JavaScript.
- Si el navegador pierde el contexto WebGL, la interfaz (`estilo.instalar_ui`) lo avisa y deja elegir entre *Activar Lite y reintentar*, *Seguir intentando* (visor nuevo en el mismo modo) o *Ver en 2D*; los botones pulsan botones ocultos de Streamlit (`y2k_lite_reintentar`, `y2k_reintentar3d`, `y2k_pasar2d`). Antes de rehacer el visor guarda la cámara y la repone en el nuevo.

**Trampas conocidas.**
- `pydeck` convierte todo texto en expresión: para un valor literal va entre comillas (`"'no-overlap'"`, `"'auto'"`).
- Los colores del PNG de relieve no deben "corregirse" (`colorSpaceConversion: none`) o el relieve se llena de púas. Algunos navegadores con protección de privacidad lo alteran: la app lo detecta y muestra un aviso que se puede cerrar.
- `map_style="__MAP_STYLE__"` evita que Streamlit ponga un mapa plano de fondo a nivel 0.
- El 3D se arma en el servidor (≈ 3 s con caché fría en un PC; más en la nube) y el navegador baja los tiles después.
- Los `components.html` de `app.py` corren en un iframe de altura 0 y llegan al DOM principal por `window.parent`.

## Intro satelital (del mapa 2D al despliegue 3D)

Animación de ~16,5 s (Three.js) que **cubre la carga del 3D**: un satélite recibe los datos de Colombia, apunta al cuadro del usuario y dispara los láseres de área y buffer y las cápsulas (las estaciones); después la pantalla se enciende como un monitor y el relieve real deck.gl empieza su secuencia (láseres, caída de pines, haces naranjas). El diseño viene de Claude Design (zip "Animación despliegue 3D estaciones").

**Archivos** (`static/intro_satelital/`, servidos por Streamlit en `/app/static/intro_satelital/`):

| Archivo | Para qué sirve |
|---|---|
| `satellite-scene.js` | Escena (globo, satélite, haz, cápsulas, láseres, brillo). Exporta `TUNE` (ajustes), `setBoxLonLat`, `setBuffer`, `precargarDatos`, `getScene` |
| `player.js` | Reproductor: capa que tapa el visor, interfaz (HUD SVG), reloj, panel de ajustes temporal, precalentamiento, arranque en el clic y encendido |
| `mosaico.js` | Primer plano con mosaico de satélite (Esri) de la cuenca; si falla, `satimg.js` pinta un terreno de respaldo |

**Flujo.**
1. Al **confirmar la cuenca** (`app.py`, tras `rango = ...`) se precalienta por detrás: se carga el reproductor, se arma el mosaico y se bajan d3/topojson/mapa mundial. No se crea WebGL. El botón **3D queda gris** hasta que `document.documentElement.dataset.y2kListo` iguala la clave de la cuenca.
2. Al pulsar 3D la animación **arranca en el clic**, sobre el mapa 2D (Streamlit tarda 2–3 s en dibujar el visor). Cuando el visor llega, el guion `_INTRO_SATELITAL` la **adopta** (la mueve dentro) o, si no hubo arranque temprano, la inicia él.
3. El guion `_ORBITA` esconde las capas de deck.gl, espera a que termine la intro (`window.__y2kIntroSatFin == turno`) y entonces corre la secuencia de entrada.
4. La intro solo corre una vez por cuenca y buffer (igual que la secuencia). No corre en celulares, en modo Lite ni con `prefers-reduced-motion`. Si la intro falla al cargar (por ejemplo, sin acceso a esm.sh), el visor 3D no se queda tapado: la capa de la intro no se vuelve a poner.

**Interfaz (HUD) de la intro.** Se dibuja en SVG dentro de `hudSvg` (`player.js`) y solo muestra datos con sentido; no hay botones de zoom ni escalas falsas.
- **Altitud** (km) en cuenta regresiva durante el descenso; transmite la velocidad, por eso no hay medidor de km/s.
- **"Calculando trayectoria"** mientras la cámara se acerca; pasa a "Lista" cuando el objetivo queda fijado.
- **Lista "Preparando lanzamiento"** con tres pasos que se calibran en orden, y debajo las barras **ÁREA** y **BUFFER** con su porcentaje. Con todo cargado se dispara.
- **"Estaciones lanzadas n/N"** usa el total real de estaciones (la intro solo dibuja hasta 250 puntos, pero el contador usa `n`, el total que manda `_datos_satelite`).
- **Sin buffer:** las dos barras se cargan juntas y, al disparar, se apagan la barra y el cañón naranja del buffer (`setBuffer` en `satellite-scene.js`). El estado `buffer` viaja desde `app.py` (`precalentar_satelite` e `intro_satelital`), así que cambiarlo repite la intro.
- Los textos de ambientación (nombre del satélite, "enlace activo", "objetivo fijado") son decoración y no representan datos.

**Cosas que no hay que romper.**
- Un solo contexto WebGL reutilizado: crear y destruir contextos (o `forceContextLoss`) termina en "context loss and was blocked" de Chrome. `destroy()` solo libera geometrías, texturas y buffers.
- No mandar las capas de deck.gl escondidas desde Python: cualquier re-render de React las repone y "se borra todo" al terminar. Se tapa el visor con CSS y las esconde el guion (con una guardia que las vuelve a esconder).
- `TUNE` en `satellite-scene.js` guarda los valores por defecto; el panel los cambia en vivo y los recuerda en `localStorage` (prefijo `y2k_sat_`).
- Tras editar los archivos de la intro hay que **recargar la página del navegador** (F5, mejor Ctrl + F5): el reproductor se carga una sola vez por página y, si no se recarga, sigue corriendo la versión vieja aunque el archivo ya cambió. El parámetro `?v=` de las direcciones cambia con la fecha de los archivos.

**Temporal (quitar antes de presentar):** `PANEL_SATELITE = True` en `terreno.py` (panel "⚙ Ajustes": pausa, tiempo, cámara final, láseres, cápsulas, con el segundo en que se nota cada ajuste y un botón "ir") y el desplegable "Ajustes de la animación 3D (temporal)" del panel Resumen (botón "Repetir animación" y altura de salida de los láseres) en `app.py`.

## Textura "Altura" del 3D

Tercera textura (junto a Satélite y Topográfico): el relieve se colorea por altitud (verdes abajo, naranjas y rojos arriba) con sombreado de ladera. Hay dos escalas: **Rango de la zona** (mínimo y máximo de la cuenca con buffer) y **Rango de Colombia** (0–5.730 m, más pixelada para ahorrar memoria). Un guion (`_HIPSOMETRICO`) intercepta `window.fetch` y devuelve, para las imágenes con la marca `y2k_hipso`, el tile de elevación coloreado. La leyenda sale de `terreno.leyenda_altura()`.

## Cómo probar cambios

- **Lógica y flujo:** `streamlit.testing.v1.AppTest` recorre las pantallas sin navegador (no ejecuta JavaScript).
- **Lo visual (3D, escáner):** abrir la app en un navegador sin ventana (Edge o Chrome con el protocolo de depuración) y sacar capturas a intervalos. Para el mapa 2D hay que probar con **ratón real** (`Input.dispatchMouseEvent`): disparar eventos de Leaflet a mano no detecta, por ejemplo, un canvas que intercepta los clics. Al correr un script de prueba aparte con `streamlit run`, el servidor no recarga los módulos del proyecto: reinícialo tras cambiar `modules/`.
- Conviene probar con una cuenca grande, con muchas estaciones, con el modo Lite, en un celular, con los tres temas y con movimiento reducido (Lite y movimiento reducido por separado y juntos).

## Convenciones

- Interfaz y textos en español. La cantidad probable se muestra siempre como **cobertura**, nunca como "calidad" (el nombre interno `calidad` se conserva en el código).
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

- **Satélite y Relieve:** Esri (Maxar, Earthstar Geographics, HERE, Garmin, FAO, NOAA, USGS y la comunidad de usuarios de GIS). Se consultan por el punto de acceso público `server.arcgisonline.com`, sin clave. Esri lo considera un servicio antiguo y recomienda uno con clave; conviene revisar sus términos antes de un uso amplio.
- **Calles:** © colaboradores de OpenStreetMap.
- **Satélite de noche:** NASA EOSDIS GIBS.
- **Relieve 3D:** modelo de elevación Terrarium (Mapzen, AWS Open Data), construido con datos SRTM y GMTED2010, cortesía del U.S. Geological Survey, entre otras fuentes.

La aplicación muestra estos créditos en el pie de página y, más cortos, en el borde de cada mapa.
