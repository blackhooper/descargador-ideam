# Descargador IDEAM

Descarga automática de series hidrometeorológicas del portal **DHIME del IDEAM** (Colombia) para todas las estaciones de una cuenca. Es una herramienta independiente, no oficial del IDEAM.

1. Dibujas tu cuenca en el mapa o subes un archivo (shapefile en ZIP, GeoJSON, KML/KMZ o GeoPackage).
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

## Publicarla en Streamlit Community Cloud

Conecta este repositorio en [share.streamlit.io](https://share.streamlit.io), con `app.py` como archivo principal. En **Advanced settings** elige Python 3.12 o 3.13. En **Secrets** pega el mismo bloque `[ideam]` de arriba.

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

La aplicación muestra estos créditos en el pie de página y en el borde de cada mapa.
