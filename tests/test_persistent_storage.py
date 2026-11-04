import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from facturacion.almacen import AlmacenAgente
from facturacion.sesiones import SesionesFacturacion


class PersistentStorageTests(unittest.TestCase):
    def test_billing_conversation_and_draft_survive_store_restart(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "agent.sqlite3"
            first_store = AlmacenAgente(database)
            first_sessions = SesionesFacturacion(almacen=first_store)
            first_session = first_sessions.obtener("18095550101")
            first_session.historial.append({"role": "user", "content": "Consulta"})
            first_session.clientes_verificados.add("131000001")
            first_session.productos_verificados.add("P001")
            draft = {"id": "B00001", "total": "100.00"}
            first_sessions.establecer_borrador(first_session, draft)
            first_store.guardar_conversacion(
                "web:client-1",
                [{"role": "user", "content": "Hola"}],
            )

            second_store = AlmacenAgente(database)
            second_sessions = SesionesFacturacion(almacen=second_store)
            restored_session = second_sessions.obtener("18095550101")

            self.assertEqual(restored_session.historial, first_session.historial)
            self.assertEqual(restored_session.clientes_verificados, {"131000001"})
            self.assertEqual(restored_session.productos_verificados, {"P001"})
            self.assertEqual(
                second_sessions.obtener_borrador(restored_session, "B00001"),
                draft,
            )
            self.assertEqual(
                second_store.cargar_conversacion("web:client-1"),
                [{"role": "user", "content": "Hola"}],
            )

    def test_expired_draft_is_removed_and_store_health_is_checked(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = AlmacenAgente(Path(temporary_directory) / "agent.sqlite3")
            sessions = SesionesFacturacion(expiracion_borrador=1, almacen=store)
            session = sessions.obtener("18095550101")
            sessions.establecer_borrador(session, {"id": "B00002"})
            session.borrador_creado_en -= 2
            sessions.guardar(session)

            self.assertIsNone(sessions.obtener_borrador(session, "B00002"))
            self.assertTrue(store.verificar())

    def test_inactive_conversations_are_pruned_while_service_stays_running(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = AlmacenAgente(Path(temporary_directory) / "agent.sqlite3")
            store.guardar_conversacion(
                "web:inactive",
                [{"role": "user", "content": "old message"}],
            )
            with store._conexion() as connection:
                connection.execute(
                    "UPDATE conversaciones SET actualizado_en = ?",
                    (time.time() - 91 * 24 * 60 * 60,),
                )
            store._ultima_purga = 0

            self.assertIsNone(store.cargar_conversacion("web:inactive"))

    def test_retention_setting_must_be_positive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            database = Path(temporary_directory) / "agent.sqlite3"
            with patch.dict(os.environ, {"AGENT_SESSION_RETENTION_DAYS": "0"}):
                with self.assertRaisesRegex(ValueError, "mayor que cero"):
                    AlmacenAgente(database)
            self.assertFalse(database.exists())


if __name__ == "__main__":
    unittest.main()
