import os
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from dotenv import dotenv_values
from fastapi.testclient import TestClient

from facturacion.agente import AgenteFacturacion, _resumen_borrador
from facturacion.almacen import AlmacenAgente
from facturacion.config import ConfiguracionFacturacion, cargar_configuracion
from facturacion.dgii_flow import UMBRAL_RFCE, decidir_ruta
from facturacion.sesiones import SesionesFacturacion
from facturacion.simulador import (
    BORRADORES,
    CONSULTAS,
    EMITIDAS,
    FACTURAS,
    app,
)
from facturacion import simulador
from configurar_facturacion import guardar_variables
from servidor import app as agente_api


class ConfiguracionFacturacionTests(unittest.TestCase):
    def test_secret_writer_preserves_other_settings_and_updates_duplicates(self):
        with tempfile.TemporaryDirectory() as directorio:
            archivo = Path(directorio) / ".env"
            archivo.write_text(
                "# comentario\n"
                "EXISTENTE=conservar\n"
                'FACTURACION_API_KEY="clave-vieja"\n'
                "FACTURACION_API_KEY=duplicada\n",
                encoding="utf-8",
            )
            secreto = 'clave#con "comillas" y \\ barra'
            guardar_variables(
                archivo,
                {"FACTURACION_API_KEY": secreto, "AGENT_BRIDGE_TOKEN": "token-local"},
            )
            contenido = archivo.read_text(encoding="utf-8")
            valores = dotenv_values(archivo)
            self.assertIn("# comentario", contenido)
            self.assertEqual(valores["EXISTENTE"], "conservar")
            self.assertEqual(valores["FACTURACION_API_KEY"], secreto)
            self.assertEqual(valores["AGENT_BRIDGE_TOKEN"], "token-local")
            self.assertEqual(contenido.count("FACTURACION_API_KEY="), 1)

    def test_feature_is_disabled_when_all_settings_are_empty(self):
        variables = {
            "FACTURACION_API_URL": "",
            "FACTURACION_API_KEY": "",
            "FACTURACION_NUMEROS_AUTORIZADOS": "",
            "AGENT_BRIDGE_TOKEN": "",
        }
        with patch.dict(os.environ, variables, clear=True):
            self.assertIsNone(cargar_configuracion())

    def test_bridge_token_alone_does_not_activate_billing_integration(self):
        with patch.dict(
            os.environ,
            {"AGENT_BRIDGE_TOKEN": "bridge-test"},
            clear=True,
        ):
            self.assertIsNone(cargar_configuracion())

    def test_partial_configuration_fails_explicitly(self):
        with patch.dict(
            os.environ,
            {"FACTURACION_API_URL": "http://localhost:9001"},
            clear=True,
        ):
            with self.assertRaisesRegex(RuntimeError, "está incompleta"):
                cargar_configuracion()

    def test_only_whitelisted_whatsapp_numbers_are_authorized(self):
        config = ConfiguracionFacturacion(
            api_url="https://billing.example",
            api_key="test-key",
            token_puente="bridge-test",
            numeros_autorizados=frozenset({"18095550101"}),
            modelo="test-model",
        )
        self.assertTrue(config.autoriza("whatsapp:18095550101"))
        self.assertFalse(config.autoriza("whatsapp:18095550102"))
        self.assertFalse(config.autoriza("whatsapp:18095550101-extra"))
        self.assertFalse(config.autoriza("web:18095550101"))


class BillingSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.api_key_patch = patch.object(simulador, "API_KEY", "dev-key")
        self.api_key_patch.start()
        self.addCleanup(self.api_key_patch.stop)
        BORRADORES.clear()
        FACTURAS.clear()
        EMITIDAS.clear()
        CONSULTAS.clear()
        self.http = TestClient(app)
        self.headers = {"X-API-Key": "dev-key"}

    def test_draft_is_calculated_by_api_and_emission_is_idempotent(self):
        payload = {
            "tipo_ecf": "31",
            "cliente": "131000001",
            "lineas": [{"codigo": "P001", "cantidad": "2"}],
            "forma_pago": "contado",
            "origen": {"canal": "whatsapp", "telefono": "18095550101"},
        }
        response = self.http.post(
            "/v1/facturas/borradores",
            headers=self.headers,
            json=payload,
        )
        self.assertEqual(response.status_code, 200)
        borrador = response.json()
        self.assertEqual(borrador["subtotal"], "7000.00")
        self.assertEqual(borrador["itbis"], "1260.00")
        self.assertEqual(borrador["total"], "8260.00")
        self.assertEqual(
            BORRADORES[borrador["id"]]["origen"]["telefono"],
            "18095550101",
        )

        ruta = f"/v1/facturas/borradores/{borrador['id']}/emitir"
        primera = self.http.post(
            ruta,
            headers={**self.headers, "Idempotency-Key": f"emitir:{borrador['id']}"},
        )
        segunda = self.http.post(
            ruta,
            headers={**self.headers, "Idempotency-Key": f"emitir:{borrador['id']}"},
        )
        self.assertEqual(primera.status_code, 200)
        self.assertEqual(primera.json(), segunda.json())
        self.assertTrue(primera.json()["e_ncf"].startswith("E31"))
        self.assertEqual(len(primera.json()["e_ncf"]), 13)
        self.assertEqual(
            self.http.post(ruta, headers=self.headers).status_code,
            400,
        )

        factura_id = primera.json()["id"]
        self.http.get(f"/v1/facturas/{factura_id}", headers=self.headers)
        aceptada = self.http.get(
            f"/v1/facturas/{factura_id}",
            headers=self.headers,
        ).json()
        self.assertEqual(aceptada["estado"], "ACEPTADO")
        respuesta_pdf = self.http.get(
            f"/v1/facturas/{factura_id}/pdf",
            headers=self.headers,
        )
        self.assertEqual(respuesta_pdf.status_code, 200)
        self.assertTrue(respuesta_pdf.content.startswith(b"%PDF-1.4"))

    def test_api_key_and_invalid_customer_are_rejected(self):
        self.assertEqual(
            self.http.get("/v1/productos", headers={"X-API-Key": "wrong"}).status_code,
            401,
        )
        response = self.http.post(
            "/v1/facturas/borradores",
            headers=self.headers,
            json={
                "tipo_ecf": "31",
                "cliente": "999999999",
                "lineas": [{"codigo": "P001", "cantidad": 1}],
                "forma_pago": "contado",
                "origen": {"canal": "whatsapp", "telefono": "18095550101"},
            },
        )
        self.assertEqual(response.status_code, 422)


