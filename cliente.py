import threading

from agente_facturacion import AgenteFacturacionElectronica
from sistem_prompts import MENSAJE_BIENVENIDA

from facturacion.agente import AgenteFacturacion
from facturacion.almacen import AlmacenAgente
from facturacion.config import cargar_configuracion
from facturacion.sesiones import SesionesFacturacion

_agente: dict[str, AgenteFacturacionElectronica] = {}
_almacen = AlmacenAgente()
_candado: dict[str, threading.Lock] = {}
_candado_id = threading.Lock()
_agentes_facturacion: dict[str, AgenteFacturacion] = {}


def definir_agente(
    cliente_id: str,
) -> tuple[AgenteFacturacionElectronica, threading.Lock]:
    """Obtiene o crea el agente y el candado asociados a un cliente."""
    with _candado_id:
        if cliente_id not in _agente:
            historial = _almacen.cargar_conversacion(cliente_id)
            _agente[cliente_id] = AgenteFacturacionElectronica(historial)
            _candado[cliente_id] = threading.Lock()
        return _agente[cliente_id], _candado[cliente_id]


def responder_a(cliente_id: str, mensaje: str) -> str:
    """Responde al mensaje usando el agente aislado del cliente."""
    agente, candado = definir_agente(cliente_id)
    with candado:
        respuesta = agente.responder(mensaje)
        _almacen.guardar_conversacion(cliente_id, agente.historial)
        if cliente_id.startswith("whatsapp:") and len(agente.historial) == 3:
            return f"*{MENSAJE_BIENVENIDA}*\n\n{respuesta}"
        return respuesta


def procesar_mensaje(
    cliente_id: str,
    mensaje: str,
    accion_id: str | None = None,
) -> dict:
    """Enruta al flujo fiscal solo si está configurado y autorizado."""
    configuracion = cargar_configuracion()
    if configuracion is not None and configuracion.autoriza(cliente_id):
        numero = cliente_id.removeprefix("whatsapp:")
        with _candado_id:
            agente = _agentes_facturacion.get(numero)
            if agente is None:
                agente = AgenteFacturacion(
                    configuracion,
                    SesionesFacturacion(),
                )
                _agentes_facturacion[numero] = agente
        if accion_id is not None:
            return agente.responder_boton(numero, accion_id).como_dict()
        return agente.responder(numero, mensaje).como_dict()

    if accion_id is not None:
        return {
            "respuesta": (
                "La acción de facturación ya no está disponible. "
                "Solicita preparar un borrador nuevamente."
            )
        }
    return {"respuesta": responder_a(cliente_id, mensaje)}


def verificar_almacen() -> bool:
    return _almacen.verificar()
