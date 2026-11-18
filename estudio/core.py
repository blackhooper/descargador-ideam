"""El "core" de un estudio: una receta pequeña en JSON con todas las decisiones.

Guarda qué se decidió, en qué paso, con qué valor, con qué fuente y quién lo decidió. No guarda los archivos
pesados (modelo de elevación, rásteres de flujo): esos van aparte en el almacén y el core solo los nombra. Con el
core y sus archivos se puede repetir el estudio igual; es la memoria de cálculo reproducible (ver el plan,
"Patrón core").
"""
from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone

from . import fuentes

VERSION_CORE = 1


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Decision:
    paso: str            # p. ej. "terreno.dem"
    clave: str           # p. ej. "fuente_dem"
    valor: object        # algo que se pueda escribir en JSON
    fuentes: list[str]   # claves de fuentes.FUENTES
    nota: str = ""
    por: str = "herramienta"   # "herramienta" (valor por defecto con su fuente) o "hidrologo" (lo cambió el usuario)
    fecha: str = field(default_factory=_ahora)

    @property
    def marca(self) -> str:
        return "hidrologo" if self.por == "hidrologo" else fuentes.marca_principal(self.fuentes)


@dataclass
class Estudio:
    nombre: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    creado: str = field(default_factory=_ahora)
    version_core: int = VERSION_CORE
    decisiones: list[Decision] = field(default_factory=list)
    archivos: dict[str, str] = field(default_factory=dict)    # nombre lógico -> nombre en el almacén
    resultados: dict[str, dict] = field(default_factory=dict)  # paso -> resumen (números, no rásteres)

    # -- decisiones --
    def decidir(self, paso: str, clave: str, valor, fuentes_: list[str], nota: str = "",
                por: str = "herramienta") -> Decision:
        """Registra (o reemplaza) una decisión. Valida que cada fuente exista."""
        for c in fuentes_:
            fuentes.fuente(c)
        d = Decision(paso, clave, valor, list(fuentes_), nota, por)
        self.decisiones = [x for x in self.decisiones if not (x.paso == paso and x.clave == clave)]
        self.decisiones.append(d)
        return d

    def decision(self, paso: str, clave: str, defecto=None):
        for d in self.decisiones:
            if d.paso == paso and d.clave == clave:
                return d.valor
        return defecto

    def fuentes_usadas(self) -> list[str]:
        return sorted({c for d in self.decisiones for c in d.fuentes})

    # -- JSON --
    def a_json(self) -> str:
        datos = asdict(self)
        return json.dumps(datos, ensure_ascii=False, indent=2)

    @classmethod
    def desde_json(cls, texto: str) -> "Estudio":
        datos = json.loads(texto)
        if datos.get("version_core", 0) > VERSION_CORE:
            raise ValueError("Este estudio se guardó con una versión más nueva de la herramienta.")
        decisiones = [Decision(**d) for d in datos.pop("decisiones", [])]
        e = cls(**datos)
        e.decisiones = decisiones
        return e