class BillingAgentTests(unittest.TestCase):
    def setUp(self):
        self.config = ConfiguracionFacturacion(
            api_url="https://billing.example",
            api_key="test-key",
            token_puente="bridge-test",
            numeros_autorizados=frozenset({"18095550101"}),
            modelo="test-model",
        )
        self.directorio_temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.directorio_temporal.cleanup)
        self.sesiones = SesionesFacturacion(
            almacen=AlmacenAgente(
                Path(self.directorio_temporal.name) / "agent.sqlite3"
            )
        )
        self.cliente = Mock()
        self.agente = AgenteFacturacion(
            self.config,
            self.sesiones,
            cliente=self.cliente,
            modelo=Mock(),
        )

    def test_preparing_invoice_creates_a_draft_but_never_emits(self):
        borrador = {
            "id": "B00012",
            "tipo_ecf": "31",
            "cliente_nombre": "Cliente de prueba",
            "lineas": [
                {"descripcion": "Servicio", "cantidad": "2", "monto": "7000.00"}
            ],
            "subtotal": "7000.00",
            "itbis": "1260.00",
            "total": "8260.00",
        }
        self.cliente.crear_borrador.return_value = borrador
        sesion = self.sesiones.obtener("18095550101")
        sesion.clientes_verificados.add("131000001")
        sesion.productos_verificados.add("P001")
        resultado = self.agente._ejecutar_herramienta(
            "preparar_factura",
            {
                "tipo_ecf": "31",
                "cliente": "131000001",
                "lineas": [{"codigo": "P001", "cantidad": 2}],
                "forma_pago": "contado",
            },
            "18095550101",
            sesion,
        )
        self.assertEqual(resultado["borrador_id"], "B00012")
        self.assertEqual(
            self.cliente.crear_borrador.call_args.args[0]["origen"],
            {"canal": "whatsapp", "telefono": "18095550101"},
        )
        self.cliente.emitir.assert_not_called()
        self.assertEqual(
            self.sesiones.obtener_borrador(sesion, "B00012"),
            borrador,
        )

    def test_model_can_prepare_a_draft_but_only_returns_confirmation_buttons(self):
        draft = {
            "id": "B00016",
            "tipo_ecf": "32",
            "cliente_nombre": None,
            "lineas": [
                {"descripcion": "Servicio", "cantidad": "1", "monto": "10.00"}
            ],
            "subtotal": "10.00",
            "itbis": "1.80",
            "total": "11.80",
        }
        self.cliente.crear_borrador.return_value = draft
        buscar_producto = SimpleNamespace(
            id="call-search",
            function=SimpleNamespace(
                name="buscar_producto",
                arguments='{"texto":"P001"}',
            ),
        )
        preparar_factura = SimpleNamespace(
            id="call-1",
            function=SimpleNamespace(
                name="preparar_factura",
                arguments=(
                    '{"tipo_ecf":"32","lineas":[{"codigo":"P001","cantidad":1}],'
                    '"forma_pago":"contado"}'
                ),
            ),
        )
        self.agente.modelo.chat.completions.create.side_effect = [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[buscar_producto],
                        )
                    )
                ]
            ),
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[preparar_factura],
                        )
                    )
                ]
            ),
        ]
        self.cliente.buscar_producto.return_value = {
            "productos": [{"codigo": "P001", "descripcion": "Servicio"}]
        }

        resultado = self.agente.responder("18095550101", "Prepara una factura")

        self.assertEqual(resultado.respuesta, "")
        self.assertEqual(resultado.interaccion["borrador_id"], "B00016")
        self.assertIn("Total: RD$ 11.80", resultado.interaccion["texto"])
        self.assertEqual(self.agente.modelo.chat.completions.create.call_count, 2)
        self.cliente.emitir.assert_not_called()

    def test_confirmation_summary_keeps_total_within_whatsapp_limit(self):
        resumen = _resumen_borrador(
            {
                "id": "B00015",
                "tipo_ecf": "32",
                "cliente_nombre": "Cliente",
                "lineas": [
                    {
                        "descripcion": "Producto " + ("x" * 200),
                        "cantidad": "1",
                        "monto": "1.00",
                    }
                    for _ in range(50)
                ],
                "subtotal": "50.00",
                "itbis": "9.00",
                "total": "59.00",
            }
        )
        self.assertLessEqual(len(resumen), 1024)
        self.assertIn("Total: RD$ 59.00", resumen)

    def test_only_confirm_button_emits_and_returns_the_accepted_pdf(self):
        session = self.sesiones.obtener("18095550101")
        draft = {"id": "B00013"}
        self.sesiones.establecer_borrador(session, draft)
        self.cliente.emitir.return_value = {
            "id": "F00013",
            "e_ncf": "E310000000013",
            "estado": "EN_PROCESO",
        }
        self.cliente.descargar_pdf.return_value = b"%PDF-1.4 test"
        with patch.object(
            self.agente,
            "_esperar_resultado",
            return_value={
                "id": "F00013",
                "e_ncf": "E310000000013",
                "estado": "ACEPTADO",
            },
        ):
            resultado = self.agente.responder_boton(
                "18095550101",
                "CONFIRMAR:B00013",
            )
            retry = self.agente.responder_boton(
                "18095550101",
                "CONFIRMAR:B00013",
            )
        self.cliente.emitir.assert_called_once_with("B00013")
        self.assertEqual(resultado.documento["nombre"], "E310000000013.pdf")
        self.assertTrue(resultado.documento["contenido_base64"])
        self.assertEqual(retry.documento["nombre"], "E310000000013.pdf")
        self.assertEqual(
            self.agente.responder_boton(
                "18095550101",
                "ENTREGADA:B00013",
            ).respuesta,
            "Documento entregado.",
        )
        self.assertIsNone(
            self.sesiones.obtener_borrador(session, "B00013")
        )

    def test_unverified_product_code_cannot_be_used_in_a_draft(self):
        session = self.sesiones.obtener("18095550101")
        with self.assertRaisesRegex(ValueError, "Busca y verifica cada producto"):
            self.agente._ejecutar_herramienta(
                "preparar_factura",
                {
                    "tipo_ecf": "32",
                    "lineas": [{"codigo": "P999", "cantidad": 1}],
                    "forma_pago": "contado",
                },
                "18095550101",
                session,
            )
        self.cliente.crear_borrador.assert_not_called()

    def test_cancel_button_never_emits(self):
        session = self.sesiones.obtener("18095550101")
        self.sesiones.establecer_borrador(session, {"id": "B00014"})
        resultado = self.agente.responder_boton(
            "18095550101",
            "CANCELAR:B00014",
        )
        self.assertIn("No se emitió", resultado.respuesta)
        self.cliente.emitir.assert_not_called()


