# ===========================================================================
# CLASES DE CALIDAD (segun el % de cantidad probable en el rango pedido)
# Se usan en el mapa, en el panel de estadisticas y en las carpetas del ZIP.
# ===========================================================================

# (limite_inferior, nombre, rango, carpeta_en_zip, color)
# Colores: paleta de estado (bien / advertencia / serio / critico)
CLASES_CALIDAD = [
    (70, "Alta", "70-100 %", "1_Calidad_Alta_70_100", "#0ca30c"),
    (50, "Media", "50-70 %", "2_Calidad_Media_50_70", "#fab219"),
    (25, "Baja", "25-50 %", "3_Calidad_Baja_25_50", "#ec835a"),
    (0, "Crítica", "0-25 %", "4_Calidad_Critica_0_25", "#d03b3b"),
]


def clasificar_calidad(porcentaje):
    """Devuelve un dict con nombre, rango, carpeta y color de la clase."""
    for limite, nombre, rango, carpeta, color in CLASES_CALIDAD:
        if porcentaje >= limite:
            return {"nombre": nombre, "rango": rango, "carpeta": carpeta, "color": color}
    limite, nombre, rango, carpeta, color = CLASES_CALIDAD[-1]
    return {"nombre": nombre, "rango": rango, "carpeta": carpeta, "color": color}


def filtrar_descargables(estaciones_df, umbral):
    """
    Estaciones que se van a descargar: las que tienen la serie en DHIME,
    tienen datos dentro del rango y superan el umbral de cantidad probable.
    """
    mascara = (estaciones_df["Porcentaje (%)"] >= umbral) & (estaciones_df["Cantidad Probable"] > 0)
    if "Serie DHIME" in estaciones_df.columns:
        mascara &= estaciones_df["Serie DHIME"] == "Sí"
    return estaciones_df[mascara]
