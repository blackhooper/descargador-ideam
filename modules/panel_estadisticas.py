import datetime
from html import escape
import altair as alt
import pandas as pd
import streamlit as st
from modules import ideam_downloader
from modules.calidad import CLASES_CALIDAD
from modules.estilo import PALETAS
from modules.terreno import ALTITUD_DUDOSA_M

NARANJA_ALERTA = "#EC835A"


def _num(n):
    return f"{n:,.0f}".replace(",", ".")


def _cifras(items):
    """Tarjetas de cifras 2x2 en HTML: a diferencia de st.metric, la etiqueta no se corta con '...'."""
    html = "".join(
        f'<div class="y2k-cifra" title="{escape(ayuda)}"><div class="l">{escape(etiqueta)}</div>'
        f'<div class="v">{escape(str(valor))}</div>{f"<div class=s>{escape(sub)}</div>" if sub else ""}</div>'
        for etiqueta, valor, sub, ayuda in items
    )
    st.markdown(f'<div class="y2k-cifras">{html}</div>', unsafe_allow_html=True)


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
        "Alerta": ["⚠️" if d else "" for d in dudosa.fillna(False)],
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
             f"pone la estación a <b>{_num(altitud)} m</b>: <b>{_num(abs(diferencia))} m más "
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
            texto += (f" En toda la zona el terreno va de {_num(minimo)} a {_num(maximo)} m, así que puede que la "
                      f"altitud esté bien y lo errado sean las coordenadas de la estación.")
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
    return (barras + etiquetas).properties(height=4 * 30).configure_view(stroke=None)


