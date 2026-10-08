# Descargador IDEAM

Descarga automática de series hidrometeorológicas del portal **DHIME del IDEAM** (Colombia) para todas las estaciones de una cuenca. Es una herramienta independiente, no oficial del IDEAM.

1. Dibujas un rectángulo sobre el mapa o subes el contorno de tu cuenca (shapefile en ZIP, GeoJSON, KML/KMZ o GeoPackage).
2. La app muestra las estaciones del IDEAM que caen adentro, y en un buffer opcional. Para cada una calcula la **cantidad probable**: qué parte del periodo consultado cubre el registro de la estación, entre su primer y su último dato. Este valor no descuenta los huecos internos.
3. Filtras por cantidad probable mínima y descargas todo en un ZIP: un Excel por estación, con el formato original del IDEAM y los bloques de años ya unidos. Si quieres, las estaciones van separadas en carpetas por cobertura del periodo. El ZIP incluye `CITACION.txt` con la cita de la fuente.

Incluye vista 3D con relieve real y aviso de estaciones cuya altitud en el catálogo no coincide con el terreno.

## Contenido

- [Usarla en tu computador](#usarla-en-tu-computador) · [Publicarla](#publicarla-en-streamlit-community-cloud)
- [Cómo está organizado](#cómo-está-organizado): las tres capas y los archivos
- [Pantallas](#pantallas): el mapa (con su plano) y la descarga
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
| **Estructura de la interfaz** | Qué pantallas hay, qué contiene cada zona, en qué orden, con qué textos y qué pasa al pulsar cada cosa. | `app.py`, `modules/panel_estadisticas.py`, `modules/map_view.py`, `terreno.construir_deck`, y las funciones de piezas de `modules/estilo.py` (las que devuelven HTML: `paso`, `pestanas`, `estado_accion`…) |
| **Estética** | Colores, materiales, tipografía, medidas, radios, sombras, animaciones, iconos, temas y modo Lite. | `modules/estilo.py` (tokens, bloques CSS e iconos) y `.streamlit/config.toml` (colores de los widgets de Streamlit) |

La estructura y la estética se conectan solo por **nombres**: las claves de los contenedores de Streamlit (`key="y2k_panel"` produce la clase CSS `.st-key-y2k_panel`), las clases de las piezas HTML propias (`.y2k-…`) y algunos atributos `data-y2k-…`. Mientras esos nombres no cambien (ver [el contrato](#el-contrato-lo-que-no-hay-que-tocar-al-cambiar-la-estética)), se puede rehacer toda la estética editando solo `estilo.py`.

### Archivos

| Archivo | Capa | Para qué sirve |
|---|---|---|
| `app.py` | Estructura | Las dos pantallas (mapa y descarga), el orden de cada zona, el estado de sesión y la cola de descarga |
| `modules/estilo.py` | Estética (+ piezas) | Tokens de tema, materiales de vidrio, CSS de toda la app, iconos, cápsulas de arriba, piezas HTML (pasos, pestañas, isla de acción, leyendas, cámara 3D, pie) y el guion de la interfaz del navegador |
| `modules/panel_estadisticas.py` | Estructura | Pestaña Resumen (cifras, gráficas, listas) y ficha de la estación seleccionada |
| `modules/map_view.py` | Estructura | Mapa 2D (Leaflet vía `streamlit-folium`): capas base, herramienta de dibujo, pines y fichas emergentes |
| `modules/terreno.py` | Lógica + estructura | Vista 3D: relieve, textura por altura, pines, cámara, secuencia de entrada y guiones de la intro satelital |
| `modules/escaner.py`, `modules/scan_overlay.js` | Estructura | Escáner del mapa 2D: animación mientras se calculan las estaciones y aparición de los pines en orden |
| `modules/escena_descarga.py` | Estructura | Animación pixel art de la descarga |
| `modules/ideam_downloader.py` | Lógica | Token, consultas por bloques de años, fusión de los Excel, cupos y turnos, `CITACION.txt` |
| `modules/ideam_parameters.py` | Lógica | Variables y parámetros visibles del portal, límites de años por frecuencia |
| `modules/ideam_catalog.py` | Lógica | Catálogo de estaciones (caché en `data/ideam_catalogo_completo.geojson`) |
| `modules/calidad.py` | Lógica | Clases de cobertura (alta ≥ 70 %, media ≥ 50 %, baja ≥ 25 %, crítica) y sus colores |
| `modules/geo_input.py`, `geo_utils.py` | Lógica | Lectura de archivos, buffer y filtro espacial |
| `static/intro_satelital/` | Estructura | Intro satelital (del mapa 2D al 3D): escena Three.js, reproductor, mosaico de satélite |
| `static/manual.html` | Documento aparte | Manual de usuario, servido en `app/static/manual.html` (tiene su propio CSS) |
| `.streamlit/config.toml` | Estética | Colores de los widgets de Streamlit en claro y oscuro (deben coincidir con los tokens) |

## Pantallas

La app tiene **dos pantallas** (`ss.paso`): `"mapa"` y `"descarga"`. No hay pantalla de inicio: el mapa del país se ve desde el primer momento.

### 1. Pantalla del mapa (`pantalla_mapa` en `app.py`)

El mapa ocupa toda la ventana y encima flota una capa funcional de vidrio. Cada zona es un contenedor de Streamlit con su clave fija (a la izquierda de cada recuadro):

**Escritorio**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ╭ y2k_marca ──────────╮      ╭ y2k_modo ─╮            ╭ y2k_acciones ──────╮ │
│ │ logo · nombre · [=] │      │  2D │ 3D  │            │ Lite · Apariencia  │ │
│ ╰─────────────────────╯      ╰───────────╯            ╰────────────────────╯ │
│ ╭ y2k_panel ──────────╮ ╭ y2k_tex3d (solo 3D) ──────╮ ╭ y2k_ficha ─────────╮ │
│ │ y2k_panel_cab       │ │ Satélite·Topográf.·Altura │ │ estación elegida   │ │
│ │ [Consulta|Resumen]  │ ╰───────────────────────────╯ ╰────────────────────╯ │
│ │ ─────────────────── │                                                      │
│ │ y2k_consulta        │         y2k_escenario                                │
│ │  1 Cuenca           │         (mapa 2D o 3D a pantalla completa,           │
│ │  2 Parámetro…       │          detrás de todo; encima, las piezas          │
│ │  3 Filtro…          │          .y2k-sobre: leyenda, cámara 3D,             │
│ │  pie                │          atribución y avisos)                        │
│ │ (o y2k_resumen)     │    ╭ y2k_dock (isla de acción) ───────────────────╮  │
│ │                     │    │ y2k_dock_fila: estado · botón principal      │  │
│ │                     │    │ aviso legal (si hay descarga posible)        │  │
│ │                     │    ╰──────────────────────────────────────────────╯  │
│ ╰─────────────────────╯                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Celular (≤ 760 px de ancho)**

```text
┌───────────────────────────┐
│╭──╮╭ 2D│3D ╮ ╭ Lite · Ap ╮│   cápsulas (la marca queda solo con el logo)
│╰──╯╰───────╯ ╰───────────╯│
│╭ y2k_ficha ──────────────╮│   ficha a lo ancho, arriba
│╰─────────────────────────╯│
│                           │
│       y2k_escenario       │
│                           │
│╭ y2k_panel (hoja) ───────╮│   hoja inferior: asa, pestañas y botón ampliar;
││ ===  [Consulta|Resumen] ││   tres alturas (mínima, media, máxima)
│╰─────────────────────────╯│
│ y2k_dock (a todo lo ancho)│   isla de acción pegada abajo
└───────────────────────────┘
```

En **horizontal** (alto ≤ 560 px y ancho > 760 px) se usa la disposición de escritorio, más compacta (`CSS_BAJO`): panel de 300 px, cápsulas de 40 px y botones de Leaflet más pequeños.

| Zona | Contenedor (`key`) | Quién la llena | Qué contiene | Material |
|---|---|---|---|---|
| Marca | `y2k_marca` | `estilo.marca()` | Logo, nombre y botón que oculta o muestra el panel (`data-y2k-panel-btn`). Lleva la marca de pantalla `.y2k-pantalla[data-p]` | vidrio claro |
| Utilidades | `y2k_acciones` | `estilo.control_tema()` | Botón **Lite** (`btn_lite`), menú **Apariencia** (tema y contraste) y enlace al manual | vidrio claro |
| Vista | `y2k_modo` | `app.pantalla_mapa` | Selector **2D/3D** (`key="vista"`) | vidrio claro |
| Texturas 3D | `y2k_tex3d` | `app.pantalla_mapa` | Satélite/Topográfico/Altura (`textura`) y escala (`escala_altura`). Vacío en 2D (el CSS lo oculta) | vidrio claro |
| Panel | `y2k_panel` | `app.pantalla_mapa` | Cabecera `y2k_panel_cab` (pestañas, `estilo.pestanas`), y las pestañas `y2k_consulta` y `y2k_resumen`, cada una con su propio desplazamiento | vidrio regular |
| Isla de acción | `y2k_dock` | `app.pantalla_mapa` | `y2k_dock_fila` (estado con `estilo.estado_accion` + botón principal), avisos (aviso legal) y una franja para los indicadores de carga | vidrio regular |
| Ficha | `y2k_ficha` | `panel_estadisticas.tarjeta_seleccionada` | Estación elegida: nombre, código, altitud, cobertura, aviso de altitud dudosa (`alerta_ficha`), **Ver en 3D** y **Quitar selección**. Vacía si no hay selección (el CSS la oculta) | vidrio regular |
| Mapa | `y2k_escenario` | `app.pantalla_mapa` | En 2D: `y2k_mapa2d` (iframe de `st_folium`), `y2k_escaner` y la leyenda. En 3D: `y2k_visor3d` (pydeck), `y2k_orbita` (guiones), cámara, leyenda y atribución | sin vidrio (es el contenido) |

**Pestaña Consulta** (`y2k_consulta`), en tres pasos numerados (`estilo.paso`):

1. **Cuenca**: área en km² cuando ya hay cuenca; botones grandes «Dibujar un rectángulo» y «Usar el área visible» (`estilo.opciones_cuenca`; en 3D, un aviso para volver a 2D); «Cómo usar el mapa» (desplegable); **Subir un archivo** (`y2k_subida`, con el cargador `subida_<n>` y el botón `usar_subida`); buffer (`buf_on`, `buf_km`) y «Borrar la cuenca» (`borrar_cuenca`).
2. **Parámetro y fechas**: series de alta frecuencia (`avanzado`), Variable, Frecuencia, Parámetro (claves dinámicas `var_…`, `frec_…`, `par_…`), Desde y Hasta (`f_ini`, `f_fin`). Mientras el servidor carga la lista de parámetros aparece un aviso y el mapa sigue usable.
3. **Filtro y archivo** (opcional): cantidad probable mínima (`umbral`) y carpetas por cobertura (`carpetas`).

Al final va el pie (`estilo.pie`): fuente de los datos, condiciones de uso, manual, versión y créditos de los mapas.

**Pestaña Resumen** (`y2k_resumen`, `panel_estadisticas.mostrar_panel`): cuatro cifras (estaciones, cobertura media, tiempo, datos), nota sobre el nivel de aprobación, aviso de altitud dudosa con su lista (`alerta_altura`, `tabla_dudosas`), gráfica de cobertura, gráfica de altitud (`graf_alt`), conteos y la lista de estaciones (`tabla_est`). En 3D, además, el desplegable temporal de ajustes de la animación.

**Isla de acción** (`y2k_dock`): siempre dice qué hay y cuál es el siguiente paso. Los estados salen de `app.pantalla_mapa`, en este orden:

| Situación | Título | Acción |
|---|---|---|
| Sin cuenca (2D) | Marca tu cuenca para empezar | Botones **Dibujar** y **Subir archivo** (`estilo.botones_inicio`) |
| Sin cuenca (3D) | Marca tu cuenca para empezar | Botón **Ir a 2D** (`dock_2d`) |
| Cuenca sin estaciones | No hay estaciones en esta zona | Enlace a Consulta |
| Falló el IDEAM | No se pudo consultar el IDEAM | Enlace a Resumen |
| Sin parámetro | N estaciones en la zona | Aviso de carga o enlace a Consulta |
| Fechas al revés | Revisa las fechas | Enlace a Consulta |
| Más de ~1 millón de filas | El periodo es demasiado largo | Botón desactivado |
| Nadie cumple el filtro | Ninguna estación cumple el filtro | Botón desactivado |
| Todo listo | N estaciones listas para descargar | **Iniciar descarga** (`iniciar_descarga`) + aviso legal |

**Contenedores invisibles** (alto cero, solo guiones o botones que pulsa el navegador): `y2k_guiones` (guion de la interfaz y sincronización del tema), `y2k_hipso` (coloreado de la textura Altura), `y2k_velo` (CSS que tapa el 3D durante la secuencia de entrada), `y2k_ocultos` (botones `y2k_lite_reintentar`, `y2k_reintentar3d`, `y2k_pasar2d`, que pulsan los avisos de fallo, y el vigía de la lista de parámetros), `y2k_precal` (precalentamiento de la intro), `y2k_orbita` (guiones del 3D) y `y2k_escaner`.

**Capas (z-index):** el mapa (`y2k_escenario`) está en 0 y sus piezas (`.y2k-sobre`) en 25 dentro de él; el panel y la ficha en 40; la isla en 45; las cápsulas en 50; los avisos de fallo en 70.

### 2. Pantalla de la descarga (`pantalla_descarga` en `app.py`)

Página normal (con desplazamiento) sobre un fondo de auroras suaves, con las cápsulas de marca y utilidades arriba:

```text
╭ y2k_marca ╮                                    ╭ y2k_acciones ╮
y2k_descarga
├─ encabezado (.y2k-encabezado): título + parámetro · periodo · estaciones
├─ columna izquierda: y2k_card_descarga
│    escena pixel art · barra de avance (.y2k-pbar) · conteos (.y2k-pmeta)
│    botones según el estado: Detener · Reintentar · nombre del ZIP ·
│    Descargar el ZIP · aviso legal · Volver al mapa · Nueva cuenca
├─ columna derecha: y2k_card_consola (registro, durante la descarga)
│                   o y2k_card_resumen_zip (resumen, al terminar)
└─ pie
```

Estados: en fila (servidor ocupado, con «Cancelar y volver»), en curso, detenida, con error y lista. Todas las tarjetas `y2k_card_*` comparten el mismo vidrio.

### Manual

`static/manual.html` es una página aparte, con su propio CSS. Describe la interfaz con los nombres de sus botones: si cambias textos visibles de la app, revísalo.

## Cómo se arma la página en cada corrida

Streamlit vuelve a ejecutar `app.py` de arriba abajo en cada interacción. El orden es:

1. Preferencias desde la dirección (`?tema=`, `?contraste=`, `?lite=1`) y valores por defecto del estado de sesión.
2. `estilo.aplicar(tema, contraste, lite)`: todo el CSS de la página.
3. `estilo.guiones_globales()` (guion de la interfaz y sincronización del tema de Streamlit), `y2k_hipso` y `y2k_velo`.
4. Cápsulas comunes: `estilo.marca()` y `estilo.control_tema()`.
5. Credenciales, catálogo de estaciones y precarga (en un hilo) de la lista de parámetros.
6. La pantalla (`pantalla_mapa` o `pantalla_descarga`).

Dentro de `pantalla_mapa` **primero se crean las zonas vacías** (modo, texturas, panel, isla, escenario, ocultos) y después se llenan en el orden en que hay datos: los controles de Consulta → el cálculo de estaciones, altitudes y disponibilidad (con indicadores de carga en la isla) → la selección → el mapa → Resumen → pestañas → isla de acción → ficha. Como casi todas las zonas son fijas (`position: fixed`), el orden en el DOM no cambia dónde se ven.

**Estado de sesión** (`st.session_state`, en el código `ss`):

| Clave | Para qué |
|---|---|
| `paso` | Pantalla actual: `"mapa"` o `"descarga"` |
| `cuenca` | Geometría de la cuenca (GeoDataFrame) o `None` |
| `vista` | `"2D"` o `"3D"` (es la clave del selector; sin `default` porque la cambian también la ficha, la lista de altitudes y los avisos, con callbacks que corren antes de dibujarlo) |
| `estacion_sel` | Código de la estación seleccionada |
| `tema`, `contraste`, `lite` | Preferencias de apariencia y rendimiento (también en la dirección) |
| `version_mapa`, `version_subida`, `version_3d` | Contadores que rehacen el mapa 2D, vacían el cargador o rehacen el visor 3D |
| `descarga`, `resultado`, `descarga_en_curso`, `nombre_zip` | Pantalla de descarga |
| `_base_cuenca`, `_mapa_version`, `_mapa_en_run_anterior` | Guardia del mapa 2D (ver [Mapa 2D](#mapa-2d)) |
| `orbita`, `saltos`, `_intro_*`, `_orbita_firma`, `_vista_prev`, `_sel_prev`, `_orbitar` | Cámara y secuencia de entrada del 3D |
| `_prev_sel`, `_dudosas_codigos` | Sincronización de la selección entre mapa, lista, gráfica y 3D |

## Sistema visual: cómo cambiar la estética

Todo lo visual de la app sale de `modules/estilo.py`. Este es el mapa del archivo, en orden:

| Sección | Qué es | ¿Se toca al cambiar la estética? |
|---|---|---|
| `FUENTE`, `ATRIB_*`, `CREDITOS_MAPAS` | Fuente de los datos y créditos (textos legales) | No |
| `PALETAS` | Colores para lo que no lee CSS: gráficas de Altair y ficha emergente del 3D | **Sí** |
| `TEMAS`, `CONTRASTES` | Opciones del menú Apariencia | No |
| `MOVIL`, `BAJO` | Puntos de quiebre (celular, pantalla baja). `MOVIL` lo usa también el guion | Con cuidado |
| `TOKENS`, `TOKENS_ALTO` | **Tokens de color y material** para claro, oscuro y alto contraste | **Sí** |
| `VIDRIO_CLARO`, `VIDRIO_REGULAR` | Qué superficies llevan cada material | Solo para agregar o quitar superficies |
| `CSS` | Estilos base: medidas (`:root`), material, composición de cada zona, componentes, pantalla de descarga | **Sí** |
| `CSS_MEDIO`, `CSS_MOVIL`, `CSS_ESTRECHO`, `CSS_BAJO` | Ajustes por tamaño: 761–1100 px, ≤ 760 px, ≤ 380 px, alto ≤ 560 px | **Sí** |
| `CSS_ALTO`, `CSS_LITE`, `CSS_MOVIMIENTO`, `CSS_FORZADOS` | Alto contraste, modo Lite, movimiento reducido y colores forzados | **Sí** |
| `aplicar()`, `_tokens_css()`, `_vidrio()` | Arman y ordenan todo el CSS | No |
| `ICONOS` | Iconos SVG de línea (heredan el color del texto) y el logo | **Sí** |
| `marca()`, `control_tema()`, `pestanas()`, `paso()`, `opciones_cuenca()`, `estado_accion()`, `botones_inicio()`, `leyenda_*()`, `controles_camara()`, `pie()`, `aviso_legal()`, `barra_pixel()` | Piezas HTML: definen la estructura y las clases de cada pieza | Solo sus clases decorativas; no los `data-y2k-*` ni la estructura |
| `_UI` (dentro, `CSS_IFRAME`) | Guion de la interfaz del navegador; `CSS_IFRAME` es el estilo de los controles de Leaflet dentro de su iframe | Solo `CSS_IFRAME` |

### Pasos para cambiar la estética

1. **Colores y materiales**: edita `TOKENS` (claro y oscuro) y `TOKENS_ALTO` (alto contraste). Cada token es una variable CSS (`--y2k-…` o `--lg-…`); ningún componente debería tener colores propios.
2. **Medidas y movimiento**: al principio de `CSS`, en `:root`: `--y2k-g` (margen entre piezas flotantes), `--y2k-panel-w` (ancho del panel), `--y2k-capsula` (alto de las cápsulas), `--y2k-r` y `--y2k-r-ctl` (radios), `--y2k-dur` y `--y2k-curva` (transiciones).
3. **Tipografía**: el `@import` de Google Fonts y la regla `font-family` al principio de `CSS` (hoy, Figtree). El manual tiene la suya.
4. **Forma de los componentes**: las reglas de `CSS` y de los bloques por tamaño. Están agrupadas por zona y comentadas (material, composición, cápsulas, panel, pasos, isla, ficha, controles, bloques de información, piezas sobre el mapa, avisos, pantalla de descarga).
5. **Colores que no son CSS**: `PALETAS` (gráficas y 3D) y `.streamlit/config.toml` (widgets de Streamlit: listas, deslizadores, fechas). Deben coincidir con los tokens.
6. **Controles de Leaflet**: `CSS_IFRAME`, dentro de `_UI`. Vive en el iframe del mapa, que no hereda las variables de la página: sus colores están escritos a mano para cada caso (clases `y2k-oscuro`, `y2k-alto`, `y2k-lite`, `y2k-bajo` que el guion pone en el `<html>` del iframe).
7. Sube la versión del guion (`_UI.replace("__V__", "…")` en `instalar_ui`) si cambiaste `_UI`, para que no siga corriendo la versión vieja en una pestaña abierta.
8. Revisa con la [lista de comprobación](#lista-de-comprobación-tras-un-cambio-estético).

### Los tokens

| Token | Uso |
|---|---|
| `y2k-bg` | Fondo de la página (se ve en la pantalla de descarga) |
| `y2k-ink`, `y2k-ink-2`, `y2k-ink-3` | Texto principal, secundario y de apoyo |
| `y2k-line`, `y2k-line-2` | Separadores y bordes suaves / marcados |
| `y2k-accent`, `y2k-accent-texto`, `y2k-accent-2`, `y2k-sobre-acento` | Botón principal, enlaces sobre vidrio, segundo color del degradado de la barra de avance, texto sobre el botón principal |
| `y2k-foco` | Contorno de foco del teclado |
| `y2k-alerta`, `y2k-alerta-borde`, `y2k-alerta-bg` | Avisos de altitud dudosa, aviso del navegador y avisos de fallo |
| `y2k-ok`, `y2k-peligro` | Paso completado; error (reservado, hoy sin uso) |
| `y2k-campo`, `y2k-campo-borde` | Campos y tarjetas dentro del vidrio (cifras, opciones, desplegables) |
| `y2k-hover`, `y2k-pista`, `y2k-lente`, `y2k-lente-sombra` | Fondo al pasar el puntero, carril de las pestañas y "lente" del elemento elegido (2D/3D, pestaña activa) |
| `lg-claro`, `lg-regular`, `lg-denso` | Tinte del vidrio claro (controles pequeños), regular (superficies con texto) y denso (sin desenfoque: Lite o navegador sin `backdrop-filter`) |
| `lg-filtro-claro`, `lg-filtro-regular` | `backdrop-filter` de cada material (desenfoque, saturación y brillo de lo que hay detrás) |
| `lg-brillo`, `lg-luz`, `lg-borde`, `lg-filo`, `lg-especular`, `lg-sombra` | Reflejo superior, canto de luz, borde inferior, filo exterior, brillo que sigue al puntero y sombra de profundidad |
| `y2k-aurora-1…3` | Halos del fondo de la pantalla de descarga |
| `y2k-mapa-fondo`, `y2k-cielo` | Fondo mientras carga el mapa 2D; cielo detrás del relieve 3D |
| `y2k-tono`, `y2k-alto` | No son colores: el guion los lee para saber el tono (claro/oscuro) y si hay alto contraste |

Los textos se calcularon para cumplir **AA (4,5:1)** sobre el vidrio ya compuesto con el peor fondo posible (negro bajo el vidrio claro, blanco bajo el oscuro) y se midieron sobre el mapa. Si bajas la opacidad de `lg-claro`/`lg-regular` o aclaras `y2k-ink-3`, vuelve a medir.

### Colores que viven fuera de `estilo.py`

Son colores **de datos o de mapa**, no de la interfaz; cambiarlos cambia el significado visual de los datos, así que van aparte:

| Qué | Dónde |
|---|---|
| Clases de cobertura (verde, amarillo, naranja, rojo) | `calidad.CLASES_CALIDAD` (los usan el mapa, el 3D, la gráfica y la leyenda) |
| Cuenca, buffer, pines, ficha emergente del 2D | `map_view.py` (`AZUL`, `NARANJA`, `GRIS`, `TINTA_2`, `ALERTA`…) |
| Cuenca, buffer, pines, haces y fantasmas del 3D; rampa de la textura Altura | `terreno.py` (`construir_deck`, `RAMPA_ALTURA`, `_ORBITA`) |
| Colores de las líneas y pines de la leyenda | `estilo.leyenda_estaciones` (deben coincidir con los dos anteriores) |
| Escáner del mapa 2D | `escaner.py` (`COLORES`) y `scan_overlay.js` |
| Escena pixel art de la descarga y consola | `escena_descarga.py`; `.y2k-consola` en `estilo.CSS` |
| Intro satelital | `static/intro_satelital/` (tiene su propia estética) |
| Aviso del navegador del 3D | `terreno.AVISO_NAVEGADOR` trae estilos en línea, pero `.y2k-aviso3d` en `estilo.CSS` los reemplaza |

### El contrato: lo que no hay que tocar al cambiar la estética

Estos nombres unen la estructura (Python), la estética (CSS) y el guion del navegador. Si cambias uno, hay que cambiarlo en todos los lugares que lo usan.

**Claves de contenedores** (producen la clase `.st-key-<clave>`): `y2k_marca`, `y2k_acciones`, `y2k_modo`, `y2k_tex3d`, `y2k_panel`, `y2k_panel_cab`, `y2k_consulta`, `y2k_resumen`, `y2k_subida`, `y2k_dock`, `y2k_dock_fila`, `y2k_ficha`, `y2k_escenario`, `y2k_mapa2d`, `y2k_visor3d`, `y2k_descarga`, `y2k_card_*`, `alerta_altura`, `alerta_ficha` y los invisibles (`y2k_guiones`, `y2k_hipso`, `y2k_velo`, `y2k_ocultos`, `y2k_precal`, `y2k_orbita`, `y2k_escaner`).

**Claves de widgets que usan el CSS o los guiones**: `vista` (también `static/intro_satelital/player.js` y `terreno.css_boton_3d_espera`), `textura`, `escala_altura`, `btn_lite`, `iniciar_descarga`, `y2k_lite_reintentar`, `y2k_reintentar3d`, `y2k_pasar2d`.

**Atributos de las piezas HTML** (los pone `estilo.py`, los lee el guion):

| Atributo | Elemento | Qué hace al pulsarlo |
|---|---|---|
| `data-y2k-panel-btn` | Botón de la marca | Oculta o muestra el panel |
| `data-y2k-tab-btn` (`consulta` o `resumen`) | Pestañas | Cambia de pestaña (también con flechas) |
| `data-y2k-asa`, `data-y2k-hoja-max` | Asa y botón de la hoja (celular) | Cambian la altura de la hoja (también arrastre y flechas) |
| `data-y2k-dibujar` | «Dibujar» | Activa la herramienta de rectángulo de Leaflet |
| `data-y2k-area` | «Usar el área visible» | Crea la cuenca con la zona visible (`aria-disabled` hasta el zoom 10) |
| `data-y2k-subir` | «Subir archivo» | Abre Consulta y el desplegable `y2k_subida` |
| `data-y2k-ver` (`consulta` o `resumen`) | Enlaces de la isla | Abren esa pestaña |
| `data-y2k-cam` (`acercar`, `alejar`, `izq`, `der`, `subir`, `bajar`, `norte`) | Botones de cámara 3D | Mueven la cámara |

**Clases que el guion busca**: `.y2k-leyenda`, `.y2k-camara`, `.y2k-camara-estado`, `.y2k-atrib3d`, `.y2k-dialogo` (la crea el guion) y `.lg-claro` / `.lg-regular` (material de las piezas HTML; el brillo especular las reconoce).

**Clases de composición** (las usa el CSS para colocar las piezas): `.y2k-sobre` (pieza HTML sobre el mapa: su contenedor de Streamlit se vuelve transparente a los clics y se estira al tamaño del mapa) y `.y2k-pantalla[data-p]` (marca la pantalla actual para esconder lo fijo del mapa al pasar a la descarga).

**Estado en `<html>`**: el guion de la interfaz escribe `data-y2k-panel` (`abierto`/`cerrado`), `data-y2k-hoja` (`min`/`media`/`max`) y `data-y2k-tab` (`consulta`/`resumen`). El precalentamiento de la intro escribe `data-y2k-listo` (mientras no coincida con la cuenca, el botón 3D queda gris). El visor 3D lleva `data-mostrar="<turno>"` durante la secuencia de entrada.

**Variables CSS que escribe el guion** (en CSS solo se les da un valor inicial): `--y2k-ov-top`, `--y2k-ov-izq`, `--y2k-ov-der`, `--y2k-ov-abajo` (la zona libre del mapa), `--y2k-ley-abajo`, `--y2k-ley-izq`, `--y2k-atrib-abajo`, `--y2k-cam-top`, `--y2k-ficha-top`, `--y2k-dock-h`, y `--mx`/`--my` en cada vidrio (brillo especular). En el iframe de Leaflet: `--tl-top`, `--tl-izq`, `--tr-top`, `--tr-der`, `--bl-abajo`, `--bl-izq`, `--br-abajo`, `--br-der`.

**Variables CSS que el guion lee**: `--y2k-lite`, `--y2k-tono`, `--y2k-alto`.

**Almacenamiento del navegador**: `localStorage` `y2k_panel`, `y2k_tab`, `y2k_leyenda` (y `y2k_sat_*` de la intro); `sessionStorage` `y2k_aviso3d_cerrado`.

### Lista de comprobación tras un cambio estético

- Claro, oscuro y alto contraste; colores forzados (Windows); con y sin modo Lite; con movimiento reducido.
- Escritorio (1440 y 1024 px), celular vertical (390 px) y horizontal (844 × 390).
- 2D y 3D, con panel abierto y cerrado, con ficha, con la hoja del celular en sus tres alturas, y la pantalla de descarga.
- Contraste AA de los textos sobre el mapa (satélite y calles), no sobre un fondo liso.
- Que el vidrio siga dejando ver el mapa (si queda opaco, ya no es vidrio) y que en Lite quede legible sin desenfoque.
- Que ningún control de Leaflet ni la leyenda queden debajo del panel, la isla o la ficha.

## Guion de la interfaz del navegador

`estilo._UI` se inyecta una vez en la página principal (`estilo.instalar_ui`, dentro de `y2k_guiones`) y sobrevive a las recargas de Streamlit. Se repasa cada 700 ms y en cada cambio del DOM. Hace:

- **Panel, hoja y pestañas** sin recargar la página (atributos en `<html>`, elecciones en `localStorage`); `role="tab"`/`tabpanel`, `aria-expanded` y `aria-selected`. La hoja del celular se arrastra solo desde el asa (no compite con mover el mapa).
- **Reparto del espacio** (`distribuir`): mide las piezas flotantes y calcula la zona libre del mapa; mueve los controles de Leaflet (por esquina), la leyenda (encima de la escala y al lado de la barra de herramientas si no cabe debajo), la atribución y la cámara 3D. También encuadra la cuenca recién montada en la zona libre.
- **Mapa 2D**: inyecta `CSS_IFRAME` (vidrio de los controles), traduce Leaflet.draw al español, pone nombres accesibles a sus botones, maneja «Dibujar» y «Usar el área visible» y vigila las teselas que fallan.
- **3D**: botones de cámara (busca el `deck` por dentro de React) y vigilancia de WebGL, red y carga lenta.
- **Varios**: traduce el cargador de archivos, quita del nombre accesible el texto de los iconos de Streamlit y mueve el brillo especular con el puntero.

## Temas, contraste, modo Lite y movimiento

- **Tema** (*Sistema / Claro / Oscuro*) y **contraste** (*Sistema / Normal / Alto*) son independientes. "Sistema" se resuelve con `prefers-color-scheme` y `prefers-contrast` en media queries (sin destello). El alto contraste usa superficies opacas y bordes nítidos en el tono vigente: no es el modo oscuro. La elección viaja en la dirección (`?tema=`, `?contraste=`). Streamlit no deja cambiar su tema desde Python: `_SINCRONIZAR_TEMA` pulsa sin que se vea su menú (oculto).
- Con **colores forzados** (`forced-colors`) se respetan los colores del sistema y solo se reponen bordes y señales que el navegador quita.
- **Modo Lite** (botón "Lite", `?lite=1`): mismos datos, controles y funciones con menos coste gráfico. Agrega `CSS_LITE` (sin desenfoque, brillos ni transiciones: variante de baja transparencia) y usa un 3D liviano (menos detalle de malla, caché menor, 1 píxel de dibujo por píxel CSS), sin intro satelital, sin secuencia de entrada ni vuelta de cámara (la cámara queda de una vez en el encuadre final), escáner 2D sin rejilla ni destellos y escena de descarga a 5 cuadros/s. Los guiones leen Lite en el navegador (variable `--y2k-lite`), así activarlo no mueve la cámara ni repite animaciones.
- **Movimiento reducido** es independiente de Lite: quita transiciones y el brillo que sigue al puntero, pero conserva el vidrio.
- Orden del CSS (`aplicar`): base → bloques por tamaño → tokens del tema → alto contraste → Lite → movimiento reducido → colores forzados.

## Avisos de fallo

Nunca cambian de modo por su cuenta; ofrecen elegir:

- Pérdida del contexto gráfico WebGL del 3D ("Fallo gráfico"): *Activar Lite y reintentar*, *Seguir intentando*, *Ver en 2D*.
- Teselas del 3D o del mapa base 2D que fallan una y otra vez ("Problema de red"; en 3D se cuenta por tipo: relieve o imagen).
- Relieve que no avanza en 40 s sin errores claros ("Carga lenta").

Reintentar rehace el visor 3D y repone la cámara y la selección; en 2D vuelve a pedir las teselas sin mover el mapa. Los textos no afirman falta de memoria gráfica cuando solo falló una descarga.

## Mapa 2D

- Solo se puede dibujar un **rectángulo** (con lápiz para mover sus esquinas y papelera para borrarlo). Un rectángulo nuevo reemplaza al anterior; "Usar el área visible" crea uno igual con la zona que se ve (`map.fire("draw:created")`), y así se puede marcar la cuenca solo con el teclado (foco en el mapa, flechas y +/−). La cuenca subida desde archivo puede tener cualquier forma. Un clic en la cuenca no abre la alerta del navegador con su GeoJSON (`show_geometry_on_click=False`).
- Al soltar (o editar) el rectángulo corre un **escáner** sobre él mientras el servidor calcula las estaciones; al terminar se desvanece, muestra "N estaciones encontradas" y los pines aparecen de norte a sur con un pequeño rebote. Mientras corre, el mapa no se mueve ni hace zoom; la barra de dibujo sigue activa y dibujar otra vez reinicia el escáner. Tope de 30 s por si algo falla; con `prefers-reduced-motion` no corre y en modo Lite se dibuja sin rejilla ni destellos y los pines aparecen sin animación.
- Aún no hay animación para la cuenca subida desde archivo (el mapa todavía no existe mientras se calcula).
- Sin cuenca, el mapa muestra el catálogo nacional agrupado (`FastMarkerCluster`) para ubicarse.
- La lista de parámetros del IDEAM se pide por detrás al arrancar el servidor (`app._iniciar_precarga_servidor`); mientras llega, el mapa ya se puede usar y Consulta avisa que la lista está cargando (un fragmento de Streamlit recarga la página una vez cuando termina).

**Contratos que no hay que romper** (si cambias `app.py`, `map_view.py` o `escaner.py`):

1. **El mapa base no debe cambiar al dibujar.** `st_folium` identifica el componente por un hash del mapa base; si cambia, Streamlit destruye el mapa y lo crea de nuevo (pantalla en blanco, salto de zoom, y se pierde el escáner). Por eso `mapa_base` solo recibe la cuenca cuando el mapa se monta de cero (archivo, volver del 3D, "Borrar la cuenca"). La guardia está en `app.py`: `ss._mapa_en_run_anterior`, `ss._base_cuenca` y `ss._mapa_version`. Las estaciones y el buffer van aparte, en `feature_group_to_add`, que se actualiza sin reconstruir el mapa.
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
| `player.js` | Reproductor: capa que tapa el mapa, interfaz (HUD SVG), reloj, panel de ajustes temporal, precalentamiento, arranque en el clic y encendido |
| `mosaico.js` | Primer plano con mosaico de satélite (Esri) de la cuenca; si falla, `satimg.js` pinta un terreno de respaldo |

**Flujo.**
1. Al **confirmar la cuenca** (`app.py`, tras `rango = ...`) se precalienta por detrás: se carga el reproductor, se arma el mosaico y se bajan d3/topojson/mapa mundial. No se crea WebGL. El botón **3D queda gris** hasta que `document.documentElement.dataset.y2kListo` iguala la clave de la cuenca.
2. Al pulsar 3D la animación **arranca en el clic**, sobre el escenario del mapa (Streamlit tarda 2–3 s en dibujar el visor). Cuando el visor llega, el guion `_INTRO_SATELITAL` la **adopta** (la mueve dentro) o, si no hubo arranque temprano, la inicia él.
3. El guion `_ORBITA` esconde las capas de deck.gl, espera a que termine la intro (`window.__y2kIntroSatFin == turno`) y entonces corre la secuencia de entrada.
4. La intro solo corre una vez por cuenca y buffer (igual que la secuencia). No corre en celulares, en modo Lite ni con `prefers-reduced-motion`. Si la intro falla al cargar (por ejemplo, sin acceso a esm.sh), el visor 3D no se queda tapado: la capa de la intro no se vuelve a poner.

**Interfaz (HUD) de la intro.** Se dibuja en SVG dentro de `hudSvg` (`player.js`) y solo muestra datos con sentido; no hay botones de zoom ni escalas falsas.
- **Altitud** (km) en cuenta regresiva durante el descenso; transmite la velocidad, por eso no hay medidor de km/s.
- **"Calculando trayectoria"** mientras la cámara se acerca; pasa a "Lista" cuando el objetivo queda fijado.
- **Lista "Preparando lanzamiento"** con tres pasos que se calibran en orden, y debajo las barras **ÁREA** y **BUFFER** con su porcentaje. Con todo cargado se dispara.
- **"Estaciones lanzadas n/N"** usa el total real de estaciones (la intro solo dibuja hasta 250 puntos, pero el contador usa `n`, el total que manda `_datos_satelite`).
- **Sin buffer:** las dos barras se cargan juntas y, al disparar, se apagan la barra y el cañón naranja del buffer (`setBuffer` en `satellite-scene.js`). El estado `buffer` viaja desde `app.py` (`precalentar_satelite` e `intro_satelital`), así que cambiarlo repite la intro.
- Los textos de ambientación (nombre del satélite, "enlace activo", "objetivo fijado") son decoración y no representan datos.
- El botón «Saltar animación» se acomoda con CSS (`.y2k-sat > button` en `estilo.CSS`) para no quedar debajo de la isla de acción.

**Cosas que no hay que romper.**
- Un solo contexto WebGL reutilizado: crear y destruir contextos (o `forceContextLoss`) termina en "context loss and was blocked" de Chrome. `destroy()` solo libera geometrías, texturas y buffers.
- No mandar las capas de deck.gl escondidas desde Python: cualquier re-render de React las repone y "se borra todo" al terminar. Se tapa el visor con CSS y las esconde el guion (con una guardia que las vuelve a esconder).
- `TUNE` en `satellite-scene.js` guarda los valores por defecto; el panel los cambia en vivo y los recuerda en `localStorage` (prefijo `y2k_sat_`).
- Tras editar los archivos de la intro hay que **recargar la página del navegador** (F5, mejor Ctrl + F5): el reproductor se carga una sola vez por página y, si no se recarga, sigue corriendo la versión vieja aunque el archivo ya cambió. El parámetro `?v=` de las direcciones cambia con la fecha de los archivos.

**Temporal (quitar antes de presentar):** `PANEL_SATELITE = True` en `terreno.py` (panel "⚙ Ajustes": pausa, tiempo, cámara final, láseres, cápsulas, con el segundo en que se nota cada ajuste y un botón "ir") y el desplegable "Ajustes de la animación 3D (temporal)" de la pestaña Resumen (botón "Repetir animación" y altura de salida de los láseres) en `app.py`.

## Textura "Altura" del 3D

Tercera textura (junto a Satélite y Topográfico): el relieve se colorea por altitud (verdes abajo, naranjas y rojos arriba) con sombreado de ladera. Hay dos escalas: **Rango de la zona** (mínimo y máximo de la cuenca con buffer) y **Rango de Colombia** (0–5.730 m, más pixelada para ahorrar memoria). Un guion (`_HIPSOMETRICO`) intercepta `window.fetch` y devuelve, para las imágenes con la marca `y2k_hipso`, el tile de elevación coloreado. La leyenda sale de `terreno.leyenda_altura()` dentro de `estilo.leyenda_altura()`.

## Cómo probar cambios

- **Lógica y flujo:** `streamlit.testing.v1.AppTest` recorre las pantallas sin navegador (no ejecuta JavaScript). La red bloquea a veces el IDEAM: conviene simular `obtener_catalogo_parametros`, `obtener_series_disponibles` y `procesar_descargas`.
- **Lo visual (3D, escáner, vidrio):** abrir la app en un navegador sin ventana (Chrome o Edge, por ejemplo con Playwright) y sacar capturas. Para el mapa 2D hay que probar con **ratón real** (eventos de ratón del navegador): disparar eventos de Leaflet a mano no detecta, por ejemplo, un canvas que intercepta los clics. Al correr un script de prueba aparte con `streamlit run`, el servidor no recarga los módulos del proyecto: reinícialo tras cambiar `modules/`.
- **Contraste:** medirlo sobre píxeles reales (captura de cada texto: fondo = mediana de la caja, tinta = el píxel más alejado), sobre el mapa y con un fondo negro o blanco bajo el vidrio.
- Conviene probar con una cuenca grande, con muchas estaciones, con el modo Lite, en un celular, con los tres temas y con movimiento reducido (Lite y movimiento reducido por separado y juntos).
- **Trampas de Streamlit:** `st.html` quita los SVG en línea (por eso el HTML propio va con `estilo.md`, que usa `st.markdown`); un `<style>` cuyo texto contenga `<` seguido de una letra (aunque sea en un comentario CSS) lo descarta el sanitizador entero; los contenedores horizontales traen un margen negativo (las cápsulas lo anulan); Streamlit pinta los captions al 60 % de opacidad (el CSS lo devuelve a 1); y al cambiar de pantalla deja un momento los elementos viejos, por eso el CSS esconde lo fijo del mapa cuando ya hay una cápsula de marca de la pantalla de descarga (`.y2k-pantalla[data-p]` + `data-stale`).

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

La aplicación muestra estos créditos al final del panel Consulta y, más cortos, en el borde de cada mapa.
