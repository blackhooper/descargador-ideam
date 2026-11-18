"""Herramientas del modo desarrollador.

Cada herramienta nueva se agrega a HERRAMIENTAS como (nombre, funcion_que_dibuja). Solo se ven en modo desarrollador;
el modo cliente no las carga.
"""
import streamlit as st

from modules.idioma import tr

from modules import herramienta_aforos



def _estudio_hidrologico():
    # Se importa al abrirla: carga pysheds, rasterio y scipy, que el resto de la app no necesita
    from estudio import pagina
    pagina.pantalla()


HERRAMIENTAS = [("Aforos y perfiles", herramienta_aforos.pantalla),
                ("Estudio hidrológico", _estudio_hidrologico)]   # [(nombre, funcion)]


def pantalla():
    st.subheader(tr("Herramientas"))
    if not HERRAMIENTAS:
        st.info(tr("Aún no hay herramientas. Aquí irán apareciendo las nuevas, antes de pasar al modo cliente."))
        return
    nombre = st.segmented_control(tr("Herramienta"), [n for n, _ in HERRAMIENTAS], default=HERRAMIENTAS[0][0],
                                  key="herramienta_activa", required=True)
    dict(HERRAMIENTAS)[nombre]()
