import datetime
import re
from html import escape
import altair as alt
import pandas as pd
import streamlit as st
from modules import ideam_downloader
from modules.calidad import CLASES_CALIDAD
from modules.estilo import PALETAS, detalles, md
from modules.terreno import ALTITUD_DUDOSA_M

NARANJA_ALERTA = "#EC835A"


def _num(n):
    return f"{n:,.0f}".replace(",", ".")


def duracion_aprox(segundos):
    """Duracion estimada en palabras ("≈ 2 min"): el formato de reloj (01:54) se presta a confusion en una estimacion."""
    s = max(0, int(segundos))
    if s < 60:
        return "menos de 1 min"
    if s < 3600:
        return f"≈ {round(s / 60)} min"
    horas, minutos = divmod(round(s / 60), 60)
    return f"≈ {horas} h {minutos} min" if minutos else f"≈ {horas} h"


def _cifras(items):
    """Tarjetas de cifras 2x2 en HTML: a diferencia de st.metric, la etiqueta no se corta con '...'."""
    html = "".join(
        f'<div class="y2k-cifra" title="{escape(ayuda)}"><div class="l">{escape(etiqueta)}</div>'
        f'<div class="v">{escape(str(valor))}</div>{f"<div class=s>{escape(sub)}</div>" if sub else ""}</div>'
        for etiqueta, valor, sub, ayuda in items
    )
    st.html(f'<div class="y2k-cifras">{html}</div>')


def _bloques_de(estaciones_df, fecha_ini, fecha_fin, dias_bloque):
    """Cuantas consultas al IDEAM hacen falta para descargar esas estaciones."""
    total = 0
    for _, row in estaciones_df.iterrows():
        total += len(ideam_downloader.calcular_bloques(
            fecha_ini, fecha_fin,
            ideam_downloader.a_fecha(row.get("Inicio serie")),
            ideam_downloader.a_fecha(row.get("Fin serie")),
            dias_bloque,
        ))
    return total


def cifras_seleccion(seleccion, param, fecha_ini, fecha_fin):
    """Consultas, tiempo estimado y registros probables de la seleccion (lo usan el resumen y la isla de accion)."""
    bloques = _bloques_de(seleccion, fecha_ini, fecha_fin, param["dias_bloque"])
    datos = int(seleccion["Cantidad Probable"].sum())
    return {"bloques": bloques, "datos": datos,
            "segundos": ideam_downloader.estimar_segundos(bloques, datos, len(seleccion))}


def tabla_estaciones(seleccion):
    """Tabla de la lista (orden estable: mejor cantidad probable primero)."""
    if seleccion is None or seleccion.empty:
        return pd.DataFrame(columns=["Código", "Estación", "Altitud (m)", "Terreno (m)", "Alerta", "Cantidad probable"])
    dudosa = seleccion["altitud_dudosa"] if "altitud_dudosa" in seleccion.columns else pd.Series(False, index=seleccion.index)
    t = pd.DataFrame({
        "Código": [ideam_downloader.codigo_de_estacion(r, i) for i, r in seleccion.iterrows()],
        "Estación": seleccion["nombre"].astype(str).str.replace(r"\s*\[\d+\]\s*$", "", regex=True).str.strip().values,
        "Altitud (m)": pd.to_numeric(seleccion.get("altitud"), errors="coerce").values,
        "Terreno (m)": pd.to_numeric(seleccion["terreno"], errors="coerce").values if "terreno" in seleccion.columns else None,
        "Alerta": ["⚠" if d else "" for d in dudosa.fillna(False)],
        "Cantidad probable": seleccion["Porcentaje (%)"].values,
    })
    return t.sort_values(["Cantidad probable", "Código"], ascending=[False, True]).reset_index(drop=True)


