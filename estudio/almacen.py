"""Dónde se guardan los estudios.

Todo lo que se guarda pasa por la interfaz `Almacen`. Hoy hay una sola versión, `AlmacenCarpeta`, que escribe en una
carpeta temporal del servidor; para conservar el estudio, la página entrega un ZIP y lo recibe de vuelta otro día.

Para conectar Supabase (u otro servicio) después, basta escribir otra clase con los mismos cinco métodos y
elegirla en `almacen_configurado`. Las etapas del estudio no cambian (decisión del usuario, 18 nov 2026).
"""
from __future__ import annotations

import io
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Protocol

from .core import Estudio

NOMBRE_CORE = "estudio.json"
LIMITE_ZIP_BYTES = 300 * 1024 * 1024   # tope al descomprimir un ZIP subido (protege el servidor)
_NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_\-][A-Za-z0-9_.\-/]*$")


class Almacen(Protocol):
    def guardar(self, estudio_id: str, nombre: str, datos: bytes) -> None: ...
    def leer(self, estudio_id: str, nombre: str) -> bytes: ...
    def existe(self, estudio_id: str, nombre: str) -> bool: ...
    def listar(self, estudio_id: str) -> list[str]: ...
    def ruta_local(self, estudio_id: str, nombre: str) -> Path: ...


def _validar_nombre(nombre: str) -> str:
    """Evita rutas que se salgan de la carpeta del estudio (.., rutas absolutas)."""
    if not _NOMBRE_VALIDO.match(nombre) or ".." in Path(nombre).parts:
        raise ValueError(f"Nombre de archivo no permitido: {nombre!r}")
    return nombre


class AlmacenCarpeta:
    """Guarda cada estudio en una subcarpeta. En la nube la carpeta es temporal: se borra al reiniciar."""

    def __init__(self, base: Path | str | None = None):
        self.base = Path(base) if base else Path(tempfile.gettempdir()) / "estudios_hidrologicos"
        self.base.mkdir(parents=True, exist_ok=True)

    def ruta_local(self, estudio_id: str, nombre: str) -> Path:
        ruta = self.base / _validar_nombre(estudio_id) / _validar_nombre(nombre)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        return ruta

    def guardar(self, estudio_id: str, nombre: str, datos: bytes) -> None:
        self.ruta_local(estudio_id, nombre).write_bytes(datos)

    def leer(self, estudio_id: str, nombre: str) -> bytes:
        return self.ruta_local(estudio_id, nombre).read_bytes()

    def existe(self, estudio_id: str, nombre: str) -> bool:
        return self.ruta_local(estudio_id, nombre).exists()

    def listar(self, estudio_id: str) -> list[str]:
        carpeta = self.base / _validar_nombre(estudio_id)
        if not carpeta.exists():
            return []
        return sorted(str(p.relative_to(carpeta)) for p in carpeta.rglob("*") if p.is_file())


def almacen_configurado(config: dict | None = None) -> Almacen:
    """Punto único para elegir el almacén. Hoy siempre la carpeta temporal."""
    return AlmacenCarpeta((config or {}).get("carpeta"))


def guardar_estudio(almacen: Almacen, estudio: Estudio) -> None:
    almacen.guardar(estudio.id, NOMBRE_CORE, estudio.a_json().encode("utf-8"))


def leer_estudio(almacen: Almacen, estudio_id: str) -> Estudio:
    return Estudio.desde_json(almacen.leer(estudio_id, NOMBRE_CORE).decode("utf-8"))


def exportar_zip(almacen: Almacen, estudio: Estudio) -> bytes:
    """ZIP con el core y todos los archivos del estudio, para descargar y retomar después."""
    guardar_estudio(almacen, estudio)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre in almacen.listar(estudio.id):
            z.writestr(nombre, almacen.leer(estudio.id, nombre))
    return buf.getvalue()


def importar_zip(almacen: Almacen, datos: bytes) -> Estudio:
    """Recibe un ZIP exportado por `exportar_zip` y deja el estudio listo para seguir."""
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        if NOMBRE_CORE not in z.namelist():
            raise ValueError("El ZIP no tiene estudio.json: no parece un estudio de esta herramienta.")
        if sum(i.file_size for i in z.infolist()) > LIMITE_ZIP_BYTES:
            raise ValueError("El ZIP es demasiado grande para abrirlo aquí.")
        estudio = Estudio.desde_json(z.read(NOMBRE_CORE).decode("utf-8"))
        for info in z.infolist():
            if info.is_dir():
                continue
            almacen.guardar(estudio.id, _validar_nombre(info.filename), z.read(info))
    return estudio
