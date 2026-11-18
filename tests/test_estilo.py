"""Hojas de estilo y guiones del navegador (`modules/recursos/`), que `modules/estilo.py` lee al arrancar."""
import re

from modules import estilo, idioma

HOJAS = ("CSS", "CSS_MEDIO", "CSS_MOVIL", "CSS_SELLO_MOVIL", "CSS_ESTRECHO", "CSS_ANGOSTO", "CSS_BAJO", "CSS_ALTO",
         "CSS_LITE", "CSS_MOVIMIENTO", "CSS_FORZADOS")


def test_las_hojas_estan_y_cierran_sus_llaves():
    for nombre in HOJAS:
        hoja = getattr(estilo, nombre)
        assert hoja.strip(), nombre
        assert hoja.count("{") == hoja.count("}"), f"{nombre}: llaves sin cerrar"


def test_no_quedan_marcas_sin_cambiar():
    todo = estilo._vidrio("".join(getattr(estilo, n) for n in HOJAS))
    assert not re.findall(r"__[A-Z_]+__", todo)


def test_ninguna_hoja_tiene_forma_de_etiqueta():
    # Streamlit sanea el bloque de estilos y lo descarta entero si encuentra algo como una etiqueta HTML; aplicar()
    # escapa los "<", pero un "</style>" escrito en una hoja cerraria el bloque antes
    for nombre in HOJAS:
        assert "</" not in getattr(estilo, nombre), nombre


def test_el_guion_lleva_sus_marcas_y_sus_textos_en_ingles():
    for marca in ("__V__", "__ICONO_ALERTA__", "__MOVIL__", "__VIDRIO__"):
        assert marca in estilo._UI, marca
    assert "__TEMA__" in estilo._SINCRONIZAR_TEMA
    # cada texto del guion con traduccion (idioma.JS_EN) sigue escrito igual en el guion
    perdidos = [es for es, _ in idioma.JS_EN if es not in estilo._UI]
    assert not perdidos, f"Textos de idioma.JS_EN que ya no estan en recursos/ui.js: {perdidos}"
