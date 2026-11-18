"""
Mapa de huecos: cuadricula de estaciones (filas) por años (columnas) con el % de datos que llegaron cada año frente a
los que caben en el periodo pedido. Se arma con la descarga ya hecha (el IDEAM no se vuelve a consultar) y sale como
imagen PNG y como tabla CSV. Los colores son los de las clases de cobertura de la app (calidad.CLASES_CALIDAD).

Sirve para ver, de un vistazo, que estaciones estan completas y cuales tienen años vacios (ej. "le faltan 1998-2003"),
cosa que la cantidad probable del IDEAM no ve porque no descuenta los huecos internos.
"""
import io
import unicodedata
from calendar import monthrange
import zipfile
from datetime import date

import pandas as pd
from PIL import Image, ImageDraw, ImageFont

from modules.calidad import CLASES_CALIDAD

# La serie multianual trae siempre 36 datos sin fecha por año: no tiene sentido un mapa por años
FRECUENCIAS_SIN_MAPA = ("Multianual",)
# Frecuencias con un numero fijo de datos por periodo calendario (el resto se calcula por segundos)
SEGUNDOS_POR_FRECUENCIA = {
    "Decadal": 10 * 86400, "Diario": 86400, "03 Veces al Día": 8 * 3600, "02 Veces al Día": 12 * 3600,
    "Horario": 3600, "Cada 10 Minutos": 600, "Cada 05 Minutos": 300, "Cada 02 Minutos": 120, "Minutal": 60,
}


def disponible(frecuencia):
    return frecuencia not in FRECUENCIAS_SIN_MAPA


def disponible_mes(frecuencia):
    """El mapa por mes no aplica a la serie anual ni a la multianual."""
    return disponible(frecuencia) and frecuencia != "Anual"


def esperados_mes(anio, mes, ini, fin, frecuencia):
    """Datos que caben en el mes dentro del periodo [ini, fin] (0 si el mes queda fuera)."""
    ultimo = monthrange(anio, mes)[1]
    desde, hasta = max(ini, date(anio, mes, 1)), min(fin, date(anio, mes, ultimo))
    if desde > hasta:
        return 0
    if frecuencia == "Mensual":
        return 1
    dias = (hasta - desde).days + 1
    return max(1, round(dias * 86400 / SEGUNDOS_POR_FRECUENCIA.get(frecuencia, 86400)))


def esperados_anio(anio, ini, fin, frecuencia):
    """Datos que caben en `anio` dentro del periodo [ini, fin] (0 si el año queda fuera)."""
    desde, hasta = max(ini, date(anio, 1, 1)), min(fin, date(anio, 12, 31))
    if desde > hasta:
        return 0
    if frecuencia == "Anual":
        return 1
    if frecuencia == "Mensual":
        return hasta.month - desde.month + 1
    dias = (hasta - desde).days + 1
    return max(1, round(dias * 86400 / SEGUNDOS_POR_FRECUENCIA.get(frecuencia, 86400)))


def tabla_huecos(huecos, rango, frecuencia):
    """DataFrame (estaciones x años) con el % de datos de cada año, 0 a 100. `huecos`: {codigo: {"nombre", "anios"}}."""
    ini, fin = (r.date() if hasattr(r, "date") else r for r in rango)
    anios = list(range(ini.year, fin.year + 1))
    filas = {}
    for codigo, item in huecos.items():
        filas[(codigo, item["nombre"])] = {
            a: min(100.0, round(item["anios"].get(a, 0) / esperados_anio(a, ini, fin, frecuencia) * 100, 1))
            if esperados_anio(a, ini, fin, frecuencia) else None
            for a in anios}
    df = pd.DataFrame.from_dict(filas, orient="index", columns=anios)
    df.index = pd.MultiIndex.from_tuples(df.index, names=["Código", "Nombre"])
    return df


