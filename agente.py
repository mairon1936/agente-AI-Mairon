import os
import json
import re
import unicodedata
from typing import Any

from dotenv import load_dotenv
from groq import (
    APIConnectionError,
    APIStatusError,
    AuthenticationError,
    Groq,
    GroqError,
    RateLimitError,
)

from datos import cargar_datos_negocio
from pedidos import (
    ESTADO_CONFIRMADO,
    actualizar_delivery,
    actualizar_estado_pedido,
    registrar_pedido,
)
from tools import (
    SYSTEM_PROMPT,
    crear_historial,
    ejecutar_herramientas,
    herramientas,
    mostrar_historial,
    preparar_mensajes_groq,
)

MODELO = "openai/gpt-oss-safeguard-20b"


def _normalizar_texto(texto: str) -> str:
    texto_sin_acentos = unicodedata.normalize("NFKD", texto)
    return "".join(
        caracter
        for caracter in texto_sin_acentos
        if not unicodedata.combining(caracter)
    ).casefold()


def _es_opcion_pedidos(mensaje: str) -> bool:
    texto = _normalizar_texto(mensaje).strip()
    return re.fullmatch(
        r"(?:opcion\s*)?8(?:[.)]?(?:\s+realizar un pedido)?)?",
        texto,
    ) is not None


def _es_opcion_delivery(mensaje: str) -> bool:
    texto = _normalizar_texto(mensaje).strip()
    return re.fullmatch(
        r"(?:opcion\s*)?9(?:[.)]?(?:\s+solicitar delivery)?)?",
        texto,
    ) is not None


def _interpretar_delivery(mensaje: str) -> str | None:
    texto = _normalizar_texto(mensaje)
    if re.search(
        r"\b(retirar|retiro|recoger|recogida|pasar|paso|recojo)\b",
        texto,
    ) or re.fullmatch(r"\s*8\s*[.)]?\s*", texto):
        return "Retiro"
    if re.search(
        r"\b(delivery|deliveri|domicilio|envio|entrega)\b",
        texto,
    ) or re.fullmatch(r"\s*9\s*[.)]?\s*", texto):
        return "Delivery"
    return None


def _es_confirmacion_pedido(mensaje: str) -> bool:
    texto = _normalizar_texto(mensaje)
    if re.search(
        r"\b(no|aun no|todavia no)\b.{0,20}\b(confirmo|confirmar|confirmado)\b",
        texto,
    ):
        return False
    return re.search(
        r"\b(confirmo|confirmar|confirmado|confirmada)\b",
        texto,
    ) is not None


def _es_solicitud_pedido(mensaje: str) -> bool:
    texto = _normalizar_texto(mensaje)
    productos = (
        r"pedido|pedidos|orden|ordenes|compra|compras|"
        r"espresso|espressos|cafe|cafes|galleta|galletas|"
        r"cappuccino|cappuccinos|cappuchino|cappuchinos|"
        r"mocha|mochas|te|tes|croissant|croissants|"
        r"sandwich|sandwiches|cold\s+brew|latte|lattes|"
        r"bebida|bebidas"
    )
    verbos_pedido = (
        r"quiero|quisiera|deseo|necesito|me gustaria|"
        r"dame|ponme|anotame|agregame|preparame|"
        r"haz(?:me)?|hacer|realiza|realizar|"
        r"registra|registrar|guarda|guardar|"
        r"ordena|ordenar|compra|comprar|pide|pedir"
    )

    if re.search(
        rf"\b({verbos_pedido})\b.{{0,80}}\b({productos})\b",
        texto,
    ) is None and re.search(
        rf"\b({productos})\b.{{0,80}}\b({verbos_pedido})\b",
        texto,
    ) is None:
        return False

    orden_explicita = re.search(
        r"\b(pedido|pedidos|ordenar|ordena|comprar|compra|pedir|pide|"
        r"registrar|registra|guardar|guarda|hacer|realizar|hazme|realiza)\b",
        texto,
    )
    consulta_sin_pedido = re.search(
        r"\b(saber|consultar|ver|conocer|precio|precios|cuanto|cuesta|"
        r"cuestan|costo|vale|valen)\b",
        texto,
    )
    if consulta_sin_pedido and not orden_explicita:
        return False
    return True


