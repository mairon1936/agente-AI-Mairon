from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel

from cliente import responder_a

load_dotenv()

app = FastAPI(title="Agente de atención al cliente")


class MensajeEntrada(BaseModel):
    cliente_id: str
    mensaje: str


@app.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


@app.post("/chat")
def chat(entrada: MensajeEntrada) -> dict[str, str]:
    respuesta = responder_a(entrada.cliente_id, entrada.mensaje)
    return {
        "cliente_id": entrada.cliente_id,
        "respuesta": respuesta,
    }
7