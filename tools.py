import unicodedata
from collections.abc import Iterable
from typing import Any
from typing import NotRequired, TypedDict

from datos import cargar_datos_negocio
from pedidos import registrar_solicitud
from sistem_prompts import SYSTEM_PROMPT


def crear_historial(
    comportamiento: str = SYSTEM_PROMPT,
) -> list[dict[str, Any]]:
    """Crea el historial inicial de una conversación."""
    return [{"role": "system", "content": comportamiento}]


class ItemPedido(TypedDict):
    cantidad: int
    producto: NotRequired[str]
    productos: NotRequired[str]


def preparar_mensajes_groq(
    historial: list[dict[str, Any]],
    mensaje_actual: str,
) -> list[dict[str, Any]]:
    """Prepara contexto reciente para Groq sin modificar el historial local."""
    if not historial:
        return [{"role": "user", "content": mensaje_actual}]

    mensajes = [historial[0]]
    respuesta_anterior = next(
        (
            mensaje.get("content")
            for mensaje in reversed(historial[1:])
            if mensaje.get("role") == "assistant"
            and isinstance(mensaje.get("content"), str)
            and mensaje["content"]
        ),
        None,
    )
    if respuesta_anterior:
        mensajes.append(
            {"role": "assistant", "content": respuesta_anterior[:400]}
        )
    mensajes.append({"role": "user", "content": mensaje_actual})
    return mensajes


def mostrar_historial(historial: list[dict[str, Any]]) -> None:
    """Imprime los mensajes visibles de una conversación."""
    for mensaje in historial:
        rol = mensaje.get("role")
        contenido = mensaje.get("content")
        if rol in {"user", "assistant"} and contenido is not None:
            print(f"{rol}: {contenido}")


herramientas = [
    {
        "type": "function",
        "function": {
            "name": "calcular_pedidos",
            "description": (
                "Usa siempre esta herramienta cuando el cliente pregunte cuánto cuesta "
                "o cuánto sería el precio de uno o varios productos del catálogo o del "
                "menú de cafetería. Calcula el total con los precios de referencia; "
                "no inventes precios."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "producto": {
                                    "type": "string",
                                    "description": (
                                        "Nombre del producto como aparece en el menú, "
                                        "incluida su presentación."
                                    ),
                                },
                                "cantidad": {
                                    "type": "integer",
                                    "minimum": 1,
                                    "description": "Cantidad solicitada del producto.",
                                },
                            },
                            "required": ["producto", "cantidad"],
                            "additionalProperties": False,
                        },
                    }
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_solicitud",
            "description": (
                "Usa esta herramienta cuando el cliente quiera realizar, guardar "
                "o registrar una solicitud de pedido. Guarda el resumen del pedido "
                "en pedidos.xlsx. Esto solo registra la solicitud localmente; no "
                "confirma que el negocio la haya recibido o aceptado."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "solicitud": {
                        "type": "string",
                        "description": (
                            "Resumen fiel del pedido solicitado por el cliente, "
                            "incluidas cantidades, productos y detalles que haya dado."
                        ),
                    },
                    "deliveri": {
                        "type": "string",
                        "enum": ["Delivery", "Retiro", "Pendiente"],
                        "description": "Modalidad de entrega elegida por el cliente.",
                    },
                },
                "required": ["solicitud"],
                "additionalProperties": False,
            },
        },
    },
]


def _normalizar_nombre(nombre: str) -> str:
    nombre_sin_acentos = unicodedata.normalize("NFKD", nombre)
    return " ".join(
        "".join(
            caracter
            for caracter in nombre_sin_acentos
            if not unicodedata.combining(caracter)
        )
        .casefold()
        .split()
    )


def _formatear_precio(precio: float) -> str:
    return f"RD${precio:g}"


def calcular_pedidos(items: Iterable[ItemPedido]) -> str:
    """Calcula el total referencial de una lista de productos y cantidades."""
    datos = cargar_datos_negocio()
    productos_menu = (
        datos["catalogo"]["productos"] + datos["menu_cafeteria"]["productos"]
    )
    detalle: list[str] = []
    total_minimo = 0.0
    total_maximo = 0.0

    for item in items:
        nombre_producto = item.get("producto") or item.get("productos")
        if not nombre_producto:
            raise ValueError("Cada producto debe incluir la clave 'producto'.")

        producto_solicitado = _normalizar_nombre(nombre_producto)
        cantidad = item["cantidad"]
        if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
            raise ValueError("La cantidad de cada producto debe ser un entero positivo.")

        coincidencias = []
        for producto in productos_menu:
            nombre = _normalizar_nombre(producto["nombre"])
            presentacion = producto["presentacion"]
            nombre_completo = _normalizar_nombre(
                f"{producto['nombre']} {presentacion}" if presentacion else producto["nombre"]
            )
            if producto_solicitado == nombre_completo or producto_solicitado == nombre:
                coincidencias.append(producto)

        if not coincidencias:
            return f"El producto '{producto_solicitado}' no está en el menú."

        coincidencias_exactas = [
            producto
            for producto in coincidencias
            if _normalizar_nombre(
                f"{producto['nombre']} {producto['presentacion']}"
                if producto["presentacion"]
                else producto["nombre"]
            )
            == producto_solicitado
        ]
        producto = (
            coincidencias_exactas[0]
            if coincidencias_exactas
            else coincidencias[0] if len(coincidencias) == 1 else None
        )
        if producto is None:
            return (
                f"El producto '{producto_solicitado}' tiene varias presentaciones "
                "en el menú; especifica cuál deseas."
            )

        precio = producto["precio"]
        if precio is None:
            return (
                f"El producto '{producto_solicitado}' está en el menú, "
                "pero no tiene un precio de referencia disponible."
            )

        subtotal_minimo = precio["minimo"] * cantidad
        subtotal_maximo = precio["maximo"] * cantidad
        total_minimo += subtotal_minimo
        total_maximo += subtotal_maximo

        texto_subtotal = _formatear_precio(subtotal_minimo)
        if subtotal_minimo != subtotal_maximo:
            texto_subtotal += f"–{_formatear_precio(subtotal_maximo)}"
        detalle.append(f"{cantidad} x {producto_solicitado} = {texto_subtotal}")

    if not detalle:
        return "No se recibieron productos para calcular."

    texto_total = _formatear_precio(total_minimo)
    if total_minimo != total_maximo:
        texto_total += f"–{_formatear_precio(total_maximo)}"

    return (
        "\n".join(detalle)
        + f"\nTotal referencial: {texto_total}."
        "\nLos precios no están confirmados y pueden cambiar; verifica la vigencia con el negocio."
    )


def ejecutar_herramientas(
    nombre: str, argumentos: dict[str, Any]
) -> str:
    """Ejecuta una herramienta disponible por su nombre."""
    if nombre in {"calcular_pedido", "calcular_pedidos"}:
        return calcular_pedidos(argumentos["items"])
    if nombre == "registrar_solicitud":
        return registrar_solicitud(
            argumentos["solicitud"],
            argumentos.get("deliveri", "Pendiente"),
        )

    return f"La herramienta '{nombre}' no existe."
