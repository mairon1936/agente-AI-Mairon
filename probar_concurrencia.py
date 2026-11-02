from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
import threading

import datos
from openpyxl import load_workbook
from datos import registrar_pedido as guardar_pedido


def main() -> None:
    cantidad_clientes = 10
    pedidos_guardados: list[tuple[str, int]] = []
    candado_lista = threading.Lock()

    with TemporaryDirectory() as directorio_temporal:
        ruta_pedido = Path(directorio_temporal) / datos.ARCHIVO_PEDIDOS.name
        if ruta_pedido.exists():
            ruta_pedido.unlink()

        ruta_original = datos.ARCHIVO_PEDIDOS
        datos.ARCHIVO_PEDIDOS = ruta_pedido

        def registrar_pedido_de_cliente(numero: int) -> str:
            codigo = f"cliente({numero})"
            fila = guardar_pedido(
                "pedido de prueba",
                cliente_id=codigo,
            )
            with candado_lista:
                pedidos_guardados.append((codigo, fila))
            return codigo

        try:
            datos.preparar_libro_pedidos()

            with ThreadPoolExecutor(max_workers=cantidad_clientes) as ejecutor:
                codigos = list(
                    ejecutor.map(
                        registrar_pedido_de_cliente,
                        range(cantidad_clientes),
                    )
                )

            libro = load_workbook(ruta_pedido, data_only=True)
            try:
                hoja = libro["pedidos"]
                codigos_en_archivo = [
                    hoja.cell(row=fila, column=2).value
                    for fila in range(2, hoja.max_row + 1)
                ]
            finally:
                libro.close()
        finally:
            datos.ARCHIVO_PEDIDOS = ruta_original

    print(f"Códigos de los clientes enviados: {codigos}")
    print(f"Cantidad de códigos enviados: {len(codigos)}")
    print(f"Códigos distintos enviados: {len(set(codigos))}")
    print(f"Códigos guardados en la lista: {[codigo for codigo, _ in pedidos_guardados]}")
    print(f"Filas con clientes en el Excel temporal: {codigos_en_archivo}")
    print(f"Cantidad de clientes guardados en el Excel: {len(codigos_en_archivo)}")
    print(f"Clientes distintos guardados en el Excel: {len(set(codigos_en_archivo))}")

    if len(codigos) != cantidad_clientes or len(set(codigos)) != cantidad_clientes:
        raise AssertionError("La prueba no generó 10 códigos de cliente únicos.")
    if (
        len(codigos_en_archivo) != cantidad_clientes
        or len(set(codigos_en_archivo)) != cantidad_clientes
        or set(codigos_en_archivo) != set(codigos)
    ):
        raise AssertionError(
            "El candado no conservó exactamente los 10 clientes en el Excel."
        )

    print("OK: el candado conservó los 10 clientes en el Excel temporal.")
    print("El pedidos.xlsx real no fue modificado.")


if __name__ == "__main__":
    main()
