import datetime
import re
from functools import partial
from html import escape
import pandas as pd
import streamlit as st
from modules import idioma, ideam_downloader
from modules.calidad import CLASES_CALIDAD, clasificar_calidad
from modules.estilo import detalles, ficha_pildora, kpis, md
from modules.idioma import tr
from modules.terreno import ALTITUD_DUDOSA_M

# ===========================================================================
# TABLERO DE CALIDAD (panel de la pantalla del mapa) Y FICHA DE LA ESTACION
# Tres cifras (estaciones encontradas, cobertura media y tamano del ZIP con el
# tiempo aproximado), un aviso de altitud dudosa y la lista de estaciones con
# casillas para quitar o volver a incluir cada una en la descarga.
# ===========================================================================


def _num(n):
    return idioma.num(n)


# Tamano del ZIP: cada registro probable ocupa unos 17 bytes ya comprimido y cada Excel suma unos 33 kB de logo,
# estilos y encabezado. Medido el 2026-10-09 con descargas reales de precipitacion diaria (PTPM_CON, 2 estaciones,
# de 1 a 45 años, una y dos consultas por estacion): el error quedo entre -6 % y +3 % (con 50 B y 30 kB era de +26 %
# a +178 %). Como el registro probable no descuenta los huecos, con estaciones de muchos faltantes sobreestima
BYTES_POR_REGISTRO = 17
BYTES_POR_EXCEL = 33_000


def duracion_aprox(segundos):
    """Duracion estimada corta: "40 s aprox.", "3 min 20 s aprox.", "1 h 05 min aprox."."""
    return tr("{t} aprox.", t=ideam_downloader.duracion_texto(max(5, segundos)))


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
    texto = tr("Según el relieve, el terreno en ese punto está a <b>{t} m</b>, pero el catálogo del IDEAM sitúa la "
               "estación a <b>{a} m</b>: <b>{d} m más {lado}</b>.", t=_num(terreno), a=_num(altitud),
               d=_num(abs(diferencia)), lado=tr("arriba") if diferencia > 0 else tr("abajo"))
    if rango:
        minimo, maximo = rango
        if altitud < minimo - ALTITUD_DUDOSA_M:
            texto += tr(" En toda la zona el terreno va de {a} a {b} m, así que esa altitud no es posible aquí.",
                        a=_num(minimo), b=_num(maximo))
        elif altitud > maximo + ALTITUD_DUDOSA_M:
            texto += tr(" En toda la zona el terreno llega como máximo a {b} m, así que esa altitud no es posible "
                        "aquí.", b=_num(maximo))
        else:
            texto += tr(" En toda la zona el terreno va de {a} a {b} m, así que la altitud podría ser correcta y el "
                        "error estar en las coordenadas de la estación.", a=_num(minimo), b=_num(maximo))
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
        altitud = tr("altitud sin dato")
    zona = tr({"cuenca": "en el área", "buffer": "en el buffer"}.get(fila.get("zona"), ""))
    # cerrada: una pildora con el nombre; al pulsarla se despliega el resto (estilo.ficha_pildora)
    ficha_pildora(_nombre_limpio(fila.get("nombre", "")), codigo)
    with st.container(key="y2k_ficha_cuerpo"):   # se desplaza el cuerpo, no el vidrio
        _cuerpo_ficha(fila, codigo, altitud, zona, rango, vista, descargable)


