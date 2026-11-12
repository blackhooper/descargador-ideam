"""Enlaces de la documentacion: los archivos y los apartados a los que apuntan el README y `documentacion/` existen."""
import os
import re

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCUMENTOS = ["README.md", "documentacion/ARQUITECTURA.md", "documentacion/ESTILO.md"]


def _texto(ruta):
    with open(os.path.join(RAIZ, ruta), encoding="utf-8") as f:
        return f.read()


def _anclas(ruta):
    """Anclas de los titulos, como las arma GitHub: minusculas, sin puntuacion y con guiones por espacios."""
    anclas = set()
    for titulo in re.findall(r"^#{1,6}\s+(.+?)\s*$", _texto(ruta), flags=re.M):
        limpio = re.sub(r"[^\w\- ]", "", titulo.lower(), flags=re.UNICODE)
        anclas.add(limpio.replace(" ", "-"))
    return anclas


def test_los_enlaces_internos_llevan_a_algo_que_existe():
    rotos = []
    for doc in DOCUMENTOS:
        sin_codigo = re.sub(r"```.*?```", "", _texto(doc), flags=re.S)
        for destino in re.findall(r"\]\(([^)\s]+)\)", sin_codigo):
            if re.match(r"[a-z]+:", destino):          # http:, https:, mailto:
                continue
            archivo, _, ancla = destino.partition("#")
            ruta = os.path.normpath(os.path.join(os.path.dirname(doc), archivo)) if archivo else doc
            if not os.path.exists(os.path.join(RAIZ, ruta)):
                rotos.append(f"{doc}: no existe {destino}")
            elif ancla and ruta.endswith(".md") and ancla not in _anclas(ruta):
                rotos.append(f"{doc}: no hay apartado {destino}")
    assert not rotos, "Enlaces rotos:\n" + "\n".join(rotos)


def test_los_archivos_que_nombra_la_tabla_de_arquitectura_existen():
    tabla = re.findall(r"^\| ((?:`[^`]+`(?:, )?)+) \|", _texto("documentacion/ARQUITECTURA.md"), flags=re.M)
    nombrados = [n for celda in tabla for n in re.findall(r"`([^`]+)`", celda)
                 if "/" in n or n.endswith((".py", ".js", ".html"))]
    assert nombrados
    # algunos van solo con su nombre (estan junto al anterior de la misma celda): vale si el archivo esta en el repo
    en_repo = {f for carpeta, _, archivos in os.walk(RAIZ) if ".git" not in carpeta for f in archivos}
    faltan = [n for n in nombrados if not os.path.exists(os.path.join(RAIZ, n)) and os.path.basename(n) not in en_repo]
    assert not faltan, f"ARQUITECTURA.md nombra archivos que no existen: {faltan}"
