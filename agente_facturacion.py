import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq, GroqError

from sistem_prompts import NOMBRE_SISTEMA, SYSTEM_PROMPT

MODELO = "openai/gpt-oss-safeguard-20b"


class AgenteFacturacionElectronica:
    """Asistente informativo que no accede a la base del negocio."""

    nombre_negocio = NOMBRE_SISTEMA

    def __init__(
        self,
        historial: list[dict[str, Any]] | None = None,
    ) -> None:
        load_dotenv()
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("No se encontró la variable de entorno GROQ_API_KEY.")

        self.cliente = Groq(api_key=api_key)
        self.historial = historial or [{"role": "system", "content": SYSTEM_PROMPT}]

    def responder(self, mensaje: str) -> str:
        self.historial.append({"role": "user", "content": mensaje})
        try:
            respuesta = self.cliente.chat.completions.create(
                model=MODELO,
                messages=self.historial,
            )
        except GroqError:
            self.historial.pop()
            return (
                "No pude procesar la consulta en este momento. "
                "Inténtalo de nuevo más tarde."
            )

        contenido = respuesta.choices[0].message.content or ""
        if not contenido.strip():
            self.historial.pop()
            return "No recibí una respuesta válida. Inténtalo de nuevo."
        self.historial.append({"role": "assistant", "content": contenido})
        return contenido

    def mostrar_historiar(self) -> None:
        for mensaje in self.historial:
            if mensaje["role"] in {"user", "assistant"}:
                print(f"{mensaje['role']}: {mensaje['content']}")
