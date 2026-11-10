"""Herramienta del modo desarrollador: aforos liquidos, curva nivel-caudal y perfiles transversales de una estacion.

Las estaciones que se ofrecen son las que tienen programa de aforos en el catalogo de DHIME (`programas`). Algunas
responden sin registros aunque figuren con programa: se avisa y no se trata como error.
"""
import pandas as pd
import streamlit as st

from modules import dhime_extras, ideam_catalog, ideam_downloader
from modules.idioma import tr


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _aforos(codigo):
    return dhime_extras.aforos_de(codigo)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _perfiles(codigo):
    return dhime_extras.perfiles_de(codigo)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _detalle(id_perfil):
    return dhime_extras.detalle_perfil(id_perfil)


def _estaciones(texto):
    cat = ideam_catalog.load_ideam_catalog_enriquecido()
    if "programas" not in cat.columns:
        return {}
    con = cat[cat["programas"].fillna("").str.contains(texto)]
    return {f"{r['nombre'].split('[')[0].strip()} [{r['idestacion']}]": str(r["idestacion"]) for _, r in con.iterrows()}


def pantalla():
    if not all(ideam_downloader.credenciales_ideam()):
        st.error(tr("Faltan las credenciales del portal DHIME (ver README)."))
        return
    opciones = _estaciones("Aforos")
    if not opciones:
        st.info(tr("No hay estaciones con programa de aforos en el catálogo."))
        return
    nombre = st.selectbox(tr("Estación con programa de aforos"), sorted(opciones), index=None,
                          placeholder=tr("Escribe el nombre o el código"), key="aforos_estacion")
    if not nombre:
        return
    codigo = opciones[nombre]
    try:
        aforos = _aforos(codigo)
    except ideam_downloader.ErrorAccesoIDEAM as e:
        st.error(str(e))
        return
    tab_aforos, tab_perfiles = st.tabs([tr("Aforos y curva"), tr("Perfiles transversales")])

    with tab_aforos:
        if aforos.empty:
            st.info(tr("El IDEAM no tiene aforos publicados para esta estación."))
        else:
            st.caption(tr("{n} aforos entre {a} y {b}", n=len(aforos), a=aforos["fecha"].min().date(),
                          b=aforos["fecha"].max().date()))
            anios = (int(aforos["fecha"].dt.year.min()), int(aforos["fecha"].dt.year.max()))
            if anios[0] < anios[1]:
                # la seccion del rio cambia con el tiempo: una sola curva para todo el periodo puede ajustar mal
                a, b = st.slider(tr("Periodo de los aforos (años)"), anios[0], anios[1], anios, key="aforos_periodo")
                aforos = aforos[aforos["fecha"].dt.year.between(a, b)]
            h0 = st.number_input(tr("Nivel de caudal cero h0 (m)"), value=0.0, step=0.05, key="aforos_h0")
            curva = dhime_extras.ajustar_curva(aforos, h0)
            puntos = pd.DataFrame({"Nivel (m)": aforos["nivel_cm"] / 100.0, "Caudal (m³/s)": aforos["caudal_m3s"],
                                   "Serie": tr("Aforos")})
            if curva:
                h = pd.Series(sorted(set((aforos["nivel_cm"] / 100.0).round(3))))
                h = h[h > h0]
                ajuste = pd.DataFrame({"Nivel (m)": h, "Caudal (m³/s)": curva["a"] * (h - h0) ** curva["b"],
                                       "Serie": tr("Curva ajustada")})
                puntos = pd.concat([puntos, ajuste], ignore_index=True)
                st.caption(f"Q = {curva['a']:.3f} · (H − {h0:.2f})^{curva['b']:.3f} · R² = {curva['r2']:.3f} · n = {curva['n']}"
                           f" — {tr('ajuste exploratorio, no es la curva oficial del IDEAM')}")
            else:
                st.caption(tr("Se necesitan al menos 5 aforos con nivel mayor que h0 para ajustar la curva."))
            st.scatter_chart(puntos, x="Nivel (m)", y="Caudal (m³/s)", color="Serie")
            st.dataframe(aforos, hide_index=True, width="stretch")
            st.download_button(tr("Descargar aforos (CSV)"), aforos.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"aforos_{codigo}.csv", mime="text/csv")

    with tab_perfiles:
        try:
            perfiles = _perfiles(codigo)
        except ideam_downloader.ErrorAccesoIDEAM as e:
            st.error(str(e))
            return
        if perfiles.empty:
            st.info(tr("El IDEAM no tiene perfiles transversales publicados para esta estación."))
            return
        st.dataframe(perfiles, hide_index=True, width="stretch")
        etiquetas = {f"{r['fecha'].date()} · {r['id_perfil']}": r["id_perfil"] for _, r in perfiles.iterrows()}
        elegido = st.selectbox(tr("Perfil"), list(etiquetas), key="aforos_perfil")
        detalle = _detalle(int(etiquetas[elegido]))
        if detalle.empty:
            st.info(tr("Este perfil no trae puntos."))
        else:
            st.line_chart(detalle.rename(columns={"abscisa_m": "Distancia (m)", "cota_m": "Cota (m)"}),
                          x="Distancia (m)", y="Cota (m)")
            st.download_button(tr("Descargar perfil (CSV)"), detalle.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"perfil_{etiquetas[elegido]}.csv", mime="text/csv")
