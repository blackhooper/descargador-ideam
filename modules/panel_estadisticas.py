import datetime
import re
from functools import partial
from html import escape
import pandas as pd
import streamlit as st
from modules import ideam_downloader
from modules.calidad import CLASES_CALIDAD, clasificar_calidad
from modules.estilo import detalles, ficha_pildora, kpis, md
from modules.terreno import ALTITUD_DUDOSA_M

# ===========================================================================
# TABLERO DE CALIDAD (panel de la pantalla del mapa) Y FICHA DE LA ESTACION
# Tres cifras (estaciones encontradas, cobertura media y tamano del ZIP con el
# tiempo aproximado), un aviso de altitud dudosa y la lista de estaciones con
# casillas para quitar o volver a incluir cada una en la descarga.
# ===========================================================================


def _num(n):
    return f"{n:,.0f}".replace(",", ".")


# Tamano del ZIP: cada registro probable ocupa unos 17 bytes ya comprimido y cada Excel suma unos 33 kB de logo,
# estilos y encabezado. Medido el 2026-10-09 con descargas reales de precipitacion diaria (PTPM_CON, 2 estaciones,
# de 1 a 45 años, una y dos consultas por estacion): el error quedo entre -6 % y +3 % (con 50 B y 30 kB era de +26 %
# a +178 %). Como el registro probable no descuenta los huecos, con estaciones de muchos faltantes sobreestima
BYTES_POR_REGISTRO = 17
BYTES_POR_EXCEL = 33_000


def duracion_aprox(segundos):
    """Duracion estimada corta: "40 s aprox.", "3 min 20 s aprox.", "1 h 05 min aprox."."""
    return f"{ideam_downloader.duracion_texto(max(5, segundos))} aprox."


def peso_zip(registros, n_estaciones):
    """Bytes aproximados del ZIP (Excel por estacion, resumen y cita)."""
    return registros * BYTES_POR_REGISTRO + n_estaciones * BYTES_POR_EXCEL + 2_000


def tamano_txt(n_bytes):
    """Tamano legible: "850 kB", "2,4 MB", "68 MB", "1,3 GB"."""
    if n_bytes < 1_000_000:
        return f"{max(1, round(n_bytes / 1000))} kB"
    if n_bytes < 10_000_000:
        return f"{n_bytes / 1_000_000:.1f} MB".replace(".", ",")
    if n_bytes < 1_000_000_000:
        return f"{round(n_bytes / 1_000_000)} MB"
    return f"{n_bytes / 1_000_000_000:.1f} GB".replace(".", ",")


