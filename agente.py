import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from groq import Groq

from tools import ejecutar_herramientas, herramientas


class Agente:
    def __init__(self, comportamiento: str) -> None:
        load_dotenv()

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("No se encontro la variable de entorno GROQ_API_KEY.")

        self.nombre_negocio = "Café Santo Domingo"
        self.cliente: Groq = Groq(api_key=api_key)
        ruta_datos = Path(__file__).with_name("informacion_negocio.json")
        with ruta_datos.open(encoding="utf-8") as archivo:
            informacion_negocio = json.load(archivo)

        instrucciones = (
            f"{comportamiento}\n\n"
            "Información de referencia del negocio (JSON):\n"
            f"{json.dumps(informacion_negocio, ensure_ascii=False)}"
        )
        self.historial: list[dict[str, Any]] = [
            {"role": "system", "content": instrucciones}
        ]

    def responder(self, mensaje: str) -> str:
        self.historial.append({"role": "user", "content": mensaje})

        rondas_herramientas = 0
        while True:
            respuesta = self.cliente.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=self.historial,
                tools=herramientas,
                tool_choice="auto",
            )
            mensaje_asistente = respuesta.choices[0].message
            llamadas = mensaje_asistente.tool_calls or []

            if not llamadas:
                contenido = mensaje_asistente.content or ""
                self.historial.append({"role": "assistant", "content": contenido})
                return contenido

            if rondas_herramientas >= 5:
                raise RuntimeError(
                    "El modelo superó el límite de llamadas consecutivas a herramientas."
                )

            self.historial.append(
                {
                    "role": "assistant",
                    "content": mensaje_asistente.content,
                    "tool_calls": [
                        {
                            "id": llamada.id,
                            "type": "function",
                            "function": {
                                "name": llamada.function.name,
                                "arguments": llamada.function.arguments,
                            },
                        }
                        for llamada in llamadas
                    ],
                }
            )

            for llamada in llamadas:
                try:
                    argumentos = json.loads(llamada.function.arguments)
                except json.JSONDecodeError as error:
                    resultado = f"Argumentos de herramienta inválidos: {error.msg}."
                else:
                    try:
                        resultado = ejecutar_herramientas(
                            llamada.function.name,
                            argumentos,
                        )
                    except (KeyError, TypeError, ValueError) as error:
                        resultado = f"Argumentos de herramienta inválidos: {error}."

                self.historial.append(
                    {
                        "role": "tool",
                        "tool_call_id": llamada.id,
                        "content": resultado,
                    }
                )

            rondas_herramientas += 1

    def mostrar_historiar(self) -> None:
        for mensaje in self.historial:
            if mensaje["role"] not in {"system", "sistem"}:
                print(f"{mensaje['role']}: {mensaje.get('content', '')}")