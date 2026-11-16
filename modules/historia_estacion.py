"""Historia de una estacion, de la API de DHIME (la misma cuenta publica del portal). Cuatro servicios:

  - Bitacora de cambios   Administracion/ConsultarHistoricoEstacion/{id}   categoria, tecnologia, estado, altitud,
                          coordenadas y fecha de instalacion en cada registro. OJO: la bitacora empieza en 2018-2020
                          (casi todas arrancan con una carga de marzo de 2018): lo anterior no queda registrado.
  - Informacion           Capturas/ConsultarInformacionEstacion/{id}       instalacion y suspension (todas las epocas)
  - Observadores          OperacionRed/ConsultarObservadoresPorIdEstacion/{id}   con fechas; muchas estaciones, vacio
  - Visitas               Hidrologia/ConsultarVisitasEstacion?IdEstacion=  fechas de visita; casi siempre vacio

Probado el 16 nov 2026 con 7 estaciones (activas, suspendidas, automaticas, convencionales): todas responden 200;
observadores y visitas vienen vacios en la mayoria. Las funciones `procesar_*` son puras (reciben el JSON) para
probarlas sin red.
"""
import math
from concurrent.futures import ThreadPoolExecutor

import streamlit as st

from modules import ideam_downloader

# Cambio de coordenadas por debajo de esto es redondeo del IDEAM (1 m = 0,00001 grados), no un traslado
UMBRAL_TRASLADO_M = 25


def _texto(valor):
    return str(valor).strip() if valor not in (None, "") else None


def _fecha(valor):
    """'2020-12-18T16:13:07' -> '2020-12-18' (None si viene vacio)."""
    return str(valor)[:10] if valor else None


def _distancia_m(lat1, lon1, lat2, lon2):
    """Metros entre dos puntos (aproximacion plana, de sobra para trasladar una estacion)."""
    kx = 111320 * math.cos(math.radians((lat1 + lat2) / 2))
    return math.hypot((lon2 - lon1) * kx, (lat2 - lat1) * 110540)


def procesar_historia(registros):
    """Eventos de la bitacora, del mas viejo al mas nuevo: lista de {fecha, tipo, antes, despues, detalle}.
    El primer registro es el `inicio` (como estaba la estacion cuando empezo la bitacora). Despues solo salen los
    cambios de verdad: categoria, tecnologia, estado, altitud y traslado (coordenadas). Se ignoran los registros
    repetidos, los espacios sobrantes de la categoria ("CP    ") y los valores vacios que el IDEAM deja un rato entre
    dos cambios de tecnologia."""
    filas = sorted((r for r in (registros or []) if isinstance(r, dict) and r.get("FechaLog")),
                   key=lambda r: (r["FechaLog"], r.get("IdLogCambio") or 0))
    eventos, ultimo = [], {}
    for r in filas:
        actual = {
            "categoria": _texto(r.get("IdCategoria")),   # el codigo ("CP"); la interfaz lo muestra con su nombre
            "tecnologia": _texto(r.get("Tecnologia")),
            "estado": _texto(r.get("EstadoEstacion")),
            "altitud": r.get("Altitud"),
            "lat": r.get("Latitud"), "lon": r.get("Longitud"),
        }
        fecha = _fecha(r["FechaLog"])
        if not ultimo:
            ultimo = {k: v for k, v in actual.items() if v is not None}
            eventos.append({"fecha": fecha, "tipo": "inicio", "antes": None, "despues": None,
                            "detalle": dict(ultimo, instalacion=_fecha(r.get("FechaInstalacion")))})
            continue
        for campo in ("categoria", "tecnologia", "estado"):
            nuevo = actual[campo]
            if nuevo is not None and nuevo != ultimo.get(campo):
                if campo in ultimo or campo == "estado":
                    eventos.append({"fecha": fecha, "tipo": campo, "antes": ultimo.get(campo), "despues": nuevo,
                                    "detalle": _nota(r)})
                ultimo[campo] = nuevo
        if actual["altitud"] is not None:
            if ultimo.get("altitud") is not None and actual["altitud"] != ultimo["altitud"]:
                eventos.append({"fecha": fecha, "tipo": "altitud", "antes": ultimo["altitud"],
                                "despues": actual["altitud"], "detalle": _nota(r)})
            ultimo["altitud"] = actual["altitud"]
        if None not in (actual["lat"], actual["lon"]):
            if None not in (ultimo.get("lat"), ultimo.get("lon")):
                d = _distancia_m(ultimo["lat"], ultimo["lon"], actual["lat"], actual["lon"])
                if d >= UMBRAL_TRASLADO_M:
                    eventos.append({"fecha": fecha, "tipo": "traslado", "antes": round(d), "despues": None,
                                    "detalle": _nota(r)})
            ultimo["lat"], ultimo["lon"] = actual["lat"], actual["lon"]
    return eventos


def _nota(registro):
    """Ultima nota del campo Observacion (el IDEAM la va acumulando con '|fecha$usuario$texto'); vacia si no hay."""
    texto = _texto(registro.get("Observacion")) or ""
    ultima = texto.split("|")[-1]
    return ultima.split("$")[-1].strip()[:200] or None


def procesar_informacion(respuesta):
    """Instalacion y suspension: {instalacion, suspension} como 'AAAA-MM-DD' (None si no hay)."""
    d = respuesta if isinstance(respuesta, dict) else {}
    return {"instalacion": _fecha(d.get("FechaInstalacion")), "suspension": _fecha(d.get("FechaSuspension"))}


def procesar_observadores(respuesta):
    """Periodos de los observadores, del mas reciente al mas viejo: [{desde, hasta, activo}]. Solo fechas: no se
    guardan ni se muestran nombres, cedulas ni telefonos (datos personales)."""
    filas = respuesta if isinstance(respuesta, list) else []
    salida = [{"desde": _fecha(o.get("FechaInicio")), "hasta": _fecha(o.get("FechaFin")),
               "activo": str(o.get("Estado", "")).strip().lower() == "activo"} for o in filas if isinstance(o, dict) and o.get("FechaInicio")]
    return sorted(salida, key=lambda o: o["desde"] or "", reverse=True)


def procesar_visitas(respuesta):
    """Resumen de las visitas: {n, primera, ultima} (n = 0 si no hay)."""
    fechas = sorted(_fecha(v.get("Fecha")) for v in (respuesta if isinstance(respuesta, list) else [])
                    if isinstance(v, dict) and v.get("Fecha"))
    return {"n": len(fechas), "primera": fechas[0] if fechas else None, "ultima": fechas[-1] if fechas else None}


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def historia_de(codigo):
    """Todo lo de la estacion en un dict: {historia, informacion, observadores, visitas}. Si algun servicio falla,
    lanza la excepcion (asi un error no queda guardado en el cache)."""
    token = ideam_downloader.obtener_token()
    pedidos = {
        "historia": (f"Administracion/ConsultarHistoricoEstacion/{codigo}", None, procesar_historia),
        "informacion": (f"Capturas/ConsultarInformacionEstacion/{codigo}", None, procesar_informacion),
        "observadores": (f"OperacionRed/ConsultarObservadoresPorIdEstacion/{codigo}", None, procesar_observadores),
        "visitas": ("Hidrologia/ConsultarVisitasEstacion", {"IdEstacion": codigo}, procesar_visitas),
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        futuros = {k: pool.submit(ideam_downloader.consultar_api, ruta, params, token)
                   for k, (ruta, params, _) in pedidos.items()}
        return {k: pedidos[k][2](f.result()) for k, f in futuros.items()}
