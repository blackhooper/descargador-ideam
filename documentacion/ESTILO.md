# Estilo del Descargador IDEAM

El sistema visual y el guion de la interfaz. La guía de uso e instalación está en el [README](../README.md) y la organización del código en [Arquitectura](ARQUITECTURA.md).

## Sistema visual: cómo cambiar la estética

Todo lo visual de la app sale de `modules/estilo.py` y de `modules/recursos/`. En `estilo.py` quedan los tokens, los iconos y las piezas HTML; las hojas de estilo y los guiones del navegador son archivos de verdad en `recursos/` (CSS y JavaScript, para editarlos con resaltado y sin escapar nada), que `estilo.py` lee al arrancar con `_recurso()`. Este es el mapa, en orden:

| Sección | Qué es | ¿Se toca al cambiar la estética? |
|---|---|---|
| `FUENTE`, `ATRIB_*`, `CREDITOS_MAPAS` | Fuente de los datos y créditos (textos legales) | No |
| `PALETAS` | Colores para lo que no lee CSS: gráficas de Altair y ficha emergente del 3D | **Sí** |
| `TEMAS`, `CONTRASTES` | Valores válidos de `?tema=` y `?contraste=` | No |
| `MOVIL`, `BAJO` | Puntos de quiebre (celular, pantalla baja). `MOVIL` lo usa también el guion | Con cuidado |
| `TOKENS`, `TOKENS_ALTO` | **Tokens de color y material** para claro, oscuro y alto contraste | **Sí** |
| `VIDRIO_CLARO`, `VIDRIO_REGULAR` | Qué superficies llevan cada material | Solo para agregar o quitar superficies |
| `CSS` (`recursos/base.css`) | Estilos base: medidas (`:root`), material, escenario, Ajustes, las tres pantallas, componentes y el cambio de pantalla | **Sí** |
| `CSS_MEDIO`, `CSS_MOVIL`, `CSS_ANGOSTO`, `CSS_ESTRECHO`, `CSS_BAJO` (`medio.css`, `movil.css`, `sello_movil.css`, `angosto.css`, `estrecho.css`, `bajo.css`) | Ajustes por tamaño: 761–1100 px, ≤ 760 px, ≤ 400 px, ≤ 380 px, alto ≤ 560 px | **Sí** |
| `CSS_ALTO`, `CSS_LITE`, `CSS_MOVIMIENTO`, `CSS_FORZADOS` (`alto_contraste.css`, `lite.css`, `movimiento.css`, `colores_forzados.css`) | Alto contraste, modo Lite, movimiento reducido y colores forzados | **Sí** |
| `aplicar()`, `_tokens_css()`, `_vidrio()` | Arman y ordenan todo el CSS | No |
| `ICONOS` | Iconos SVG de línea (heredan el color del texto) | **Sí** |
| `ajustes()`, `cabecera_inicio()`, `etiqueta()`, `pasos()`, `pie_inicio()`, `cabecera_panel()`, `boton_consulta()`, `boton_abrir_panel()`, `seccion()`, `acciones_area()`, `kpis()`, `aviso()`, `marca_listo()`, `marca_filtro()`, `herramientas_2d()`, `herramientas_3d()`, `leyenda_*()`, `pie()`, `cabecera_exportar()`, `progreso()`, `recibo()`, `resumen_final()`, `legal_exportar()` | Piezas HTML: definen la estructura y las clases de cada pieza | Solo sus clases decorativas; no los `data-y2k-*` ni la estructura |
| `_UI` (`recursos/ui.js`; dentro, `CSS_IFRAME`) y `_SINCRONIZAR_TEMA` (`sincronizar_tema.html`) | Guion de la interfaz del navegador; `CSS_IFRAME` es el estilo de los controles de Leaflet dentro de su iframe | Solo `CSS_IFRAME` |

### Pasos para cambiar la estética

