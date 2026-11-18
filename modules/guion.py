"""Guiones del navegador: un solo lugar por donde la app inyecta JavaScript en la pagina.

Todos los guiones (interfaz, escaner, camara del 3D, intro satelital, cookie de acceso) corren en un iframe sin alto
y llegan a la pagina por `window.parent`. Hasta ahora cada modulo llamaba a `st.components.v1.html`, que Streamlit
retira ("will be removed after 2026-06-01; replace with st.iframe"). Con todo pasando por `inyectar`, el cambio es de
una linea.

Por defecto se sigue usando `components.html` (es con lo que esta probada la app, fijada en Streamlit 1.64). Con la
variable de entorno Y2K_IFRAME=1 se usa `st.iframe`, para probar la migracion antes de actualizar Streamlit: hay que
revisar sobre todo la vista 3D y la intro satelital, que dependen de cuando se vuelve a ejecutar cada guion.
"""
import os

import streamlit as st
import streamlit.components.v1 as components

USAR_IFRAME = os.environ.get("Y2K_IFRAME") == "1"


def inyectar(html):
    """Ejecuta `html` (uno o varios <script>) en un iframe invisible del mismo origen que la pagina."""
    if USAR_IFRAME:
        st.iframe(html, height=1)
    else:
        components.html(html, height=0)