def tabla_dudosas(zona):
    """Estaciones cuya altitud del catalogo no cuadra con el relieve, de la mayor diferencia a la menor."""
    columnas = ["Código", "Estación", "Catálogo", "Terreno", "Diferencia"]
    if zona is None or zona.empty or "altitud_dudosa" not in zona.columns:
        return pd.DataFrame(columns=columnas)
    d = zona[zona["altitud_dudosa"].fillna(False).astype(bool)]
    t = pd.DataFrame({
        "Código": [ideam_downloader.codigo_de_estacion(r, i) for i, r in d.iterrows()],
        "Estación": d["nombre"].astype(str).str.replace(r"\s*\[\d+\]\s*$", "", regex=True).str.strip().values,
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


def _grafica_clases(seleccion, paleta):
    filas = []
    for orden, (limite, nombre, rango, _, color) in enumerate(CLASES_CALIDAD):
        cantidad = int((seleccion["Clase calidad"] == nombre).sum())
        filas.append({"Clase": f"{nombre} ({rango})", "Estaciones": cantidad,
                      "Participación": cantidad / len(seleccion) if len(seleccion) else 0, "color": color, "orden": orden})
    datos = pd.DataFrame(filas)
    base = alt.Chart(datos).encode(
        y=alt.Y("Clase:N", sort=alt.SortField("orden"), title=None,
                axis=alt.Axis(labelLimit=220, ticks=False, domain=False, labelColor=paleta["tinta"])),
        x=alt.X("Estaciones:Q", title=None, scale=alt.Scale(domain=[0, max(1, datos["Estaciones"].max()) * 1.15], nice=False),
                axis=alt.Axis(labels=False, ticks=False, domain=False, grid=False)),
    )
    barras = base.mark_bar(cornerRadiusEnd=4, height=18).encode(
        color=alt.Color("color:N", scale=None, legend=None),
        tooltip=[alt.Tooltip("Clase:N"), alt.Tooltip("Estaciones:Q"),
                 alt.Tooltip("Participación:Q", format=".0%", title="De la selección")])
    etiquetas = base.mark_text(align="left", dx=6, fontSize=13, color=paleta["tinta_3"]).encode(text=alt.Text("Estaciones:Q", format="d"))
    # fondo transparente: la grafica se ve sobre el vidrio del panel
    return (barras + etiquetas).properties(height=4 * 30, background="transparent").configure_view(stroke=None)


def _grafica_altitud(tabla, seleccionada, paleta):
    """Un punto por estacion, de la mas baja a la mas alta. Clic = seleccionar. Triangulo naranja = altitud dudosa."""
    datos = tabla.dropna(subset=["Altitud (m)"]).sort_values("Altitud (m)").reset_index(drop=True)
    datos["Orden"] = range(1, len(datos) + 1)
    datos["Elegida"] = datos["Código"] == seleccionada
    datos["Dudosa"] = datos["Alerta"] != ""
    datos["Terreno"] = datos["Terreno (m)"].map(lambda v: f"{_num(v)} m" if pd.notna(v) else "sin dato")
    datos["Altitud dudosa"] = datos["Dudosa"].map({True: "Sí", False: "No"})
    minimo, maximo = datos["Altitud (m)"].min(), datos["Altitud (m)"].max()
    paso = 500 if maximo - minimo > 900 else 250 if maximo - minimo > 150 else 50
    dominio = [minimo // paso * paso, (-(-maximo // paso)) * paso if maximo > minimo else minimo + paso]
    punto = alt.selection_point(name="punto", fields=["Código"], on="click", empty=False)
    color = (alt.when(alt.datum.Elegida).then(alt.value(paleta["tinta"]))
             .when(alt.datum.Dudosa).then(alt.value(NARANJA_ALERTA))
             .otherwise(alt.value(paleta["acento"])))
    grafica = alt.Chart(datos).mark_point(filled=True, opacity=1, stroke=paleta["superficie"], strokeWidth=1.2).encode(
        x=alt.X("Orden:Q", title=None, axis=None, scale=alt.Scale(domain=[0.5, max(1.5, len(datos) + 0.5)])),
        y=alt.Y("Altitud (m):Q", title=None, scale=alt.Scale(domain=dominio, nice=False),
                axis=alt.Axis(values=list(range(int(dominio[0]), int(dominio[1]) + 1, paso)), grid=True,
                              gridColor=paleta["rejilla"], domain=False, ticks=False, labelColor=paleta["tinta_3"],
                              labelExpr="replace(format(datum.value, ',.0f'), ',', '.')")),
        size=alt.condition(alt.datum.Elegida, alt.value(240), alt.value(80)),
        # la altitud dudosa se distingue por la forma ademas del color
        shape=alt.condition(alt.datum.Dudosa, alt.value("triangle-up"), alt.value("circle")),
        color=color,
        tooltip=[alt.Tooltip("Estación:N"), alt.Tooltip("Altitud (m):Q", format=",.0f", title="Altitud del catálogo"),
                 alt.Tooltip("Terreno:N", title="Relieve"), alt.Tooltip("Altitud dudosa:N")],
    ).add_params(punto).properties(height=130, background="transparent").configure_view(stroke=None)
    return grafica, minimo, maximo


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


def tarjeta_seleccionada(fila, rango=None, vista="2D"):
    """Ficha flotante de la estacion elegida (desde el mapa, la lista o la grafica)."""
    try:
        altitud = _num(float(fila.get("altitud"))) + " m"
    except (TypeError, ValueError):
        altitud = "altitud sin dato"
    zona = "en la cuenca" if fila.get("zona") == "cuenca" else "en el buffer"
    nombre = re.sub(r"\s*\[\d+\]\s*$", "", str(fila.get("nombre", ""))).strip()   # el codigo va en la linea de abajo
    md(f'<div class="y2k-ficha-cab"><small>Estación seleccionada</small><b>{escape(nombre)}</b>'
       f'<span>{escape(str(ideam_downloader.codigo_de_estacion(fila)))} · {altitud} · {zona}</span></div>')
    serie = fila.get("Serie DHIME") if "Serie DHIME" in fila.index else None
    if serie == "Sí":
        st.caption(f"Cantidad probable **{fila['Porcentaje (%)']:.0f} %** (cobertura {str(fila.get('Clase calidad', '')).lower()}) · "
                   f"serie {str(fila.get('Inicio serie'))[:4]}–{str(fila.get('Fin serie'))[:4]}")
    elif serie == "No":
        st.caption("Sin serie de este parámetro en DHIME")
    if fila.get("altitud_dudosa") and fila.get("terreno") is not None:
        with st.container(key="alerta_ficha"), st.expander("Altitud dudosa · Ver detalles", icon=":material/warning:"):
            st.markdown(f'<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                        f'{_explicacion_altitud(float(fila["altitud"]), float(fila["terreno"]), rango)}'
                        f'{" En el mapa 3D, la marca naranja muestra dónde quedaría con la altitud del catálogo." if vista == "3D" else ""}'
                        f'</p>', unsafe_allow_html=True)
    with st.container(horizontal=True, gap="small"):
        if vista != "3D":
            st.button("Ver en 3D", key="ver_3d", icon=":material/landscape:", width="stretch", on_click=_ver_en_3d)
        st.button("Quitar selección", key="quitar_sel", icon=":material/close:", width="stretch",
                  on_click=_quitar_seleccion)


def mostrar_panel(zona, seleccion, param, fecha_ini, fecha_fin, umbral, seleccionada, tabla, tema="claro",
                  dudosas=None, rango=None, cifras=None):
    """Pestana "Resumen". tema: nombre de la paleta ("claro"/"oscuro") o la paleta ya resuelta (dict)."""
    paleta = tema if isinstance(tema, dict) else PALETAS.get(tema, PALETAS["claro"])
    if zona is None:
        st.html('<p class="y2k-hint">Marca tu cuenca para ver aquí el resumen.</p>')
        return
    if zona.empty:
        st.warning("No hay estaciones del IDEAM en esta zona. Activa o amplía el buffer.")
        return

    cifras = cifras or cifras_seleccion(seleccion, param, fecha_ini, fecha_fin)
    bloques, datos = cifras["bloques"], cifras["datos"]
    _cifras([
        ("Estaciones", len(seleccion), f"de {len(zona)} en la zona",
         f"Estaciones que se van a descargar, de {len(zona)} en la cuenca y el buffer"),
        ("Cobertura media", f"{seleccion['Porcentaje (%)'].mean():.0f} %" if len(seleccion) else "–", "del periodo",
         "Promedio de la cantidad probable: qué parte del periodo consultado cubre el registro de las estaciones "
         "que se van a descargar (no descuenta los huecos internos)"),
        ("Tiempo", duracion_aprox(cifras["segundos"]), f"{bloques} consultas",
         f"{bloques} consultas al IDEAM de hasta {param['dias_bloque']} días. Depende de la velocidad de respuesta "
         "del servidor del IDEAM."),
        ("Datos", f"{round(datos / 1000)}k" if datos >= 100_000 else _num(datos), "registros probables",
         "Registros que cabrían entre el primer y el último dato de cada estación dentro del periodo, según la "
         "frecuencia. No descuenta los datos faltantes."),
    ])
    # Nivel de aprobacion del dato (ver manual): mucho dato reciente sigue siendo preliminar
    detalles("Los datos recientes pueden ser preliminares.",
             "<p>Cada dato del IDEAM tiene un nivel de aprobación (preliminar, en revisión o definitivo); los "
             "preliminares pueden cambiar. Cada Excel lo indica en la columna «Nivel de Aprobación».</p>",
             ver="Nivel de aprobación")

    # Estaciones cuya altitud del catalogo no cuadra con el relieve real
    if dudosas is not None and len(dudosas):
        st.session_state["_dudosas_codigos"] = list(dudosas["Código"])
        codigos_sel = set(tabla["Código"])
        en_seleccion = int(dudosas["Código"].isin(codigos_sel).sum())
        peor = dudosas.iloc[0]
        n = len(dudosas)
        rango_txt = (f"En esta zona el relieve va de <b>{_num(rango[0])} a {_num(rango[1])} m</b>. " if rango else "")
        # Aviso de una linea; el detalle y la lista quedan adentro
        with st.container(key="alerta_altura"), st.expander(
                f"Altitud dudosa en {n} {'estaciones' if n != 1 else 'estación'} · Ver lista",
                icon=":material/warning:"):
            st.markdown(
                f'<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                f'{n} {"estaciones tienen" if n != 1 else "estación tiene"}'
                f'{f" ({en_seleccion} en la descarga)" if en_seleccion else ""} en el catálogo una altitud que difiere en '
                f'más de {ALTITUD_DUDOSA_M} m del relieve en su punto. {rango_txt}'
                f'La mayor diferencia es la de <b>{escape(peor["Estación"])}</b>: el catálogo indica {_num(peor["Catálogo"])} m '
                f'y el relieve, {_num(peor["Terreno"])} m ({_num(abs(peor["Diferencia"]))} m de diferencia). '
                f'Elige una fila para verla en el mapa 3D.</p>', unsafe_allow_html=True)
            st.dataframe(
                dudosas, hide_index=True, width="stretch", key="tabla_dudosas",
                on_select=_al_elegir_dudosa, selection_mode="single-row",
                column_order=["Estación", "Catálogo", "Terreno", "Diferencia"],
                column_config={"Catálogo": st.column_config.NumberColumn(format="%d m"),
                               "Terreno": st.column_config.NumberColumn("Relieve", format="%d m"),
                               "Diferencia": st.column_config.NumberColumn(format="%+d m",
                                                                           help="Catálogo menos relieve")})

    if param.get("avanzado") and len(seleccion):
        st.warning(f"Descarga avanzada: {bloques} consultas de {param['dias_bloque']} días "
                   f"(≈ {bloques // max(1, len(seleccion))} por estación).", icon=":material/hourglass_top:")

    if len(seleccion) == 0:
        st.warning(f"Ninguna estación alcanza el {umbral} % de cantidad probable. Baja el mínimo o cambia las fechas.")
        return

    st.html('<p class="y2k-titulo-seccion">Cobertura del periodo</p>')
    detalles("Estaciones por clase de cobertura.",
             "<p>Según qué parte del periodo cubre el registro de cada estación (entre su primer y su último dato). "
             "100 % significa que el registro abarca todo el periodo, aunque puede tener huecos.</p>",
             ver="Cómo se calcula")
    st.altair_chart(_grafica_clases(seleccion, paleta), width="stretch")

    grafica, minimo, maximo = _grafica_altitud(tabla, seleccionada, paleta)
    st.html('<p class="y2k-titulo-seccion">Altitud de las estaciones</p>')
    st.altair_chart(grafica, width="stretch", on_select="rerun", selection_mode="punto", key="graf_alt")
    st.caption(f"De {_num(minimo)} a {_num(maximo)} m ({_num(maximo - minimo)} m de desnivel) · haz clic en un punto "
               f"para seleccionar la estación{' · triángulo naranja: altitud dudosa' if (tabla['Alerta'] != '').any() else ''}")

    en_cuenca = int((seleccion["zona"] == "cuenca").sum()) if "zona" in seleccion.columns else len(seleccion)
    fines = pd.to_datetime(seleccion["Fin serie"], errors="coerce")
    activas = int((fines >= pd.Timestamp(datetime.date.today() - datetime.timedelta(days=365))).sum())
    en_buffer = len(seleccion) - en_cuenca
    st.markdown(f"**{en_cuenca}** en la cuenca{f' · **{en_buffer}** en el buffer' if en_buffer else ''}  \n"
                f"**{activas}** activas (con datos en el último año) · **{len(seleccion) - activas}** históricas")

    st.dataframe(
        tabla, hide_index=True, width="stretch", height=260,
        on_select="rerun", selection_mode="single-row", key="tabla_est",
        column_order=["Alerta", "Estación", "Altitud (m)", "Cantidad probable"],
        column_config={
            "Alerta": st.column_config.TextColumn("⚠", width=34, help="⚠ = altitud dudosa (no coincide con el relieve)"),
            "Altitud (m)": st.column_config.NumberColumn("Altitud", format="%d m"),
            "Cantidad probable": st.column_config.ProgressColumn("Cobertura", format="%.0f %%", min_value=0, max_value=100,
                                                                 help="Cantidad probable: qué parte del periodo cubre "
                                                                      "el registro de la estación"),
        },
    )