1. **Colores y materiales**: edita `TOKENS` (claro y oscuro) y `TOKENS_ALTO` (alto contraste). Cada token es una variable CSS (`--y2k-…` o `--lg-…`); ningún componente debería tener colores propios.
2. **Medidas y movimiento**: al principio de `CSS`, en `:root`: `--y2k-g` (margen entre piezas flotantes), `--y2k-panel-w` (ancho del panel), `--y2k-capsula` (alto de las cápsulas), `--y2k-r` y `--y2k-r-ctl` (radios), `--y2k-dur` y `--y2k-curva` (transiciones).
3. **Tipografía**: el `@import` de Google Fonts y la regla `font-family` al principio de `CSS` (hoy, Figtree). El manual tiene la suya.
4. **Forma de los componentes**: las reglas de `CSS` y de los bloques por tamaño. Están agrupadas por zona y comentadas (material, escenario, Ajustes, pantalla 1, pantalla 2: panel, tablero, herramientas, píldoras y ficha; pantalla 3: avance, recibo y resumen; cambio de pantalla).
5. **Colores que no son CSS**: `PALETAS` (gráficas y 3D) y `.streamlit/config.toml` (widgets de Streamlit: listas, deslizadores, fechas). Deben coincidir con los tokens.
6. **Controles de Leaflet**: `CSS_IFRAME`, dentro de `_UI`. Vive en el iframe del mapa, que no hereda las variables de la página: sus colores están escritos a mano para cada caso (clases `y2k-oscuro`, `y2k-alto`, `y2k-lite`, `y2k-bajo` que el guion pone en el `<html>` del iframe).
7. Sube la versión del guion (`_UI.replace("__V__", "…")` en `instalar_ui`) si cambiaste `recursos/ui.js`, para que no siga corriendo la versión vieja en una pestaña abierta.
8. En las hojas de `recursos/` siguen valiendo las marcas `__VIDRIO__`, `__VIDRIO_CLARO__`, `__VIDRIO_REGULAR__`, `__P_PARAM__`, `__P_MAPA__` y `__P_EXPORT__`, que `estilo._vidrio()` cambia por los selectores de verdad; y no se escribe nada con forma de etiqueta HTML en un comentario (Streamlit descartaría el bloque).
9. Revisa con la [lista de comprobación](#lista-de-comprobación-tras-un-cambio-estético).

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

**Claves de contenedores** (producen la clase `.st-key-<clave>`): `y2k_escenario`, `y2k_mapa2d`, `y2k_visor3d`, `y2k_ajustes`, `y2k_inicio` (cuerpo `y2k_inicio_cuerpo`), `y2k_fechas`, `y2k_panel`, `y2k_panel_cab`, `y2k_cuerpo`, `y2k_buffer`, `y2k_abrir`, `y2k_herr`, `y2k_filtro`, `y2k_dock`, `y2k_dock_izq`, `y2k_dock_der`, `y2k_ficha` (cuerpo `y2k_ficha_cuerpo`), `y2k_exportar` (cuerpo `y2k_exportar_cuerpo`), `alerta_altura`, `alerta_ficha` y los invisibles (`y2k_guiones`, `y2k_hipso`, `y2k_velo`, `y2k_ocultos`, `y2k_precal`, `y2k_orbita`, `y2k_escaner`).

**Claves de widgets que usan el CSS o los guiones**: `vista` (también `static/intro_satelital/player.js` y `terreno.css_boton_3d_espera`), `serie`, `ir_mapa`, `preparar`, `filtro_cob`, `carpetas`, `y2k_repetir_intro`, `lite_menu`, `pref_tono`, `pref_alto`, `bajar_zip` y los ocultos `y2k_lite_reintentar`, `y2k_reintentar3d`, `y2k_pasar2d`, `y2k_borrar`, `y2k_subir`, `chip_param`, `y2k_tex_<n>`, `y2k_esc_<n>`. `textura` y `escala_altura` ya no son widgets: son claves de sesión que ponen esos botones.

**Atributos de las piezas HTML** (los pone `estilo.py`, los lee el guion):

| Atributo | Elemento | Qué hace al pulsarlo |
|---|---|---|
| `data-y2k-panel-btn` | Botón de la cabecera del panel y «Consulta» (escritorio) | Oculta o muestra el panel |
| `data-y2k-consulta`, `data-y2k-hoja-cerrar` | «Consulta» de la barra y ✕ de la tarjeta (celular) | Abren y cierran la tarjeta de la consulta (también Escape y tocar el mapa) |
| `data-y2k-pulsar="<clave>"` | Chip de la variable, opciones de textura y escala del 3D | Pulsa el botón oculto de esa clave (`chip_param`: volver a Parámetros; `y2k_tex_<n>`, `y2k_esc_<n>`) |
| `data-y2k-menu` / `data-y2k-menu-de` (`dibujo`, `capas`, `camara`, `capas3d`) | Botones de la cápsula de herramientas y sus menús | Abren y cierran el menú (Escape, flechas, clic fuera) |
| `data-y2k-dibujar` | «Dibujar un rectángulo», «Redibujar» | Activa la herramienta de rectángulo de Leaflet |
| `data-y2k-editar` | «Ajustar» | Activa la edición de las esquinas de Leaflet |
| `data-y2k-area` | «Usar el área visible» | Crea el área con la zona visible (`aria-disabled` hasta el zoom 10) |
| `data-y2k-subir`, `data-y2k-2d` | «Subir un archivo», «Ver en 2D» | Pulsan los botones ocultos `y2k_subir`, `y2k_pasar2d` |
| `data-y2k-borrar` | «Borrar» | En 2D quita el rectángulo en el navegador y avisa a `st_folium` con `draw:deleted` (Python recibe la lista vacía): el mapa no se rehace y conserva encuadre y zoom. En 3D (sin Leaflet) pulsa el oculto `y2k_borrar` |
| `data-y2k-ficha-btn`, `data-y2k-ficha-quitar` | Píldora de la ficha y su ✕ | Despliegan o cierran la ficha (`data-y2k-ficha` en `<html>`); la ✕ pulsa `quitar_sel` |
| `data-y2k-capa` | Opciones del menú Mapa base | Eligen la capa base (pulsan el control de capas oculto de Leaflet) |
| `data-y2k-zoom` (`mas`, `menos`) | Zoom de la cápsula | Acercan o alejan el mapa |
| `data-y2k-cam` (`acercar`, `alejar`, `izq`, `der`, `subir`, `bajar`, `norte`) | Cruceta y zoom del menú Cámara del 3D | Mueven la cámara (el menú no se cierra; inclinación hasta 70°, alejarse hasta `minZoom`) |

**Clases que el guion busca**: `.y2k-pantalla` (la pantalla actual), `.y2k-cierre-hoja` (la crea el guion: capa invisible sobre el mapa con la consulta del celular abierta), `.y2k-leyenda`, `.y2k-camara-estado`, `.y2k-atrib3d`, `.y2k-dialogo` (la crea el guion), `.y2k-sat` (capa de la intro, la crea `player.js`) y `.lg-claro` / `.lg-regular` (material de las piezas HTML; el brillo especular las reconoce).

**Clases de composición** (las usa el CSS para colocar las piezas): `.y2k-sobre` (pieza HTML sobre el mapa: su contenedor de Streamlit se vuelve transparente a los clics y se estira al tamaño del mapa) y `.y2k-pantalla[data-p]` (con `:has()`, decide qué huecos se ven en cada pantalla y si el mapa va velado).

**Estado en `<html>`**: el guion de la interfaz escribe `data-y2k-panel` (`abierto`/`cerrado`; al llegar al mapa desde Parámetros, `cerrado` en el escritorio), `data-y2k-hoja` (`abierta`/`cerrada`, la consulta del celular; al salir del mapa se cierra), `data-y2k-ficha` (`abierta`/`cerrada`), `data-y2k-3d` (`1` con el visor 3D: el CSS quita el desenfoque y la máscara de la consulta del celular), `data-y2k-p` (la pantalla) y `data-y2k-mapa-listo` (el mapa 2D cargó: habilita «Seleccionar área en el mapa»). El precalentamiento de la intro escribe `data-y2k-listo` (mientras no coincida con el área, el botón 3D queda gris). El visor 3D lleva `data-mostrar="<turno>"` durante la secuencia de entrada.

**Variables CSS que escribe el guion** (en CSS solo se les da un valor inicial): `--y2k-ov-top`, `--y2k-ov-izq`, `--y2k-ov-der`, `--y2k-ov-abajo` (la zona libre del mapa), `--y2k-ley-abajo`, `--y2k-ley-izq`, `--y2k-atrib-abajo`, `--y2k-atrib-der`, `--y2k-dock-h` (en el celular, la distancia del borde de abajo a la barra), y `--mx`/`--my` en cada vidrio (brillo especular). En el iframe de Leaflet: `--tl-top`, `--tl-izq`, `--tr-top`, `--tr-der`, `--bl-abajo`, `--bl-izq`, `--br-abajo`, `--br-der`, `--acc-top`, `--acc-der` (dónde salen «Guardar» y «Cancelar» del dibujo), y la clase `y2k-hoja-abierta` en su `<html>` (aparta la escala y los créditos con la consulta del celular abierta).

**Variables CSS que el guion lee**: `--y2k-lite`, `--y2k-tono`, `--y2k-alto`. `--y2k-sello` (esquina del botón de Streamlit) la pone `aplicar(sello=True)`, que en el celular agrega además `CSS_SELLO_MOVIL`: el crédito del relieve 3D va en la franja de abajo, a la izquierda de ese botón (en el escritorio lo coloca `distribuir`, en la misma franja, si no choca con la píldora 2D/3D). «Saltar animación» de la intro sube también por encima de esa esquina. El guion escribe también `--y2k-abrir-w` (ancho del botón «Consulta» del escritorio, para poner el filtro a su lado).

**Almacenamiento del navegador**: `localStorage` `y2k_panel` (y `y2k_sat_*` de la intro); `sessionStorage` `y2k_aviso3d_cerrado`.

### Lista de comprobación tras un cambio estético

- Claro, oscuro y alto contraste; colores forzados (Windows); con y sin modo Lite; con movimiento reducido.
- Escritorio (1440 y 1024 px), celular vertical (390 px) y horizontal (844 × 390).
- Las tres pantallas; Parámetros en Estándar y en Especial; en el mapa, 2D y 3D, con panel abierto y cerrado, con ficha, con los menús de herramientas y el del buffer abiertos, y en el celular con la consulta abierta y cerrada; la exportación en curso y terminada.
- Con la esquina del botón de Streamlit reservada (`Y2K_SELLO=1`): que nada importante quede debajo.
- Que no salgan barras de desplazamiento en las cápsulas (Ajustes, píldoras), que en las tarjetas la barra quede dentro de la curva y que en reposo sea transparente.
- La barra del celular en 360, 380 y 390 px: que «Preparar descarga» no se salga y tenga el alto de «Consulta».
- Contraste AA de los textos sobre el mapa (satélite y calles), no sobre un fondo liso.
- Que el vidrio siga dejando ver el mapa (si queda opaco, ya no es vidrio) y que en Lite quede legible sin desenfoque.
- Que ni la leyenda ni la escala o la atribución de Leaflet queden debajo del panel, las píldoras o la ficha, y que los menús no queden tapados.

## Guion de la interfaz del navegador

`estilo._UI` se inyecta una vez en la página principal (`estilo.instalar_ui`, dentro de `y2k_guiones`) y sobrevive a las recargas de Streamlit. Se repasa cada 500 ms y en cada cambio del DOM. Hace:

- **Panel y consulta del celular** sin recargar la página (atributos en `<html>`; la elección del panel del escritorio, en `localStorage`), con `aria-expanded`. En el celular no hay arrastres (el gesto se confundía con «jalar para recargar», que además queda desactivado con `overscroll-behavior: none`): el botón «Consulta» abre y cierra la tarjeta; con ella abierta, una capa invisible sobre el mapa la cierra al tocarlo. Con la tarjeta abierta, lo que va sobre el mapa (herramientas, filtro, leyenda, créditos, ficha) se oculta enseguida y, al cerrarla, vuelve cuando la tarjeta ya bajó (transición con demora); `distribuir` reparte el espacio como si la tarjeta estuviera cerrada, así nada salta de lugar.
- **Menús de la cápsula de herramientas** (`role="menu"`; el de Cámara, `role="group"`): abren y cierran, se recorren con flechas, Escape devuelve el foco. Sus opciones manejan los controles ocultos de Leaflet.
- **Un toque fuera cierra cualquier desplegable** (`alPulsar`, en `pointerdown`): menús de la cápsula, leyenda, ficha y, si el toque cae en el mapa 2D, también los menús de Streamlit (Ajustes, buffer, filtro). Los toques en el mapa 2D caen en su iframe: el guion los escucha ahí y, si hay un menú de Streamlit abierto, le manda un clic al `body` de la página (así se cierran).
- **Pantallas**: marca el escenario como `inert` en Parámetros y Exportación, y en Parámetros detiene el botón principal (con dos destellos rojos) hasta que Python marca que está listo y el mapa 2D cargó (alguna tesela, 6 s con el mapa creado o, si no carga, 15 s).
- **Reparto del espacio** (`distribuir`): mide las piezas flotantes y calcula la zona libre del mapa; sube la leyenda, la escala y la atribución por encima de las píldoras que comparten su columna, y pone las acciones del dibujo de Leaflet junto a la cápsula de herramientas. También encuadra el área recién montada en la zona libre.
- **Mapa 2D**: inyecta `CSS_IFRAME` (oculta los controles de Leaflet, que maneja la cápsula, y da vidrio a las acciones del dibujo), traduce Leaflet.draw al español, maneja dibujar, ajustar, «Usar el área visible», capas y zoom, y vigila las teselas que fallan.
- **3D**: cámara (busca el `deck` por dentro de React) y vigilancia de WebGL, red y carga lenta. En el celular, con la consulta abierta la cámara deja de girar sola y la tarjeta va sin desenfoque ni máscara (el teléfono no recalcula el vidrio sobre el relieve). Cada 150 ms (`vigia3d`) ajusta la **neblina** (`.y2k-neblina`, sobre el lienzo; ver [Vista 3D](ARQUITECTURA.md#vista-3d-guía-para-quien-la-modifique)) y, con el menú Cámara abierto, la brújula y la línea de rumbo e inclinación. El clic derecho sobre el 3D no abre el menú del navegador (gira e inclina, como en cualquier mapa).
- **Varios**: traduce el cargador de archivos y las listas desplegables de Streamlit («Elegir todas», «Elegir las N coincidencias», «Sin resultados» y las etiquetas de sus botones de borrar; `traducirListas`), quita del nombre accesible el texto de los iconos de Streamlit y mueve el brillo especular con el puntero. En las listas desplegables, los nombres largos se cortan con «…» (CSS).

## Temas, contraste, modo Lite y movimiento

- **Tema** (*Claro / Oscuro*) y **alto contraste** (un interruptor) son independientes y están en el menú Ajustes. Sin elegir, siguen al equipo: se resuelven con `prefers-color-scheme` y `prefers-contrast` en media queries (sin destello); el interruptor de contraste solo fuerza el alto contraste (apagado, vuelve a seguir al equipo). El alto contraste usa superficies opacas y bordes nítidos en el tono vigente: no es el modo oscuro. La elección viaja en la dirección (`?tema=`, `?contraste=`). Streamlit no deja cambiar su tema desde Python: `_SINCRONIZAR_TEMA` pulsa sin que se vea su menú (oculto).
- Con **colores forzados** (`forced-colors`) se respetan los colores del sistema y solo se reponen bordes y señales que el navegador quita.
- **Modo Lite** (interruptor en Ajustes, `?lite=1`; con Lite activo se ve la marca «Lite» junto a Ajustes): mismos datos, controles y funciones con menos coste gráfico. Agrega `CSS_LITE` (sin desenfoque, brillos ni transiciones: variante de baja transparencia) y usa un 3D liviano (menos detalle de malla, caché menor, 1 píxel de dibujo por píxel CSS), sin intro satelital, sin secuencia de entrada ni vuelta de cámara (la cámara queda de una vez en el encuadre final) y escáner 2D sin rejilla ni destellos. Los guiones leen Lite en el navegador (variable `--y2k-lite`), así activarlo no mueve la cámara ni repite animaciones.
- **Movimiento reducido** es independiente de Lite: quita transiciones, animaciones de entrada y el brillo que sigue al puntero, pero conserva el vidrio. La intro del 3D no se reproduce sola (un aviso lo dice); «Repetir animación» sí la muestra, porque la pide la persona.
- Orden del CSS (`aplicar`): base → bloques por tamaño → tokens del tema → alto contraste → Lite → movimiento reducido → colores forzados.
