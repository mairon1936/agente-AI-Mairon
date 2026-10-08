import json
from collections.abc import Iterable
from pathlib import Path
from typing import TypedDict


class ItemPedido(TypedDict):
    productos: str
    cantidad: int


def _normalizar_nombre(nombre: str) -> str:
    return " ".join(nombre.lower().split())


def _formatear_precio(precio: float) -> str:
    return f"RD${precio:g}"


def calcular_pedidos(itms: Iterable[ItemPedido]) -> str:
    """Calcula el total referencial de una lista de productos y cantidades."""
    ruta_datos = Path(__file__).with_name("informacion_negocio.json")
    with ruta_datos.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)

    productos_menu = datos["catalogo"]["productos"]
    detalle: list[str] = []
    total_minimo = 0.0
    total_maximo = 0.0

    for item in itms:
        producto_solicitado = _normalizar_nombre(item["productos"])
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
        + f"\nTotal referencial: {texto_total}.\nLos precios son referenciales y pueden cambiar."
    )