def _cuerpo_ficha(fila, codigo, altitud, zona, rango, vista, descargable):
    ss = st.session_state
    md(f'<p class="y2k-ficha-dato">{tr("Código")} {escape(codigo)} · {altitud}{f" · {zona}" if zona else ""}</p>')
    serie = fila.get("Serie DHIME") if "Serie DHIME" in fila.index else None
    if serie == "Sí":
        st.caption(tr("Cobertura **{p} %** ({clase}) · serie {a}–{b}", p=f"{fila['Porcentaje (%)']:.0f}",
                      clase=tr(str(fila.get('Clase calidad', ''))).lower(),
                      a=str(fila.get('Inicio serie'))[:4], b=str(fila.get('Fin serie'))[:4]))
    elif serie == "No":
        st.caption(tr("Sin serie de esta variable en DHIME"))
    if descargable:
        ss[f"incluir_{codigo}"] = codigo not in ss.get("excluidas", set())
        st.toggle(tr("Incluir en la descarga"), key=f"incluir_{codigo}", on_change=_incluir, args=(codigo,))
    if fila.get("altitud_dudosa") and fila.get("terreno") is not None:
        with st.container(key="alerta_ficha"), st.expander(tr("Altitud dudosa · Ver detalles"), icon=":material/warning:"):
            st.markdown(f'<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                        f'{_explicacion_altitud(float(fila["altitud"]), float(fila["terreno"]), rango)}'
                        f'{tr(" En el mapa 3D, la marca naranja muestra dónde quedaría con la altitud del catálogo.") if vista == "3D" else ""}'
                        f'</p>', unsafe_allow_html=True)
    with st.container(horizontal=True, gap="small"):
        if vista != "3D":
            st.button(tr("Ver en 3D"), key="ver_3d", icon=":material/landscape:", width="stretch", on_click=_ver_en_3d)
        st.button(tr("Quitar selección"), key="quitar_sel", icon=":material/close:", width="stretch", on_click=_quitar_seleccion)


