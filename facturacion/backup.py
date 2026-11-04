import argparse
import os
import platform
import shutil
import sqlite3
import tarfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from .almacen import _ruta_base_datos


ROOT = Path(__file__).resolve().parents[1]


def crear_respaldo(
    *,
    base_datos: Path | None = None,
    directorio_respaldo: Path | None = None,
    directorio_puente: Path | None = None,
    retencion_dias: int = 30,
) -> Path:
    if retencion_dias < 1:
        raise ValueError("La retención de respaldos debe ser mayor que cero.")
    origen = (base_datos or _ruta_base_datos()).resolve()
    if not origen.is_file():
        raise FileNotFoundError(f"No se encontró la base de datos: {origen}")
    destino_raiz = (directorio_respaldo or Path(os.getenv(
        "AGENT_BACKUP_DIR",
        str(ROOT / "backups"),
    ))).resolve()
    puente = (
        directorio_puente
        if directorio_puente is not None
        else Path(
            os.getenv(
                "BRIDGE_DATA_DIR",
                str(ROOT / "data" / "bridge"),
            )
        )
    ).resolve()
    destino_raiz.mkdir(parents=True, exist_ok=True)
    if platform.system() != "Windows":
        destino_raiz.chmod(0o700)

    marca_tiempo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destino = destino_raiz / f"respaldo-{marca_tiempo}"
    destino.mkdir(mode=0o700)
    archivo_db = destino / "agent.sqlite3"
    temporal_db = destino / ".agent.sqlite3.tmp"
    try:
        with closing(sqlite3.connect(origen, timeout=30)) as origen_db:
            with origen_db:
                with closing(sqlite3.connect(temporal_db)) as respaldo_db:
                    with respaldo_db:
                        origen_db.backup(respaldo_db)
                        integridad = respaldo_db.execute(
                            "PRAGMA integrity_check"
                        ).fetchone()
                        if integridad is None or integridad[0] != "ok":
                            raise RuntimeError(
                                "La copia de la base de datos no pasó integrity_check."
                            )
        os.replace(temporal_db, archivo_db)

        cola = puente / "whatsapp-queue"
        if cola.is_dir():
            archivo_cola = destino / "whatsapp-queue.tar.gz"
            with tarfile.open(archivo_cola, "w:gz") as respaldo_cola:
                for nombre in ("pending", "processing", "completed", "failed"):
                    carpeta = cola / nombre
                    if carpeta.exists():
                        respaldo_cola.add(
                            carpeta,
                            arcname=f"whatsapp-queue/{nombre}",
                            recursive=False,
                        )
                        for archivo in carpeta.iterdir():
                            if archivo.is_file() and archivo.suffix == ".json":
                                respaldo_cola.add(
                                    archivo,
                                    arcname=f"whatsapp-queue/{nombre}/{archivo.name}",
                                    recursive=False,
                                )

        if platform.system() != "Windows":
            for archivo in destino.iterdir():
                archivo.chmod(0o600)
        limite = time.time() - retencion_dias * 24 * 60 * 60
        for anterior in destino_raiz.glob("respaldo-*"):
            if anterior == destino:
                continue
            if anterior.stat().st_mtime < limite and anterior.is_dir():
                for archivo in anterior.iterdir():
                    if archivo.is_file():
                        archivo.unlink()
                anterior.rmdir()
    except Exception:
        shutil.rmtree(destino, ignore_errors=True)
        raise
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description="Crea y verifica un respaldo del agente.")
    parser.add_argument("--retention-days", type=int, default=30)
    argumentos = parser.parse_args()
    resultado = crear_respaldo(retencion_dias=argumentos.retention_days)
    print(f"Respaldo verificado creado en: {resultado}")


if __name__ == "__main__":
    main()
