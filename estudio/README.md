# Estudio hidrológico express

Herramienta en la nube para hacer un estudio hidrológico sin ArcGIS, del modelo de elevación al informe en Word y
PDF. El plan completo, con sus ocho etapas y las fuentes acordadas, está en el plan del proyecto. Esta carpeta
contiene la **etapa 1, Terreno**: delimitar la cuenca y su red de drenaje.

Es una herramienta del **modo desarrollador** del descargador: entra con la clave de desarrollador y abre Ajustes →
Vista → Herramientas → «Estudio hidrológico». Usa la misma dirección, la misma clave y los mismos estilos que el
descargador. Las librerías del análisis de terreno (pysheds, rasterio, scipy) están en el `requirements.txt` de la raíz
y solo se cargan al abrir la herramienta.

```bash
streamlit run app.py                         # el descargador; el estudio está en Herramientas
python -m pytest -q tests/test_estudio.py    # pruebas del estudio, sin red
```

## Regla de la herramienta: todo con fuente

Cada cálculo y cada decisión apunta a una fuente del registro, y cada fuente lleva una **marca** que dice qué
tan oficial es su respaldo:

| Marca | Significa |
|---|---|
| Fuente ambiental oficial | IDEAM, CAR u otra corporación, Minambiente o ANLA. |
| Otra entidad oficial | IGAC, SGC, INVÍAS… cuando las ambientales no lo traen. |
| Estudio académico colombiano | Universidad o revista colombiana, con mediciones hechas en Colombia. |
| Referencia técnica | Método publicado sin norma colombiana que lo fije. |
| Decisión del hidrólogo | Valor que la página propone y el hidrólogo puede cambiar. |
| Sin fuente oficial | Control propio de la herramienta, declarado. |

En la página, cada paso tiene un botón «i» con lo que hace, por qué se hace, la calidad del dato si hace falta, lo que decide el hidrólogo y sus
fuentes (con página o tabla). Bajo cada resultado hay una línea con la fuente y su marca. Al final aparece la
bibliografía en APA 7.

## Archivos

| Archivo | Qué tiene |
|---|---|
| `fuentes.py` | Registro de fuentes: cita APA 7, cita corta, marca, enlace y qué se toma de cada una. |
| `pasos.py` | Texto de las ayudas «i» de cada paso. También será la memoria de cálculo del informe (etapa 8). |
| `core.py` | El estudio como receta JSON (`Estudio`): decisiones con sus fuentes, archivos y resultados. |
| `almacen.py` | Dónde se guardan los archivos. Hoy es una carpeta temporal y el estudio se guarda o se retoma en un ZIP. Supabase se agrega después como otra clase con los mismos cinco métodos (`guardar`, `leer`, `existe`, `listar`, `ruta_local`), sin tocar el resto. |
| `terreno.py` | Cálculo de la etapa 1, sin Streamlit. Lee el modelo de elevación, lo acondiciona, ubica el punto de cierre, delimita la cuenca, extrae la red, compara con un segundo modelo y exporta. |
| `trabajos.py` | Trabajos en segundo plano. Leer y acondicionar el modelo corre en un hilo mientras la persona llena lo demás, y un punto junto al título se enciende al terminar. No hay pantallas de carga. |
| `ui.py` | Piezas visuales propias: tarjetas, ayudas «i», marcas, cifras y bibliografía. Lo común (tokens, vidrio, botón azul, Ajustes) viene de `modules/estilo.py`; el CSS propio solo aplica con el estudio abierto. |
| `pagina.py` | La página: `pantalla()`, que abre `modules/herramientas.py`. Lo que guarda en `session_state` lleva el prefijo `est_` para no chocar con el descargador. |

## Etapa 1, paso a paso

1. **Área de trabajo.** Se marca con un rectángulo en el mapa, un archivo o coordenadas. Si la cuenca toca el borde, la página ofrece ampliar el área y vuelve a delimitar.
2. **Modelo de elevación.** Copernicus GLO-30 leído en línea, solo de la ventana necesaria, o un GeoTIFF propio. Se reproyecta a EPSG:9377 con celdas de 30 m. La ayuda explica la calidad: no hay modelo gratuito más fino que 30 m para Colombia (el ALOS PALSAR de 12,5 m es el SRTM remuestreado, según la NASA), con tres estudios colombianos de respaldo (Capachero et al., 2015; Buitrago y Martínez, 2016; Vélez y Suárez, 2025).
3. **Flujo.** Relleno de depresiones (Barnes et al., 2014a), zonas planas (Barnes et al., 2014b), dirección D8 (O'Callaghan y Mark, 1984) y acumulación. Es el procedimiento del IDEAM (2013, p. 104).
4. **Punto de cierre.** Clic, estación hidrológica del catálogo IDEAM o coordenadas. Se ajusta a la celda de mayor acumulación dentro del radio (300 m por defecto).
5. **Cuenca y red.** Polígono, área, elevaciones y red con orden de Strahler. El umbral de la red (1 km² por defecto) queda declarado.
6. **Comparación.** La misma cuenca con el SRTM (Mapzen Terrain Tiles). Se informan la diferencia de área y la coincidencia (intersección sobre unión).
7. **Exportar.** GeoPackage en EPSG:9377 (áreas en ha con dos decimales, Res. 940 de 2026), KML en WGS84 y el estudio completo en ZIP.

**Validación con el río Teusacá** (estación RÍO TEUSACA - APOSENTOS, 2120700404):

| | Resultado |
|---|---|
| Área con Copernicus | 358,01 km², frente a 358,24 km² del POMCA del río Bogotá (CAR, 2019, tabla 5.9), un 0,06 % de diferencia |
| Elevaciones | 2548 a 3668 m, frente a 2565 a 3684 m del POMCA |
| Área con SRTM | 349,72 km², con 94,7 % de coincidencia |

**Nota técnica.** pysheds no enruta la celda del borde del modelo, así que la prueba de borde revisa las dos
primeras filas y columnas de cada lado. Una prueba con un D8 escrito aparte lo verifica.