class BillingBridgeTests(unittest.TestCase):
    def setUp(self):
        self.entorno = patch.dict(
            os.environ,
            {
                "FACTURACION_API_URL": "https://billing.example",
                "FACTURACION_API_KEY": "billing-test-key",
                "FACTURACION_NUMEROS_AUTORIZADOS": "18095550101",
                "AGENT_BRIDGE_TOKEN": "bridge-test-token",
            },
        )
        self.entorno.start()
        self.addCleanup(self.entorno.stop)
        self.http = TestClient(agente_api)
        self.http.__enter__()
        self.addCleanup(self.http.__exit__, None, None, None)

    def test_chat_thread_limiter_supports_500_concurrent_requests(self):
        self.assertEqual(
            agente_api.state.chat_thread_limiter.total_tokens,
            500,
        )

    def test_bridge_token_is_required_and_web_users_cannot_confirm_invoices(self):
        body = {
            "cliente_id": "web:visitor",
            "mensaje": "Emitir",
            "accion_id": "CONFIRMAR:B00001",
        }
        no_autenticado = self.http.post("/chat", json=body)
        self.assertEqual(no_autenticado.status_code, 401)

        respuesta = self.http.post(
            "/chat",
            json=body,
            headers={"X-Agent-Bridge-Token": "bridge-test-token"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertIn("ya no está disponible", respuesta.json()["respuesta"])

    def test_bridge_token_is_enforced_even_when_billing_is_disabled(self):
        with patch.dict(
            os.environ,
            {
                "AGENT_BRIDGE_TOKEN": "bridge-only-token",
                "FACTURACION_API_URL": "",
                "FACTURACION_API_KEY": "",
                "FACTURACION_NUMEROS_AUTORIZADOS": "",
            },
        ):
            response = self.http.post(
                "/chat",
                json={"cliente_id": "web:client", "mensaje": "Hola"},
            )
        self.assertEqual(response.status_code, 401)


class DGIIRouteTests(unittest.TestCase):
    def test_consumption_below_threshold_uses_rfce(self):
        self.assertEqual(decidir_ruta("32", Decimal("249999.99")), "rfce")
        self.assertEqual(
            decidir_ruta("32", UMBRAL_RFCE),
            "recepcion",
        )
        self.assertEqual(decidir_ruta("31", Decimal("100.00")), "recepcion")
        with self.assertRaises(ValueError):
            decidir_ruta("34", Decimal("100.00"))


if __name__ == "__main__":
    unittest.main()