def tabla_meses(huecos, rango, frecuencia):
    """DataFrame con una fila por estacion y año y una columna por mes (1 a 12) con el % de datos de ese mes, 0 a 100
    (None fuera del periodo). `huecos[codigo]["meses"]`: {(año, mes): datos}."""
    ini, fin = (r.date() if hasattr(r, "date") else r for r in rango)
    filas, indice = [], []
    for codigo, item in huecos.items():
        for a in range(ini.year, fin.year + 1):
            fila = {}
            for mes in range(1, 13):
                esperado = esperados_mes(a, mes, ini, fin, frecuencia)
                fila[mes] = min(100.0, round(item.get("meses", {}).get((a, mes), 0) / esperado * 100, 1)) if esperado else None
            filas.append(fila)
            indice.append((codigo, item["nombre"], a))
    df = pd.DataFrame(filas, columns=range(1, 13)).astype(float)   # None -> NaN (fuera del periodo)
    df.index = pd.MultiIndex.from_tuples(indice, names=["Código", "Nombre", "Año"])
    return df


def _color(pct):
    for limite, _, _, _, color in CLASES_CALIDAD:
        if pct >= limite:
            return color
    return CLASES_CALIDAD[-1][4]


_TTF = ("DejaVuSans.ttf", "Arial.ttf", "arial.ttf", "LiberationSans-Regular.ttf", "NotoSans-Regular.ttf")


def _fuente(tamano):
    """(fuente, con_tildes): una TrueType del sistema si hay (con tildes y eñes); si no, la de Pillow, que no las trae."""
    for nombre in _TTF:
        try:
            return ImageFont.truetype(nombre, tamano), True
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=tamano), False
    except TypeError:   # Pillow viejo: fuente de tamaño fijo
        return ImageFont.load_default(), False


def _sin_tildes(texto):
    """Texto en ASCII (quita tildes y cambia la raya por un guion) para la fuente que no trae esos signos."""
    base = unicodedata.normalize("NFKD", texto.replace("–", "-").replace("·", "|"))
    return "".join(c for c in base if not unicodedata.combining(c)).encode("ascii", "replace").decode()


def png(tabla, titulo=""):
    """Imagen PNG (bytes) del mapa de huecos: una celda por estacion y año, coloreada por clase de cobertura."""
    celda_w, celda_h = (34 if len(tabla.columns) > 25 else 46), 24
    (fuente, tildes), (fuente_c, _), (fuente_t, _) = _fuente(13), _fuente(10), _fuente(15)

    def t(texto):
        return texto if tildes else _sin_tildes(texto)
    nombres = [t(f"{n.split('[')[0].strip()[:28]} [{c}]") for c, n in tabla.index]
    margen_izq = int(max([fuente.getlength(n) for n in nombres] + [60])) + 16
    alto_arriba = 56 if titulo else 34
    ancho = margen_izq + celda_w * len(tabla.columns) + 16
    alto = alto_arriba + celda_h * len(tabla) + 54
    img = Image.new("RGB", (ancho, alto), "white")
    d = ImageDraw.Draw(img)
    if titulo:
        d.text((8, 8), t(titulo), fill="#222", font=fuente_t)
    anios = list(tabla.columns)
    paso = 1 if len(anios) <= 25 else 5
    for j, a in enumerate(anios):
        if paso == 1 or a % paso == 0:
            d.text((margen_izq + j * celda_w + 2, alto_arriba - 18), str(a)[-4:] if paso == 1 else str(a),
                   fill="#333", font=fuente_c)
    for i, nombre in enumerate(nombres):
        y = alto_arriba + i * celda_h
        d.text((8, y + 5), nombre, fill="#222", font=fuente)
        for j, a in enumerate(anios):
            v = tabla.iloc[i, j]
            x = margen_izq + j * celda_w
            if pd.isna(v):
                d.rectangle([x, y, x + celda_w - 2, y + celda_h - 2], fill="#e6e8ee")
                continue
            d.rectangle([x, y, x + celda_w - 2, y + celda_h - 2], fill=_color(v))
            if celda_w >= 40:
                d.text((x + 4, y + 6), f"{v:.0f}", fill="white", font=fuente_c)
    y = alto_arriba + len(tabla) * celda_h + 16
    x = 8
    for limite, nombre, rango, _, color in CLASES_CALIDAD:
        d.rectangle([x, y, x + 14, y + 14], fill=color)
        d.text((x + 20, y), t(f"{nombre} {rango}"), fill="#222", font=fuente)
        x += 30 + int(fuente.getlength(t(f"{nombre} {rango}"))) + 16
    d.text((8, y + 22), t("% de datos de cada año frente a los que caben en el periodo pedido · Fuente: IDEAM · DHIME"),
           fill="#666", font=fuente_c)
    salida = io.BytesIO()
    img.save(salida, "PNG", optimize=True)
    return salida.getvalue()


