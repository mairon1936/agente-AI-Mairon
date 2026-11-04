import os
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from agente_facturacion import AgenteFacturacionElectronica
from cliente import responder_a
from sistem_prompts import MENSAJE_BIENVENIDA, NOMBRE_SISTEMA, SYSTEM_PROMPT


class AgenteFacturacionTests(unittest.TestCase):
    @patch.dict(os.environ, {"GROQ_API_KEY": "test-key"})
    @patch("agente_facturacion.Groq")
    def test_uses_billing_prompt_without_business_database(self, groq_class):
        response = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Consulta general."))]
        )
        groq_class.return_value.chat.completions.create.return_value = response
        agente = AgenteFacturacionElectronica()

        self.assertEqual(agente.responder("Hola"), "Consulta general.")
        arguments = groq_class.return_value.chat.completions.create.call_args.kwargs
        self.assertEqual(arguments["messages"][0]["content"], SYSTEM_PROMPT)
        self.assertIn(NOMBRE_SISTEMA, SYSTEM_PROMPT)
        self.assertNotIn("Café Santo Domingo", SYSTEM_PROMPT)

    def test_whatsapp_first_response_includes_exact_bold_welcome(self):
        agente = SimpleNamespace(
            historial=[{}, {}, {}],
            responder=lambda mensaje: "¿Cómo puedo ayudarte?",
        )
        candado = threading.Lock()

        with (
            patch("cliente.definir_agente", return_value=(agente, candado)),
        ):
            respuesta = responder_a("whatsapp:test-client", "Hola")

        self.assertEqual(
            respuesta,
            f"*{MENSAJE_BIENVENIDA}*\n\n¿Cómo puedo ayudarte?",
        )


if __name__ == "__main__":
    unittest.main()
