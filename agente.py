import os

from dotenv import load_dotenv
from groq import Groq


class Agente:
    def __init__(self, comportamiento: str) -> None:
        load_dotenv()

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("No se encontro la variable de entorno GROQ_API_KEY.")

        self.nombre_negocio = "Café Santo Domingo"
        self.cliente: Groq = Groq(api_key=api_key)
        self.historial: list[dict[str, str]] = [
            {"role": "system", "content": comportamiento}
        ]

    def responder(self, mensaje: str) -> str:
        self.historial.append({"role": "user", "content": mensaje})

        respuesta = self.cliente.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=self.historial,
        )
        contenido = respuesta.choices[0].message.content
        self.historial.append({"role": "assistant", "content": contenido})

        return contenido

    def mostrar_historiar(self) -> None:
        for mensaje in self.historial:
            if mensaje["role"] not in {"system", "sistem"}:
                print(f"{mensaje['role']}: {mensaje['content']}")