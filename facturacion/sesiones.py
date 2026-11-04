import threading
import time
from dataclasses import dataclass, field
from typing import Any

from .almacen import AlmacenAgente


@dataclass
class SesionFacturacion:
    identificador: str = ""
    historial: list[dict[str, Any]] = field(default_factory=list)
    clientes_verificados: set[str] = field(default_factory=set)
    productos_verificados: set[str] = field(default_factory=set)
    borrador_pendiente: dict[str, Any] | None = None
    borrador_creado_en: float = 0
    candado: threading.RLock = field(default_factory=threading.RLock)


class SesionesFacturacion:
    """Sesiones persistidas en SQLite para sobrevivir reinicios del proceso."""

    def __init__(
        self,
        expiracion_borrador: int = 1800,
        almacen: AlmacenAgente | None = None,
    ) -> None:
        self._sesiones: dict[str, SesionFacturacion] = {}
        self._candado = threading.Lock()
        self._expiracion_borrador = expiracion_borrador
        self.almacen = almacen or AlmacenAgente()

    def obtener(self, numero: str) -> SesionFacturacion:
        with self._candado:
            sesion = self._sesiones.get(numero)
            if sesion is None:
                estado = self.almacen.cargar_sesion_facturacion(numero)
                sesion = SesionFacturacion(identificador=numero)
                if estado is not None:
                    sesion.historial = estado["historial"]
                    sesion.clientes_verificados = estado["clientes"]
                    sesion.productos_verificados = estado["productos"]
                    sesion.borrador_pendiente = estado["borrador"]
                    sesion.borrador_creado_en = estado["borrador_creado_en"]
                self._sesiones[numero] = sesion
            return sesion

    def guardar(self, sesion: SesionFacturacion) -> None:
        self.almacen.guardar_sesion_facturacion(
            sesion.identificador,
            historial=sesion.historial,
            clientes=sesion.clientes_verificados,
            productos=sesion.productos_verificados,
            borrador=sesion.borrador_pendiente,
            borrador_creado_en=sesion.borrador_creado_en,
        )

    def establecer_borrador(
        self,
        sesion: SesionFacturacion,
        borrador: dict[str, Any],
    ) -> None:
        sesion.borrador_pendiente = dict(borrador)
        sesion.borrador_creado_en = time.time()
        self.guardar(sesion)

    def obtener_borrador(
        self,
        sesion: SesionFacturacion,
        borrador_id: str,
    ) -> dict[str, Any] | None:
        borrador = sesion.borrador_pendiente
        if borrador is None or borrador.get("id") != borrador_id:
            return None
        if time.time() - sesion.borrador_creado_en > self._expiracion_borrador:
            sesion.borrador_pendiente = None
            sesion.borrador_creado_en = 0
            self.guardar(sesion)
            return None
        return borrador

    def limpiar_borrador(self, sesion: SesionFacturacion) -> None:
        sesion.borrador_pendiente = None
        sesion.borrador_creado_en = 0
        self.guardar(sesion)

    def recortar_historial(
        self,
        sesion: SesionFacturacion,
        max_mensajes: int = 24,
    ) -> None:
        historial = sesion.historial
        if len(historial) > max_mensajes:
            del historial[: len(historial) - max_mensajes]
        while historial and not (
            historial[0].get("role") == "user"
            and isinstance(historial[0].get("content"), str)
        ):
            historial.pop(0)
        self.guardar(sesion)
