"""Arranca la app simulada y abre un navegador (Playwright) para recorrerla como un usuario.

Si Playwright no esta instalado, estas pruebas se saltan: `pip install playwright && playwright install chromium`.
"""
import mimetypes
import os
import re
import socket
import struct
import subprocess
import sys
import time
import urllib.request
import zlib

import pytest

playwright_sync = pytest.importorskip("playwright.sync_api", reason="Playwright no esta instalado")

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
CLAVE = "cliente-prueba"
# Carpeta opcional con paquetes de npm ya descomprimidos (<paquete>@<version>/package/...), para servir Leaflet y
# compania donde no hay salida a los CDN. En GitHub no hace falta.
CDN_LOCAL = os.environ.get("INTERFAZ_CDN_LOCAL")


def _png_liso(r, g, b):
    """PNG de un pixel de ese color (las teselas del mapa en las pruebas)."""
    def trozo(tipo, datos):
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos))
    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + trozo(b"IDAT", zlib.compress(bytes([0, r, g, b]))) + trozo(b"IEND", b""))


TESELA = _png_liso(120, 140, 110)


def _puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def servidor():
    """Direccion de la app simulada, ya arrancada."""
    puerto = _puerto_libre()
    proceso = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", os.path.join(AQUI, "app_simulada.py"),
         "--server.headless", "true", "--server.port", str(puerto), "--browser.gatherUsageStats", "false",
         "--secrets.files", os.path.join(AQUI, "secretos_prueba.toml")],
        cwd=RAIZ, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://localhost:{puerto}"
    try:
        for _ in range(120):
            try:
                urllib.request.urlopen(url + "/_stcore/health", timeout=1)
                break
            except Exception:
                if proceso.poll() is not None:
                    raise RuntimeError("La app simulada no arranco")
                time.sleep(.5)
        else:
            raise RuntimeError("La app simulada no respondio en un minuto")
        yield url
    finally:
        proceso.terminate()
        try:
            proceso.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proceso.kill()


@pytest.fixture(scope="session")
def playwright():
    with playwright_sync.sync_playwright() as p:
        yield p


@pytest.fixture(scope="session")
def navegador(playwright):
    ruta = os.environ.get("CHROMIUM")
    nav = playwright.chromium.launch(executable_path=ruta) if ruta else playwright.chromium.launch()
    yield nav
    nav.close()


@pytest.fixture(scope="session")
def celular(playwright):
    """Opciones de contexto de un iPhone 13 (pantalla, tactil y agente de usuario)."""
    opciones = dict(playwright.devices["iPhone 13"])
    opciones.pop("default_browser_type", None)
    return opciones


def _archivo_cdn(url):
    """Archivo local de un recurso de CDN (jsdelivr, unpkg, cdnjs, jquery), si esta en INTERFAZ_CDN_LOCAL."""
    def de(paquete, version, archivo):
        ruta = os.path.join(CDN_LOCAL, f"{paquete}@{version}".replace("/", "_"), "package", archivo)
        return ruta if os.path.isfile(ruta) else None
    m = re.search(r"(?:cdn\.jsdelivr\.net/npm|unpkg\.com)/((?:@[^/]+/)?[^@/]+)@([^/]+)/([^?]+)", url)
    if m:
        return de(*m.groups())
    m = re.search(r"cdnjs\.cloudflare\.com/ajax/libs/([^/]+)/([^/]+)/([^?]+)", url)
    if m:
        paquete = {"leaflet.draw": "leaflet-draw", "Leaflet.awesome-markers": "leaflet.awesome-markers"}.get(
            m.group(1), m.group(1))
        return de(paquete, m.group(2), "dist/" + m.group(3)) or de(paquete, "latest", "dist/" + m.group(3))
    m = re.search(r"code\.jquery\.com/jquery-([\d.]+)(\.min)?\.js", url)
    if m:
        return de("jquery", m.group(1), f"dist/jquery{m.group(2) or ''}.js")
    return None


def _sin_red(ruta):
    """Las teselas del mapa se cambian por una imagen lisa (rapido y sin depender de servidores ajenos). Lo demas
    sale a internet, salvo que haya copia local de los CDN."""
    url = ruta.request.url
    if re.search(r"terrarium|arcgisonline|tile\.openstreetmap|gibs|/tile/|\.png($|\?)|\.jpe?g($|\?)", url):
        return ruta.fulfill(body=TESELA, content_type="image/png")
    if CDN_LOCAL:
        archivo = _archivo_cdn(url)
        if archivo:
            return ruta.fulfill(path=archivo, content_type=mimetypes.guess_type(archivo)[0])
        return ruta.abort()
    return ruta.continue_()


def abrir(navegador, servidor, errores=None, **opciones):
    """Pagina nueva con la sesion ya iniciada, en Parametros y con las listas cargadas."""
    contexto = navegador.new_context(**({"viewport": {"width": 1440, "height": 900}} | opciones))
    contexto.route(lambda u: not u.startswith("http://localhost"), _sin_red)
    pagina = contexto.new_page()
    if errores is not None:
        pagina.on("pageerror", lambda e: errores.append(str(e)))
    pagina.goto(servidor + "/?tema=claro")
    pagina.fill("input[type=password]", CLAVE)
    pagina.keyboard.press("Enter")
    pagina.wait_for_selector(".st-key-ir_mapa button")
    pagina.wait_for_selector('.st-key-ir_mapa button[aria-disabled="false"]', timeout=60000)
    return pagina


@pytest.fixture
def pagina(navegador, servidor):
    errores = []
    p = abrir(navegador, servidor, errores)
    yield p
    p.context.close()
    assert not errores, f"Errores de JavaScript en la pagina: {errores[:3]}"


def marco_mapa(pagina):
    return next(f for f in pagina.frames if "streamlit_folium" in f.url)


def ir_al_mapa_con_area(pagina):
    """De Parametros al mapa, con el area visible (Bogota y alrededores) como zona de estudio."""
    pagina.click(".st-key-ir_mapa button")
    pagina.wait_for_selector('[data-y2k-menu="dibujo"]:visible', timeout=30000)
    pagina.wait_for_function("() => [...document.querySelectorAll('iframe')].some(f => /streamlit_folium/.test(f.src))")
    marco = marco_mapa(pagina)
    marco.wait_for_function("() => window.map && window.map.setView")
    marco.evaluate("() => window.map.setView([4.9, -74.0], 11, {animate: false})")
    pagina.wait_for_timeout(1200)
    pagina.locator('[data-y2k-menu="dibujo"]:visible').click()
    pagina.locator("[data-y2k-area]:visible").first.click()
    pagina.wait_for_selector(".st-key-preparar button:visible:not([disabled])", timeout=60000)
