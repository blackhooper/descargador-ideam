"""Traducciones de la interfaz (`modules/idioma.py`): todo texto de `tr()` tiene su entrada en ingles, ninguna
entrada sobra ni se repite y los huecos {asi} coinciden en los dos idiomas."""
import ast
import glob
import os
import re

from modules import idioma

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FUENTES = [os.path.join(RAIZ, "app.py")] + sorted(glob.glob(os.path.join(RAIZ, "modules", "*.py")))

# Entradas que no estan escritas tal cual en el codigo: llegan de los datos del IDEAM (frecuencias, en minusculas)
# o se arman juntando trozos. Si se agrega otra asi, va aqui con su motivo.
COMPUESTAS = {
    # frecuencia del parametro, tal como la da el IDEAM (app._frecuencia_txt)
    "anual", "mensual", "decadal", "multianual", "minutal", "3 veces al día", "2 veces al día",
    "cada 10 minutos", "cada 5 minutos", "cada 05 minutos", "cada 02 minutos", "cada 2 minutos",
    # estilo: "Rango de…" con la palabra cambiada por "Escala"
    "Escala de la zona", "Escala de Colombia",
    # ideam_downloader.error_acceso: el mensaje mas el aviso final
    "El portal del IDEAM rechazó el acceso de la herramienta. Lo más probable es que el portal haya cambiado su "
    "forma de acceso y el Descargador necesite actualizarse. Si el problema continúa, la herramienta necesita una "
    "actualización.",
    "No se pudo acceder al portal del IDEAM. Si el problema continúa, la herramienta necesita una actualización.",
}


def _arbol(ruta):
    with open(ruta, encoding="utf-8") as f:
        return ast.parse(f.read())


def _textos_de_tr():
    """{texto: "archivo:linea"} de cada tr("…") escrito con un texto fijo."""
    textos = {}
    for ruta in FUENTES:
        for nodo in ast.walk(_arbol(ruta)):
            if (isinstance(nodo, ast.Call) and getattr(nodo.func, "id", getattr(nodo.func, "attr", None)) == "tr"
                    and nodo.args and isinstance(nodo.args[0], ast.Constant) and isinstance(nodo.args[0].value, str)):
                textos.setdefault(nodo.args[0].value, f"{os.path.relpath(ruta, RAIZ)}:{nodo.lineno}")
    return textos


def _textos_del_codigo():
    """Todos los textos fijos del codigo (menos el diccionario): un texto puede pasar a tr() dentro de una variable."""
    textos = set()
    for ruta in FUENTES:
        if os.path.basename(ruta) != "idioma.py":
            textos |= {n.value for n in ast.walk(_arbol(ruta)) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    return textos


def test_todo_texto_de_tr_tiene_traduccion():
    faltan = {t: donde for t, donde in _textos_de_tr().items() if t not in idioma.EN}
    assert not faltan, "Textos sin entrada en idioma.EN:\n" + "\n".join(f"  {d}  {t!r}" for t, d in faltan.items())


def test_ninguna_entrada_sobra():
    codigo = _textos_del_codigo()
    sobran = [t for t in idioma.EN if t not in codigo and t not in COMPUESTAS]
    assert not sobran, "Entradas de idioma.EN que el codigo ya no usa:\n" + "\n".join(f"  {t!r}" for t in sobran)
    assert not [t for t in COMPUESTAS if t not in idioma.EN], "COMPUESTAS nombra entradas que ya no existen"


def test_ninguna_entrada_se_repite():
    ruta = os.path.join(RAIZ, "modules", "idioma.py")
    diccionario = next(n.value for n in ast.walk(_arbol(ruta))
                       if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "EN")
    claves = [k.value for k in diccionario.keys]
    repetidas = sorted({k for k in claves if claves.count(k) > 1})
    assert not repetidas, f"Entradas repetidas en idioma.EN: {repetidas}"


def test_los_huecos_coinciden_en_los_dos_idiomas():
    huecos = lambda texto: sorted(re.findall(r"\{(\w+)\}", texto))   # noqa: E731
    distintos = {es: en for es, en in idioma.EN.items() if huecos(es) != huecos(en)}
    assert not distintos, f"Huecos {{asi}} distintos entre el español y el inglés: {distintos}"


def test_tr_llena_los_huecos_y_cae_al_espanol():
    assert idioma.tr("de {n}", n=3) == "de 3"
    assert idioma.tr("Texto que no existe") == "Texto que no existe"
