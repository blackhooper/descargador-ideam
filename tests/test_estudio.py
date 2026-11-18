"""Pruebas del estudio hidrológico (etapa 1). Se corren con:  python -m unittest discover -s tests

No usan la red: el terreno es un valle sintético en forma de V cuya cuenca se conoce de antemano.
"""
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.transform import from_origin

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from estudio import almacen, core, fuentes, pasos, terreno  # noqa: E402

N = 60                     # celdas por lado
X0, Y0 = 4_990_000.0, 2_100_000.0   # esquina noroeste en EPSG:9377 (sabana de Bogotá)


def superficie():
    filas, cols = np.mgrid[0:N, 0:N]
    return 2600 + 2.0 * np.abs(cols - 30) + 1.0 * (N - 1 - filas)


def valle_sintetico(ruta: Path) -> Path:
    """Valle en V que baja hacia el sur: el cauce va por la columna 30 y sale por la última fila."""
    z = superficie()
    perfil = dict(driver="GTiff", height=N, width=N, count=1, dtype="float32", crs=terreno.CRS_TRABAJO,
                  transform=from_origin(X0, Y0, 30, 30), nodata=terreno.NODATA)
    with rasterio.open(ruta, "w", **perfil) as d:
        d.write(z.astype("float32"), 1)
    return ruta


def celdas_que_llegan(z, salida):
    """Cuenta, con un D8 escrito aparte (O'Callaghan y Mark, 1984), las celdas cuyo camino pasa por `salida`.
    Sirve de referencia independiente de pysheds. Como pysheds, no enruta las celdas del borde del modelo (salvo la
    salida): se toman como salidas del modelo."""
    filas, cols = z.shape

    def borde(f, c):
        return f in (0, filas - 1) or c in (0, cols - 1)

    vecinos = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    total = 0
    for f in range(filas):
        for c in range(cols):
            ff, cc = f, c
            while True:
                if (ff, cc) == salida:
                    total += 1
                    break
                if borde(ff, cc):
                    break
                mejor, paso = 0.0, None
                for df, dc in vecinos:
                    nf, nc = ff + df, cc + dc
                    if 0 <= nf < filas and 0 <= nc < cols:
                        pendiente = (z[ff, cc] - z[nf, nc]) / (30 * (2 ** 0.5 if df and dc else 1))
                        if pendiente > mejor:
                            mejor, paso = pendiente, (nf, nc)
                if paso is None:
                    break
                ff, cc = paso
    return total


def a_lonlat(x, y):
    return Transformer.from_crs(terreno.CRS_TRABAJO, terreno.CRS_GEOGRAFICO, always_xy=True).transform(x, y)


class Fuentes(unittest.TestCase):
    def test_cada_paso_cita_fuentes_registradas(self):
        for p in pasos.PASOS.values():
            self.assertTrue(p.fuentes, p.clave)
            for c in p.fuentes:
                fuentes.fuente(c)      # lanza KeyError si la clave no existe
            self.assertIn(p.marca, fuentes.MARCAS)

    def test_marca_principal_toma_la_mas_oficial(self):
        self.assertEqual(fuentes.marca_principal(["strahler_1957", "ideam_era_2013"]), "ambiental")
        self.assertEqual(fuentes.marca_principal(["strahler_1957", "herramienta_control_borde"]), "literatura")

    def test_bibliografia_sin_repetir_y_ordenada(self):
        b = fuentes.bibliografia(["strahler_1957", "ideam_era_2013", "strahler_1957"])
        self.assertEqual(len(b), 2)
        self.assertEqual(b, sorted(b, key=str.lower))


class Core(unittest.TestCase):
    def test_decidir_reemplaza_y_conserva_al_ir_y_volver_de_json(self):
        e = core.Estudio(nombre="Prueba")
        e.decidir("terreno.red", "umbral_km2", 1.0, ["mads_rondas_2018"])
        e.decidir("terreno.red", "umbral_km2", 0.5, ["mads_rondas_2018"], por="hidrologo")
        self.assertEqual(len(e.decisiones), 1)
        self.assertEqual(e.decision("terreno.red", "umbral_km2"), 0.5)
        otra = core.Estudio.desde_json(e.a_json())
        self.assertEqual(otra.decision("terreno.red", "umbral_km2"), 0.5)
        self.assertEqual(otra.decisiones[0].marca, "hidrologo")

    def test_fuente_desconocida_es_error(self):
        with self.assertRaises(KeyError):
            core.Estudio(nombre="x").decidir("a", "b", 1, ["no_existe"])