def csv(tabla):
    return tabla.to_csv().encode("utf-8-sig")


MESES = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def csv_meses(tabla):
    """CSV largo: una fila por estacion, año y mes, con el % de datos."""
    largo = tabla.astype(float).stack().dropna().reset_index()
    largo.columns = ["Código", "Nombre", "Año", "Mes", "Datos (%)"]
    return largo.to_csv(index=False).encode("utf-8-sig")


def png_meses(tabla, titulo=""):
    """Imagen PNG (bytes) del mapa por mes: un bloque por estacion, con los años en filas y los 12 meses en columnas."""
    celda_w, celda_h = 34, 17
    (fuente, tildes), (fuente_c, _), (fuente_t, _) = _fuente(13), _fuente(10), _fuente(15)

    def t(texto):
        return texto if tildes else _sin_tildes(texto)

    estaciones = list(dict.fromkeys((c, n) for c, n, _ in tabla.index))
    anios = len(tabla) // max(1, len(estaciones))
    margen = 52
    alto_bloque = 26 + 16 + anios * celda_h + 14
    alto_arriba = 40 if titulo else 12
    ancho = max(margen + celda_w * 12 + 16, 660)
    alto = alto_arriba + alto_bloque * len(estaciones) + 54
    img = Image.new("RGB", (ancho, alto), "white")
    d = ImageDraw.Draw(img)
    if titulo:
        d.text((8, 8), t(titulo), fill="#222", font=fuente_t)
    y0 = alto_arriba
    for codigo, nombre in estaciones:
        d.text((8, y0), t(f"{nombre.split('[')[0].strip()} [{codigo}]"), fill="#222", font=fuente)
        for j, m in enumerate(MESES):
            d.text((margen + j * celda_w + 6, y0 + 22), t(m), fill="#333", font=fuente_c)
        bloque = tabla.xs(codigo, level="Código")
        for i, ((_, anio), fila) in enumerate(bloque.iterrows()):
            y = y0 + 40 + i * celda_h
            d.text((8, y + 3), str(anio), fill="#333", font=fuente_c)
            for j, mes in enumerate(range(1, 13)):
                v = fila[mes]
                x = margen + j * celda_w
                d.rectangle([x, y, x + celda_w - 2, y + celda_h - 2], fill="#e6e8ee" if pd.isna(v) else _color(v))
        y0 += alto_bloque
    y = y0 + 4
    x = 8
    for limite, nombre, rango, _, color in CLASES_CALIDAD:
        d.rectangle([x, y, x + 14, y + 14], fill=color)
        d.text((x + 20, y), t(f"{nombre} {rango}"), fill="#222", font=fuente)
        x += 30 + int(fuente.getlength(t(f"{nombre} {rango}"))) + 16
    d.text((8, y + 22), t("% de datos de cada mes frente a los que caben · Gris: fuera del periodo · Fuente: IDEAM · DHIME"),
           fill="#666", font=fuente_c)
    salida = io.BytesIO()
    img.save(salida, "PNG", optimize=True)
    return salida.getvalue()


def agregar_al_zip(zip_bytes, tabla, titulo="", por_mes=False):
    """Copia del ZIP con `mapa_de_huecos.png` y `mapa_de_huecos.csv` añadidos (por año o, con `por_mes`, por mes)."""
    salida = io.BytesIO()
    imagen, datos = (png_meses(tabla, titulo), csv_meses(tabla)) if por_mes else (png(tabla, titulo), csv(tabla))
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as origen, zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as destino:
        for info in origen.infolist():
            destino.writestr(info.filename, origen.read(info.filename))
        destino.writestr("mapa_de_huecos.png", imagen)
        destino.writestr("mapa_de_huecos.csv", datos)
    return salida.getvalue()