def tablero(zona, descargables, seleccion, param, cifras, dudosas=None, rango=None, ubicacion=None):
    """Tablero de calidad: cifras, aviso de altitud dudosa y lista de estaciones con casillas. `ubicacion`: texto
    del filtro ("Antioquia · Medellín") si las estaciones se eligieron por ubicacion en vez de con un area."""
    ss = st.session_state
    n_sel, n_desc, n_zona = len(seleccion), len(descargables), len(zona)
    sin_info = n_zona - n_desc
    kpis([
        (n_zona, tr("Estaciones encontradas"),
         tr("{n} {estaciones} sin información", n=sin_info,
            estaciones=tr("estaciones") if sin_info != 1 else tr("estación")) if sin_info
         else tr("Todas con información"),
         (tr("Estaciones con esta serie en {u}.", u=ubicacion) if ubicacion
          else tr("Estaciones del IDEAM en el área y el buffer."))
         + tr(" {n} tienen datos de esta variable en el periodo.", n=n_desc)),
        (f"{seleccion['Porcentaje (%)'].mean():.0f} %" if n_sel else "–", tr("Cobertura media del periodo"), "",
         tr("Promedio de la cantidad probable de las estaciones seleccionadas: qué parte del periodo consultado cubre "
            "su registro (no descuenta los huecos internos).")),
        (f"≈ {tamano_txt(peso_zip(cifras['datos'], n_sel))}" if n_sel else "–", tr("Tamaño del ZIP"),
         duracion_aprox(cifras["segundos"]) if n_sel else "",
         tr("Estimación para {n} {estaciones} y {r} registros probables. La descarga hace {b} consultas al IDEAM ",
            n=n_sel, estaciones=tr("estaciones") if n_sel != 1 else tr("estación"), r=registros_txt(cifras['datos']),
            b=cifras['bloques'])
         + (tr("(una por estación: la serie multianual se pide de una vez).") if param["frecuencia"] == "Multianual"
            else tr("de hasta {d} días.", d=param['dias_bloque']))),
    ])

    # Estaciones cuya altitud del catalogo no cuadra con el relieve real: una linea ambar; el detalle adentro
    if dudosas is not None and len(dudosas):
        ss["_dudosas_codigos"] = list(dudosas["Código"])
        n = len(dudosas)
        peor = dudosas.iloc[0]
        rango_txt = tr("En esta zona el relieve va de <b>{a} a {b} m</b>. ", a=_num(rango[0]), b=_num(rango[1])) \
            if rango else ""
        with st.container(key="alerta_altura"), st.expander(
                tr("{n} {estaciones} con altitud dudosa", n=n, estaciones=tr("estaciones") if n != 1 else tr("estación")),
                icon=":material/warning:"):
            st.markdown(
                '<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                + tr("En el catálogo, su altitud difiere en más de {m} m del relieve en su punto. ", m=ALTITUD_DUDOSA_M)
                + rango_txt
                + tr("La mayor diferencia es la de <b>{e}</b>: el catálogo indica {c} m y el relieve, {t} m. Elige una "
                     "fila para verla en el mapa 3D.", e=escape(peor["Estación"]), c=_num(peor["Catálogo"]),
                     t=_num(peor["Terreno"]))
                + '</p>', unsafe_allow_html=True)
            st.dataframe(
                dudosas, hide_index=True, width="stretch", key="tabla_dudosas",
                on_select=_al_elegir_dudosa, selection_mode="single-row",
                column_order=["Estación", "Catálogo", "Terreno", "Diferencia"],
                column_config={"Estación": st.column_config.TextColumn(tr("Estación")),
                               "Catálogo": st.column_config.NumberColumn(tr("Catálogo"), format="%d m"),
                               "Terreno": st.column_config.NumberColumn(tr("Relieve"), format="%d m"),
                               "Diferencia": st.column_config.NumberColumn(tr("Diferencia"), format="%+d m",
                                                                           help=tr("Catálogo menos relieve"))})

    if param.get("avanzado") and n_sel:
        detalles(tr("Serie de alta frecuencia: {b} consultas al IDEAM.", b=cifras['bloques']),
                 "<p>" + tr("El IDEAM entrega estas series de a {d} días por consulta (≈ {n} por estación), así que la "
                            "descarga tarda más.", d=param['dias_bloque'], n=cifras['bloques'] // max(1, n_sel))
                 + "</p>", ver="Ver más")

    # Lista con casillas: marcada = se descarga. Un clic en el nombre selecciona la estacion
    tabla = tabla_lista(descargables)
    codigos = list(tabla["Código"])
    excluidas = set(ss.get("excluidas", set()))
    md(f'<div class="y2k-lista-cab"><span>{tr("Estaciones a descargar")}</span>'
       f'<span><b>{n_sel}</b> {tr("de")} {n_desc}</span></div>')
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
            "●": st.column_config.TextColumn("", width=28, help=tr("Color de su clase de cobertura (ver la leyenda)")),
            "Estación": st.column_config.TextColumn(tr("Estación"), width=176),
            "Cobertura": st.column_config.TextColumn(tr("Cobertura"), width=66,
                                                     help=tr("Cantidad probable: qué parte del periodo cubre el "
                                                             "registro de la estación")),
        },
    )
    en_cuenca = int((seleccion["zona"] == "cuenca").sum()) if "zona" in seleccion.columns else n_sel
    fines = pd.to_datetime(seleccion["Fin serie"], errors="coerce")
    activas = int((fines >= pd.Timestamp(datetime.date.today() - datetime.timedelta(days=365))).sum())
    lugar = "" if ubicacion else (tr("{n} en el área", n=en_cuenca)
                                  + (tr(" · {n} en el buffer", n=n_sel - en_cuenca) if n_sel - en_cuenca else "") + " · ")
    st.caption(lugar + tr("{n} con datos en el último año", n=activas))
    detalles(tr("Los datos recientes pueden ser preliminares."),
             "<p>" + tr("Cada dato del IDEAM tiene un nivel de aprobación (preliminar, en revisión o definitivo); los "
                        "preliminares pueden cambiar. Cada Excel lo indica en la columna «Nivel de Aprobación».")
             + "</p>", ver="Ver más")


def reparto_cobertura(colores):
    """[(nombre de la clase, n, color)] a partir de los colores de las estaciones guardadas."""
    return [(tr(nombre), sum(1 for c in colores if c.lower() == color.lower()), color)
            for _, nombre, _, _, color in CLASES_CALIDAD]
