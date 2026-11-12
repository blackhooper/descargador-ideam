# Arquitectura del Descargador IDEAM

Cómo está organizada la app por dentro. La guía de uso e instalación está en el [README](../README.md) y el sistema visual en [Estilo](ESTILO.md).

## Cómo está organizado

### Las tres capas

El código está separado para que se pueda cambiar **cómo se ve** sin tocar **qué hace** ni **dónde va cada cosa**:

| Capa | Qué decide | Dónde está |
|---|---|---|
| **Datos y lógica** | Consultas al IDEAM, catálogo, cobertura, buffer, relieve, ZIP. No sabe nada de la interfaz. | `modules/ideam_downloader.py`, `ideam_parameters.py`, `ideam_catalog.py`, `calidad.py`, `geo_input.py`, `geo_utils.py`, la parte de cálculo de `terreno.py` |
| **Estructura de la interfaz** | Qué pantallas hay, qué contiene cada zona, en qué orden, con qué textos y qué pasa al pulsar cada cosa. | `app.py`, `modules/panel_estadisticas.py`, `modules/map_view.py`, `terreno.construir_deck`, y las funciones de piezas de `modules/estilo.py` (las que dibujan HTML: `cabecera_inicio`, `seccion`, `kpis`, `herramientas_2d`, `recibo`…) |
| **Estética** | Colores, materiales, tipografía, medidas, radios, sombras, animaciones, iconos, temas y modo Lite. | `modules/estilo.py` (tokens, bloques CSS e iconos) y `.streamlit/config.toml` (colores de los widgets de Streamlit) |