class Almacen(unittest.TestCase):
    def test_zip_ida_y_vuelta(self):
        with tempfile.TemporaryDirectory() as t:
            alm = almacen.AlmacenCarpeta(t)
            e = core.Estudio(nombre="Teusacá")
            alm.guardar(e.id, "terreno/dem.tif", b"123")
            datos = almacen.exportar_zip(alm, e)
            with zipfile.ZipFile(io.BytesIO(datos)) as z:
                self.assertIn(almacen.NOMBRE_CORE, z.namelist())
            alm2 = almacen.AlmacenCarpeta(Path(t) / "otro")
            e2 = almacen.importar_zip(alm2, datos)
            self.assertEqual(e2.nombre, "Teusacá")
            self.assertEqual(alm2.leer(e2.id, "terreno/dem.tif"), b"123")

    def test_rechaza_rutas_que_salen_de_la_carpeta(self):
        with tempfile.TemporaryDirectory() as t:
            alm = almacen.AlmacenCarpeta(t)
            for malo in ("../fuera.txt", "/etc/passwd", "a/../../b"):
                with self.assertRaises(ValueError):
                    alm.ruta_local("estudio", malo)

    def test_zip_sin_estudio_se_rechaza(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("otra_cosa.txt", "hola")
        with tempfile.TemporaryDirectory() as t, self.assertRaises(ValueError):
            almacen.importar_zip(almacen.AlmacenCarpeta(t), buf.getvalue())


class Terreno(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.flujo = terreno.acondicionar(valle_sintetico(Path(cls.tmp.name) / "valle.tif"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_area_de_celda(self):
        self.assertAlmostEqual(self.flujo.area_celda_km2, 0.0009, places=7)   # 30 m × 30 m

    def test_el_punto_se_ajusta_al_cauce(self):
        # clic 4 celdas al este del cauce, cerca de la salida
        lon, lat = a_lonlat(X0 + 34 * 30 + 15, Y0 - 55 * 30 - 15)
        p = terreno.ubicar_punto_cierre(self.flujo, lon, lat, radio_m=150)
        self.assertEqual(p.columna, 30)
        self.assertGreater(p.distancia_m, 0)

    def test_cuenca_del_valle(self):
        lon, lat = a_lonlat(X0 + 30 * 30 + 15, Y0 - 58 * 30 - 15)
        p = terreno.ubicar_punto_cierre(self.flujo, lon, lat, radio_m=60)
        c = terreno.delinear(self.flujo, p)
        # mismo número de celdas que el D8 de referencia: el valle no tiene depresiones ni zonas planas
        self.assertEqual(c.celdas, celdas_que_llegan(superficie(), (p.fila, p.columna)))
        self.assertAlmostEqual(c.area_km2, c.celdas * 0.0009, places=6)
        # el valle ocupa todo el modelo: la prueba de borde debe avisar que puede estar cortada
        self.assertTrue(c.cortada)
        self.assertIn("norte", c.lados_borde)
        self.assertAlmostEqual(c.poligono.area / 1e6, c.area_km2, delta=0.05 * c.area_km2)

        red = terreno.red_drenaje(self.flujo, c, umbral_km2=0.05)
        self.assertGreater(len(red), 0)
        self.assertTrue((red["orden"] >= 1).all())
        self.assertLessEqual(red["longitud_km"].sum(), c.area_km2 * 20)

        comp = terreno.comparar_cuencas(c, c)
        self.assertAlmostEqual(comp["coincidencia_pct"], 100.0, places=6)
        self.assertAlmostEqual(comp["diferencia_pct"], 0.0, places=6)

        capas = terreno.capas(c, red, "dem_propio", 0.05)
        gpkg = terreno.exportar_gpkg(capas, Path(self.tmp.name) / "c.gpkg")
        kml = terreno.exportar_kml(capas, Path(self.tmp.name) / "c.kml")
        self.assertTrue(gpkg.stat().st_size > 0 and kml.stat().st_size > 0)
        import geopandas as gpd
        cu = gpd.read_file(gpkg, layer="cuenca")
        self.assertEqual(cu.crs.to_epsg(), 9377)
        # Res. 940 de 2026: áreas en hectáreas con dos decimales
        self.assertEqual(round(float(cu["area_ha"].iloc[0]), 2), float(cu["area_ha"].iloc[0]))

    def test_ampliar_bbox_solo_hacia_los_lados_cortados(self):
        self.assertEqual(terreno.ampliar_bbox((-74, 4, -73, 5), ["norte"]), (-74, 4, -73, 5.1))
        self.assertEqual(terreno.ampliar_bbox((-74, 4, -73, 5), ["zona sin dato"]), (-74.1, 3.9, -72.9, 5.1))

    def test_bbox_invalido(self):
        with self.assertRaises(terreno.ErrorTerreno):
            terreno._validar_bbox((-73, 4, -74, 5))


if __name__ == "__main__":
    unittest.main()
