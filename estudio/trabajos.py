"""Trabajos en segundo plano.

Leer el modelo de elevación y acondicionarlo tarda de 5 a 20 segundos. La página no muestra pantallas de carga
(regla del diseño): el trabajo corre en un hilo mientras la persona sigue llenando los demás campos, y un punto junto
a la etiqueta se enciende cuando termina.

Este módulo no depende de Streamlit; la página guarda un `Trabajos` en `st.cache_resource`.
"""
from __future__ import annotations

import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Trabajo:
    clave: str
    estado: str = "cargando"        # "cargando", "listo" o "error"
    resultado: object = None
    error: str = ""                 # mensaje para la persona
    detalle: str = ""               # traza, para el registro
    inicio: float = field(default_factory=time.time)
    fin: float = 0.0

    @property
    def segundos(self) -> float:
        return (self.fin or time.time()) - self.inicio


class Trabajos:
    def __init__(self, maximo: int = 12):
        self._candado = threading.Lock()
        self._trabajos: dict[str, Trabajo] = {}
        self.maximo = maximo

    def obtener(self, clave: str) -> Trabajo | None:
        with self._candado:
            return self._trabajos.get(clave)

    def iniciar(self, clave: str, funcion: Callable[[], object], mensaje_error: Callable[[Exception], str]) -> Trabajo:
        """Arranca `funcion` en un hilo si no hay ya un trabajo con esa clave (o si el anterior falló)."""
        with self._candado:
            previo = self._trabajos.get(clave)
            if previo and previo.estado != "error":
                return previo
            t = Trabajo(clave)
            self._trabajos[clave] = t
            # los más viejos se olvidan para no llenar la memoria del servidor
            while len(self._trabajos) > self.maximo:
                self._trabajos.pop(next(iter(self._trabajos)))

        def correr():
            try:
                t.resultado = funcion()
                t.estado = "listo"
            except Exception as e:   # se informa a la persona; nunca se cae la página
                t.error = mensaje_error(e)
                t.detalle = traceback.format_exc()
                t.estado = "error"
            finally:
                t.fin = time.time()

        threading.Thread(target=correr, daemon=True, name=f"estudio-{clave[:20]}").start()
        return t

    def pendientes(self, claves) -> bool:
        return any((t := self.obtener(c)) is not None and t.estado == "cargando" for c in claves)
