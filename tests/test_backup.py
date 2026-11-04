import sqlite3
import tarfile
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from facturacion.backup import crear_respaldo


class BackupTests(unittest.TestCase):
    def test_backup_contains_valid_database_and_message_queue(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database = root / "data" / "agent.sqlite3"
            database.parent.mkdir()
            with closing(sqlite3.connect(database)) as connection:
                with connection:
                    connection.execute("CREATE TABLE sample (value TEXT)")
                    connection.execute("INSERT INTO sample VALUES ('persisted')")

            bridge = root / "bridge" / "whatsapp-queue"
            (bridge / "pending").mkdir(parents=True)
            (bridge / "pending" / "message.json").write_text(
                '{"id":"test"}',
                encoding="utf-8",
            )
            backup = crear_respaldo(
                base_datos=database,
                directorio_respaldo=root / "backups",
                directorio_puente=root / "bridge",
            )

            with closing(sqlite3.connect(backup / "agent.sqlite3")) as connection:
                with connection:
                    self.assertEqual(
                        connection.execute("PRAGMA integrity_check").fetchone()[0],
                        "ok",
                    )
                    self.assertEqual(
                        connection.execute("SELECT value FROM sample").fetchone()[0],
                        "persisted",
                    )
            with tarfile.open(backup / "whatsapp-queue.tar.gz", "r:gz") as archive:
                self.assertIn(
                    "whatsapp-queue/pending/message.json",
                    archive.getnames(),
                )


if __name__ == "__main__":
    unittest.main()
