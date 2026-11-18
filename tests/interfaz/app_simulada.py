"""La app de verdad (`app.py`, sin cambios) contra el IDEAM simulado. Para verla a mano, desde la raiz del repo:

    streamlit run tests/interfaz/app_simulada.py --secrets.files tests/interfaz/secretos_prueba.toml

Clave de acceso de prueba: `cliente-prueba`.
"""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

from tests.interfaz import ideam_simulado  # noqa: E402

ideam_simulado.instalar()
with open(os.path.join(RAIZ, "app.py"), encoding="utf-8") as _f:
    exec(compile(_f.read(), "app.py", "exec"))