def _es_consulta_precio_menu(mensaje: str, datos: dict[str, Any]) -> bool:
    texto = _normalizar_texto(mensaje)
    consulta_precio = re.search(
        r"\b(precio|precios|cuanto|cuesta|cuestan|costar|vale|valen|valor|"
        r"costo|sale|salen)\b|\ba como\b",
        texto,
    )
    if consulta_precio is None:
        return False

    if re.search(
        r"\b(menu|carta|bebida|bebidas|catalogo|producto|productos)\b",
        texto,
    ):
        return True

    productos = (
        datos["catalogo"]["productos"] + datos["menu_cafeteria"]["productos"]
    )
    for producto in productos:
        nombres = (producto["nombre"], producto["familia"])
        if any(
            _normalizar_texto(nombre) in texto
            or _normalizar_texto(nombre.removeprefix("Café Santo Domingo "))
            in texto
            for nombre in nombres
        ):
            return True
    return False


def _datos_seguros_para_contexto(datos: dict[str, Any]) -> dict[str, Any]:
    def productos_sin_precios(productos: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                clave: producto[clave]
                for clave in ("nombre", "familia", "presentacion")
                if producto.get(clave) is not None
            }
            for producto in productos
        ]

    return {
        "negocio": datos["negocio"],
        "catalogo": {
            "nota": datos["catalogo"].get("nota", ""),
            "productos": productos_sin_precios(datos["catalogo"]["productos"]),
        },
        "menu_cafeteria": {
            "nota": datos["menu_cafeteria"].get("nota", ""),
            "productos": productos_sin_precios(
                datos["menu_cafeteria"]["productos"]
            ),
        },
        "servicios": [
            {"nombre": servicio["nombre"]}
            for servicio in datos.get("servicios", [])
        ],
    }