def registros_txt(n):
    """Cifra corta para muchos registros: 1,2 M · 48 k · 950."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f} M".replace(".", ",")
    if n >= 100_000:
        return f"{round(n / 1000)} k"
    return _num(n)


def _bloques_de(estaciones_df, fecha_ini, fecha_fin, param):
    """Cuantas consultas al IDEAM hacen falta para descargar esas estaciones."""
    total = 0
    for _, row in estaciones_df.iterrows():
        total += len(ideam_downloader.bloques_de(
            param, fecha_ini, fecha_fin,
            ideam_downloader.a_fecha(row.get("Inicio serie")),
            ideam_downloader.a_fecha(row.get("Fin serie")),
        ))
    return total


def cifras_seleccion(seleccion, param, fecha_ini, fecha_fin):
    """Consultas, tiempo estimado y registros probables de la seleccion."""
    bloques = _bloques_de(seleccion, fecha_ini, fecha_fin, param)
    datos = int(seleccion["Cantidad Probable"].sum()) if len(seleccion) else 0
    return {"bloques": bloques, "datos": datos,
            "segundos": ideam_downloader.estimar_segundos(bloques, datos, len(seleccion))}


def _nombre_limpio(nombre):
    return re.sub(r"\s*\[\d+\]\s*$", "", str(nombre)).strip()


def tabla_lista(descargables):
    """Lista de las estaciones que se pueden descargar (mejor cobertura primero): codigo, punto de color de su
    clase, nombre (con ⚠ si la altitud es dudosa) y cobertura."""
    columnas = ["Código", "●", "Estación", "Cobertura", "color"]
    if descargables is None or descargables.empty:
        return pd.DataFrame(columns=columnas)
    dudosa = (descargables["altitud_dudosa"].fillna(False).astype(bool) if "altitud_dudosa" in descargables.columns
              else pd.Series(False, index=descargables.index))
    t = pd.DataFrame({
        "Código": [ideam_downloader.codigo_de_estacion(r, i) for i, r in descargables.iterrows()],
        "●": "●",
        "Estación": [_nombre_limpio(n) + (" ⚠" if d else "") for n, d in zip(descargables["nombre"], dudosa)],
        "Cobertura": pd.to_numeric(descargables["Porcentaje (%)"], errors="coerce").values,
        "color": [clasificar_calidad(p)["color"] for p in descargables["Porcentaje (%)"]],
    })
    return t.sort_values(["Cobertura", "Código"], ascending=[False, True]).reset_index(drop=True)[columnas]


def tabla_dudosas(zona):
    """Estaciones cuya altitud del catalogo no cuadra con el relieve, de la mayor diferencia a la menor."""
    columnas = ["Código", "Estación", "Catálogo", "Terreno", "Diferencia"]
    if zona is None or zona.empty or "altitud_dudosa" not in zona.columns:
        return pd.DataFrame(columns=columnas)
    d = zona[zona["altitud_dudosa"].fillna(False).astype(bool)]
    t = pd.DataFrame({
        "Código": [ideam_downloader.codigo_de_estacion(r, i) for i, r in d.iterrows()],
        "Estación": [_nombre_limpio(n) for n in d["nombre"]],
        "Catálogo": pd.to_numeric(d["altitud"], errors="coerce").values,
        "Terreno": pd.to_numeric(d["terreno"], errors="coerce").values,
    })
    t["Diferencia"] = t["Catálogo"] - t["Terreno"]
    return t.reindex(t["Diferencia"].abs().sort_values(ascending=False).index).reset_index(drop=True)[columnas]


def _explicacion_altitud(altitud, terreno, rango):
    """Frase que compara la altitud del catalogo con el relieve real."""
    diferencia = altitud - terreno
    texto = (f"Según el relieve, el terreno en ese punto está a <b>{_num(terreno)} m</b>, pero el catálogo del IDEAM "
             f"sitúa la estación a <b>{_num(altitud)} m</b>: <b>{_num(abs(diferencia))} m más "
             f"{'arriba' if diferencia > 0 else 'abajo'}</b>.")
    if rango:
        minimo, maximo = rango
        if altitud < minimo - ALTITUD_DUDOSA_M:
            texto += (f" En toda la zona el terreno va de {_num(minimo)} a {_num(maximo)} m, así que esa altitud "
                      f"no es posible aquí.")
        elif altitud > maximo + ALTITUD_DUDOSA_M:
            texto += (f" En toda la zona el terreno llega como máximo a {_num(maximo)} m, así que esa altitud "
                      f"no es posible aquí.")
        else:
            texto += (f" En toda la zona el terreno va de {_num(minimo)} a {_num(maximo)} m, así que la altitud "
                      f"podría ser correcta y el error estar en las coordenadas de la estación.")
    return texto


def _ver_en_3d():
    st.session_state["vista"] = "3D"
    st.session_state["_orbitar"] = True


def _al_elegir_dudosa():
    """Al elegir una fila de la lista de altitudes dudosas: se selecciona y se muestra en el 3D.
    Va en un callback porque cambia la vista antes de que se dibuje el selector 2D/3D."""
    filas = ((st.session_state.get("tabla_dudosas") or {}).get("selection") or {}).get("rows", [])
    codigos = st.session_state.get("_dudosas_codigos", [])
    if filas and filas[0] < len(codigos):
        st.session_state["estacion_sel"] = str(codigos[filas[0]])
        _ver_en_3d()


def _quitar_seleccion():
    st.session_state["estacion_sel"] = None


def _al_marcar(clave, codigos):
    """Casillas de la lista: las filas marcadas se descargan; las demas quedan excluidas. Un clic en una celda
    selecciona la estacion (ficha y mapa)."""
    ss = st.session_state
    sel = (ss.get(clave) or {}).get("selection") or {}
    marcadas = set(sel.get("rows", []))
    otras = set(ss.get("excluidas", set())) - set(codigos)   # exclusiones de estaciones que hoy no estan en la lista
    ss.excluidas = otras | {c for i, c in enumerate(codigos) if i not in marcadas}
    celdas = sel.get("cells") or []
    if celdas and celdas[0][0] < len(codigos) and str(codigos[celdas[0][0]]) != ss.get("estacion_sel"):
        ss.estacion_sel = str(codigos[celdas[0][0]])
        ss._centrar = True   # el mapa va a la estacion elegida


def _incluir(codigo):
    """Interruptor de la ficha: incluir o quitar la estacion de la descarga (la lista se rehace con el cambio)."""
    ss = st.session_state
    excl = set(ss.get("excluidas", set()))
    if ss.get(f"incluir_{codigo}"):
        excl.discard(codigo)
    else:
        excl.add(codigo)
    ss.excluidas = excl
    ss.version_lista = ss.get("version_lista", 0) + 1


def tarjeta_seleccionada(fila, rango=None, vista="2D", descargable=False):
    """Ficha flotante de la estacion elegida (desde el mapa o la lista)."""
    codigo = str(ideam_downloader.codigo_de_estacion(fila))
    try:
        altitud = _num(float(fila.get("altitud"))) + " m"
    except (TypeError, ValueError):
        altitud = "altitud sin dato"
    zona = "en el área" if fila.get("zona") == "cuenca" else "en el buffer"
    # cerrada: una pildora con el nombre; al pulsarla se despliega el resto (estilo.ficha_pildora)
    ficha_pildora(_nombre_limpio(fila.get("nombre", "")), codigo)
    with st.container(key="y2k_ficha_cuerpo"):   # se desplaza el cuerpo, no el vidrio
        _cuerpo_ficha(fila, codigo, altitud, zona, rango, vista, descargable)


def _cuerpo_ficha(fila, codigo, altitud, zona, rango, vista, descargable):
    ss = st.session_state
    md(f'<p class="y2k-ficha-dato">Código {escape(codigo)} · {altitud} · {zona}</p>')
    serie = fila.get("Serie DHIME") if "Serie DHIME" in fila.index else None
    if serie == "Sí":
        st.caption(f"Cobertura **{fila['Porcentaje (%)']:.0f} %** ({str(fila.get('Clase calidad', '')).lower()}) · "
                   f"serie {str(fila.get('Inicio serie'))[:4]}–{str(fila.get('Fin serie'))[:4]}")
    elif serie == "No":
        st.caption("Sin serie de esta variable en DHIME")
    if descargable:
        ss[f"incluir_{codigo}"] = codigo not in ss.get("excluidas", set())
        st.toggle("Incluir en la descarga", key=f"incluir_{codigo}", on_change=_incluir, args=(codigo,))
    if fila.get("altitud_dudosa") and fila.get("terreno") is not None:
        with st.container(key="alerta_ficha"), st.expander("Altitud dudosa · Ver detalles", icon=":material/warning:"):
            st.markdown(f'<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                        f'{_explicacion_altitud(float(fila["altitud"]), float(fila["terreno"]), rango)}'
                        f'{" En el mapa 3D, la marca naranja muestra dónde quedaría con la altitud del catálogo." if vista == "3D" else ""}'
                        f'</p>', unsafe_allow_html=True)
    with st.container(horizontal=True, gap="small"):
        if vista != "3D":
            st.button("Ver en 3D", key="ver_3d", icon=":material/landscape:", width="stretch", on_click=_ver_en_3d)
        st.button("Quitar selección", key="quitar_sel", icon=":material/close:", width="stretch", on_click=_quitar_seleccion)


def tablero(zona, descargables, seleccion, param, cifras, dudosas=None, rango=None):
    """Tablero de calidad: cifras, aviso de altitud dudosa y lista de estaciones con casillas."""
    ss = st.session_state
    n_sel, n_desc, n_zona = len(seleccion), len(descargables), len(zona)
    sin_info = n_zona - n_desc
    kpis([
        (n_zona, "Estaciones encontradas",
         f"{sin_info} {'estaciones' if sin_info != 1 else 'estación'} sin información" if sin_info else "Todas con información",
         f"Estaciones del IDEAM en el área y el buffer. {n_desc} tienen datos de esta variable en el periodo."),
        (f"{seleccion['Porcentaje (%)'].mean():.0f} %" if n_sel else "–", "Cobertura media del periodo", "",
         "Promedio de la cantidad probable de las estaciones seleccionadas: qué parte del periodo consultado cubre su "
         "registro (no descuenta los huecos internos)."),
        (f"≈ {tamano_txt(peso_zip(cifras['datos'], n_sel))}" if n_sel else "–", "Tamaño del ZIP",
         duracion_aprox(cifras["segundos"]) if n_sel else "",
         f"Estimación para {n_sel} {'estaciones' if n_sel != 1 else 'estación'} y {registros_txt(cifras['datos'])} "
         f"registros probables. La descarga hace {cifras['bloques']} consultas al IDEAM "
         + ("(una por estación: la serie multianual se pide de una vez)." if param["frecuencia"] == "Multianual"
            else f"de hasta {param['dias_bloque']} días.")),
    ])

    # Estaciones cuya altitud del catalogo no cuadra con el relieve real: una linea ambar; el detalle adentro
    if dudosas is not None and len(dudosas):
        ss["_dudosas_codigos"] = list(dudosas["Código"])
        n = len(dudosas)
        peor = dudosas.iloc[0]
        rango_txt = f"En esta zona el relieve va de <b>{_num(rango[0])} a {_num(rango[1])} m</b>. " if rango else ""
        with st.container(key="alerta_altura"), st.expander(
                f"{n} {'estaciones' if n != 1 else 'estación'} con altitud dudosa", icon=":material/warning:"):
            st.markdown(
                f'<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                f'En el catálogo, su altitud difiere en más de {ALTITUD_DUDOSA_M} m del relieve en su punto. {rango_txt}'
                f'La mayor diferencia es la de <b>{escape(peor["Estación"])}</b>: el catálogo indica {_num(peor["Catálogo"])} m '
                f'y el relieve, {_num(peor["Terreno"])} m. Elige una fila para verla en el mapa 3D.</p>', unsafe_allow_html=True)
            st.dataframe(
                dudosas, hide_index=True, width="stretch", key="tabla_dudosas",
                on_select=_al_elegir_dudosa, selection_mode="single-row",
                column_order=["Estación", "Catálogo", "Terreno", "Diferencia"],
                column_config={"Catálogo": st.column_config.NumberColumn(format="%d m"),
                               "Terreno": st.column_config.NumberColumn("Relieve", format="%d m"),
                               "Diferencia": st.column_config.NumberColumn(format="%+d m", help="Catálogo menos relieve")})

    if param.get("avanzado") and n_sel:
        detalles(f"Serie de alta frecuencia: {cifras['bloques']} consultas al IDEAM.",
                 f"<p>El IDEAM entrega estas series de a {param['dias_bloque']} días por consulta "
                 f"(≈ {cifras['bloques'] // max(1, n_sel)} por estación), así que la descarga tarda más.</p>", ver="Ver más")

    # Lista con casillas: marcada = se descarga. Un clic en el nombre selecciona la estacion
    tabla = tabla_lista(descargables)
    codigos = list(tabla["Código"])
    excluidas = set(ss.get("excluidas", set()))
    md(f'<div class="y2k-lista-cab"><span>Estaciones a descargar</span>'
       f'<span><b>{n_sel}</b> de {n_desc}</span></div>')
    clave = f"lista_{abs(hash(tuple(codigos))) % 10 ** 8}_{ss.get('version_lista', 0)}"
    colores = tabla["color"].tolist()
    vista = tabla.drop(columns=["color"]).style.apply(
        lambda col: [f"color: {c}" for c in colores], subset=["●"]).format({"Cobertura": "{:.0f} %"})
    st.dataframe(
        vista, hide_index=True, width="stretch", height=min(38 + 35 * max(1, len(tabla)), 330), key=clave,
        on_select=partial(_al_marcar, clave, codigos), selection_mode=["multi-row", "single-cell"],
        selection_default={"selection": {"rows": [i for i, c in enumerate(codigos) if c not in excluidas]}},
        column_order=["●", "Estación", "Cobertura"],
        column_config={
            "●": st.column_config.TextColumn("", width=28, help="Color de su clase de cobertura (ver la leyenda)"),
            "Estación": st.column_config.TextColumn(width=176),
            "Cobertura": st.column_config.TextColumn(width=66, help="Cantidad probable: qué parte del periodo cubre el "
                                                                     "registro de la estación"),
        },
    )
    en_cuenca = int((seleccion["zona"] == "cuenca").sum()) if "zona" in seleccion.columns else n_sel
    fines = pd.to_datetime(seleccion["Fin serie"], errors="coerce")
    activas = int((fines >= pd.Timestamp(datetime.date.today() - datetime.timedelta(days=365))).sum())
    st.caption(f"{en_cuenca} en el área{f' · {n_sel - en_cuenca} en el buffer' if n_sel - en_cuenca else ''} · "
               f"{activas} con datos en el último año")
    detalles("Los datos recientes pueden ser preliminares.",
             "<p>Cada dato del IDEAM tiene un nivel de aprobación (preliminar, en revisión o definitivo); los "
             "preliminares pueden cambiar. Cada Excel lo indica en la columna «Nivel de Aprobación».</p>",
             ver="Ver más")


def reparto_cobertura(colores):
    """[(nombre de la clase, n, color)] a partir de los colores de las estaciones guardadas."""
    return [(nombre, sum(1 for c in colores if c.lower() == color.lower()), color)
            for _, nombre, _, _, color in CLASES_CALIDAD]