def _grafica_altitud(tabla, seleccionada, paleta):
    """Un punto por estacion, de la mas baja a la mas alta. Clic = seleccionar. Naranja = altitud dudosa."""
    datos = tabla.dropna(subset=["Altitud (m)"]).sort_values("Altitud (m)").reset_index(drop=True)
    datos["Orden"] = range(1, len(datos) + 1)
    datos["Elegida"] = datos["Código"] == seleccionada
    datos["Dudosa"] = datos["Alerta"] != ""
    datos["Terreno"] = datos["Terreno (m)"].map(lambda v: f"{_num(v)} m" if pd.notna(v) else "sin dato")
    minimo, maximo = datos["Altitud (m)"].min(), datos["Altitud (m)"].max()
    paso = 500 if maximo - minimo > 900 else 250 if maximo - minimo > 150 else 50
    dominio = [minimo // paso * paso, (-(-maximo // paso)) * paso if maximo > minimo else minimo + paso]
    punto = alt.selection_point(name="punto", fields=["Código"], on="click", empty=False)
    color = (alt.when(alt.datum.Elegida).then(alt.value(paleta["tinta"]))
             .when(alt.datum.Dudosa).then(alt.value(NARANJA_ALERTA))
             .otherwise(alt.value(paleta["acento"])))
    grafica = alt.Chart(datos).mark_circle(opacity=1, stroke=paleta["superficie"], strokeWidth=1.2).encode(
        x=alt.X("Orden:Q", title=None, axis=None, scale=alt.Scale(domain=[0.5, max(1.5, len(datos) + 0.5)])),
        y=alt.Y("Altitud (m):Q", title=None, scale=alt.Scale(domain=dominio, nice=False),
                axis=alt.Axis(values=list(range(int(dominio[0]), int(dominio[1]) + 1, paso)), grid=True,
                              gridColor=paleta["rejilla"], domain=False, ticks=False, labelColor=paleta["tinta_3"],
                              labelExpr="replace(format(datum.value, ',.0f'), ',', '.')")),
        size=alt.condition(alt.datum.Elegida, alt.value(240), alt.value(70)),
        color=color,
        tooltip=[alt.Tooltip("Estación:N"), alt.Tooltip("Altitud (m):Q", format=",.0f", title="Altitud catálogo"),
                 alt.Tooltip("Terreno:N", title="Terreno real"), alt.Tooltip("Alerta:N", title="Inconsistente")],
    ).add_params(punto).properties(height=130).configure_view(stroke=None)
    return grafica, minimo, maximo


def _ver_en_3d():
    st.session_state["vista"] = "3D"
    st.session_state["_orbitar"] = True


def tarjeta_seleccionada(fila, rango=None, vista="2D"):
    """Ficha de la estacion elegida (desde la lista, la grafica o el mapa)."""
    with st.container(border=True):
        nombre = str(fila.get("nombre", ""))
        st.markdown(f"**{nombre}**")
        try:
            altitud = _num(float(fila.get("altitud"))) + " m"
        except (TypeError, ValueError):
            altitud = "sin dato"
        zona = "en la cuenca" if fila.get("zona") == "cuenca" else "en el buffer"
        st.caption(f"{ideam_downloader.codigo_de_estacion(fila)} · {altitud} · {zona}")
        if fila.get("altitud_dudosa") and fila.get("terreno") is not None:
            with st.container(key="alerta_ficha"), st.expander("⚠️ Altitud inconsistente · ver más"):
                st.markdown(f'<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                            f'{_explicacion_altitud(float(fila["altitud"]), float(fila["terreno"]), rango)}'
                            f'{" En el mapa 3D la marca naranja muestra dónde quedaría con la altitud del catálogo." if vista == "3D" else ""}'
                            f'</p>', unsafe_allow_html=True)
                if vista != "3D":
                    st.button("Verla en el mapa 3D", key="ver_3d", icon=":material/landscape:",
                              use_container_width=True, on_click=_ver_en_3d)
        if fila.get("Serie DHIME") == "Sí":
            st.caption(f"Cantidad probable **{fila['Porcentaje (%)']:.0f} %** ({fila.get('Clase calidad', '')}) · "
                       f"serie {str(fila.get('Inicio serie'))[:4]}–{str(fila.get('Fin serie'))[:4]}")
        else:
            st.caption("Sin serie de este parámetro en DHIME")
        if st.button("Quitar selección", key="quitar_sel", use_container_width=True):
            st.session_state["estacion_sel"] = None
            st.rerun()


def mostrar_panel(zona, seleccion, param, fecha_ini, fecha_fin, umbral, seleccionada, tabla, tema="claro",
                  dudosas=None, rango=None, vista="2D"):
    paleta = PALETAS[tema]
    st.markdown("### RESUMEN")
    if zona is None:
        st.info("Dibuja o sube tu cuenca para ver aquí el resumen.")
        return
    if zona.empty:
        st.warning("No hay estaciones del IDEAM dentro de la cuenca. Activa o agranda el buffer.")
        return

    if seleccionada is not None:
        fila = zona[[ideam_downloader.codigo_de_estacion(r, i) == seleccionada for i, r in zona.iterrows()]]
        if not fila.empty:
            tarjeta_seleccionada(fila.iloc[0], rango, vista)

    bloques = _bloques_de(seleccion, fecha_ini, fecha_fin, param["dias_bloque"])
    segundos = ideam_downloader.estimar_segundos(bloques, int(seleccion["Cantidad Probable"].sum()), len(seleccion))
    datos = int(seleccion["Cantidad Probable"].sum())
    _cifras([
        ("Estaciones", len(seleccion), f"de {len(zona)} en la zona",
         f"Estaciones que se van a descargar, de {len(zona)} en la cuenca y el buffer"),
        ("Calidad media", f"{seleccion['Porcentaje (%)'].mean():.0f} %" if len(seleccion) else "–", "cantidad probable",
         "Promedio de la cantidad probable de datos de las estaciones a descargar"),
        ("Tiempo", ideam_downloader.formatear_duracion(segundos), f"{bloques} consultas",
         f"{bloques} consultas al IDEAM de hasta {param['dias_bloque']} días. Depende de qué tan rápido responda su servidor."),
        ("Datos", f"{round(datos / 1000)}k" if datos >= 100_000 else _num(datos), "registros probables",
         "Cantidad de registros que el IDEAM dice tener en el rango de fechas"),
    ])

    # Estaciones cuya altitud del catalogo no cuadra con el relieve real
    if dudosas is not None and len(dudosas):
        codigos_sel = set(tabla["Código"])
        en_seleccion = int(dudosas["Código"].isin(codigos_sel).sum())
        peor = dudosas.iloc[0]
        rango_txt = (f"Según el relieve, el terreno de esta zona va de <b>{_num(rango[0])} a {_num(rango[1])} m</b>. "
                     if rango else "")
        # Alerta pequena de una linea; el detalle queda adentro ("ver más")
        with st.container(key="alerta_altura"), st.expander(
                f"⚠️ Inconsistencia en altura de estaciones ({len(dudosas)}) · ver más"):
            st.markdown(
                f'<p class="y2k-hint" style="color:var(--y2k-ink-2) !important">'
                f'{len(dudosas)} {"estaciones" if len(dudosas) != 1 else "estación"}'
                f'{f" ({en_seleccion} en la descarga)" if en_seleccion else ""} tienen en el catálogo una altitud que '
                f'se aleja más de {ALTITUD_DUDOSA_M} m del terreno real en su punto. {rango_txt}'
                f'La mayor es <b>{escape(peor["Estación"])}</b>: el catálogo dice {_num(peor["Catálogo"])} m y el '
                f'terreno mide {_num(peor["Terreno"])} m ({_num(abs(peor["Diferencia"]))} m de diferencia). '
                f'Clic en una para verla en el mapa 3D.</p>', unsafe_allow_html=True)
            st.dataframe(
                dudosas, hide_index=True, use_container_width=True, key="tabla_dudosas",
                on_select="rerun", selection_mode="single-row",
                column_order=["Estación", "Catálogo", "Terreno", "Diferencia"],
                column_config={"Catálogo": st.column_config.NumberColumn(format="%d m"),
                               "Terreno": st.column_config.NumberColumn(format="%d m"),
                               "Diferencia": st.column_config.NumberColumn(format="%+d m",
                                                                           help="Catálogo menos terreno")})

    if param.get("avanzado") and len(seleccion):
        st.warning(f"⏳ Descarga avanzada: {bloques} consultas de {param['dias_bloque']} días "
                   f"(≈ {bloques // max(1, len(seleccion))} por estación).")

    if len(seleccion) == 0:
        st.warning(f"Ninguna estación supera {umbral} % de cantidad probable. Baja el mínimo o cambia las fechas.")
        return

    st.markdown("**Calidad aproximada de los datos**")
    st.markdown('<p class="y2k-hint">Estaciones por clase, según la cantidad probable de datos que el IDEAM '
                'reporta para el rango de fechas (100 % = serie completa).</p>', unsafe_allow_html=True)
    st.altair_chart(_grafica_clases(seleccion, paleta), use_container_width=True)

    grafica, minimo, maximo = _grafica_altitud(tabla, seleccionada, paleta)
    st.markdown("**Altitud de las estaciones**")
    st.altair_chart(grafica, use_container_width=True, on_select="rerun", selection_mode="punto", key="graf_alt")
    st.caption(f"De la más baja a la más alta · de {_num(minimo)} a {_num(maximo)} m ({_num(maximo - minimo)} m de desnivel). "
               f"Clic en un punto para ubicarla{' · naranja = altitud inconsistente' if (tabla['Alerta'] != '').any() else ''}.")

    en_cuenca = int((seleccion["zona"] == "cuenca").sum()) if "zona" in seleccion.columns else len(seleccion)
    fines = pd.to_datetime(seleccion["Fin serie"], errors="coerce")
    activas = int((fines >= pd.Timestamp(datetime.date.today() - datetime.timedelta(days=365))).sum())
    buffer_txt = f" · en el buffer **{len(seleccion) - en_cuenca}**" if len(seleccion) - en_cuenca else ""
    st.markdown(f"En la cuenca **{en_cuenca}**{buffer_txt}  \nActivas hoy **{activas}** · Históricas **{len(seleccion) - activas}**")

    st.dataframe(
        tabla, hide_index=True, use_container_width=True, height=260,
        on_select="rerun", selection_mode="single-row", key="tabla_est",
        column_order=["Alerta", "Estación", "Altitud (m)", "Cantidad probable"],
        column_config={
            "Alerta": st.column_config.TextColumn("⚠", width=34, help="⚠️ = altitud inconsistente con el terreno real"),
            "Altitud (m)": st.column_config.NumberColumn("Altitud", format="%d m"),
            "Cantidad probable": st.column_config.ProgressColumn("Prob.", format="%.0f %%", min_value=0, max_value=100),
        },
    )
