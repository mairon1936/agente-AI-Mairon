import json
import logging
import os
import platform
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

logger = logging.getLogger("agente.almacen")


def _ruta_base_datos() -> Path:
    ruta_configurada = os.getenv("AGENT_DATABASE_PATH", "").strip()
    if ruta_configurada:
        return Path(ruta_configurada).expanduser()
    directorio = os.getenv("AGENT_DATA_DIR", "").strip()
    base = (
        Path(directorio).expanduser()
        if directorio
        else Path(__file__).resolve().parents[1] / "data"
    )
    return base / "agent.sqlite3"


class AlmacenAgente:
    """Almacén SQLite persistente para conversaciones y sesiones fiscales."""

    def __init__(self, ruta: Path | None = None) -> None:
        self.ruta = (ruta or _ruta_base_datos()).resolve()
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        if platform.system() != "Windows":
            self.ruta.parent.chmod(0o700)
        self._retencion_dias = int(os.getenv("AGENT_SESSION_RETENTION_DAYS", "90"))
        if self._retencion_dias < 1:
            raise ValueError("AGENT_SESSION_RETENTION_DAYS debe ser mayor que cero.")
        self._candado_purga = threading.Lock()
        self._ultima_purga = 0.0
        self._inicializar()
        logger.info("Almacén persistente del agente inicializado.")

    def _conectar(self) -> sqlite3.Connection:
        conexion = sqlite3.connect(self.ruta, timeout=30)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA busy_timeout = 30000")
        conexion.execute("PRAGMA synchronous = FULL")
        return conexion

    @contextmanager
    def _conexion(self) -> Generator[sqlite3.Connection, None, None]:
        conexion = self._conectar()
        try:
            with conexion:
                yield conexion
        finally:
            conexion.close()

    def _inicializar(self) -> None:
        with self._conexion() as conexion:
            conexion.execute("PRAGMA journal_mode = WAL")
            conexion.executescript(
                """
                CREATE TABLE IF NOT EXISTS conversaciones (
                    cliente_id TEXT PRIMARY KEY,
                    historial_json TEXT NOT NULL,
                    actualizado_en REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sesiones_facturacion (
                    cliente_id TEXT PRIMARY KEY,
                    historial_json TEXT NOT NULL,
                    clientes_json TEXT NOT NULL,
                    productos_json TEXT NOT NULL,
                    borrador_json TEXT,
                    borrador_creado_en REAL NOT NULL,
                    actualizado_en REAL NOT NULL
                );
                """
            )
        if platform.system() != "Windows":
            self.ruta.chmod(0o600)
        self._purgar(force=True)

    def _purgar(self, *, force: bool = False) -> None:
        ahora = time.monotonic()
        if not force and ahora - self._ultima_purga < 60 * 60:
            return
        with self._candado_purga:
            ahora = time.monotonic()
            if not force and ahora - self._ultima_purga < 60 * 60:
                return
            limite = time.time() - self._retencion_dias * 24 * 60 * 60
            with self._conexion() as conexion:
                conexion.execute(
                    "DELETE FROM conversaciones WHERE actualizado_en < ?",
                    (limite,),
                )
                conexion.execute(
                    "DELETE FROM sesiones_facturacion WHERE actualizado_en < ?",
                    (limite,),
                )
            self._ultima_purga = ahora

    def guardar_conversacion(
        self,
        cliente_id: str,
        historial: list[dict[str, Any]],
    ) -> None:
        self._purgar()
        with self._conexion() as conexion:
            conexion.execute(
                """
                INSERT INTO conversaciones (cliente_id, historial_json, actualizado_en)
                VALUES (?, ?, ?)
                ON CONFLICT(cliente_id) DO UPDATE SET
                    historial_json = excluded.historial_json,
                    actualizado_en = excluded.actualizado_en
                """,
                (cliente_id, json.dumps(historial, ensure_ascii=False), time.time()),
            )

    def cargar_conversacion(self, cliente_id: str) -> list[dict[str, Any]] | None:
        self._purgar()
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT historial_json FROM conversaciones WHERE cliente_id = ?",
                (cliente_id,),
            ).fetchone()
        if fila is None:
            return None
        historial = json.loads(fila["historial_json"])
        if not isinstance(historial, list):
            raise RuntimeError("El historial persistido del agente está dañado.")
        return historial

    def guardar_sesion_facturacion(
        self,
        cliente_id: str,
        *,
        historial: list[dict[str, Any]],
        clientes: set[str],
        productos: set[str],
        borrador: dict[str, Any] | None,
        borrador_creado_en: float,
    ) -> None:
        self._purgar()
        with self._conexion() as conexion:
            conexion.execute(
                """
                INSERT INTO sesiones_facturacion (
                    cliente_id, historial_json, clientes_json, productos_json,
                    borrador_json, borrador_creado_en, actualizado_en
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cliente_id) DO UPDATE SET
                    historial_json = excluded.historial_json,
                    clientes_json = excluded.clientes_json,
                    productos_json = excluded.productos_json,
                    borrador_json = excluded.borrador_json,
                    borrador_creado_en = excluded.borrador_creado_en,
                    actualizado_en = excluded.actualizado_en
                """,
                (
                    cliente_id,
                    json.dumps(historial, ensure_ascii=False),
                    json.dumps(sorted(clientes), ensure_ascii=False),
                    json.dumps(sorted(productos), ensure_ascii=False),
                    (
                        json.dumps(borrador, ensure_ascii=False)
                        if borrador is not None
                        else None
                    ),
                    borrador_creado_en,
                    time.time(),
                ),
            )

    def cargar_sesion_facturacion(self, cliente_id: str) -> dict[str, Any] | None:
        self._purgar()
        with self._conexion() as conexion:
            fila = conexion.execute(
                "SELECT * FROM sesiones_facturacion WHERE cliente_id = ?",
                (cliente_id,),
            ).fetchone()
        if fila is None:
            return None
        borrador = (
            json.loads(fila["borrador_json"])
            if fila["borrador_json"] is not None
            else None
        )
        return {
            "historial": json.loads(fila["historial_json"]),
            "clientes": set(json.loads(fila["clientes_json"])),
            "productos": set(json.loads(fila["productos_json"])),
            "borrador": borrador,
            "borrador_creado_en": fila["borrador_creado_en"],
        }

    def verificar(self) -> bool:
        self._purgar()
        with self._conexion() as conexion:
            resultado = conexion.execute("PRAGMA quick_check").fetchone()
        return resultado is not None and resultado[0] == "ok"