class Agente:
    def __init__(self, comportamiento: str = SYSTEM_PROMPT) -> None:
        load_dotenv()

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("No se encontro la variable de entorno GROQ_API_KEY.")

        self.nombre_negocio = "Café Santo Domingo"
        self.cliente: Groq = Groq(api_key=api_key)
        self.comportamiento = comportamiento
        self.esperando_detalle_pedido = False
        self.esperando_metodo_entrega = False
        self.esperando_confirmacion_pedido = False
        self.fila_pedido_pendiente: int | None = None
        self.delivery_preseleccionado = False

        self.historial = crear_historial(comportamiento)

    def _crear_instrucciones(
        self,
        informacion_negocio: dict[str, Any],
        contexto: dict[str, Any] | None = None,
    ) -> str:
        datos_contexto = (
            contexto
            if contexto is not None
            else _datos_seguros_para_contexto(informacion_negocio)
        )
        instrucciones = (
            f"{self.comportamiento}\n\n"
            "Usa solo estos datos verificados para responder. No reveles "
            "información interna. Datos (JSON):\n"
            f"{json.dumps(datos_contexto, ensure_ascii=False, separators=(',', ':'))}"
        )
        return instrucciones

    def _mensajes_para_groq(self, mensaje_actual: str) -> list[dict[str, Any]]:
        return preparar_mensajes_groq(self.historial, mensaje_actual)

    def _manejar_error_groq(self, error: GroqError) -> str:
        if isinstance(error, AuthenticationError):
            contenido = (
                "Groq rechazó la clave API. Verifica que GROQ_API_KEY sea válida "
                "y esté configurada en el archivo .env."
            )
        elif isinstance(error, RateLimitError):
            contenido = (
                "Groq alcanzó el límite de solicitudes o cuota disponible. "
                "Inténtalo de nuevo más tarde."
            )
        elif isinstance(error, APIConnectionError):
            contenido = (
                "No se pudo conectar con Groq. Verifica tu conexión a internet "
                "e inténtalo de nuevo."
            )
        elif isinstance(error, APIStatusError):
            if error.status_code == 413:
                contenido = (
                    "El servicio alcanzó temporalmente su límite de procesamiento. "
                    "Espera un minuto y vuelve a intentarlo."
                )
            else:
                contenido = (
                    f"Groq no pudo completar la solicitud (HTTP {error.status_code}). "
                    "Inténtalo de nuevo más tarde."
                )
        else:
            contenido = "Groq no pudo completar la solicitud. Inténtalo de nuevo."

        self.historial.append({"role": "assistant", "content": contenido})
        return contenido

    def responder(self, mensaje: str) -> str:
        datos_actuales = cargar_datos_negocio()
        solicitud_pedido = _es_solicitud_pedido(mensaje)
        consulta_precio_menu = _es_consulta_precio_menu(mensaje, datos_actuales)
        max_completion_tokens = 256
        if consulta_precio_menu:
            self.historial[0]["content"] = self.comportamiento
        else:
            texto_normalizado = _normalizar_texto(mensaje)
            contexto = _datos_seguros_para_contexto(datos_actuales)
            contexto_relevante: dict[str, Any] = {}

            if re.search(
                r"\b(menu|carta|cafeteria|bebida|bebidas|acompanamiento|"
                r"latte|espresso|mocha|croissant|galleta|sandwich)\b",
                texto_normalizado,
            ):
                contexto_relevante["menu_cafeteria"] = contexto["menu_cafeteria"]
            if re.search(
                r"\b(catalogo|producto|productos|molido|grano|capsula|"
                r"cafe|cafes|recomendacion|recomendar|recomiend\w*)\b",
                texto_normalizado,
            ):
                contexto_relevante["catalogo"] = contexto["catalogo"]
            if re.search(
                r"\b(servicio|servicios|sucursal|sucursales|contacto|"
                r"telefono|direccion|evento|oficina)\b",
                texto_normalizado,
            ):
                contexto_relevante["servicios"] = contexto["servicios"]

            self.historial[0]["content"] = (
                self._crear_instrucciones(datos_actuales, contexto_relevante)
                if contexto_relevante
                else self.comportamiento
            )
            if contexto_relevante:
                max_completion_tokens = (
                    768
                    if "catalogo" in contexto_relevante
                    and "menu_cafeteria" not in contexto_relevante
                    else 512
                )
        self.historial.append({"role": "user", "content": mensaje})

        if (
            self.esperando_confirmacion_pedido
            and self.fila_pedido_pendiente is not None
            and _es_confirmacion_pedido(mensaje)
        ):
            try:
                actualizar_estado_pedido(
                    self.fila_pedido_pendiente,
                    ESTADO_CONFIRMADO,
                )
            except OSError:
                contenido = (
                    "No pude actualizar la confirmación del pedido. "
                    "Inténtalo de nuevo más tarde."
                )
                self.historial.append({"role": "assistant", "content": contenido})
                return contenido
            except ValueError:
                contenido = "No encontré un pedido pendiente para confirmar."
                self.historial.append({"role": "assistant", "content": contenido})
                return contenido

            self.esperando_confirmacion_pedido = False
            deliveri = _interpretar_delivery(mensaje)
            if deliveri is not None:
                try:
                    actualizar_delivery(self.fila_pedido_pendiente, deliveri)
                except OSError:
                    contenido = (
                        "El pedido quedó confirmado, pero no pude actualizar "
                        "la modalidad de entrega. Inténtalo de nuevo más tarde."
                    )
                    self.historial.append({"role": "assistant", "content": contenido})
                    return contenido
                self.esperando_metodo_entrega = False
                self.fila_pedido_pendiente = None
                contenido = (
                    "El pedido quedó confirmado por ti y la modalidad de entrega "
                    "quedó registrada. Esto no confirma su aceptación por el negocio."
                )
            elif self.esperando_metodo_entrega:
                contenido = (
                    "El pedido quedó confirmado por ti. "
                    "Indica si deseas delivery o pasarás a retirarlo."
                )
            else:
                self.fila_pedido_pendiente = None
                contenido = (
                    "El pedido quedó confirmado por ti. Esto no confirma su "
                    "aceptación por el negocio."
                )
            self.historial.append({"role": "assistant", "content": contenido})
            return contenido

        if self.esperando_metodo_entrega:
            deliveri = _interpretar_delivery(mensaje)
            if deliveri is None:
                contenido = "Indica si deseas delivery o pasarás a retirar el pedido."
                self.historial.append({"role": "assistant", "content": contenido})
                return contenido
            try:
                if self.fila_pedido_pendiente is None:
                    raise ValueError("No hay un pedido pendiente de modalidad.")
                actualizar_delivery(self.fila_pedido_pendiente, deliveri)
            except OSError:
                contenido = (
                    "No pude actualizar la modalidad del pedido. "
                    "Inténtalo de nuevo más tarde."
                )
                self.historial.append({"role": "assistant", "content": contenido})
                return contenido
            self.esperando_metodo_entrega = False
            if self.esperando_confirmacion_pedido:
                contenido = (
                    "La modalidad de entrega quedó registrada. "
                    "El pedido sigue pendiente de confirmación por el cliente."
                )
            else:
                self.fila_pedido_pendiente = None
                contenido = (
                    "El pedido quedó confirmado por ti y la modalidad de entrega "
                    "quedó registrada. Esto no confirma su aceptación por el negocio."
                )
            self.historial.append({"role": "assistant", "content": contenido})
            return contenido

        if _es_opcion_pedidos(mensaje) or _es_opcion_delivery(mensaje):
            self.esperando_detalle_pedido = True
            self.delivery_preseleccionado = _es_opcion_delivery(mensaje)
            menu = datos_actuales["menu_cafeteria"]["productos"]
            categorias: dict[str, list[str]] = {}
            for producto in menu:
                categorias.setdefault(producto["familia"], []).append(
                    producto["nombre"]
                )
            productos_disponibles = "\n".join(
                f"{categoria}: {', '.join(productos)}"
                for categoria, productos in categorias.items()
            )
            contenido = (
                "Escribe los productos, las cantidades y cualquier detalle "
                "de tu pedido."
                + (f"\nProductos disponibles:\n{productos_disponibles}" if categorias else "")
            )
            if self.delivery_preseleccionado:
                contenido = "Solicitud de delivery.\n" + contenido
            self.historial.append({"role": "assistant", "content": contenido})
            return contenido

        if getattr(self, "esperando_detalle_pedido", False):
            if not mensaje.strip():
                contenido = "Escribe al menos los productos y las cantidades del pedido."
                self.historial.append({"role": "assistant", "content": contenido})
                return contenido
            if not consulta_precio_menu:
                self.esperando_detalle_pedido = False
                delivery_preseleccionado = self.delivery_preseleccionado
                self.delivery_preseleccionado = False
                return self._registrar_pedido(mensaje, delivery_preseleccionado)

        if solicitud_pedido and not consulta_precio_menu:
            return self._registrar_pedido(mensaje)

        if consulta_precio_menu:
            eleccion_herramienta = {
                "type": "function",
                "function": {"name": "calcular_pedidos"},
            }
        else:
            eleccion_herramienta = "auto"

        argumentos_solicitud: dict[str, Any] = {
            "model": MODELO,
            "messages": self._mensajes_para_groq(mensaje),
            "max_completion_tokens": max_completion_tokens,
        }
        if consulta_precio_menu:
            herramienta_calculo = next(
                herramienta
                for herramienta in herramientas
                if herramienta["function"]["name"] == "calcular_pedidos"
            )
            argumentos_solicitud["tools"] = [herramienta_calculo]
            argumentos_solicitud["tool_choice"] = eleccion_herramienta

        try:
            respuesta = self.cliente.chat.completions.create(
                **argumentos_solicitud,
            )
        except GroqError as error:
            return self._manejar_error_groq(error)
        mensaje_asistente = respuesta.choices[0].message
        llamadas = mensaje_asistente.tool_calls or []

        if not llamadas:
            if consulta_precio_menu:
                contenido = (
                    "No pude calcular el precio en este momento. "
                    "Inténtalo de nuevo más tarde."
                )
                self.historial.append({"role": "assistant", "content": contenido})
                return contenido
            contenido = mensaje_asistente.content or ""
            self.historial.append({"role": "assistant", "content": contenido})
            return contenido

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

        resultados_herramienta = []
        for llamada in llamadas:
            try:
                argumentos = json.loads(llamada.function.arguments)
            except json.JSONDecodeError as error:
                if llamada.function.name == "calcular_pedidos":
                    resultado = (
                        "No pude calcular el precio solicitado. "
                        "Inténtalo de nuevo con el nombre del producto."
                    )
                elif llamada.function.name == "registrar_solicitud":
                    resultado = "No pude registrar una solicitud vacía."
                else:
                    resultado = f"La herramienta recibió argumentos inválidos: {error.msg}."
            else:
                try:
                    resultado = ejecutar_herramientas(
                        llamada.function.name,
                        argumentos,
                    )
                except OSError:
                    if llamada.function.name == "calcular_pedidos":
                        resultado = (
                            "No pude consultar el precio en este momento. "
                            "Inténtalo de nuevo más tarde."
                        )
                    elif llamada.function.name == "registrar_solicitud":
                        resultado = (
                            "No pude registrar la solicitud ahora. "
                            "Inténtalo de nuevo más tarde."
                        )
                    else:
                        raise
                except (KeyError, TypeError, ValueError) as error:
                    if llamada.function.name == "calcular_pedidos":
                        resultado = (
                            "No pude calcular el precio solicitado. "
                            "Verifica el producto y su presentación."
                        )
                    elif llamada.function.name == "registrar_solicitud":
                        resultado = "No pude registrar una solicitud vacía."
                    else:
                        resultado = f"La herramienta no pudo completar la solicitud: {error}."

            self.historial.append(
                {
                    "role": "tool",
                    "tool_call_id": llamada.id,
                    "content": resultado,
                }
            )
            resultados_herramienta.append(resultado)

        if consulta_precio_menu or solicitud_pedido:
            contenido = "\n".join(resultados_herramienta)
            self.historial.append({"role": "assistant", "content": contenido})
            return contenido

        try:
            respuesta_final = self.cliente.chat.completions.create(
                model=MODELO,
                messages=self.historial,
            )
        except GroqError as error:
            return self._manejar_error_groq(error)
        contenido = respuesta_final.choices[0].message.content or ""
        self.historial.append({"role": "assistant", "content": contenido})
        return contenido

    def _registrar_pedido(
        self,
        solicitud: str,
        delivery_preseleccionado: bool = False,
    ) -> str:
        try:
            fila = registrar_pedido(
                solicitud,
                "Delivery" if delivery_preseleccionado else "Pendiente",
            )
        except OSError:
            contenido = (
                "No pude registrar la solicitud ahora. "
                "Inténtalo de nuevo más tarde."
            )
        except ValueError:
            contenido = "No pude registrar la solicitud. Verifica los productos y vuelve a intentarlo."
        else:
            self.esperando_confirmacion_pedido = True
            self.fila_pedido_pendiente = fila
            if delivery_preseleccionado:
                contenido = (
                    "Su pedido se ha realizado en 15 minutos estará listo. "
                    "La solicitud de delivery quedó registrada."
                )
            else:
                self.esperando_metodo_entrega = True
                contenido = (
                    "Su pedido se ha realizado en 15 minutos estará listo. "
                    "¿Desea delivery o pasa a retirarlo?"
                )
        self.historial.append({"role": "assistant", "content": contenido})
        return contenido

    def mostrar_historiar(self) -> None:
        mostrar_historial(self.historial)