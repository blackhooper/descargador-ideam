"""Acceso por clave y modos de uso (cliente / desarrollador).

- Modo cliente: la app tal como esta. Su clave es TEMPORAL: solo mantiene la pagina privada por ahora.
- Modo desarrollador: la misma app mas un apartado "Herramientas" donde se iran sumando las nuevas.
La clave decide el modo: la del desarrollador abre el modo desarrollador y la del cliente abre el modo cliente.

Las claves se configuran como secretos (nunca en el codigo), en `.streamlit/secrets.toml` o en Settings -> Secrets:

    [acceso]
    cliente = "..."
    desarrollador = "..."

Se pide una sola vez: al acertar, el navegador guarda una cookie (1 ano) con una huella de la clave y las recargas
entran solas. Cambiar la clave en los secretos cierra las sesiones guardadas. "Cerrar sesion" (Ajustes) la borra.

AVISO: esto NO es seguridad real. Es una puerta para que no entre cualquiera por curiosidad; la huella viaja en una
cookie del navegador y quien tenga el enlace y la clave entra. Para proteger datos de verdad hace falta una cuenta
de usuario en el servidor.
"""
import hashlib
import hmac

import streamlit as st
import streamlit.components.v1 as components

from modules.idioma import tr

COOKIE = "y2k_acceso"
MODOS = ("cliente", "desarrollador")


def _claves():
    """{modo: clave} con las claves configuradas (las vacias no cuentan)."""
    try:
        bloque = st.secrets.get("acceso", {})
        return {m: str(bloque.get(m, "")).strip() for m in MODOS if str(bloque.get(m, "")).strip()}
    except Exception:
        return {}


def _huella(modo, clave):
    return hashlib.sha256(f"y2k|{modo}|{clave}".encode()).hexdigest()


def _modo_de_clave(escrita, claves):
    """Modo que abre la clave escrita (la del desarrollador tiene prioridad), o None."""
    for modo in ("desarrollador", "cliente"):
        if modo in claves and hmac.compare_digest(escrita.encode(), claves[modo].encode()):
            return modo
    return None


def _modo_de_cookie(claves):
    try:
        huella = st.context.cookies.get(COOKIE, "")
    except Exception:
        return None
    for modo in ("desarrollador", "cliente"):
        if modo in claves and huella and hmac.compare_digest(huella, _huella(modo, claves[modo])):
            return modo
    return None


def _js_cookie(valor, segundos):
    # el iframe comparte origen con la pagina: la cookie queda en la pagina (Secure solo bajo https)
    components.html(f"""<script>
    try {{
      const w = window.parent;
      const seguro = w.location.protocol === "https:" ? "; Secure" : "";
      w.document.cookie = "{COOKIE}={valor}; max-age={segundos}; path=/; SameSite=Lax" + seguro;
    }} catch (e) {{}}
    </script>""", height=0)


def modo():
    """Modo actual ("cliente" o "desarrollador"), o None si aun no hay acceso."""
    return st.session_state.get("modo_acceso")


def es_desarrollador():
    return modo() == "desarrollador"


def puerta():
    """Pide la clave hasta que se acierte. Llamar al principio de la app: si no hay acceso, detiene la corrida."""
    ss = st.session_state
    claves = _claves()
    if not claves:
        st.error(tr("Falta configurar las claves de acceso. En tu computador van en `.streamlit/secrets.toml`; en "
                    "Streamlit Cloud, en Settings → Secrets de la app, así:")
                 + "\n\n```toml\n[acceso]\ncliente = \"...\"\ndesarrollador = \"...\"\n```")
        st.stop()
    if ss.get("modo_acceso") not in claves:           # tambien cubre una clave quitada de los secretos
        # tras cerrar sesion, la cookie que el navegador mando al abrir la pagina ya no vale en esta sesion
        ss.modo_acceso = None if ss.get("sesion_cerrada") else _modo_de_cookie(claves)
    if ss.pop("_borrar_cookie", None):
        _js_cookie("", 0)
    if ss.get("modo_acceso"):
        if ss.pop("_poner_cookie", None):              # recien acertada: se guarda para las proximas recargas
            _js_cookie(_huella(ss.modo_acceso, claves[ss.modo_acceso]), 365 * 24 * 3600)
        return
    _, centro, _ = st.columns([1, 1.2, 1])
    with centro:
        st.markdown("&nbsp;")
        with st.form("y2k_acceso_form", border=True):
            st.subheader(tr("Descargador IDEAM"))
            st.caption(tr("Acceso restringido. Escribe la clave para entrar; solo se pide una vez en este navegador."))
            escrita = st.text_input(tr("Clave"), type="password", key="y2k_clave_escrita")
            enviar = st.form_submit_button(tr("Entrar"), type="primary", width="stretch")
        if enviar:
            nuevo = _modo_de_clave(escrita, claves)
            if nuevo:
                ss.modo_acceso = nuevo
                ss.sesion_cerrada = False
                ss._poner_cookie = True
                st.rerun()
            st.error(tr("Clave incorrecta."))
    st.stop()


def _cerrar_sesion():
    st.session_state.modo_acceso = None
    st.session_state.sesion_cerrada = True
    st.session_state._borrar_cookie = True
    st.session_state.vista_dev = "descargador"


def menu():
    """Contenido de Ajustes para el acceso: cambio de vista (solo desarrollador) y cerrar sesion."""
    if not modo():
        return
    st.markdown(f'<p class="y2k-menu-tit">{tr("Acceso")}</p>', unsafe_allow_html=True)
    st.caption(tr("Modo desarrollador") if es_desarrollador() else tr("Modo cliente"))
    if es_desarrollador():
        st.segmented_control(tr("Vista"), ["descargador", "herramientas"], key="vista_dev", required=True,
                             width="stretch", format_func=lambda v: tr("Descargador") if v == "descargador"
                             else tr("Herramientas"))
    st.button(tr("Cerrar sesión"), key="y2k_salir", on_click=_cerrar_sesion, width="stretch")

