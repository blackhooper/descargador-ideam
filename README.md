# Descargador IDEAM

Descarga automática de series hidrometeorológicas del portal **DHIME del IDEAM** (Colombia) para todas las estaciones de una cuenca.

1. Dibujas tu cuenca en el mapa o subes un archivo (shapefile en ZIP, GeoJSON, KML/KMZ o GeoPackage).
2. La app muestra las estaciones del IDEAM que caen adentro (y en un buffer opcional). Para cada una calcula la **cantidad probable de datos** del parámetro y el rango de fechas que elijas.
3. Filtras por calidad mínima y descargas todo en un ZIP: un Excel por estación, con el formato original del IDEAM y los bloques de años ya unidos. Si quieres, las estaciones van separadas en carpetas por calidad.

Incluye vista 3D con relieve real y aviso de estaciones cuya altitud en el catálogo no coincide con el terreno.

## Usarla en tu computador

Necesitas Python 3.12 o superior.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Antes de arrancar, crea el archivo `.streamlit/secrets.toml` con el usuario y la clave del portal DHIME:

```toml
[ideam]
usuario = "..."
clave = "..."
```

## Publicarla en Streamlit Community Cloud

Conecta este repositorio en [share.streamlit.io](https://share.streamlit.io), con `app.py` como archivo principal. En **Advanced settings** elige Python 3.12 o 3.13. En **Secrets** pega el mismo bloque `[ideam]` de arriba.

## Notas

- Los datos son del IDEAM. Esta herramienta solo automatiza las consultas que se pueden hacer a mano en el portal DHIME.
- El servidor permite como máximo 2 descargas a la vez para no saturar el servicio del IDEAM. Las demás esperan turno.
