import json
import os
import re
import unicodedata
from collections.abc import Iterable
from typing import Any
from typing import NotRequired, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

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
                "o cuánto sería el precio de uno o varios productos. Calcula con los "
                "precios del archivo datos_negocio_cafe_santo_domingo.xlsx; si un "
                "producto no figura allí, consulta fuentes de internet y presenta "
                "cualquier precio encontrado como referencia no confirmada."
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


def _palabras_nombre(nombre: str) -> set[str]:
    return set(re.findall(r"\w+", _normalizar_nombre(nombre)))


class ErrorBusquedaOficial(RuntimeError):
    """Indica que no fue posible consultar las fuentes oficiales."""


def _producto_en_catalogo_local(
    producto_solicitado: str,
    productos: list[dict[str, Any]],
) -> bool:
    palabras_solicitadas = _palabras_nombre(producto_solicitado)
    return any(
        palabras_solicitadas
        and palabras_solicitadas.issubset(
            _palabras_nombre(producto["nombre"])
        )
        for producto in productos
    )


def _buscar_producto_en_fuente_oficial(producto: str) -> bool:
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    search_engine_id = os.getenv("GOOGLE_CSE_ID")
    if not api_key or not search_engine_id:
        raise ErrorBusquedaOficial(
            "Google Custom Search no está configurado. Define "
            "GOOGLE_CSE_API_KEY y GOOGLE_CSE_ID para verificar productos."
        )

    parametros = urlencode(
        {
            "key": api_key,
            "cx": search_engine_id,
            "q": f'site:induban.com "{producto}"',
            "num": 5,
        }
    )
    solicitud = Request(
        f"https://www.googleapis.com/customsearch/v1?{parametros}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(solicitud, timeout=10) as respuesta:
            resultados = json.loads(respuesta.read().decode("utf-8"))
    except HTTPError as error:
        raise ErrorBusquedaOficial(
            f"Google Custom Search respondió con el estado HTTP {error.code}."
        ) from error
    except (URLError, TimeoutError, OSError) as error:
        raise ErrorBusquedaOficial(
            "No se pudo conectar con Google Custom Search."
        ) from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ErrorBusquedaOficial(
            "Google Custom Search devolvió una respuesta inválida."
        ) from error

    if not isinstance(resultados, dict):
        raise ErrorBusquedaOficial(
            "Google Custom Search devolvió una respuesta inválida."
        )
    elementos = resultados.get("items", [])
    if not isinstance(elementos, list):
        raise ErrorBusquedaOficial(
            "Google Custom Search devolvió una respuesta inválida."
        )

    palabras_especificas = _palabras_nombre(producto) - {
        "cafe",
        "santo",
        "domingo",
        "de",
        "del",
        "la",
        "el",
        "en",
        "y",
    }
    if not palabras_especificas:
        return False

    for resultado in elementos:
        if not isinstance(resultado, dict):
            continue
        url = resultado.get("link")
        if not isinstance(url, str) or urlparse(url).hostname not in {
            "induban.com",
            "www.induban.com",
        }:
            continue
        texto_resultado = _normalizar_nombre(
            f"{resultado.get('title', '')} {resultado.get('snippet', '')}"
        )
        if palabras_especificas.issubset(_palabras_nombre(texto_resultado)):
            return True
    return False


def buscar_precio_en_internet(producto: str) -> str:
    """Busca referencias de precio en internet cuando el producto no está en Excel."""
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    search_engine_id = os.getenv("GOOGLE_CSE_ID")
    if not api_key or not search_engine_id:
        return (
            f"El producto '{producto}' no aparece en el menú del Excel. "
            "No puedo consultar precios en internet porque Google Custom Search "
            "no está configurado (GOOGLE_CSE_API_KEY y GOOGLE_CSE_ID)."
        )

    parametros = urlencode(
        {
            "key": api_key,
            "cx": search_engine_id,
            "q": f"{producto} precio RD$",
            "num": 5,
        }
    )
    solicitud = Request(
        f"https://www.googleapis.com/customsearch/v1?{parametros}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(solicitud, timeout=10) as respuesta:
            resultados = json.loads(respuesta.read().decode("utf-8"))
    except HTTPError as error:
        return (
            f"El producto '{producto}' no aparece en el menú del Excel. "
            f"La búsqueda web respondió con HTTP {error.code}."
        )
    except (URLError, TimeoutError, OSError):
        return (
            f"El producto '{producto}' no aparece en el menú del Excel. "
            "No se pudo conectar con la búsqueda web."
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        return (
            f"El producto '{producto}' no aparece en el menú del Excel. "
            "La búsqueda web devolvió una respuesta inválida."
        )

    if not isinstance(resultados, dict):
        return (
            f"El producto '{producto}' no aparece en el menú del Excel. "
            "La búsqueda web devolvió una respuesta inválida."
        )
    elementos = resultados.get("items", [])
    if not isinstance(elementos, list):
        return (
            f"El producto '{producto}' no aparece en el menú del Excel. "
            "La búsqueda web devolvió una respuesta inválida."
        )
    if not elementos:
        return (
            f"El producto '{producto}' no aparece en el menú del Excel y "
            "no encontré referencias de precio en internet."
        )

    fuentes = []
    for elemento in elementos:
        if not isinstance(elemento, dict):
            continue
        titulo = elemento.get("title")
        enlace = elemento.get("link")
        fragmento = elemento.get("snippet")
        if not isinstance(enlace, str) or not enlace.startswith(
            ("https://", "http://")
        ):
            continue
        detalle = f"- {titulo or enlace}"
        if isinstance(fragmento, str) and fragmento:
            detalle += f": {fragmento}"
        detalle += f" ({enlace})"
        fuentes.append(detalle)

    if not fuentes:
        return (
            f"El producto '{producto}' no aparece en el menú del Excel y "
            "no encontré fuentes web utilizables."
        )

    return (
        f"El producto '{producto}' no aparece en el menú del Excel. "
        "Encontré estas posibles referencias en internet; verifica el precio "
        "y su vigencia directamente con cada comercio:\n"
        + "\n".join(fuentes)
    )


def verificar_productos_pedido(
    productos_solicitados: list[str],
    datos: dict[str, Any] | None = None,
) -> list[str]:
    """Devuelve los productos que no se pudieron verificar local u oficialmente."""
    informacion = datos if datos is not None else cargar_datos_negocio()
    productos_locales = (
        informacion["catalogo"]["productos"]
        + informacion["menu_cafeteria"]["productos"]
    )
    no_verificados: list[str] = []
    for producto in productos_solicitados:
        if _producto_en_catalogo_local(producto, productos_locales):
            continue
        if not _buscar_producto_en_fuente_oficial(producto):
            no_verificados.append(producto)
    return no_verificados


def _formatear_precio(precio: float) -> str:
    return f"RD${precio:g}"


def calcular_pedidos(items: Iterable[ItemPedido]) -> str:
    """Calcula el total referencial de una lista de productos y cantidades."""
    datos = cargar_datos_negocio()
    productos_menu = datos["menu_cafeteria"]["productos"]
    detalle: list[str] = []
    total_minimo = 0.0
    total_maximo = 0.0
    hay_productos_fuera_del_excel = False

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
            hay_productos_fuera_del_excel = True
            detalle.append(buscar_precio_en_internet(nombre_producto))
            continue

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

    respuesta = "\n".join(detalle)
    if hay_productos_fuera_del_excel:
        if total_minimo > 0:
            respuesta += (
                f"\nSubtotal de productos encontrados en el Excel: {texto_total}."
            )
        respuesta += (
            "\nNo se calculó un total completo porque hay productos fuera "
            "del Excel."
        )
    else:
        respuesta += (
            f"\nTotal referencial: {texto_total}."
            "\nLos precios no están confirmados y pueden cambiar; "
            "verifica la vigencia con el negocio."
        )
    return respuesta


def ejecutar_herramientas(
    nombre: str,
    argumentos: dict[str, Any],
    cliente_id: str = "terminar",
) -> str:
    """Ejecuta una herramienta disponible por su nombre."""
    if nombre in {"calcular_pedido", "calcular_pedidos"}:
        return calcular_pedidos(argumentos["items"])
    if nombre == "registrar_solicitud":
        return registrar_solicitud(
            argumentos["solicitud"],
            argumentos.get("deliveri", "Pendiente"),
            cliente_id,
        )

    return f"La herramienta '{nombre}' no existe."
