# Descargador IDEAM

Descarga automática de series hidrometeorológicas del portal **DHIME del IDEAM** (Colombia) para todas las estaciones de una cuenca. Es una herramienta independiente, no oficial del IDEAM.

1. Eliges la frecuencia, el parámetro y el periodo. Mientras tanto, el mapa y los datos del IDEAM se cargan por detrás.
2. En el mapa dibujas un rectángulo o subes el contorno de tu cuenca (shapefile en ZIP, GeoJSON, KML/KMZ o GeoPackage). La app muestra las estaciones del IDEAM que caen adentro, y en un buffer opcional. Para cada una calcula la **cantidad probable**: qué parte del periodo consultado cubre el registro de la estación, entre su primer y su último dato. Este valor no descuenta los huecos internos.
3. Revisas las estaciones y quitas las que no quieras, y descargas todo en un ZIP: un Excel por estación, con el formato original del IDEAM y los bloques de años ya unidos. Si quieres, las estaciones van separadas en carpetas por cobertura del periodo. El ZIP incluye `CITACION.txt` con la cita de la fuente.

Incluye vista 3D con relieve real y aviso de estaciones cuya altitud en el catálogo no coincide con el terreno.

## Contenido

- [Usarla en tu computador](#usarla-en-tu-computador) · [Publicarla](#publicarla-en-streamlit-community-cloud)
- [Cómo está organizado](#cómo-está-organizado): las tres capas y los archivos
- [Pantallas](#pantallas): Parámetros, Mapa y Exportación (con sus planos)
- [Cómo se arma la página en cada corrida](#cómo-se-arma-la-página-en-cada-corrida)
- [Sistema visual: cómo cambiar la estética](#sistema-visual-cómo-cambiar-la-estética) y [lo que no hay que tocar](#el-contrato-lo-que-no-hay-que-tocar-al-cambiar-la-estética)
- [Guion de la interfaz](#guion-de-la-interfaz-del-navegador) · [Temas, contraste, Lite y movimiento](#temas-contraste-modo-lite-y-movimiento) · [Avisos de fallo](#avisos-de-fallo)
- [Mapa 2D](#mapa-2d) · [Vista 3D](#vista-3d-guía-para-quien-la-modifique) · [Intro satelital](#intro-satelital-del-mapa-2d-al-despliegue-3d) · [Textura "Altura"](#textura-altura-del-3d)
- [Cómo probar cambios](#cómo-probar-cambios) · [Convenciones](#convenciones) · [Uso de los datos](#uso-de-los-datos) · [Créditos de los mapas](#fuentes-y-créditos-de-los-mapas)

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

## Cómo está organizado

### Las tres capas

El código está separado para que se pueda cambiar **cómo se ve** sin tocar **qué hace** ni **dónde va cada cosa**:

| Capa | Qué decide | Dónde está |
|---|---|---|
| **Datos y lógica** | Consultas al IDEAM, catálogo, cobertura, buffer, relieve, ZIP. No sabe nada de la interfaz. | `modules/ideam_downloader.py`, `ideam_parameters.py`, `ideam_catalog.py`, `calidad.py`, `geo_input.py`, `geo_utils.py`, la parte de cálculo de `terreno.py` |
| **Estructura de la interfaz** | Qué pantallas hay, qué contiene cada zona, en qué orden, con qué textos y qué pasa al pulsar cada cosa. | `app.py`, `modules/panel_estadisticas.py`, `modules/map_view.py`, `terreno.construir_deck`, y las funciones de piezas de `modules/estilo.py` (las que dibujan HTML: `cabecera_inicio`, `seccion`, `kpis`, `herramientas_2d`, `recibo`…) |
| **Estética** | Colores, materiales, tipografía, medidas, radios, sombras, animaciones, iconos, temas y modo Lite. | `modules/estilo.py` (tokens, bloques CSS e iconos) y `.streamlit/config.toml` (colores de los widgets de Streamlit) |

La estructura y la estética se conectan solo por **nombres**: las claves de los contenedores de Streamlit (`key="y2k_panel"` produce la clase CSS `.st-key-y2k_panel`), las clases de las piezas HTML propias (`.y2k-…`) y algunos atributos `data-y2k-…`. Mientras esos nombres no cambien (ver [el contrato](#el-contrato-lo-que-no-hay-que-tocar-al-cambiar-la-estética)), se puede rehacer toda la estética editando solo `estilo.py`.

### Archivos

| Archivo | Capa | Para qué sirve |
|---|---|---|
| `app.py` | Estructura | Las tres pantallas (Parámetros, Mapa y Exportación), los huecos fijos de cada zona, las cargas por detrás, el estado de sesión y la cola de descarga |
| `modules/estilo.py` | Estética (+ piezas) | Tokens de tema, materiales de vidrio, CSS de toda la app, iconos, menú de Ajustes, piezas HTML (tarjeta de Parámetros, secciones y cifras del panel, cápsula de herramientas, leyendas, avance, recibo) y el guion de la interfaz del navegador |
| `modules/panel_estadisticas.py` | Estructura | Tablero de calidad del panel (cifras, altitud dudosa, lista con casillas) y ficha de la estación seleccionada |
| `modules/map_view.py` | Estructura | Mapa 2D (Leaflet vía `streamlit-folium`): capas base, herramienta de dibujo (oculta: la maneja la cápsula de herramientas), pines (también los excluidos) y fichas emergentes |
| `modules/terreno.py` | Lógica + estructura | Vista 3D: relieve, textura por altura, pines, cámara, secuencia de entrada y guiones de la intro satelital |
| `modules/escaner.py`, `modules/scan_overlay.js` | Estructura | Escáner del mapa 2D: animación mientras se calculan las estaciones y aparición de los pines en orden |
| `modules/ideam_downloader.py` | Lógica | Token, consultas por bloques de años, fusión de los Excel, cupos y turnos, `CITACION.txt` |
| `modules/ideam_parameters.py` | Lógica | Variables y parámetros visibles del portal, límites de años por frecuencia |
| `modules/ideam_catalog.py` | Lógica | Catálogo de estaciones (caché en `data/ideam_catalogo_completo.geojson`) |
| `modules/calidad.py` | Lógica | Clases de cobertura (alta ≥ 70 %, media ≥ 50 %, baja ≥ 25 %, crítica) y sus colores |
| `modules/geo_input.py`, `geo_utils.py` | Lógica | Lectura de archivos, buffer y filtro espacial |
| `static/intro_satelital/` | Estructura | Intro satelital (del mapa 2D al 3D): escena Three.js, reproductor, mosaico de satélite |
| `static/manual.html` | Documento aparte | Manual de usuario, servido en `app/static/manual.html` (tiene su propio CSS) |
| `.streamlit/config.toml` | Estética | Colores de los widgets de Streamlit en claro y oscuro (deben coincidir con los tokens) |

## Pantallas

La app tiene **tres pantallas** (`ss.paso`): `"parametros"`, `"mapa"` y `"descarga"` (Exportación). Las tres comparten el **mismo mapa 2D**, que va siempre en el mismo lugar del árbol de Streamlit (`y2k_escenario`): por eso no se vuelve a cargar al cambiar de pantalla, y en Parámetros se carga por detrás mientras la persona elige qué descargar. En Parámetros y Exportación el mapa queda velado y desenfocado (`.st-key-y2k_escenario::after`) y sin foco ni clics (`inert`).

Arriba a la derecha, en las tres, va el menú **Ajustes** (`y2k_ajustes`, `estilo.ajustes`): tema claro/oscuro, alto contraste, modo Lite y manual. Con Lite activo, junto al botón aparece la marca «Lite». Durante una descarga el menú se bloquea (cambiar algo recargaría la página y la detendría).

**Huecos fijos.** Justo después del escenario, `app.py` crea siempre, en este orden, los contenedores de las tres pantallas (vacíos los que no se usan): `y2k_inicio`, `y2k_panel`, `y2k_abrir`, `y2k_herr`, `y2k_dock`, `y2k_ficha`, `y2k_exportar` y `y2k_ocultos`. Así cada uno conserva su lugar: al cambiar de pantalla, Streamlit deja un momento los elementos viejos hasta terminar la corrida (en Exportación, toda la descarga), y como siguen dentro de su propio contenedor, el CSS los oculta enseguida por su clave. Lo condicional (`y2k_precal`, el diálogo de subida) va después de todos.

### 1. Parámetros (`pantalla_parametros` en `app.py`)

```text
┌──────────────────────────────────────────────────────────────────────┐
│ mapa 2D velado (y2k_escenario)                         ╭ y2k_ajustes ╮
│              ╭ y2k_inicio (tarjeta centrada) ─────────╮ ╰─────────────╯
│              │ eyebrow · título · bajada               │             │
│              │ Frecuencia            [frec_0 / frec_1] │             │
│              │ Parámetro ●           [par_<frecuencia>]│  ● = punto  │
│              │ Desde [f_ini]   Hasta [f_fin]           │  de estado  │
│              │ ▸ Ajustes avanzados (avanzado, carpetas)│             │
│              │ [ Seleccionar área en el mapa → ] ir_mapa             │
│              │ estado del botón (.y2k-espera)          │             │
│              │ 1 Marca · 2 Revisa · 3 Descarga (.y2k-como)           │
│              │ Modo Lite (lite_inicio) · condiciones   │             │
│              ╰─────────────────────────────────────────╯             │
└──────────────────────────────────────────────────────────────────────┘
```

En el celular la tarjeta sube desde abajo como una hoja; Desde y Hasta siguen en una fila (`y2k_fechas`).

- **Lista de parámetros** (`_iniciar_precarga_servidor`): se pide en un hilo al arrancar el servidor. Mientras carga, el desplegable (`par_espera`) está en gris y no se puede abrir, y el punto `.y2k-punto[data-estado]` respira en gris; al cargar, se enciende en verde (`listo`) y aparece el desplegable de verdad (`par_<frecuencia>`, con búsqueda al escribir y precipitación por defecto). Si falla, el punto se pone rojo y aparece **Reintentar**.
- **Parámetros legibles** (`_parametros_de`): todas las variables de la frecuencia elegida, con la descripción y la unidad; la variable va delante solo si la descripción no la nombra. Sin códigos como `PTPM_CON` (salvo que dos se llamen igual).
- **Series por detrás** (`_precargar_series`): al elegir un parámetro se pide en un hilo qué estaciones tienen esa serie (lo que necesita el mapa para evaluar). Compartido entre sesiones; si falló, se reintenta a los 30 s.
- **El botón espera** a que todo esté listo: lista cargada, parámetro elegido, fechas válidas, periodo que cabe en Excel y series cargadas (`disabled` desde Python), y además que el mapa 2D haya cargado (eso lo sabe el navegador: el guion pone `aria-disabled` y bloquea el clic hasta `html[data-y2k-mapa-listo]`). La línea `.y2k-espera` dice qué falta; si el servidor está listo y el mapa no, el guion la cambia por «Cargando el mapa…».
- Un **vigía** (`_vigia`, un fragmento con `run_every=1`) revisa cada segundo lo que carga por detrás y recarga la página una vez al terminar.
- `_ir_mapa` (callback) guarda la consulta en `ss.consulta` (etiqueta del parámetro y fechas) y pasa a `"mapa"` antes de que corra el guion: la pantalla nueva sale en la misma recarga.

### 2. Mapa (`pantalla_mapa` en `app.py`)

**Escritorio**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ╭ y2k_panel ───────────────────╮ ╭ y2k_ficha (estación) ─╮  ╭ y2k_ajustes ╮  │
│ │ y2k_panel_cab: [← parámetro · periodo] [⇤] │           │  ╰─────────────╯  │
│ │ ──────────────────────────── │ ╰───────────────────────╯  ╭ y2k_herr ╮     │
│ │ y2k_cuerpo (con scroll)      │                            │ ✎ Dibujo ▸│     │
│ │  ÁREA DE ESTUDIO   ≈ 381 km² │       y2k_escenario        │ ▤ Capas  ▸│     │
│ │  Redibujar·Ajustar·Subir·Borrar   (mapa 2D o 3D a         │ +  −      │     │
│ │  Buffer (buf_on, buf_km)     │     pantalla completa)     ╰──────────╯     │
│ │  CALIDAD DE LOS DATOS        │                                             │
│ │  [Estaciones][Cobertura][Registros]                                        │
│ │  ⚠ N con altitud dudosa      │  ╭ leyenda ╮                                │
│ │  lista con casillas          │  ╰─────────╯                                │
│ │  pie y créditos              │  ╭ y2k_dock_izq ──────╮   ╭ y2k_dock_der ─╮ │
│ ╰──────────────────────────────╯  │ 2D│3D · Textura ▾ ↻│   │Preparar desc.→│ │
│                                   ╰────────────────────╯   ╰───────────────╯ │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Celular (≤ 760 px de ancho)**

```text
┌───────────────────────────┐
│╭ y2k_ficha ─────────╮ ╭⚙╮ │   ficha arriba, junto a la columna de Ajustes
│╰────────────────────╯ ╭✎╮ │   cápsula de herramientas bajo Ajustes
│       y2k_escenario   │▤│ │
│                       ╰─╯ │
│╭ y2k_panel (hoja) ───────╮│   hoja inferior: asa, píldora de la consulta y
││ ===  [← parámetro]  [^] ││   botón ampliar; tres alturas (mín., media, máx.)
│╰─────────────────────────╯│
│ y2k_dock: 2D│3D  Preparar │   barra de vidrio pegada abajo
└───────────────────────────┘
```

En **horizontal** (alto ≤ 560 px y ancho > 760 px) se usa la disposición de escritorio, más compacta (`CSS_BAJO`).

| Zona | Contenedor (`key`) | Quién la llena | Qué contiene | Material |
|---|---|---|---|---|
| Panel | `y2k_panel` | `app.pantalla_mapa` | Cabecera `y2k_panel_cab` (asa de la hoja, píldora `chip_param` que vuelve a Parámetros, `estilo.controles_panel`) y cuerpo `y2k_cuerpo` con desplazamiento propio | vidrio regular |
| Reabrir panel | `y2k_abrir` | `estilo.boton_abrir_panel` | Botón «Panel» (solo se ve con el panel plegado, en escritorio) | vidrio claro |
| Herramientas | `y2k_herr` | `estilo.herramientas_2d` / `estilo.controles_camara` | En 2D: menús **Dibujo** (dibujar, área visible, subir, ajustar esquinas, borrar) y **Mapa base**, y zoom. En 3D: botones de cámara | vidrio claro (los menús, denso) |
| Píldoras | `y2k_dock` (`y2k_dock_izq`, `y2k_dock_der`) | `app.pantalla_mapa` | Izquierda: selector **2D/3D** (`vista`), y en 3D el menú **Textura** (`textura`, `escala_altura`) y **Repetir animación** (`y2k_repetir_intro`, temporal). Derecha: **Preparar descarga** (`preparar`; desactivado con la razón en la ayuda) | vidrio claro |
| Ficha | `y2k_ficha` | `panel_estadisticas.tarjeta_seleccionada` | Estación elegida: nombre, código, altitud, cobertura, interruptor **Incluir en la descarga**, aviso de altitud dudosa (`alerta_ficha`), **Ver en 3D** y **Cerrar** | vidrio regular |
| Mapa | `y2k_escenario` | `app.pantalla_mapa` | En 2D: `y2k_mapa2d` (iframe de `st_folium`), `y2k_escaner` y la leyenda. En 3D: `y2k_visor3d` (pydeck), `y2k_orbita` (guiones), leyenda, atribución y el aviso de movimiento reducido | sin vidrio (es el contenido) |

**Cuerpo del panel** (`y2k_cuerpo`), en dos secciones (`estilo.seccion`):

1. **Área de estudio**: área en km²; sin área, «Dibujar un rectángulo», «Subir archivo» y el enlace «usa el área visible» (alternativa de teclado); con área, cuatro acciones compactas (`estilo.acciones_area`: Redibujar, Ajustar, Subir, Borrar). En 3D, un aviso y «Ver en 2D». Después, el buffer (`buf_on`, `buf_km`).
2. **Calidad de los datos** (`panel_estadisticas.tablero`): tres cifras (`estilo.kpis`: estaciones listas, cobertura media, registros probables con el tiempo estimado), la línea ámbar de altitud dudosa (`alerta_altura`, con la lista `tabla_dudosas` que lleva al 3D) y la **lista con casillas** (`st.dataframe` con selección `multi-row` + `single-cell`: las filas marcadas se descargan; un clic en una celda selecciona la estación y el mapa va a ella). Las excluidas se guardan en `ss.excluidas` (códigos) y en el mapa salen huecas con borde punteado. Al final, la nota de datos preliminares y el pie (`estilo.pie`, con los créditos de los mapas).

Los estados sin datos (sin área, zona sin estaciones, IDEAM caído, periodo demasiado largo, ninguna estación con datos) se explican en la sección de calidad, y **Preparar descarga** queda desactivado con la razón en su ayuda.

**Subir un archivo** abre un diálogo (`dialogo_subida`, `st.dialog`) con el cargador `subida_<n>` y el botón `usar_subida`. Lo abre el botón oculto `y2k_subir`, que pulsan los botones HTML «Subir».

**Capas (z-index):** el mapa (`y2k_escenario`) está en 0 y sus piezas (`.y2k-sobre`) en 25 dentro de él; el velo de Parámetros y Exportación en 30; las tarjetas y el panel en 40; la ficha en 42; las píldoras en 45; las herramientas y el botón «Panel» en 50; Ajustes en 55; la intro satelital en 60; los avisos de fallo en 70.

### 3. Exportación (`pantalla_descarga` en `app.py`)

```text
mapa 2D velado                                              ╭ y2k_ajustes ╮
          ╭ y2k_exportar (tarjeta) ─────────────────────────────────────╮
          │ ● EXPORTACIÓN · título                                      │
          │ ┌ izquierda ───────────────────┐ ┌ derecha ───────────────┐ │
          │ │ 42 %          Faltan ≈ 1 min │ │ recibo (.y2k-recibo):  │ │
          │ │ ▓▓▓▓▓▓▓░░░░░ (.y2k-barra)    │ │ parámetro, periodo,    │ │
          │ │ estaciones · guardadas ·     │ │ estaciones, archivo,   │ │
          │ │ omitidas                     │ │ fuente                 │ │
          │ │ [Detener] / resumen + reparto│ │ condiciones de uso     │ │
          │ │ nombre del ZIP + Descargar   │ │ (.y2k-legal-bloque)    │ │
          │ │ [Volver al mapa][Nueva consulta]                      │ │
          │ └──────────────────────────────┘ └────────────────────────┘ │
          ╰─────────────────────────────────────────────────────────────╯
```

En el celular la tarjeta es una hoja inferior y las dos columnas van una debajo de la otra.

- **Estados** (`ss.estado_descarga`): `pendiente` → `en_curso` → `lista` o `error`, y `detenida`. `_preparar` (callback de «Preparar descarga») deja la descarga en `pendiente` y pasa a la pantalla. La corrida que la encuentra en `pendiente` dibuja la tarjeta (recibo, condiciones, «Detener») y descarga en esa misma corrida, actualizando el avance real en un `st.empty()` (`estilo.progreso`, que llama `ideam_downloader.procesar_descargas` vía `ui["progreso"]`). Si una corrida encuentra `en_curso`, la anterior se cortó («Detener» u otra recarga): queda `detenida`.
- **Todos los botones son callbacks** (`_detener`, `_reintentar_descarga`, `_volver_mapa`, `_nueva_consulta`) que cambian el estado antes de que corra el guion. Por eso «Volver al mapa» funciona siempre (antes, tras «Detener», la siguiente corrida volvía a empezar la descarga antes de ver el botón).
- Al terminar: barra en verde con la duración, una frase con lo guardado y lo omitido, el reparto por cobertura (`estilo.resumen_final`, `panel_estadisticas.reparto_cobertura`) y la entrega (`_entrega`, un fragmento: el nombre del ZIP `nombre_zip` se aplica mientras se escribe, sin recargar la tarjeta).
- **Turnos**: como máximo 4 descargas a la vez en el servidor; si no hay cupo, un aviso dice el puesto en la fila y el tiempo estimado.
- El mapa de fondo solo se monta de cero si no hay una descarga por empezar: al cargar, el componente del mapa podría recargar la página y cortarla.

### Manual

`static/manual.html` es una página aparte, con su propio CSS. Describe la interfaz con los nombres de sus botones: si cambias textos visibles de la app, revísalo.

## Cómo se arma la página en cada corrida

Streamlit vuelve a ejecutar `app.py` de arriba abajo en cada interacción. El orden es:

1. Preferencias desde la dirección (`?tema=`, `?contraste=`, `?lite=1`) y valores por defecto del estado de sesión. Si `paso` no tiene con qué seguir (por ejemplo, mapa sin consulta), vuelve a `"parametros"`.
2. `estilo.aplicar(tema, contraste, lite)`: todo el CSS de la página.
3. `estilo.guiones_globales(pantalla)`: la marca de la pantalla (`.y2k-pantalla[data-p]`), el guion de la interfaz y la sincronización del tema de Streamlit. Después, `y2k_hipso` y `y2k_velo`.
4. `estilo.ajustes()`: el menú de Ajustes (bloqueado durante una descarga).
5. Credenciales y catálogo de estaciones.
6. **El escenario** (`y2k_escenario`) y **los huecos fijos** de las tres pantallas (ver [Pantallas](#pantallas)). No pongas nada condicional antes de ellos: cambiaría su lugar y el mapa se volvería a cargar.
7. Precarga (en un hilo) de la lista de parámetros y la pantalla: `pantalla_parametros`, `pantalla_mapa` o `pantalla_descarga`.

Dentro de `pantalla_mapa` se llena primero el panel (área y buffer), después se calculan las estaciones, las altitudes y la disponibilidad (con indicadores de carga en la sección de calidad), luego el mapa, el tablero de calidad, la cápsula de herramientas, las píldoras, la ficha y los botones ocultos. Como casi todas las zonas son fijas (`position: fixed`), el orden en el DOM no cambia dónde se ven.

**Estado de sesión** (`st.session_state`, en el código `ss`):

| Clave | Para qué |
|---|---|
| `paso` | Pantalla actual: `"parametros"`, `"mapa"` o `"descarga"` |
| `consulta` | Lo elegido en Parámetros: `{"etiqueta", "ini", "fin"}` (el parámetro se busca en el catálogo por su etiqueta) |
| `cuenca` | Geometría del área (GeoDataFrame) o `None` |
| `excluidas`, `version_lista` | Códigos de las estaciones quitadas de la descarga; contador que rehace la lista cuando las cambia la ficha |
| `vista` | `"2D"` o `"3D"` (es la clave del selector; sin `default` porque la cambian también la ficha, la lista de altitudes y los avisos, con callbacks que corren antes de dibujarlo) |
| `estacion_sel` | Código de la estación seleccionada |
| `tema`, `contraste`, `lite` | Preferencias de apariencia y rendimiento (también en la dirección) |
| `version_mapa`, `version_subida`, `version_3d`, `subida_abierta` | Contadores que rehacen el mapa 2D, vacían el cargador o rehacen el visor 3D; si el diálogo de subida está abierto |
| `descarga`, `estado_descarga`, `resultado`, `nombre_zip` | Exportación |
| `_base_cuenca`, `_mapa_version`, `_mapa_en_run_anterior`, `_capa_args` | Guardia del mapa 2D (ver [Mapa 2D](#mapa-2d)) y la capa de estaciones que se repite detrás de Parámetros y Exportación |
| `orbita`, `saltos`, `_intro_*`, `_orbita_firma`, `_vista_prev`, `_sel_prev`, `_orbitar`, `_repetir_intro` | Cámara y secuencia de entrada del 3D |
| `_prev_sel`, `_centrar`, `_dudosas_codigos` | Sincronización de la selección entre el mapa, la lista y el 3D |

Los widgets de Parámetros y del panel usan `persist_state="session"`: conservan su valor al pasar a otra pantalla y volver.

## Sistema visual: cómo cambiar la estética

Todo lo visual de la app sale de `modules/estilo.py`. Este es el mapa del archivo, en orden:

| Sección | Qué es | ¿Se toca al cambiar la estética? |
|---|---|---|
| `FUENTE`, `ATRIB_*`, `CREDITOS_MAPAS` | Fuente de los datos y créditos (textos legales) | No |
| `PALETAS` | Colores para lo que no lee CSS: gráficas de Altair y ficha emergente del 3D | **Sí** |
| `TEMAS`, `CONTRASTES` | Valores válidos de `?tema=` y `?contraste=` | No |
| `MOVIL`, `BAJO` | Puntos de quiebre (celular, pantalla baja). `MOVIL` lo usa también el guion | Con cuidado |
| `TOKENS`, `TOKENS_ALTO` | **Tokens de color y material** para claro, oscuro y alto contraste | **Sí** |
| `VIDRIO_CLARO`, `VIDRIO_REGULAR` | Qué superficies llevan cada material | Solo para agregar o quitar superficies |
| `CSS` | Estilos base: medidas (`:root`), material, escenario, Ajustes, las tres pantallas, componentes y el cambio de pantalla | **Sí** |
| `CSS_MEDIO`, `CSS_MOVIL`, `CSS_ESTRECHO`, `CSS_BAJO` | Ajustes por tamaño: 761–1100 px, ≤ 760 px, ≤ 380 px, alto ≤ 560 px | **Sí** |
| `CSS_ALTO`, `CSS_LITE`, `CSS_MOVIMIENTO`, `CSS_FORZADOS` | Alto contraste, modo Lite, movimiento reducido y colores forzados | **Sí** |
| `aplicar()`, `_tokens_css()`, `_vidrio()` | Arman y ordenan todo el CSS | No |
| `ICONOS` | Iconos SVG de línea (heredan el color del texto) | **Sí** |
| `ajustes()`, `cabecera_inicio()`, `etiqueta()`, `espera()`, `como_funciona()`, `pie_inicio()`, `controles_panel()`, `asa_hoja()`, `boton_abrir_panel()`, `seccion()`, `acciones_area()`, `kpis()`, `herramientas_2d()`, `controles_camara()`, `leyenda_*()`, `pie()`, `cabecera_exportar()`, `progreso()`, `recibo()`, `resumen_final()`, `legal_exportar()` | Piezas HTML: definen la estructura y las clases de cada pieza | Solo sus clases decorativas; no los `data-y2k-*` ni la estructura |
| `_UI` (dentro, `CSS_IFRAME`) | Guion de la interfaz del navegador; `CSS_IFRAME` es el estilo de los controles de Leaflet dentro de su iframe | Solo `CSS_IFRAME` |

### Pasos para cambiar la estética

1. **Colores y materiales**: edita `TOKENS` (claro y oscuro) y `TOKENS_ALTO` (alto contraste). Cada token es una variable CSS (`--y2k-…` o `--lg-…`); ningún componente debería tener colores propios.
2. **Medidas y movimiento**: al principio de `CSS`, en `:root`: `--y2k-g` (margen entre piezas flotantes), `--y2k-panel-w` (ancho del panel), `--y2k-capsula` (alto de las cápsulas), `--y2k-r` y `--y2k-r-ctl` (radios), `--y2k-dur` y `--y2k-curva` (transiciones).
3. **Tipografía**: el `@import` de Google Fonts y la regla `font-family` al principio de `CSS` (hoy, Figtree). El manual tiene la suya.
4. **Forma de los componentes**: las reglas de `CSS` y de los bloques por tamaño. Están agrupadas por zona y comentadas (material, escenario, Ajustes, pantalla 1, pantalla 2: panel, tablero, herramientas, píldoras y ficha; pantalla 3: avance, recibo y resumen; cambio de pantalla).
5. **Colores que no son CSS**: `PALETAS` (gráficas y 3D) y `.streamlit/config.toml` (widgets de Streamlit: listas, deslizadores, fechas). Deben coincidir con los tokens.
6. **Controles de Leaflet**: `CSS_IFRAME`, dentro de `_UI`. Vive en el iframe del mapa, que no hereda las variables de la página: sus colores están escritos a mano para cada caso (clases `y2k-oscuro`, `y2k-alto`, `y2k-lite`, `y2k-bajo` que el guion pone en el `<html>` del iframe).
7. Sube la versión del guion (`_UI.replace("__V__", "…")` en `instalar_ui`) si cambiaste `_UI`, para que no siga corriendo la versión vieja en una pestaña abierta.
8. Revisa con la [lista de comprobación](#lista-de-comprobación-tras-un-cambio-estético).

### Los tokens

| Token | Uso |
|---|---|
| `y2k-bg` | Fondo de la página (se ve mientras carga) |
| `y2k-ink`, `y2k-ink-2`, `y2k-ink-3` | Texto principal, secundario y de apoyo |
| `y2k-line`, `y2k-line-2` | Separadores y bordes suaves / marcados |
| `y2k-accent`, `y2k-accent-texto`, `y2k-accent-2`, `y2k-sobre-acento` | Botón principal, enlaces sobre vidrio, segundo color del degradado de la barra de avance, texto sobre el botón principal |
| `y2k-foco` | Contorno de foco del teclado |
| `y2k-alerta`, `y2k-alerta-borde`, `y2k-alerta-bg` | Avisos de altitud dudosa, aviso del navegador y avisos de fallo |
| `y2k-ok`, `y2k-ok-luz`, `y2k-peligro` | Listo (texto) y el verde luminoso del punto de estado y la barra completa; error y acciones de borrar |
| `y2k-campo`, `y2k-campo-borde` | Campos y tarjetas dentro del vidrio (cifras, acciones, recibo, desplegables, píldora de la consulta) |
| `y2k-hover`, `y2k-pista`, `y2k-lente`, `y2k-lente-sombra` | Fondo al pasar el puntero, carril de la barra de avance y "lente" del elemento elegido (2D/3D, menú abierto) |
| `lg-claro`, `lg-regular`, `lg-denso` | Tinte del vidrio claro (controles pequeños), regular (superficies con texto) y denso (sin desenfoque: Lite o navegador sin `backdrop-filter`) |
| `lg-filtro-claro`, `lg-filtro-regular` | `backdrop-filter` de cada material (desenfoque, saturación y brillo de lo que hay detrás) |
| `lg-brillo`, `lg-luz`, `lg-borde`, `lg-filo`, `lg-especular`, `lg-sombra` | Reflejo superior, canto de luz, borde inferior, filo exterior, brillo que sigue al puntero y sombra de profundidad |
| `y2k-velo` | Velo sobre el mapa en Parámetros y Exportación |
| `y2k-mapa-fondo`, `y2k-cielo` | Fondo mientras carga el mapa 2D; cielo detrás del relieve 3D |
| `y2k-tono`, `y2k-alto` | No son colores: el guion los lee para saber el tono (claro/oscuro) y si hay alto contraste |

Los textos se calcularon para cumplir **AA (4,5:1)** sobre el vidrio ya compuesto con el peor fondo posible (negro bajo el vidrio claro, blanco bajo el oscuro) y se midieron sobre el mapa. Si bajas la opacidad de `lg-claro`/`lg-regular` o aclaras `y2k-ink-3`, vuelve a medir.

### Colores que viven fuera de `estilo.py`

Son colores **de datos o de mapa**, no de la interfaz; cambiarlos cambia el significado visual de los datos, así que van aparte:

| Qué | Dónde |
|---|---|
| Clases de cobertura (verde, amarillo, naranja, rojo) | `calidad.CLASES_CALIDAD` (los usan el mapa, el 3D, la lista, el reparto de la exportación y la leyenda) |
| Cuenca, buffer, pines, ficha emergente del 2D | `map_view.py` (`AZUL`, `NARANJA`, `GRIS`, `TINTA_2`, `ALERTA`…) |
| Cuenca, buffer, pines, haces y fantasmas del 3D; rampa de la textura Altura | `terreno.py` (`construir_deck`, `RAMPA_ALTURA`, `_ORBITA`) |
| Colores de las líneas y pines de la leyenda | `estilo.leyenda_estaciones` (deben coincidir con los dos anteriores) |
| Escáner del mapa 2D | `escaner.py` (`COLORES`) y `scan_overlay.js` |
| Intro satelital | `static/intro_satelital/` (tiene su propia estética) |
| Aviso del navegador del 3D | `terreno.AVISO_NAVEGADOR` trae estilos en línea, pero `.y2k-aviso3d` en `estilo.CSS` los reemplaza |

### El contrato: lo que no hay que tocar al cambiar la estética

Estos nombres unen la estructura (Python), la estética (CSS) y el guion del navegador. Si cambias uno, hay que cambiarlo en todos los lugares que lo usan.

**Claves de contenedores** (producen la clase `.st-key-<clave>`): `y2k_escenario`, `y2k_mapa2d`, `y2k_visor3d`, `y2k_ajustes`, `y2k_inicio`, `y2k_fechas`, `y2k_panel`, `y2k_panel_cab`, `y2k_panel_fila`, `y2k_cuerpo`, `y2k_abrir`, `y2k_herr`, `y2k_dock`, `y2k_dock_izq`, `y2k_dock_der`, `y2k_ficha`, `y2k_exportar`, `alerta_altura`, `alerta_ficha` y los invisibles (`y2k_guiones`, `y2k_hipso`, `y2k_velo`, `y2k_ocultos`, `y2k_precal`, `y2k_orbita`, `y2k_escaner`).

**Claves de widgets que usan el CSS o los guiones**: `vista` (también `static/intro_satelital/player.js` y `terreno.css_boton_3d_espera`), `textura`, `escala_altura`, `ir_mapa`, `chip_param`, `preparar`, `y2k_repetir_intro`, `lite_inicio`, `lite_menu`, `pref_tono`, `pref_alto`, `bajar_zip` y los ocultos `y2k_lite_reintentar`, `y2k_reintentar3d`, `y2k_pasar2d`, `y2k_borrar`, `y2k_subir`.

**Atributos de las piezas HTML** (los pone `estilo.py`, los lee el guion):

| Atributo | Elemento | Qué hace al pulsarlo |
|---|---|---|
| `data-y2k-panel-btn` | Botón de la cabecera del panel y «Panel» | Oculta o muestra el panel |
| `data-y2k-asa`, `data-y2k-hoja-max` | Asa y botón de la hoja (celular) | Cambian la altura de la hoja (también arrastre y flechas) |
| `data-y2k-menu` / `data-y2k-menu-de` (`dibujo`, `capas`) | Botones de la cápsula de herramientas y sus menús | Abren y cierran el menú (Escape, flechas, clic fuera) |
| `data-y2k-dibujar` | «Dibujar», «Redibujar» | Activa la herramienta de rectángulo de Leaflet |
| `data-y2k-editar` | «Ajustar» | Activa la edición de las esquinas de Leaflet |
| `data-y2k-area` | «Usar el área visible» | Crea el área con la zona visible (`aria-disabled` hasta el zoom 10) |
| `data-y2k-subir`, `data-y2k-borrar`, `data-y2k-2d` | «Subir», «Borrar», «Ver en 2D» | Pulsan los botones ocultos `y2k_subir`, `y2k_borrar`, `y2k_pasar2d` |
| `data-y2k-capa` | Opciones del menú Mapa base | Eligen la capa base (pulsan el control de capas oculto de Leaflet) |
| `data-y2k-zoom` (`mas`, `menos`) | Zoom de la cápsula | Acercan o alejan el mapa |
| `data-y2k-cam` (`acercar`, `alejar`, `izq`, `der`, `subir`, `bajar`, `norte`) | Botones de cámara 3D | Mueven la cámara |
| `data-y2k-espera` (`data-servidor`, `data-texto`) | Línea de estado de Parámetros | El guion cambia su texto por «Cargando el mapa…» mientras el mapa no carga |

**Clases que el guion busca**: `.y2k-pantalla` (la pantalla actual), `.y2k-leyenda`, `.y2k-camara-estado`, `.y2k-atrib3d`, `.y2k-dialogo` (la crea el guion), `.y2k-sat` (capa de la intro, la crea `player.js`) y `.lg-claro` / `.lg-regular` (material de las piezas HTML; el brillo especular las reconoce).

**Clases de composición** (las usa el CSS para colocar las piezas): `.y2k-sobre` (pieza HTML sobre el mapa: su contenedor de Streamlit se vuelve transparente a los clics y se estira al tamaño del mapa) y `.y2k-pantalla[data-p]` (con `:has()`, decide qué huecos se ven en cada pantalla y si el mapa va velado).

**Estado en `<html>`**: el guion de la interfaz escribe `data-y2k-panel` (`abierto`/`cerrado`), `data-y2k-hoja` (`min`/`media`/`max`), `data-y2k-p` (la pantalla) y `data-y2k-mapa-listo` (el mapa 2D cargó: habilita «Seleccionar área en el mapa»). El precalentamiento de la intro escribe `data-y2k-listo` (mientras no coincida con el área, el botón 3D queda gris). El visor 3D lleva `data-mostrar="<turno>"` durante la secuencia de entrada.

**Variables CSS que escribe el guion** (en CSS solo se les da un valor inicial): `--y2k-ov-top`, `--y2k-ov-izq`, `--y2k-ov-der`, `--y2k-ov-abajo` (la zona libre del mapa), `--y2k-ley-abajo`, `--y2k-ley-izq`, `--y2k-atrib-abajo`, `--y2k-dock-h`, y `--mx`/`--my` en cada vidrio (brillo especular). En el iframe de Leaflet: `--tl-top`, `--tl-izq`, `--tr-top`, `--tr-der`, `--bl-abajo`, `--bl-izq`, `--br-abajo`, `--br-der`, `--acc-top`, `--acc-der` (dónde salen «Guardar» y «Cancelar» del dibujo).

**Variables CSS que el guion lee**: `--y2k-lite`, `--y2k-tono`, `--y2k-alto`.

**Almacenamiento del navegador**: `localStorage` `y2k_panel`, `y2k_leyenda` (y `y2k_sat_*` de la intro); `sessionStorage` `y2k_aviso3d_cerrado`.

### Lista de comprobación tras un cambio estético

- Claro, oscuro y alto contraste; colores forzados (Windows); con y sin modo Lite; con movimiento reducido.
- Escritorio (1440 y 1024 px), celular vertical (390 px) y horizontal (844 × 390).
- Las tres pantallas; en el mapa, 2D y 3D, con panel abierto y cerrado, con ficha, con los menús de herramientas abiertos y con la hoja del celular en sus tres alturas; la exportación en curso y terminada.
- Contraste AA de los textos sobre el mapa (satélite y calles), no sobre un fondo liso.
- Que el vidrio siga dejando ver el mapa (si queda opaco, ya no es vidrio) y que en Lite quede legible sin desenfoque.
- Que ni la leyenda ni la escala o la atribución de Leaflet queden debajo del panel, las píldoras o la ficha, y que los menús no queden tapados.

## Guion de la interfaz del navegador

`estilo._UI` se inyecta una vez en la página principal (`estilo.instalar_ui`, dentro de `y2k_guiones`) y sobrevive a las recargas de Streamlit. Se repasa cada 500 ms y en cada cambio del DOM. Hace:

- **Panel y hoja** sin recargar la página (atributos en `<html>`, la elección en `localStorage`), con `aria-expanded`. La hoja del celular se arrastra solo desde el asa (no compite con mover el mapa).
- **Menús de la cápsula de herramientas** (`role="menu"`): abren y cierran, se recorren con flechas, Escape devuelve el foco. Sus opciones manejan los controles ocultos de Leaflet.
- **Pantallas**: marca el escenario como `inert` en Parámetros y Exportación, y en Parámetros hace esperar al botón principal hasta que el mapa 2D cargó (alguna tesela, 6 s con el mapa creado o, si no carga, 15 s).
- **Reparto del espacio** (`distribuir`): mide las piezas flotantes y calcula la zona libre del mapa; sube la leyenda, la escala y la atribución por encima de las píldoras que comparten su columna, y pone las acciones del dibujo de Leaflet junto a la cápsula de herramientas. También encuadra el área recién montada en la zona libre.
- **Mapa 2D**: inyecta `CSS_IFRAME` (oculta los controles de Leaflet, que maneja la cápsula, y da vidrio a las acciones del dibujo), traduce Leaflet.draw al español, maneja dibujar, ajustar, «Usar el área visible», capas y zoom, y vigila las teselas que fallan.
- **3D**: botones de cámara (busca el `deck` por dentro de React) y vigilancia de WebGL, red y carga lenta.
- **Varios**: traduce el cargador de archivos, quita del nombre accesible el texto de los iconos de Streamlit y mueve el brillo especular con el puntero.

## Temas, contraste, modo Lite y movimiento

- **Tema** (*Claro / Oscuro*) y **alto contraste** (un interruptor) son independientes y están en el menú Ajustes. Sin elegir, siguen al equipo: se resuelven con `prefers-color-scheme` y `prefers-contrast` en media queries (sin destello); el interruptor de contraste solo fuerza el alto contraste (apagado, vuelve a seguir al equipo). El alto contraste usa superficies opacas y bordes nítidos en el tono vigente: no es el modo oscuro. La elección viaja en la dirección (`?tema=`, `?contraste=`). Streamlit no deja cambiar su tema desde Python: `_SINCRONIZAR_TEMA` pulsa sin que se vea su menú (oculto).
- Con **colores forzados** (`forced-colors`) se respetan los colores del sistema y solo se reponen bordes y señales que el navegador quita.
- **Modo Lite** (interruptor en Ajustes y en la tarjeta de Parámetros, `?lite=1`; con Lite activo se ve la marca «Lite» junto a Ajustes): mismos datos, controles y funciones con menos coste gráfico. Agrega `CSS_LITE` (sin desenfoque, brillos ni transiciones: variante de baja transparencia) y usa un 3D liviano (menos detalle de malla, caché menor, 1 píxel de dibujo por píxel CSS), sin intro satelital, sin secuencia de entrada ni vuelta de cámara (la cámara queda de una vez en el encuadre final) y escáner 2D sin rejilla ni destellos. Los guiones leen Lite en el navegador (variable `--y2k-lite`), así activarlo no mueve la cámara ni repite animaciones.
- **Movimiento reducido** es independiente de Lite: quita transiciones, animaciones de entrada y el brillo que sigue al puntero, pero conserva el vidrio. La intro del 3D no se reproduce sola (un aviso lo dice); «Repetir animación» sí la muestra, porque la pide la persona.
- Orden del CSS (`aplicar`): base → bloques por tamaño → tokens del tema → alto contraste → Lite → movimiento reducido → colores forzados.

## Avisos de fallo

Nunca cambian de modo por su cuenta; ofrecen elegir:

- Pérdida del contexto gráfico WebGL del 3D ("Fallo gráfico"): *Activar Lite y reintentar*, *Seguir intentando*, *Ver en 2D*.
- Teselas del 3D o del mapa base 2D que fallan una y otra vez ("Problema de red"; en 3D se cuenta por tipo: relieve o imagen).
- Relieve que no avanza en 40 s sin errores claros ("Carga lenta").

Reintentar rehace el visor 3D y repone la cámara y la selección; en 2D vuelve a pedir las teselas sin mover el mapa. Los textos no afirman falta de memoria gráfica cuando solo falló una descarga.

## Mapa 2D

- Solo se puede dibujar un **rectángulo** («Ajustar» mueve sus esquinas y «Borrar» lo quita). Los controles de Leaflet (zoom, dibujo, capas) están ocultos: los maneja la cápsula de herramientas de la página, y las acciones del dibujo («Guardar», «Cancelar») salen junto a ella. Un rectángulo nuevo reemplaza al anterior; "Usar el área visible" crea uno igual con la zona que se ve (`map.fire("draw:created")`), y así se puede marcar la cuenca solo con el teclado (foco en el mapa, flechas y +/−). La cuenca subida desde archivo puede tener cualquier forma. Un clic en la cuenca no abre la alerta del navegador con su GeoJSON (`show_geometry_on_click=False`).
- Al soltar (o editar) el rectángulo corre un **escáner** sobre él mientras el servidor calcula las estaciones; al terminar se desvanece, muestra "N estaciones con datos" y los pines aparecen de norte a sur con un pequeño rebote. Mientras corre, el mapa no se mueve ni hace zoom; la barra de dibujo sigue activa y dibujar otra vez reinicia el escáner. Tope de 30 s por si algo falla; con `prefers-reduced-motion` no corre y en modo Lite se dibuja sin rejilla ni destellos y los pines aparecen sin animación.
- Aún no hay animación para la cuenca subida desde archivo (el mapa todavía no existe mientras se calcula).
- Sin área, el mapa muestra el catálogo nacional agrupado (`FastMarkerCluster`) para ubicarse. La capa se arma de nuevo en cada corrida: folium no deja volver a dibujar el mismo objeto (el agrupador quedaría sin definir).
- La lista de parámetros del IDEAM se pide por detrás al arrancar el servidor (`app._iniciar_precarga_servidor`) y las series del parámetro elegido, al elegirlo (`app._precargar_series`); ver [Parámetros](#1-parámetros-pantalla_parametros-en-apppy).

**Contratos que no hay que romper** (si cambias `app.py`, `map_view.py` o `escaner.py`):

1. **El mapa base no debe cambiar al dibujar ni al cambiar de pantalla.** `st_folium` identifica el componente por un hash del mapa base; si cambia, Streamlit destruye el mapa y lo crea de nuevo (pantalla en blanco, salto de zoom, y se pierde el escáner). Por eso `mapa_base` solo recibe el área cuando el mapa se monta de cero (archivo, volver del 3D, «Borrar»). La guardia está en `app.mapa_2d`: `ss._mapa_en_run_anterior`, `ss._base_cuenca` y `ss._mapa_version`. Las estaciones y el buffer van aparte, en `feature_group_to_add`, que se actualiza sin reconstruir el mapa. Y el mapa debe ir siempre en `y2k_escenario`, antes de cualquier cosa condicional.
2. **Los pines llevan `options.y2k = "pin"`** (`map_view._marca`). folium descarta los argumentos que no conoce; la marca se escribe directo en `marcador.options`.
3. **Los pines deben ir en el mismo canvas que el rectángulo.** No les pongas un panel propio: con `prefer_canvas` cada panel tiene un canvas del tamaño del mapa y el de encima se come los clics del lápiz y la papelera (se comprobó con ratón real).
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
- Los colores del PNG de relieve no deben "corregirse" (`colorSpaceConversion: none`) o el relieve se llena de picos falsos. Algunos navegadores con protección de privacidad lo alteran: la app lo detecta y muestra un aviso que se puede cerrar.
- `map_style="__MAP_STYLE__"` evita que Streamlit ponga un mapa plano de fondo a nivel 0.
- El 3D se arma en el servidor (≈ 3 s con caché fría en un PC; más en la nube) y el navegador baja los tiles después.
- Los `components.html` de `app.py` corren en un iframe de altura 0 y llegan al DOM principal por `window.parent`.

## Intro satelital (del mapa 2D al despliegue 3D)

Animación de ~16,5 s (Three.js) que **cubre la carga del 3D**: un satélite recibe los datos de Colombia, apunta al cuadro del usuario y dispara los láseres de área y buffer y las cápsulas (las estaciones); después la pantalla se enciende como un monitor y el relieve real deck.gl empieza su secuencia (láseres, caída de pines, haces naranjas). El diseño viene de Claude Design (zip "Animación despliegue 3D estaciones").

**Archivos** (`static/intro_satelital/`, servidos por Streamlit en `/app/static/intro_satelital/`):

| Archivo | Para qué sirve |
|---|---|
| `satellite-scene.js` | Escena (globo, satélite, haz, cápsulas, láseres, brillo). Exporta `TUNE` (ajustes), `setBoxLonLat`, `setBuffer`, `precargarDatos`, `getScene` |
| `player.js` | Reproductor: capa que cubre la ventana, interfaz (HUD SVG), reloj, panel de ajustes (apagado), precalentamiento, arranque en el clic y encendido |
| `mosaico.js` | Primer plano con mosaico de satélite (Esri) de la cuenca; si falla, `satimg.js` pinta un terreno de respaldo |

**Flujo.**
1. Al **confirmar la cuenca** (`app.py`, tras `rango = ...`) se precalienta por detrás: se carga el reproductor, se arma el mosaico y se bajan d3/topojson/mapa mundial. No se crea WebGL. El botón **3D queda gris** hasta que `document.documentElement.dataset.y2kListo` iguala la clave de la cuenca.
2. Al pulsar 3D la animación **arranca en el clic** (Streamlit tarda 2–3 s en dibujar el visor). Su capa (`.y2k-sat`) va directo en `<body>`, fija, encima de todos los controles (z-index 60): si viviera dentro de un contenedor de Streamlit, este podría rehacerse al pasar del 2D al 3D y la animación se perdería sin aviso (así pasaba antes). Cuando el visor llega, el guion `_INTRO_SATELITAL` la **adopta** (le pone su turno) o, si no hubo arranque temprano, la inicia él. Si el visor 3D desaparece (vuelta al 2D, otra pantalla), la capa se retira. «Saltar animación» o la tecla Escape la terminan.
3. El guion `_ORBITA` esconde las capas de deck.gl, espera a que termine la intro (`window.__y2kIntroSatFin == turno`) y entonces corre la secuencia de entrada.
4. La intro solo corre una vez por área y buffer (igual que la secuencia); «Repetir animación» la vuelve a pedir (`forzar`). No corre en celulares ni en modo Lite. Con `prefers-reduced-motion` no corre sola, pero sí al pedirla con «Repetir animación». Si la intro falla al cargar (por ejemplo, sin acceso a esm.sh), el visor 3D no se queda tapado: la capa de la intro no se vuelve a poner.

**Interfaz (HUD) de la intro.** Se dibuja en SVG dentro de `hudSvg` (`player.js`) y solo muestra datos con sentido; no hay botones de zoom ni escalas falsas.
- **Altitud** (km) en cuenta regresiva durante el descenso; transmite la velocidad, por eso no hay medidor de km/s.
- **"Calculando trayectoria"** mientras la cámara se acerca; pasa a "Lista" cuando el objetivo queda fijado.
- **Lista "Preparando lanzamiento"** con tres pasos que se calibran en orden, y debajo las barras **ÁREA** y **BUFFER** con su porcentaje. Con todo cargado se dispara.
- **"Estaciones lanzadas n/N"** usa el total real de estaciones (la intro solo dibuja hasta 250 puntos, pero el contador usa `n`, el total que manda `_datos_satelite`).
- **Sin buffer:** las dos barras se cargan juntas y, al disparar, se apagan la barra y el cañón naranja del buffer (`setBuffer` en `satellite-scene.js`). El estado `buffer` viaja desde `app.py` (`precalentar_satelite` e `intro_satelital`), así que cambiarlo repite la intro.
- Los textos de ambientación (nombre del satélite, "enlace activo", "objetivo fijado") son decoración y no representan datos.
- El botón «Saltar animación» se acomoda con CSS (`.y2k-sat > button` en `estilo.CSS`) y recibe el foco al empezar.

**Cosas que no hay que romper.**
- Un solo contexto WebGL reutilizado: crear y destruir contextos (o `forceContextLoss`) termina en "context loss and was blocked" de Chrome. `destroy()` solo libera geometrías, texturas y buffers.
- No mandar las capas de deck.gl escondidas desde Python: cualquier re-render de React las repone y "se borra todo" al terminar. Se tapa el visor con CSS y las esconde el guion (con una guardia que las vuelve a esconder).
- `TUNE` en `satellite-scene.js` guarda los valores por defecto; el panel de ajustes (si se enciende con `PANEL_SATELITE`) los cambia en vivo y los recuerda en `localStorage` (prefijo `y2k_sat_`).
- Tras editar los archivos de la intro hay que **recargar la página del navegador** (F5, mejor Ctrl + F5): el reproductor se carga una sola vez por página y, si no se recarga, sigue corriendo la versión vieja aunque el archivo ya cambió. El parámetro `?v=` de las direcciones cambia con la fecha de los archivos.

**Temporal (quitar antes de presentar):** el botón «Repetir animación» (↻) de las píldoras del 3D (`y2k_repetir_intro` en `app.py`). El panel «⚙ Ajustes» de la intro está apagado (`PANEL_SATELITE = False` en `terreno.py`); se enciende solo para afinarla.

## Textura "Altura" del 3D

Tercera textura (junto a Satélite y Topográfico): el relieve se colorea por altitud (verdes abajo, naranjas y rojos arriba) con sombreado de ladera. Hay dos escalas: **Rango de la zona** (mínimo y máximo de la cuenca con buffer) y **Rango de Colombia** (0–5.730 m, más pixelada para ahorrar memoria). Un guion (`_HIPSOMETRICO`) intercepta `window.fetch` y devuelve, para las imágenes con la marca `y2k_hipso`, el tile de elevación coloreado. La leyenda sale de `terreno.leyenda_altura()` dentro de `estilo.leyenda_altura()`.

## Cómo probar cambios

- **Lógica y flujo:** `streamlit.testing.v1.AppTest` recorre las pantallas sin navegador (no ejecuta JavaScript). La red bloquea a veces el IDEAM: conviene simular `obtener_catalogo_parametros`, `obtener_series_disponibles` y `procesar_descargas`.
- **Lo visual (3D, escáner, vidrio):** abrir la app en un navegador sin ventana (Chrome o Edge, por ejemplo con Playwright) y sacar capturas. Para el mapa 2D hay que probar con **ratón real** (eventos de ratón del navegador): disparar eventos de Leaflet a mano no detecta, por ejemplo, un canvas que intercepta los clics. Al correr un script de prueba aparte con `streamlit run`, el servidor no recarga los módulos del proyecto: reinícialo tras cambiar `modules/`.
- **Contraste:** medirlo sobre píxeles reales (captura de cada texto: fondo = mediana de la caja, tinta = el píxel más alejado), sobre el mapa y con un fondo negro o blanco bajo el vidrio.
- Conviene probar con una cuenca grande, con muchas estaciones, con el modo Lite, en un celular, con los tres temas y con movimiento reducido (Lite y movimiento reducido por separado y juntos).
- **Trampas de Streamlit:** `st.html` quita los SVG en línea (por eso el HTML propio va con `estilo.md`, que usa `st.markdown`); un `<style>` cuyo texto contenga `<` seguido de una letra (aunque sea en un comentario CSS) lo descarta el sanitizador entero; los contenedores horizontales traen un margen negativo (las cápsulas lo anulan); Streamlit pinta los captions al 60 % de opacidad (el CSS lo devuelve a 1); los botones con ayuda y los popover traen una copia oculta en el DOM (en las pruebas, usa `:visible`); `st.dataframe` no acepta `args` (el callback va con `functools.partial`); y al cambiar de pantalla deja los elementos viejos hasta terminar la corrida, por eso las tres pantallas tienen [huecos fijos](#pantallas).

## Convenciones

- Interfaz y textos en español. La cantidad probable se muestra siempre como **cobertura**, nunca como "calidad" (el nombre interno `calidad` se conserva en el código).
- Colores solo a través de tokens (`estilo.TOKENS`); los colores de datos y de mapa, en sus módulos (ver [Colores que viven fuera de `estilo.py`](#colores-que-viven-fuera-de-estilopy)).
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

La aplicación muestra estos créditos al final del panel del mapa y, más cortos, en el borde de cada mapa.
