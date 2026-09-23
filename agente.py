import os

from dotenv import load_dotenv
from groq import Groq


class Agente:
    def __init__(self, comportamiento: str) -> None:
        load_dotenv()

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("No se encontro la variable de entorno GROQ_API_KEY.")

        self.cliente: Groq = Groq(api_key=api_key)
        self.historial: list[dict[str, str]] = [
            {"role": "system", "content": comportamiento}
        ]