La estructura y la estética se conectan solo por **nombres**: las claves de los contenedores de Streamlit (`key="y2k_panel"` produce la clase CSS `.st-key-y2k_panel`), las clases de las piezas HTML propias (`.y2k-…`) y algunos atributos `data-y2k-…`. Mientras esos nombres no cambien (ver [el contrato](ESTILO.md#el-contrato-lo-que-no-hay-que-tocar-al-cambiar-la-estética)), se puede rehacer toda la estética editando solo `estilo.py`.

### Archivos

| Archivo | Capa | Para qué sirve |
|---|---|---|
| `app.py` | Estructura | Las tres pantallas (Parámetros, Mapa y Exportación), los huecos fijos de cada zona, las cargas por detrás, el estado de sesión y la cola de descarga |
| `modules/trabajo.py` | Lógica | La descarga como trabajo en su propio hilo: turno, avance, detener, ZIP parcial y registro para retomarla tras una recarga |
| `modules/logica.py` | Lógica | Lo que `app.py` calcula sin dibujar: periodo y atajos, encuadre del mapa, tabla de completitud, variantes del ZIP. No toca Streamlit, para poder probarlo |
| `modules/idioma.py` | Idioma | `tr()` y el diccionario español → inglés de la interfaz (y de los textos del guion del navegador) |
| `modules/estilo.py` | Estética (+ piezas) | Tokens de tema, materiales de vidrio, CSS de toda la app, iconos, menú de Ajustes, piezas HTML (tarjeta de Parámetros, secciones y cifras del panel, cápsula de herramientas, leyendas, avance, recibo) y el guion de la interfaz del navegador |
| `modules/recursos/` | Estética | Hojas de estilo (`base.css` y una por tamaño o modo) y guiones del navegador (`ui.js`, `sincronizar_tema.html`) que `estilo.py` lee al arrancar |
| `modules/panel_estadisticas.py` | Estructura | Tablero de calidad del panel (cifras, altitud dudosa, lista con casillas) y ficha de la estación seleccionada |
| `modules/map_view.py` | Estructura | Mapa 2D (Leaflet vía `streamlit-folium`): capas base, herramienta de dibujo (oculta: la maneja la cápsula de herramientas), pines (también los excluidos) y fichas emergentes |
| `modules/terreno.py` | Lógica + estructura | Vista 3D: relieve, textura por altura, pines, cámara, secuencia de entrada y guiones de la intro satelital |
| `modules/escaner.py`, `modules/scan_overlay.js` | Estructura | Escáner del mapa 2D: animación mientras se calculan las estaciones y aparición de los pines en orden |
| `modules/ideam_downloader.py` | Lógica | Token, consultas por bloques de años (`bloques_de`), tabla de la serie especial (`obtener_series_calculo`), fusión de los Excel, cupos y turnos, `CITACION.txt` |
| `modules/ideam_parameters.py` | Lógica | Catálogo de la serie estándar y la especial como en el portal (`obtener_catalogo_parametros`, `variables_de`, `parametros_de`, `frecuencias_especiales`), límites de años por frecuencia y de la multianual (`periodo_excedido`), filtro por ubicación (`departamentos_de`, `municipios_de`, `estaciones_de`, `filtro_ubicacion`), cantidad probable |
| `modules/ideam_catalog.py` | Lógica | Catálogo de estaciones (caché en `data/ideam_catalogo_completo.geojson`), una fila por estación: si el IDEAM repite un `idestacion`, queda la de modificación más reciente (`_quitar_duplicados`) |
| `modules/guion.py` | Estructura | `inyectar(html)`: el único punto por donde entran los guiones de la página (iframe de altura 0). Con la variable de entorno `Y2K_IFRAME=1` usa `st.iframe` en lugar de `components.html`, para probar la migración |
| `modules/calidad.py` | Lógica | Clases de cobertura (alta ≥ 70 %, media ≥ 50 %, baja ≥ 25 %, crítica) y sus colores |
| `modules/geo_input.py`, `geo_utils.py` | Lógica | Lectura de archivos, buffer y filtro espacial |
| `static/intro_satelital/` | Estructura | Intro satelital (del mapa 2D al 3D): escena Three.js, reproductor, mosaico de satélite |
| `static/manual.html` | Documento aparte | Manual de usuario, servido en `app/static/manual.html` (tiene su propio CSS) |
| `.streamlit/config.toml` | Estética | Colores de los widgets de Streamlit en claro y oscuro (deben coincidir con los tokens) |

## Pantallas

La app tiene **tres pantallas** (`ss.paso`): `"parametros"`, `"mapa"` y `"descarga"` (Exportación). Las tres comparten el **mismo mapa 2D**, que va siempre en el mismo lugar del árbol de Streamlit (`y2k_escenario`): por eso no se vuelve a cargar al cambiar de pantalla, y en Parámetros se carga por detrás mientras la persona elige qué descargar. En Parámetros y Exportación el mapa queda velado y desenfocado (`.st-key-y2k_escenario::after`) y sin foco ni clics (`inert`).

Arriba a la derecha, en las tres, va el menú **Ajustes** (`y2k_ajustes`, `estilo.ajustes`, ícono ◐ de claro/oscuro): tema claro/oscuro, alto contraste, modo Lite y manual. Con Lite activo, junto al botón aparece la marca «Lite». Durante una descarga el menú se bloquea (cambiar algo recargaría la página y la detendría).

Junto a Ajustes va el botón de idioma (`y2k_idioma`): **EN** muestra la app en inglés y **ES** la devuelve al español. El idioma viaja en la dirección (`?lang=en`), así que un enlace con ese parámetro abre la app directamente en inglés. Los textos pasan por `tr()` de `modules/idioma.py`: en español salen tal cual y en inglés se buscan en su diccionario `EN` (un texto nuevo sin traducción sale en español, sin romper nada). Los nombres que vienen del IDEAM (variables, parámetros, departamentos, estaciones) y el manual no se traducen.

**Sin textos de carga.** Ninguna pantalla dice «Cargando…»: la única señal de que la lista de variables del IDEAM está lista es el punto de la etiqueta «Variable», que se enciende en azul. El botón principal es siempre azul: si se pulsa antes de que todo cargó, no avanza y da dos destellos rojos. En el mapa, mientras se evalúa el área, el escáner la recorre.

**Avisos discretos** (`estilo.aviso`): una línea con su icono y, si hay detalle, «Ver más» (`<details>`). Se usan para fechas inválidas, periodo demasiado largo para Excel o para una serie multianual, series de alta frecuencia y los estados sin datos del mapa. Los errores llevan `role="alert"`.

**Botones principales de vidrio líquido azul**: tinte del acento que deja ver un poco del fondo desenfocado, brillo superior, cáustica abajo y canto de luz (tokens `y2k-boton-tinte`, `y2k-boton-brillo`, `y2k-boton-caustica`, `y2k-boton-canto`). En alto contraste son opacos y sin brillos; en Lite, sin desenfoque. El texto queda por encima de 6,5:1 en claro y oscuro.

**Esquina del botón de Streamlit.** En Streamlit Community Cloud, su botón («Manage app», o su logo y la foto de quien la ve) va abajo a la derecha, fuera de la app, y no se puede mover. `app._en_streamlit_cloud()` lo detecta (`*.streamlit.app` o `/mount/src`) y `estilo.aplicar(sello=True)` reserva esa esquina (`--y2k-sello`): «Preparar descarga», la barra del celular y las tarjetas del celular quedan por encima. `Y2K_SELLO=1` lo simula en otro servidor.

**Vidrio sin desplazamiento.** Ninguna superficie de vidrio se desplaza: las tarjetas de Parámetros y Exportación, la ficha y el panel tienen un cuerpo interior que se desplaza (`y2k_inicio_cuerpo`, `y2k_exportar_cuerpo`, `y2k_ficha_cuerpo`, `y2k_cuerpo`). Así el brillo que sigue al puntero (va en el fondo del propio vidrio) queda siempre bajo el puntero y el canto de luz no se desfasa. El cuerpo ocupa toda la tarjeta, con el mismo margen interior arriba, abajo y a los lados, y el contenido se desvanece al llegar al borde (`mask-image`, `--y2k-fundido`) en lugar de cortarse en una franja.

**Barras de desplazamiento como las del celular.** Con ratón, las barras del panel, las tarjetas, la ficha, los menús, los desplegables y la lista de estaciones son transparentes en reposo y se ven mientras se desplaza o con el puntero sobre la barra (el guion marca `[data-y2k-desplaza]` en el elemento y lo quita al quedarse quieto). En alto contraste y con colores forzados se ven siempre.

**Huecos fijos.** Justo después del escenario, `app.py` crea siempre, en este orden, los contenedores de las tres pantallas (vacíos los que no se usan): `y2k_inicio`, `y2k_panel`, `y2k_abrir`, `y2k_herr`, `y2k_filtro`, `y2k_dock`, `y2k_ficha`, `y2k_exportar` y `y2k_ocultos`. Así cada uno conserva su lugar: al cambiar de pantalla, Streamlit deja un momento los elementos viejos hasta terminar la corrida (en Exportación, toda la descarga), y como siguen dentro de su propio contenedor, el CSS los oculta enseguida por su clave. Lo condicional (`y2k_precal`, el diálogo de subida) va después de todos.

### 1. Parámetros (`pantalla_parametros` en `app.py`)

```text
┌──────────────────────────────────────────────────────────────────────┐
│ mapa 2D velado (y2k_escenario)                         ╭ y2k_ajustes ╮
│              ╭ y2k_inicio (tarjeta centrada) ─────────╮ ╰─────────────╯
│              │ IDEAM · Consulta y descarga de datos…   │             │
│              │ Serie de tiempo y frecuencia   [serie]  │             │
│              │   Estándar │ Especial                   │             │
│              │ Frecuencia (solo Especial) [frec_especial]            │
│              │ Variable ●   [var_est / var_esp_<frecuencia>]         │
│              │ Parámetro    [par_est_<variable> /                    │
│              │               par_esp_<frecuencia>_<variable>]        │
│              │ Desde [f_ini]   Hasta [f_fin]           │  ● = punto  │
│              │ ▸ Filtrar por ubicación · opcional      │  de estado  │
│              │   [y2k_ubicacion: ubic_dep, ubic_mun,   │             │
│              │    ubic_est] (cerrado por defecto)      │             │
│              │ [ Seleccionar área en el mapa → ] ir_mapa             │
│              │   (con filtro: «Ver N estaciones en el mapa»)         │
│              │ 1 Establecer parámetros · 2 Delimitar el área de      │
│              │   análisis · 3 Preparar la descarga                   │
│              │ condiciones de uso                      │             │
│              ╰─────────────────────────────────────────╯             │
└──────────────────────────────────────────────────────────────────────┘
```

En el celular la tarjeta flota abajo, con margen a los lados; Desde y Hasta siguen en una fila (`y2k_fechas`) y los pasos muestran solo sus títulos.

- **Serie de tiempo y frecuencia** (`serie`), igual que en la página del IDEAM: **Estándar** pide la variable (`var_est`) y luego el parámetro (`par_est_<variable>`). **Especial** pide la frecuencia (`frec_especial`: Decadal o Multianual), la variable (`var_esp_<frecuencia>`) y el parámetro (`par_esp_<frecuencia>_<variable>`). Cada desplegable sale de `app._desplegable` y cada variable recuerda su parámetro. Solo se ofrecen las variables que tienen parámetros en la serie (y frecuencia) elegida. Las de alta frecuencia van en Estándar, como en la página, y muestran un aviso discreto con «Ver más»: el IDEAM las entrega de a un mes por consulta. Ver [Series estándar y especial](#series-estándar-y-especial).
- **Lista de variables** (`_iniciar_precarga_servidor`): se pide en un hilo al arrancar el servidor. Mientras carga, los desplegables (`espera_<campo>`) están en gris y no se pueden abrir, y el punto `.y2k-punto[data-estado]` respira en gris; al cargar, se enciende en azul (`listo`) y aparecen los desplegables de verdad (con búsqueda al escribir; por defecto, Precipitación y el día pluviométrico). Si falla, el punto se pone rojo y aparece **Reintentar** (`ideam_parameters.limpiar_catalogo`).
- **Textos de las listas**: los de la página. En Estándar, la descripción del parámetro (si dos se llaman igual en una variable, con la etiqueta: «… [PTPM_CON]»; si el IDEAM no trae descripción o trae «null», la etiqueta). En Especial, «descripción |cálculo [etiqueta]»; sin descripción, «etiqueta |cálculo».
- **Serie multianual**: no se puede partir en bloques, así que si el periodo pasa el límite de una consulta (`ideam_parameters.periodo_excedido`) aparece un aviso y el botón no avanza.
- **Series por detrás** (`_precargar_series`): al elegir una variable se pide en un hilo qué estaciones tienen esa serie (lo que necesita el mapa para evaluar). Compartido entre sesiones; si falló, se reintenta a los 30 s.
- **El botón es siempre azul** (nunca gris). Avanza cuando todo está listo: lista cargada, variable elegida, fechas válidas, periodo que cabe en Excel y series cargadas (Python lo marca en `.y2k-cta-listo[data-listo]`, `estilo.marca_listo`) y el mapa 2D cargado (`html[data-y2k-mapa-listo]`). Si se pulsa antes, el guion detiene el clic y le pone `.y2k-parpadeo` (dos destellos rojos); para lectores de pantalla queda `aria-disabled="true"`. `_ir_mapa` recibe además `listo` y no hace nada si no lo está (por si el guion no cargó).
- **Pasos** (`estilo.pasos(n)`, `estilo.PASOS`): Parámetros, Área y estaciones, Descarga. Van numerados en la cabecera de las tres pantallas, con el actual resaltado; en el panel del mapa y en el celular solo el paso actual muestra su nombre.
- **Atajos de periodo** (`y2k_atajos`, `app._atajo_periodo`): «Últimos 10 años», «Últimos 30 años» y «Todo» llenan Desde y Hasta.
- Un **vigía** (`_vigia`, un fragmento con `run_every=1`) revisa cada segundo lo que carga por detrás y recarga la página una vez al terminar.
- **Filtrar por ubicación** (`app._filtro_ubicacion`, `st.expander` dentro de `y2k_ubicacion`), como «Datos Estación» de la página del IDEAM: **Departamento** (`ubic_dep`, vacío por defecto; su × quita el filtro), **Municipio** (`ubic_mun`, «Todos» por defecto) y **Estaciones** (`ubic_est`, un `st.multiselect` que busca por nombre o código y muestra los años del primer y el último dato; vacío = todas). Va cerrado por defecto, para no llenar la tarjeta, y abierto si ya hay un filtro. Las listas salen de las estaciones de la serie (`obtener_series_disponibles`, ya cargadas por detrás al elegir el parámetro), así que no hay esperas: mientras no llegan, el Departamento está en gris. Si cambia la serie o el departamento, lo elegido que ya no está en la lista se olvida (`_vigente`). Con un departamento elegido, el botón dice «Ver N estaciones en el mapa». Ver [Filtro por ubicación](#filtro-por-ubicación).
- `_ir_mapa` (callback) guarda la consulta en `ss.consulta` (clave única del parámetro, fechas y `filtro`: `{"codigos", "texto"}` o `None`) y pasa a `"mapa"` antes de que corra el guion: la pantalla nueva sale en la misma recarga. Con filtro, quita el área que hubiera (y rearma el mapa, `version_mapa`, para que no quede el rectángulo) y marca `ss._encuadrar` para que el mapa 2D se encuadre en las estaciones.

#### Filtro por ubicación

Replica la sección «Datos Estación» de la página del IDEAM (atencionciudadano.ideam.gov.co). La página llena Departamento y Municipio con la tabla `SERIESTIEMPOESTACIONES_VIEW` del servicio de mapas (`MapServer/8`) y filtra en el navegador la lista de estaciones de la serie (`Reportes/ObtenerEstacionesSerieTiempo`) por `IdDepartamento`, `IdMunicipio` y nombre; la tabla muestra Código, Nombre, FechaIni, FechaFin y Cantidad probable. La app usa esa misma lista para todo: trae los mismos departamentos y municipios (mismos id) y ya está cargada. Los nombres son los de la lista («Choco», «Argelia»); la capa 8 los trae con algunas tildes más y con el departamento en los municipios homónimos («Chocó», «Argelia (Antioquia)»).

- Es otra forma de elegir las estaciones y **reemplaza al área**: el mapa muestra solo esas estaciones (`app._estaciones_del_filtro`, con `zona = "filtro"`), encuadradas (`app._encuadre`); sin rectángulo ni buffer. El 3D y el rango del relieve usan un recuadro de las estaciones con unos 2 km de margen (`app._marco`, `terreno.construir_deck(marco_gdf=…)`), que no se dibuja.
- En el panel, la sección **Estaciones elegidas** (`estilo.ubicacion_elegida`) dice de dónde son («Antioquia · Medellín · 2 estaciones») y ofrece **Quitar filtro** (botón oculto `y2k_quitar_ubicacion`, `app._quitar_filtro_mapa`: vuelve al modo área y vacía también los campos de Parámetros). Dibujar o subir un área también quita el filtro.
- La tabla con casillas y cobertura es la del panel del mapa: no se repite en la tarjeta.
- El recibo de la descarga y la ayuda de «Estaciones encontradas» dicen la ubicación en lugar de «en el área / en el buffer».

#### Series estándar y especial

Se arman con los mismos servicios que usa la página del IDEAM (`widgets/Ciudadano/Widget.js` de atencionciudadano.ideam.gov.co), comprobado contra el portal en vivo el 2026-10-09:

| | Estándar | Especial |
|---|---|---|
| Frecuencia | — | Lista fija de la página: Decadal y Multianual |
| Variable | `PortalDescargas/obtenerVariables` | La misma lista |
| Parámetro | `GestionDatos/ConsultarInformacionSeriesTiempoGD?idparametro=<variable>`, solo los que tienen `Visible = true`, en el orden del servicio | Tabla `SERIESTIEMPOCALCULO_VIEW` del servicio de mapas de DHIME (`dhime.ideam.gov.co/server/rest/services/CNE/Estaciones/MapServer/9`, pública, sin token; `ideam_downloader.obtener_series_calculo`), filtrada por frecuencia y variable y ordenada por descripción |
| Descarga | `"TipoSerie": "Estandard"`, `"Calculo": ""` | `"TipoSerie": "Decadal"` o `"Multianual"`, `"Calculo"`: `SUM`, `MAX`, `MIN`, `AVG` o `NA` |

- Cada parámetro tiene una **clave única** (`clave`): `PRECIPITACION|PTPM_CON` o `Decadal|PRECIPITACION|SUM|PTPM_CON`. La etiqueta sola no sirve: una misma etiqueta va con varios cálculos (TMX_CON decadal: AVG, MAX y MIN) y en más de una variable (TV_CAL_* en Tensión de vapor y Presión atmosférica).
- La serie especial es un cálculo sobre una **serie base** (la de la etiqueta). Como en la página, las estaciones y su cantidad probable salen de esa serie. La **decadal** trae un dato por década (36 por año: días 1, 11 y 21). La **multianual** trae siempre 36 filas: el mínimo, la media y el máximo de cada mes en todo el periodo.
- **Límite por consulta**: el de la frecuencia de la serie base (`frecuencia_base`, de `Restricciones/GestionDatos`): diaria 30 años, mensual 50, horaria 10. Si se pasa, el IDEAM responde HTTP 400 sin cuerpo. Medido: con N años de límite acepta unos días más de N años de calendario. La decadal se parte en bloques cuyos cortes caen al final de un mes (`ideam_downloader.bloques_de`), así ninguna década queda partida. La multianual va siempre en una consulta, porque partirla daría otros mínimos, medias y máximos, y por eso la pantalla de Parámetros no deja pedir más de N × 365,25 días.
- **Verificador de completitud** (`ideam_downloader.contar_datos`): al guardar cada Excel se cuentan las filas con fecha y valor (columna «Valor» del encabezado del IDEAM) y se comparan con las esperadas del periodo (`Esperados`, de la misma frecuencia que la cantidad probable). Van en `resumen_descarga.csv` como «Datos reales» y «Completitud real (%)», y la media de las guardadas, en el resumen final. Comprobado con Excel reales: 7.121 y 7.267 datos en 20 años diarios (97,5 % y 99,5 %), 180 en 5 años decadales, 36 en la multianual y 359 de 360 meses en una mensual.
- **Nivel de aprobación** (`ideam_downloader.analizar_excel`, que lee el Excel una sola vez y también cuenta los datos): cada Excel del IDEAM trae el nivel de cada dato (definitivo, en revisión o preliminar). `resumen_descarga.csv` suma las columnas «Definitivo (%)», «En revisión (%)» y «Preliminar (%)», calculadas sobre los datos que sí llegaron (vacías en las estaciones omitidas). Comprobado con un Excel real de temperatura máxima diaria de Tibaitatá de 1990 a 2023: 11.487 datos, 81,5 % definitivos, 1,8 % en revisión y 16,7 % preliminares. Prueba: `tests/test_niveles_aprobacion.py`.
- Si un cálculo no tiene datos (por ejemplo TMX_CON decadal MIN), el IDEAM devuelve un ZIP vacío; la estación queda omitida con ese motivo en `resumen_descarga.csv`.
- Si el servicio de mapas no responde, la serie Estándar sigue funcionando: la Especial queda vacía («No disponible por ahora») y se reintenta a los 5 minutos.
- **Catálogo recortado** (`ideam_catalog.COLUMNAS`): del servicio del IDEAM solo se guardan y se cargan las columnas que la app usa o que describen la estación (el servicio trae unas 40, con observaciones internas y nombres de usuario). Al cargarlo se agrega la columna `codigo` (`_con_codigo`), y `ideam_downloader.codigos_de(df)` la devuelve sin recorrer las filas.
- **Tope de estaciones** (`MAX_ESTACIONES_ZONA` en `app.py`, 1.500): por encima no se evalúa el área; el panel pide reducirla o elegir por ubicación.
- **ZIP parcial** (`procesar_descargas`, `ui["parcial"]`): si la descarga se corta con estaciones ya guardadas, el ZIP se cierra con ellas (`resumen_descarga.csv` marca las demás como «Sin descargar») y Exportación ofrece «Descargar lo guardado».
- **Variantes del ZIP** (`app._zip_final`): además del ZIP plano solo se guarda la variante elegida (carpetas, mapa de huecos o ambas).
- **`resumen_descarga.csv`**: columnas «Cobertura estimada (%)» y «Clase estimada» (antes «Cantidad probable (%)» y «Cobertura»), «Datos reales», «Completitud real (%)», niveles de aprobación, «Resultado», «Archivo» y «Detalle».
- **Nombre de cada Excel** (`ideam_downloader.nombre_excel`): `ESTACION_[código]_RÓTULO.xlsx`. El código va siempre, así dos estaciones con el mismo nombre no se pisan dentro del ZIP; si aun así coincidiera, se numera (`_(2)`).
- **Bloques alineados al mes** (`calcular_bloques` con `alinear_mes`, serie decadal): el corte retrocede al fin del mes anterior, nunca avanza, para no pasarse del límite del IDEAM.
- **Detener** (`procesar_descargas`): una señal (`threading.Event`) llega a cada hilo, que la revisa antes de pedir el siguiente bloque. Al detener o fallar no quedan consultas corriendo contra el IDEAM.
- **Carpetas**: la clase de cada Excel sale de la completitud real medida al guardarlo (`clasificar_calidad(real)`), la misma del resumen; solo si no se pudo medir se usa la cobertura estimada.
- Los Excel y el ZIP llevan el rótulo de la serie (`ideam_downloader.rotulo_serie`): `…_PTPM_CON.xlsx`, `…_PTPM_CON_Decadal_SUM.xlsx`, `…_PTPM_TT_M_Multianual.xlsx`. `CITACION.txt` indica la serie y el cálculo.
- REC VIENTO tiene filas en la tabla, pero la página no la ofrece porque no está entre las variables del portal; se omite igual.

### 2. Mapa (`pantalla_mapa` en `app.py`)

**Escritorio**

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ ╭ y2k_panel ───────────────────╮  ╭ y2k_ficha ─────────╮    ╭ y2k_ajustes ╮  │
│ │ y2k_panel_cab: Consulta  [⇤] │  │ ⌖ Estación  ▾   ✕  │    ╰─────────────╯  │
│ │ ──────────────────────────── │  ╰────────────────────╯    ╭ y2k_herr ╮     │
│ │ y2k_cuerpo (con scroll)      │                            │ ✎ Dibujo ▸│     │
│ │  ÁREA DE ESTUDIO ( ≈ 381 km²)│       y2k_escenario        │ ▤ Capas  ▸│     │
│ │  Redibujar · Ajustar · Borrar│     (mapa 2D o 3D a        │ +  −      │     │
│ │  (◎ Buffer · 2 km ▾)         │     pantalla completa)     ╰──────────╯     │
│ │  COBERTURA ESTIMADA    (‹ Precipitación)                                    │
│ │  [Encontradas][Cobertura][ZIP]                                             │
│ │  ⚠ N con altitud dudosa      │  ╭ Leyenda ●●●● ▴╮         ( Preparar desc. → )│
│ │  lista con casillas          │  ╰───────────────╯           y2k_dock_der     │
│ │  pie y créditos              │  ╭ y2k_dock_izq ──────╮                       │
│ ╰──────────────────────────────╯  │ 2D│3D · ↻         │  crédito 3D [ sello ]  │
│                                   ╰────────────────────╯                       │
└──────────────────────────────────────────────────────────────────────────────┘
```

Al llegar desde Parámetros, la consulta del escritorio **arranca cerrada** (se ve el mapa entero y el botón «Consulta» para abrirla); el guion la marca cerrada ya en el clic de «Seleccionar área en el mapa», sin parpadeo. Cerrada, el panel queda `inert` (sin foco ni clics: algunos elementos de Streamlit se fuerzan visibles y, aunque transparentes, tapaban la leyenda). En 3D la cápsula de herramientas lleva **Cámara** y **Textura del relieve**. En Streamlit Community Cloud, el crédito del relieve 3D va abajo, en la franja del botón «Manage app» y a su izquierda. En 2D, el crédito de los mapas de Leaflet va abajo, a la derecha de la píldora 2D/3D y centrado con ella (lo coloca `distribuir`: clase `y2k-credito-abajo` y variables `--cred-*` en el `<html>` del iframe); llega hasta «Preparar descarga» si comparten franja o hasta el botón de Streamlit.

**Celular (≤ 760 px de ancho)**

```text
┌───────────────────────────┐
│(⌖ Estación ▾ ✕)       ╭◐╮ │   ficha: píldora arriba, junto a la columna de Ajustes
│                       ╭✎╮ │   cápsula de herramientas bajo Ajustes
│       y2k_escenario   │▤│ │
│                       ╰─╯ │
│ ╭ y2k_panel ──────────╮   │   la consulta: tarjeta flotante con margen, de hasta
│ │ Consulta         ✕  │   │   3/4 de la pantalla; arranca cerrada. Abierta, se
│ │ área, buffer, calidad│  │   apartan herramientas, leyenda, escala y créditos
│ ╰─────────────────────╯   │   del mapa, ficha y cámara; tocar el mapa la cierra
│(≡ Consulta 2D│3D Preparar→)   barra flotante: «Consulta» abre y cierra
│                 [ sello ] │   esquina libre para el botón de Streamlit
└───────────────────────────┘
```

En **horizontal** (alto ≤ 560 px y ancho > 760 px) se usa la disposición de escritorio, más compacta (`CSS_BAJO`).

| Zona | Contenedor (`key`) | Quién la llena | Qué contiene | Material |
|---|---|---|---|---|
| Panel | `y2k_panel` | `app.pantalla_mapa` | Cabecera `y2k_panel_cab` (`estilo.cabecera_panel`: título «Consulta», plegar en escritorio y ✕ en el celular) y cuerpo `y2k_cuerpo` con desplazamiento propio | vidrio regular |
| Reabrir panel | `y2k_abrir` | `estilo.boton_abrir_panel` | Botón «Consulta» (solo se ve con el panel plegado, en escritorio) | vidrio claro |
| Herramientas | `y2k_herr` | `estilo.herramientas_2d` / `estilo.herramientas_3d` | En 2D: menús **Dibujo** (dibujar, área visible, subir, ajustar esquinas, borrar) y **Mapa base** (Satélite con nombres, el inicial; Satélite; Relieve; Calles; Satélite de noche), y zoom. En 3D: menú **Cámara**, que agrupa todos los controles de cámara (una cruceta: arriba y abajo inclinan, a los lados gira y al centro una brújula que gira con el mapa y vuelve al norte; zoom; una línea con rumbo e inclinación; y la guía de gestos, con dibujos del ratón o de los dedos según el equipo; sigue abierto entre pulsaciones), y menú **Textura del relieve** (Satélite, Topográfico, Altura y, con Altura, su escala; pulsan los ocultos `y2k_tex_<n>` y `y2k_esc_<n>`) | vidrio claro (los menús, denso) |
| Filtro | `y2k_filtro` | `app.pantalla_mapa` | Botón circular arriba a la izquierda del mapa (con un área evaluada): menú con un deslizador de rango de **cobertura del periodo** (`filtro_cob`, de 5 en 5 %). Lo que queda fuera no se ve en el mapa ni en la lista y no se descarga. Activo, muestra el rango («50–100 %») y ofrece «Quitar el filtro» | vidrio claro |
| Píldoras | `y2k_dock` (`y2k_dock_izq`, `y2k_dock_der`) | `app.pantalla_mapa` | Izquierda: en el celular, el botón **Consulta** (`estilo.boton_consulta`); el selector **2D/3D** (`vista`; en el celular, elegir uno cierra la consulta para ver el mapa) y, en 3D, **Repetir animación** (`y2k_repetir_intro`, temporal). Derecha: **Preparar descarga** (`preparar`; desactivado con la razón en la ayuda), que es la cápsula misma (sin contenedor de vidrio alrededor, del mismo alto que la de 2D/3D; en el celular, 40 px como «Consulta»), por encima de la esquina del botón de Streamlit. Si la barra no alcanza, cede espacio: hasta 400 px de ancho pierde la flecha (`CSS_ANGOSTO`) y, por debajo de unos 350 px, el texto termina en «…» (toda la cadena de envoltorios de Streamlit puede encogerse) | vidrio claro (2D/3D); vidrio azul (Preparar) |
| Ficha | `y2k_ficha` (cuerpo `y2k_ficha_cuerpo`) | `panel_estadisticas.tarjeta_seleccionada` y `estilo.ficha_pildora` | Estación elegida. Arranca **cerrada**, como una píldora con el nombre (abierta tapaba el mapa, sobre todo en 3D); al pulsarla se despliega: código, altitud, zona, cobertura, interruptor **Incluir en la descarga**, aviso de altitud dudosa (`alerta_ficha`), **Ver en 3D** y **Quitar selección**. La ✕ de la píldora quita la selección; tocar fuera la cierra; otra estación la vuelve a cerrar | vidrio regular |
| Mapa | `y2k_escenario` | `app.pantalla_mapa` | En 2D: `y2k_mapa2d` (iframe de `st_folium`), `y2k_escaner` y la leyenda. En 3D: `y2k_visor3d` (pydeck), `y2k_orbita` (guiones), leyenda, atribución y el aviso de movimiento reducido. La **leyenda** es un desplegable cerrado (el resumen muestra los cuatro colores); abierta, los colores van bajo el título «Disponibilidad estimada de datos en el periodo» | sin vidrio (es el contenido) |

**Cuerpo del panel** (`y2k_cuerpo`), en dos secciones (`estilo.seccion`):

1. **Área de estudio** (o **Estaciones elegidas**, si se eligieron por ubicación en Parámetros: ver [Filtro por ubicación](#filtro-por-ubicación)): con área, su tamaño en una cápsula (`.y2k-km`) y tres acciones compactas (`estilo.acciones_area`: Redibujar, Ajustar, Borrar); sin área, «Sin definir» (dibujar o subir el área se hace desde el menú **Dibujo** de la cápsula de herramientas, sin repetirlo en el panel). En 3D, un aviso y «Ver en 2D». Después, el **buffer** en una píldora pequeña (`app._control_buffer`, `st.popover` con clave `pop_buffer`): al pulsarla se activa o desactiva (`buf_on`) y se cambia el ancho con − y + de 0,5 en 0,5 km (`buf_km`).
2. **Cobertura estimada** (`panel_estadisticas.tablero`): a la derecha del título, la variable consultada en corto (`.y2k-chip`, solo su nombre; al pulsarla pulsa el botón oculto `chip_param` y vuelve a Parámetros). Tres cifras (`estilo.kpis`): **Estaciones encontradas** (y cuántas no tienen información), **Cobertura media del periodo** y **Tamaño del ZIP** con el tiempo aproximado («≈ 12 MB», «3 min 20 s aprox.»; `panel_estadisticas.peso_zip`: unos 17 bytes por registro probable ya comprimido más unos 33 kB por Excel de logo, estilos y encabezado; medido con descargas reales de precipitación diaria, el error quedó entre −6 % y +3 %). Debajo, la nota «La cobertura es estimada» (aviso informativo con «Ver más»: no descuenta los huecos; la completitud real se mide al descargar). Después, la línea discreta de altitud dudosa (`alerta_altura`, con la lista `tabla_dudosas` que lleva al 3D) y la **lista con casillas** (`st.dataframe` con selección `multi-row` + `single-cell`: las filas marcadas se descargan; un clic en una celda selecciona la estación y el mapa va a ella). Las excluidas se guardan en `ss.excluidas` (códigos) y en el mapa salen huecas con borde punteado. Al final, la nota de datos preliminares (una línea con «Ver más») y el pie (`estilo.pie`, con los créditos de los mapas).

Los estados sin datos (sin área, zona sin estaciones, IDEAM caído, periodo demasiado largo, ninguna estación con datos) se explican en la sección de calidad, y **Preparar descarga** queda desactivado con la razón en su ayuda. Mientras se evalúa el área no hay textos de carga: el escáner la recorre en el mapa.

**Subir un archivo** abre un diálogo (`dialogo_subida`, `st.dialog`) con el cargador `subida_<n>` y el botón `usar_subida`. Lo abre el botón oculto `y2k_subir`, que pulsa «Subir un archivo» del menú Dibujo.

**Capas (z-index):** el mapa (`y2k_escenario`) está en 0 y sus piezas (`.y2k-sobre`) en 25 dentro de él; el velo de Parámetros y Exportación en 30; la capa invisible que cierra la consulta del celular al tocar el mapa (`.y2k-cierre-hoja`) en 39; las tarjetas y el panel en 40; la ficha en 42; las píldoras en 45; las herramientas y el botón «Consulta» del escritorio en 50; Ajustes en 55; la intro satelital en 60; los avisos de fallo en 70.

### 3. Exportación (`pantalla_descarga` en `app.py`)

```text
mapa 2D velado                                              ╭ y2k_ajustes ╮
          ╭ y2k_exportar (tarjeta) ─────────────────────────────────────╮
          │ ● EXPORTACIÓN · título                                      │
          │ ┌ izquierda ───────────────────┐ ┌ derecha ───────────────┐ │
          │ │ 42 %          Faltan ≈ 1 min │ │ recibo (.y2k-recibo):  │ │
          │ │ ▓▓▓▓▓▓▓░░░░░ (.y2k-barra)    │ │ variable, periodo,     │ │
          │ │ estaciones · guardadas ·     │ │ estaciones, archivo    │ │
          │ │ omitidas                     │ │ (lista), fuente        │ │
          │ │ [Detener] / resumen + reparto│ │ condiciones de uso     │ │
          │ │ nombre del ZIP + Descargar   │ │ (.y2k-legal-bloque)    │ │
          │ │ [Volver al mapa][Nueva consulta]                      │ │
          │ └──────────────────────────────┘ └────────────────────────┘ │
          ╰─────────────────────────────────────────────────────────────╯
```

En el celular la tarjeta flota abajo, con margen, y las dos columnas van una debajo de la otra. Al terminar, antes del nombre del ZIP está **Separar en carpetas por completitud** (`carpetas`): la descarga arma siempre un ZIP plano y, si se marca, `ideam_downloader.zip_con_carpetas` lo reorganiza al momento (sin volver a descargar) y rehace `resumen_descarga.csv` con las rutas nuevas; se guarda en el resultado para no rehacerlo mientras se escribe el nombre. En el recibo, «Archivo» es una lista ordenada (`.y2k-archivo`): un Excel por estación, carpetas por completitud real (si se eligieron), `resumen_descarga.csv` y `CITACION.txt`. El aviso de datos preliminares no se repite aquí: ya está en el panel del mapa.

- **La descarga es un trabajo del servidor** (`modules/trabajo.py`, `ss.trabajo`): corre en su propio hilo, no en la corrida de Streamlit. `_preparar` (callback de «Preparar descarga») crea el `Trabajo`, lo arranca y pasa a la pantalla. Estados (`trabajo.estado`): `en_curso` → `lista`, `error` o `detenida`. La pantalla solo lo mira: el fragmento `_avance_vivo` (`run_every=1`) dibuja cada segundo el avance (`ideam_downloader.html_avance` con las cifras que deja `procesar_descargas` vía `ui["avance"]`) o el puesto en la fila, y rehace la pantalla al terminar. «Detener» activa `trabajo.detener`; lo ya guardado queda en `trabajo.parcial`. El id del trabajo viaja en la dirección (`?descarga=`): si la página se recarga (sesión nueva), `trabajo.buscar` lo encuentra y se restauran la descarga y la consulta. La pantalla manda un latido por segundo; tras 120 s sin latidos (pestaña cerrada) el trabajo se detiene solo, y los terminados se olvidan a los 15 min sin que nadie los mire.
- **Todos los botones son callbacks** (`_detener`, `_reintentar_descarga`, `_volver_mapa`, `_nueva_consulta`) que cambian el estado antes de que corra el guion. Por eso «Volver al mapa» funciona siempre (antes, tras «Detener», la siguiente corrida volvía a empezar la descarga antes de ver el botón).
- Al terminar: barra en verde con la duración, una frase con lo guardado y lo omitido y la **completitud real media** frente a la cobertura estimada (`resultado["completitud"]`), el reparto por completitud real (`estilo.resumen_final`, `panel_estadisticas.reparto_cobertura`) y la entrega (`_entrega`, un fragmento: el nombre del ZIP `nombre_zip` se aplica mientras se escribe, sin recargar la tarjeta).
- **Turnos**: como máximo 4 descargas a la vez en el servidor; si no hay cupo, un aviso dice el puesto en la fila y el tiempo estimado.
- El mapa de fondo solo se monta de cero si no hay una descarga por empezar: al cargar, el componente del mapa podría recargar la página y cortarla.

### Manual

`static/manual.html` es una página aparte, con su propio CSS. Describe la interfaz con los nombres de sus botones: si cambias textos visibles de la app, revísalo.

## Cómo se arma la página en cada corrida

Streamlit vuelve a ejecutar `app.py` de arriba abajo en cada interacción. El orden es:

1. Preferencias desde la dirección (`?tema=`, `?contraste=`, `?lite=1`) y valores por defecto del estado de sesión. Si `paso` no tiene con qué seguir (por ejemplo, mapa sin consulta), vuelve a `"parametros"`.
2. `estilo.aplicar(tema, contraste, lite, sello)`: todo el CSS de la página (`sello`: reservar la esquina del botón de Streamlit Community Cloud).
3. `estilo.guiones_globales(pantalla)`: la marca de la pantalla (`.y2k-pantalla[data-p]`), el guion de la interfaz y la sincronización del tema de Streamlit. Después, `y2k_hipso` y `y2k_velo`.
4. `estilo.ajustes()`: el menú de Ajustes (bloqueado durante una descarga).
5. Credenciales y catálogo de estaciones.
6. **El escenario** (`y2k_escenario`) y **los huecos fijos** de las tres pantallas (ver [Pantallas](#pantallas)). No pongas nada condicional antes de ellos: cambiaría su lugar y el mapa se volvería a cargar.
7. Precarga (en un hilo) de la lista de variables y la pantalla: `pantalla_parametros`, `pantalla_mapa` o `pantalla_descarga`.

Dentro de `pantalla_mapa` se llena primero el panel (área y buffer), después se calculan las estaciones, las altitudes y la disponibilidad (sin textos de carga: el escáner recorre el área), luego el mapa, el tablero de calidad, la cápsula de herramientas, las píldoras, la ficha y los botones ocultos. Como casi todas las zonas son fijas (`position: fixed`), el orden en el DOM no cambia dónde se ven.

**Estado de sesión** (`st.session_state`, en el código `ss`):

| Clave | Para qué |
|---|---|
| `paso` | Pantalla actual: `"parametros"`, `"mapa"` o `"descarga"` |
| `consulta` | Lo elegido en Parámetros: `{"etiqueta", "ini", "fin"}` (la serie se busca en el catálogo por su etiqueta) |
| `cuenca` | Geometría del área (GeoDataFrame) o `None` |
| `excluidas`, `version_lista` | Códigos de las estaciones quitadas de la descarga; contador que rehace la lista cuando las cambia la ficha |
| `vista` | `"2D"` o `"3D"` (es la clave del selector; sin `default` porque la cambian también la ficha, la lista de altitudes y los avisos, con callbacks que corren antes de dibujarlo) |
| `estacion_sel` | Código de la estación seleccionada |
| `tema`, `contraste`, `lite` | Preferencias de apariencia y rendimiento (también en la dirección) |
| `version_mapa`, `version_subida`, `version_3d`, `subida_abierta` | Contadores que rehacen el mapa 2D, vacían el cargador o rehacen el visor 3D; si el diálogo de subida está abierto |
| `descarga`, `trabajo`, `nombre_zip` | Exportación |
| `_base_cuenca`, `_mapa_version`, `_mapa_montado`, `_mapa_en_run_anterior`, `_capa_args` | Guardia del mapa 2D (ver [Mapa 2D](#mapa-2d)) y la capa de estaciones que se repite detrás de Parámetros y Exportación |
| `orbita`, `saltos`, `_intro_*`, `_orbita_firma`, `_vista_prev`, `_sel_prev`, `_orbitar`, `_repetir_intro` | Cámara y secuencia de entrada del 3D |
| `_prev_sel`, `_centrar`, `_dudosas_codigos` | Sincronización de la selección entre el mapa, la lista y el 3D |

Los widgets de Parámetros y del panel usan `persist_state="session"`: conservan su valor al pasar a otra pantalla y volver.

## Avisos de fallo

Nunca cambian de modo por su cuenta; ofrecen elegir:

- Pérdida del contexto gráfico WebGL del 3D ("Fallo gráfico"): *Activar Lite y reintentar*, *Seguir intentando*, *Ver en 2D*.
- Teselas del 3D o del mapa base 2D que fallan una y otra vez ("Problema de red"; en 3D se cuenta por tipo: relieve o imagen).
- Relieve que no avanza en 40 s sin errores claros ("Carga lenta").

Reintentar rehace el visor 3D y repone la cámara y la selección; en 2D vuelve a pedir las teselas sin mover el mapa. Los textos no afirman falta de memoria gráfica cuando solo falló una descarga.

## Mapa 2D

- Mapa base inicial: **Satélite con nombres** (imagen de Esri con su capa de rótulos `Reference/World_Boundaries_and_Places` encima; las dos van en un `FeatureGroup` que el control de capas trata como un solo mapa base).
- Solo se puede dibujar un **rectángulo** («Ajustar» mueve sus esquinas y «Borrar» lo quita sin rehacer el mapa: se queda el encuadre y el zoom). Los controles de Leaflet (zoom, dibujo, capas) están ocultos: los maneja la cápsula de herramientas de la página, y las acciones del dibujo («Guardar», «Cancelar») salen junto a ella. «Dibujar» y «Ajustar» se activan con el manejador de Leaflet.draw (`activarHerramienta` en el guion: busca el `draw_control_*` del iframe y llama a `handler.enable()`), no con un clic en sus botones ocultos: en iPhone, iPad y iPod, Leaflet.draw hace que esos botones respondan al toque (`touchstart`) y el clic simulado no hacía nada (en el iPhone no se podía dibujar). Mientras se dibuja o se ajusta (`draw:drawstart`/`draw:editstart`), el contenedor del mapa lleva `touch-action: none` para que el navegador no desplace ni amplíe a mitad del gesto. Un rectángulo nuevo reemplaza al anterior; "Usar el área visible" crea uno igual con la zona que se ve (`map.fire("draw:created")`), y así se puede marcar la cuenca solo con el teclado (foco en el mapa, flechas y +/−). La cuenca subida desde archivo puede tener cualquier forma. Un clic en la cuenca no abre la alerta del navegador con su GeoJSON (`show_geometry_on_click=False`).
- Al soltar (o editar) el rectángulo corre un **escáner** sobre él mientras el servidor calcula las estaciones; al terminar se desvanece, muestra "N estaciones con datos" y los pines aparecen de norte a sur con un pequeño rebote. Mientras corre, el mapa no se mueve ni hace zoom; la barra de dibujo sigue activa y dibujar otra vez reinicia el escáner. Tope de 30 s por si algo falla; con `prefers-reduced-motion` no corre y en modo Lite se dibuja sin rejilla ni destellos y los pines aparecen sin animación.
- Aún no hay animación para la cuenca subida desde archivo (el mapa todavía no existe mientras se calcula).
- Sin área, el mapa muestra el catálogo nacional agrupado (`FastMarkerCluster`) para ubicarse. La capa se arma de nuevo en cada corrida: folium no deja volver a dibujar el mismo objeto (el agrupador quedaría sin definir).
- La lista de variables del IDEAM se pide por detrás al arrancar el servidor (`app._iniciar_precarga_servidor`) y las series de la variable elegida, al elegirla (`app._precargar_series`); ver [Parámetros](#1-parámetros-pantalla_parametros-en-apppy).

**Contratos que no hay que romper** (si cambias `app.py`, `map_view.py` o `escaner.py`):

1. **El mapa base no debe cambiar al dibujar ni al cambiar de pantalla.** `st_folium` identifica el componente por un hash del mapa base; si cambia, Streamlit destruye el mapa y lo crea de nuevo (pantalla en blanco, salto de zoom, y se pierde el escáner). Por eso `mapa_base` solo recibe el área cuando el mapa se monta de cero (archivo, volver del 3D). La guardia está en `app.mapa_2d`: `ss._mapa_montado`, `ss._base_cuenca` y `ss._mapa_version`. `_mapa_montado` lo pone en `True` la corrida que dibuja el mapa (aunque después pida otra con `st.rerun`: lo enviado ya llegó al navegador) y solo lo apaga una corrida que **termina** sin dibujarlo (final de `app.py`). Antes se miraba solo la corrida anterior, y una corrida interrumpida antes de llegar al mapa (por ejemplo, al tocar una estación y enseguida «Borrar») hacía rehacer el mapa con el área y perder el zoom. Las estaciones y el buffer van aparte, en `feature_group_to_add`, que se actualiza sin reconstruir el mapa. Y el mapa debe ir siempre en `y2k_escenario`, antes de cualquier cosa condicional.
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
| `saltos`, `fantasmas` | `LineLayer`, `ScatterplotLayer` | Altitudes dudosas; sobre `saltos` suben los haces naranjas (la altitud del catálogo y la del terreno se leen en la ficha, no sobre el relieve) |

**Cámara y secuencia.**
- Streamlit maneja la vista como estado de React (controlado), así que `deck.setProps({viewState})` no mueve nada. El guion busca el `deck` por dentro de React (`__reactFiber$`) y llama a `deck.props.onViewStateChange` en cada cuadro.
- La cámara gira alrededor de un punto en `z = 0`; para orbitar una estación a otra altura se usa `position: [0, 0, altura]`.
- La secuencia de entrada se esconde y anima las capas con `layer.clone()` y al final devuelve las originales. Corre una sola vez por cuenca y buffer (`ss._intro_firma` / `ss._intro_turno` en `app.py`) y se ata al turno de la vuelta para que el HTML no cambie entre recargas. Respeta `prefers-reduced-motion`.
- Mientras corre la secuencia, un CSS (que manda Python) tapa el visor hasta que el guion escondió las capas y marcó `data-mostrar="<turno>"`; se destapa solo a los 12 s si algo falla. Ya no hay cubierta de "Alistando las estaciones": la intro satelital cubre la espera.
- Cada ejecución del guion lleva un número (`__y2kOrbitaId`): si arranca otra, la anterior se detiene.

**Escena.** Toda la escena se baja la altura del terreno en el centro de la cuenca (la cámara apunta a nivel 0). Contornos, pines y relieve usan esa misma base. `EXAGERACION = 2`.

**Memoria gráfica (lo más delicado).** Se llegó a perder el contexto WebGL (3D en blanco). Valores que se probaron estables:
- **Relieve acotado a la zona** (`extent` del `TerrainLayer`): el recuadro del área con su buffer más, a cada lado, su propio tamaño (unas 3 veces el área, mínimo ~7 km) o lo que alcanza a verse con el encuadre inicial de la cámara (pantalla de 1400 px; 500 px en el celular), lo que sea mayor. Lo de más allá casi no se veía y era la mayor parte de los tiles al inclinar.
- **Neblina solo donde termina el relieve**: el guion de la interfaz (`bordeRelieve`) busca, en tres columnas de la pantalla, en qué altura el suelo sale del `extent` (con `viewport.unproject`, entre el borde de arriba y el centro, que es lo que mira la cámara) y la neblina (`.y2k-neblina`) tapa de ahí hacia arriba, con una franja de transición del 12 % del alto (`--n-y`, `--n-banda`). Si el borde no se ve (de cerca o mirando hacia abajo), no hay neblina. Antes dependía solo de la inclinación y, de cerca, al levantar la vista aparecía a pocos metros. Encima del borde solo hay cielo (`--y2k-cielo`), del mismo color que la neblina (`--y2k-niebla`): los dos son azul oscuro también en el tema claro.
- **Inclinación**: la vuelta de cámara termina en 35–45° (`terreno.PITCH_MIN`, `PITCH_MAX`); a mano se llega hasta 70° (`terreno.MAX_PITCH`, en `ViewState`, en `_ORBITA` y en la cámara de la interfaz).
- **Tope para alejarse** (`minZoom`): hasta que el recuadro del relieve casi llena la pantalla a lo ancho y, con la inclinación máxima, el borde de abajo de la pantalla sigue cayendo dentro de él (si no, el relieve se ve suelto en el cielo); nunca por encima del encuadre inicial.
- Vista de conjunto: `tile_size` 512, `mesh_max_error` 8, `far_z_multiplier` 1,5. Cerca de una estación: 256, 4 y 1,6. Modo ligero (celular o modo Lite): 10 y 1,3. Con el relieve acotado y la neblina en su borde, dibujar más lejos solo gastaba memoria gráfica.
- `max_cache_size` 50–100, `refinement_strategy="'no-overlap'"` y `useDevicePixels` ≤ 1,5 puesto desde JavaScript.
- Si el navegador pierde el contexto WebGL, la interfaz (`estilo.instalar_ui`) lo avisa y deja elegir entre *Activar Lite y reintentar*, *Seguir intentando* (visor nuevo en el mismo modo) o *Ver en 2D*; los botones pulsan botones ocultos de Streamlit (`y2k_lite_reintentar`, `y2k_reintentar3d`, `y2k_pasar2d`). Antes de rehacer el visor guarda la cámara y la repone en el nuevo.

**Trampas conocidas.**
- `pydeck` convierte todo texto en expresión: para un valor literal va entre comillas (`"'no-overlap'"`, `"'auto'"`).
- Los colores del PNG de relieve no deben "corregirse" (`colorSpaceConversion: none`) o el relieve se llena de picos falsos. Algunos navegadores con protección de privacidad (Brave, Safari privado) lo alteran: `terreno.AVISO_NAVEGADOR` lo detecta y pone una píldora mínima arriba al centro («Tu navegador altera el relieve»), que al tocarla despliega la explicación y se cierra con su ✕ (no vuelve en la sesión). Es un `<aside>` y no un `<div>`: el CSS estira a pantalla completa los `<div>` que cuelgan del visor (así el aviso anterior tapaba toda la pantalla y, en el celular, su ✕ quedaba debajo de Ajustes).
- `map_style="__MAP_STYLE__"` evita que Streamlit ponga un mapa plano de fondo a nivel 0.
- El 3D se arma en el servidor (≈ 3 s con caché fría en un PC; más en la nube) y el navegador baja los tiles después.
- Los guiones de `app.py` entran por `guion.inyectar` (ver [Archivos](#archivos)): corren en un iframe de altura 0 y llegan al DOM principal por `window.parent`.
- **Relieve para cálculos** (`terreno.zoom_para`): la revisión de altitud y el rango del relieve bajan el zoom de los tiles hasta que el área quepa en un tope de tiles (150 y 64), en lugar de pedir siempre el zoom máximo. Un tile que falla se recuerda 5 minutos (`_TILES_FALLIDOS`, `SEGUNDOS_SIN_REINTENTO`) y no se vuelve a pedir en cada corrida.

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
- El botón «Saltar animación» se acomoda con CSS (`.y2k-sat > button` en `estilo.CSS`, por encima de la esquina del botón de Streamlit) y recibe el foco al empezar.

**Cosas que no hay que romper.**
- Un solo contexto WebGL reutilizado: crear y destruir contextos (o `forceContextLoss`) termina en "context loss and was blocked" de Chrome. `destroy()` solo libera geometrías, texturas y buffers.
- No mandar las capas de deck.gl escondidas desde Python: cualquier re-render de React las repone y "se borra todo" al terminar. Se tapa el visor con CSS y las esconde el guion (con una guardia que las vuelve a esconder).
- `TUNE` en `satellite-scene.js` guarda los valores por defecto; el panel de ajustes (si se enciende con `PANEL_SATELITE`) los cambia en vivo y los recuerda en `localStorage` (prefijo `y2k_sat_`).
- Tras editar los archivos de la intro hay que **recargar la página del navegador** (F5, mejor Ctrl + F5): el reproductor se carga una sola vez por página y, si no se recarga, sigue corriendo la versión vieja aunque el archivo ya cambió. El parámetro `?v=` de las direcciones cambia con la fecha de los archivos.

**Temporal (quitar antes de presentar):** el botón «Repetir animación» (↻) de las píldoras del 3D (`y2k_repetir_intro` en `app.py`). El panel «⚙ Ajustes» de la intro está apagado (`PANEL_SATELITE = False` en `terreno.py`); se enciende solo para afinarla.

## Textura "Altura" del 3D

Tercera textura (junto a Satélite y Topográfico): el relieve se colorea por altitud (verdes abajo, naranjas y rojos arriba) con sombreado de ladera. Hay dos escalas: **Rango de la zona** (mínimo y máximo de la cuenca con buffer) y **Rango de Colombia** (0–5.730 m, más pixelada para ahorrar memoria). Un guion (`_HIPSOMETRICO`) intercepta `window.fetch` y devuelve, para las imágenes con la marca `y2k_hipso`, el tile de elevación coloreado. La leyenda sale de `terreno.leyenda_altura()` dentro de `estilo.leyenda_altura()`.

## Rediseño de noviembre de 2026

- **Lista de estaciones** (`panel_estadisticas.tabla_lista`): columnas ●, Estación, Código, Serie (años) y Cob.; con más de ocho estaciones aparece el buscador `buscar_estacion` (nombre o código). El panel mide 440 px (`--y2k-panel-w`; 350 px en pantallas medianas).
- **Estaciones sin serie**: `app.zona_mapa` no las dibuja salvo que esté activo `ver_sin_serie` («Mostrar las N sin serie», dentro del filtro de la lista).
- **Altitud dudosa**: halo punteado (`map_view.HALO_DUDOSA`) alrededor del punto, en lugar del borde naranja, que se confundía con la clase «Regular». Los grupos de marcadores usan un azul neutro para no parecer clases de cobertura.
- **Encuadre** (`app._encuadre`): con 20 estaciones o más usa los percentiles 1 y 99, para que una estación lejana (San Andrés) no aleje el mapa, y admite medios niveles de zoom.
- **Preparar descarga**: cuando no se puede, el botón dice el motivo corto («Delimita el área», «Elige una estación»…); el detalle sigue en la ayuda.
- **Línea de carga**: si una recarga pasa de 3 s, una línea fina recorre el borde superior del mapa (`[data-test-script-state="running"]`, solo CSS).
- **Exportación**: mientras descarga, «Ahora:» nombra las estaciones en curso (`ideam_downloader`, `en_curso`). Al terminar, el orden es cifras (`estilo.kpis`), reparto, nombre y **Descargar el ZIP**, y después las opciones (carpetas, mapa de huecos). La columna derecha muestra `app._tabla_completitud` (estimada, real y diferencia por estación) y el recibo queda plegado en «Lo que pediste».

## Pruebas

- **Lógica** (`python -m pytest -q tests`): bloques de descarga, cobertura, catálogo, mapa de huecos y `modules/logica.py`. No abren la app ni salen a internet. `tests/test_idioma.py` revisa las traducciones: que todo texto de `tr()` tenga su entrada en `idioma.EN`, que ninguna sobre ni se repita y que los huecos `{así}` coincidan en los dos idiomas.
- **Interfaz** (`tests/interfaz/`): arrancan la app de verdad contra un IDEAM simulado (`ideam_simulado.py`: variables, series, Excel y relieve inventados, siempre iguales) y la recorren con un navegador (Playwright): acceso, Parámetros, mapa, descarga completa con su ZIP, detener a medias y el flujo en celular. Necesitan `pip install playwright` y `playwright install chromium`; sin Playwright se saltan solas.
- Para ver la app simulada a mano: `streamlit run tests/interfaz/app_simulada.py --secrets.files tests/interfaz/secretos_prueba.toml` (clave `cliente-prueba`).
- En GitHub corren las dos en cada PR (`.github/workflows/pruebas.yml`, trabajos `pytest` e `interfaz`).
