"""Recorrido completo de la app, como lo haria un usuario, contra el IDEAM simulado: acceso, Parametros, mapa,
descarga, ZIP y detener a medias."""
import io
import zipfile

from .conftest import CLAVE, abrir, ir_al_mapa_con_area, marco_mapa


def _zip_descargado(pagina, boton):
    with pagina.expect_download() as descarga:
        pagina.locator(f".st-key-{boton} button").click()
    with open(descarga.value.path(), "rb") as f:
        return descarga.value.suggested_filename, zipfile.ZipFile(io.BytesIO(f.read()))


def test_acceso_rechaza_la_clave_mala(navegador, servidor):
    pagina = navegador.new_page()
    pagina.goto(servidor)
    pagina.fill("input[type=password]", "no-es-la-clave")
    pagina.keyboard.press("Enter")
    pagina.wait_for_timeout(1500)
    assert pagina.locator(".st-key-ir_mapa").count() == 0
    pagina.fill("input[type=password]", CLAVE)
    pagina.keyboard.press("Enter")
    pagina.wait_for_selector(".st-key-ir_mapa button")
    pagina.context.close()


def test_parametros_muestra_pasos_y_atajos(pagina):
    tarjeta = pagina.locator(".st-key-y2k_inicio")
    texto = tarjeta.inner_text()
    for esperado in ("Parámetros", "Área y estaciones", "Descarga", "Variable", "Últimos 10 años", "Todo"):
        assert esperado in texto
    assert tarjeta.locator(".y2k-pasos [aria-current]").inner_text().strip().endswith("Parámetros")
    campo = '.st-key-y2k_inicio [data-testid="stDateInput"] input'
    antes = pagina.locator(campo).first.input_value()
    pagina.locator(".st-key-atajo_10 button").click()
    pagina.wait_for_function("([c, v]) => document.querySelector(c).value !== v", arg=[campo, antes])


def test_descarga_completa_y_zip(pagina):
    ir_al_mapa_con_area(pagina)
    panel = pagina.locator(".st-key-y2k_cuerpo").inner_text()
    assert "Cobertura estimada" in panel and "Estaciones con datos" in panel

    pagina.locator(".st-key-preparar button:visible").first.click()
    pagina.wait_for_selector(".st-key-bajar_zip", timeout=180000)
    exportar = pagina.locator(".st-key-y2k_exportar").inner_text()
    assert "Estaciones guardadas" in exportar and "Completitud real media" in exportar

    nombre, archivo = _zip_descargado(pagina, "bajar_zip")
    assert nombre.startswith("IDEAM_PTPM_CON_") and nombre.endswith(".zip")
    nombres = archivo.namelist()
    excel = [n for n in nombres if n.endswith(".xlsx")]
    assert excel and all("/" in n for n in excel)          # en carpetas por completitud
    assert any(n.endswith("resumen_descarga.csv") for n in nombres)
    assert any(n.endswith("CITACION.txt") for n in nombres)


def test_detener_entrega_lo_que_ya_bajo(pagina):
    ir_al_mapa_con_area(pagina)
    pagina.locator(".st-key-preparar button:visible").first.click()
    pagina.wait_for_selector(".y2k-prog-meta .ahora", timeout=30000)
    pagina.wait_for_timeout(1500)
    pagina.get_by_text("Detener la descarga").click()
    pagina.wait_for_selector(".st-key-bajar_parcial", timeout=30000)
    _, archivo = _zip_descargado(pagina, "bajar_parcial")
    resumen = next(n for n in archivo.namelist() if n.endswith("resumen_descarga.csv"))
    assert "Sin descargar" in archivo.read(resumen).decode("utf-8-sig")


def test_celular_llega_hasta_el_zip(navegador, servidor, celular):
    errores = []
    pagina = abrir(navegador, servidor, errores, **celular)
    ir_al_mapa_con_area(pagina)
    pagina.locator(".st-key-preparar button:visible").first.click()
    pagina.wait_for_selector(".st-key-bajar_zip", timeout=180000)
    pagina.context.close()
    assert not errores


def test_recargar_la_pagina_no_corta_la_descarga(pagina):
    ir_al_mapa_con_area(pagina)
    pagina.locator(".st-key-preparar button:visible").first.click()
    pagina.wait_for_selector(".y2k-prog-meta .ahora", timeout=30000)
    assert "descarga=" in pagina.url
    pagina.reload()
    pagina.wait_for_selector(".st-key-y2k_exportar .y2k-prog, .st-key-bajar_zip", timeout=60000)
    pagina.wait_for_selector(".st-key-bajar_zip", timeout=180000)
    _, archivo = _zip_descargado(pagina, "bajar_zip")
    assert any(n.endswith(".xlsx") for n in archivo.namelist())
    # la consulta sigue ahi: se puede volver al mapa y preparar otra descarga
    pagina.locator(".st-key-volver_mapa button").click()
    pagina.wait_for_selector(".st-key-preparar button:visible:not([disabled])", timeout=60000)


def test_ficha_de_la_estacion_y_escala_del_mapa(pagina):
    ir_al_mapa_con_area(pagina)
    marco = marco_mapa(pagina)
    # la escala va con los creditos, no suelta en la otra esquina
    marco.wait_for_selector(".leaflet-bottom.leaflet-right .leaflet-control-scale", state="attached", timeout=20000)
    assert marco.locator(".leaflet-bottom.leaflet-left .leaflet-control-scale").count() == 0
    pin = marco.evaluate("""() => { let r = null; map.eachLayer(l => {
        if (r || !l.options || l.options.y2k !== 'pin' || l.options.interactive === false || !l.getTooltip()) return;
        const p = map.latLngToContainerPoint(l.getLatLng());
        if (p.x > 300 && p.x < 900 && p.y > 250 && p.y < 650) r = [p.x, p.y]; }); return r; }""")
    pagina.mouse.click(*pin)
    pagina.wait_for_selector("[data-y2k-ficha-btn]", state="attached", timeout=20000)
    pagina.locator("[data-y2k-ficha-btn]").click()
    ficha = pagina.locator(".st-key-y2k_ficha")
    ficha.locator(".y2k-ficha .cifras b").first.wait_for(timeout=10000)
    cifras = ficha.locator(".y2k-ficha .cifras b").all_inner_texts()
    assert len(cifras) == 3 and cifras[0].endswith(" m") and cifras[1].endswith(" %"), cifras
    assert ficha.locator(".y2k-ficha .id .cod").inner_text().isdigit()
    # la ✕ de la pildora quita la seleccion (su boton va oculto)
    pagina.locator("[data-y2k-ficha-quitar]").click()
    pagina.wait_for_selector("[data-y2k-ficha-btn]", state="detached", timeout=20000)
