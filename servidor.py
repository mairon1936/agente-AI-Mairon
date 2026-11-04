import anyio
import hmac
import os
import sqlite3
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from cliente import procesar_mensaje, verificar_almacen
from facturacion.config import cargar_configuracion

load_dotenv()
cargar_configuracion()

MAX_SOLICITUDES_CONCURRENTES = 500


@asynccontextmanager
async def lifespan(aplicacion: FastAPI) -> AsyncGenerator[None, None]:
    limitador = anyio.to_thread.current_default_thread_limiter()
    limitador.total_tokens = MAX_SOLICITUDES_CONCURRENTES
    aplicacion.state.chat_thread_limiter = limitador
    yield


app = FastAPI(
    title="Agente de atención al cliente",
    lifespan=lifespan,
)


class MensajeEntrada(BaseModel):
    cliente_id: str = Field(min_length=1, max_length=140)
    mensaje: str = Field(min_length=1, max_length=2000)
    accion_id: str | None = Field(default=None, max_length=100)


@app.get("/salud")
def salud() -> dict[str, str]:
    try:
        if not verificar_almacen():
            raise HTTPException(status_code=503, detail="Almacén no disponible.")
    except sqlite3.Error as error:
        raise HTTPException(
            status_code=503,
            detail="Almacén no disponible.",
        ) from error
    return {"estado": "ok"}


@app.post("/chat")
async def chat(
    entrada: MensajeEntrada,
    x_agent_bridge_token: str | None = Header(default=None),
) -> dict:
    configuracion = cargar_configuracion()
    token_puente = (
        configuracion.token_puente
        if configuracion is not None
        else os.getenv("AGENT_BRIDGE_TOKEN", "").strip()
    )
    if token_puente and not hmac.compare_digest(
        x_agent_bridge_token or "",
        token_puente,
    ):
        raise HTTPException(status_code=401, detail="Puente no autorizado.")
    resultado = await anyio.to_thread.run_sync(
        procesar_mensaje,
        entrada.cliente_id,
        entrada.mensaje,
        entrada.accion_id,
        limiter=app.state.chat_thread_limiter,
    )
    return {"cliente_id": entrada.cliente_id, **resultado}
7