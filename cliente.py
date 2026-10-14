import threading

from agente import Agente
from sistem_prompts import SYSTEM_PROMPT

_agente: dict[str, Agente] = {}
_candado: dict[str, threading.Lock] = {}
_candado_id = threading.Lock()


def definir_agente(cliente_id: str) -> tuple[Agente, threading.Lock]:
    """Obtiene o crea el agente y el candado asociados a un cliente."""
    with _candado_id:
        if cliente_id not in _agente:
            _agente[cliente_id] = Agente(SYSTEM_PROMPT)
            _candado[cliente_id] = threading.Lock()
        return _agente[cliente_id], _candado[cliente_id]


def responder_a(cliente_id: str, mensaje: str) -> str:
    """Responde al mensaje usando el agente aislado del cliente."""
    agente, candado = definir_agente(cliente_id)
    with candado:
        return agente.responder(mensaje)
