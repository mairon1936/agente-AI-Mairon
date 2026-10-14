from datetime import datetime

from openpyxl import Workbook, load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from datos import ARCHIVO_PEDIDOS

ESTADO_PENDIENTE = "Pendiente de confirmación"
ESTADO_CONFIRMADO = "Confirmado por el cliente"


def _abrir_libro_pedidos() -> tuple[Workbook, Worksheet]:
    ARCHIVO_PEDIDOS.parent.mkdir(parents=True, exist_ok=True)
    if ARCHIVO_PEDIDOS.exists():
        libro = load_workbook(ARCHIVO_PEDIDOS)
    else:
        libro = Workbook()

    if "pedidos" in libro.sheetnames:
        hoja = libro["pedidos"]
    else:
        hoja = libro.active
        hoja.title = "pedidos"

    encabezados = ("fecha_solicitud", "solicitud", "deliveri", "estado")
    if hoja.max_row == 1 and all(celda.value is None for celda in hoja[1]):
        for columna, encabezado in enumerate(encabezados, start=1):
            hoja.cell(row=1, column=columna, value=encabezado)
    elif tuple(celda.value for celda in hoja[1][:2]) != encabezados[:2]:
        libro.close()
        raise ValueError(
            "La hoja 'pedidos' debe tener los encabezados "
            "'fecha_solicitud' y 'solicitud'."
        )

    encabezado_delivery = hoja.cell(row=1, column=3)
    if encabezado_delivery.value is None:
        encabezado_delivery.value = "deliveri"
    elif encabezado_delivery.value != "deliveri":
        libro.close()
        raise ValueError("La tercera columna de la hoja 'pedidos' debe ser 'deliveri'.")

    encabezado_estado = hoja.cell(row=1, column=4)
    if encabezado_estado.value is None:
        encabezado_estado.value = "estado"
    elif encabezado_estado.value != "estado":
        libro.close()
        raise ValueError("La cuarta columna de la hoja 'pedidos' debe ser 'estado'.")

    for fila in range(2, hoja.max_row + 1):
        if hoja.cell(row=fila, column=4).value is None:
            hoja.cell(row=fila, column=4, value=ESTADO_PENDIENTE)

    return libro, hoja


def preparar_libro_pedidos() -> None:
    """Asegura encabezados y visualización sin añadir ningún pedido."""
    libro, hoja = _abrir_libro_pedidos()
    try:
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = f"A1:D{hoja.max_row}"
        hoja.column_dimensions["A"].width = 28
        hoja.column_dimensions["B"].width = 80
        hoja.column_dimensions["C"].width = 18
        hoja.column_dimensions["D"].width = 32
        libro.save(ARCHIVO_PEDIDOS)
    finally:
        libro.close()


def registrar_pedido(solicitud: str, deliveri: str = "Pendiente") -> int:
    """Guarda un pedido y devuelve la fila donde quedó registrado."""
    if not isinstance(solicitud, str) or not solicitud.strip():
        raise ValueError("La solicitud no puede estar vacía.")
    if deliveri not in {"Delivery", "Retiro", "Pendiente"}:
        raise ValueError("La modalidad debe ser Delivery, Retiro o Pendiente.")

    libro, hoja = _abrir_libro_pedidos()
    try:
        fecha = datetime.now().astimezone().isoformat(timespec="seconds")
        fila = hoja.max_row + 1
        hoja.cell(row=fila, column=1, value=fecha)
        celda_solicitud = hoja.cell(row=fila, column=2, value=solicitud.strip())
        celda_solicitud.data_type = "s"
        hoja.cell(row=fila, column=3, value=deliveri)
        hoja.cell(row=fila, column=4, value=ESTADO_PENDIENTE)
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = f"A1:D{hoja.max_row}"
        hoja.column_dimensions["A"].width = 28
        hoja.column_dimensions["B"].width = 80
        hoja.column_dimensions["C"].width = 18
        hoja.column_dimensions["D"].width = 32
        libro.save(ARCHIVO_PEDIDOS)
        return fila
    finally:
        libro.close()


def actualizar_delivery(fila: int, deliveri: str) -> None:
    """Actualiza la modalidad de entrega de un pedido previamente registrado."""
    if isinstance(fila, bool) or not isinstance(fila, int) or fila < 2:
        raise ValueError("La fila del pedido no es válida.")
    if deliveri not in {"Delivery", "Retiro"}:
        raise ValueError("La modalidad debe ser Delivery o Retiro.")

    libro, hoja = _abrir_libro_pedidos()
    try:
        if fila > hoja.max_row:
            raise ValueError("No se encontró el pedido que se debe actualizar.")
        hoja.cell(row=fila, column=3, value=deliveri)
        hoja.auto_filter.ref = f"A1:D{hoja.max_row}"
        libro.save(ARCHIVO_PEDIDOS)
    finally:
        libro.close()


def actualizar_estado_pedido(fila: int, estado: str) -> None:
    """Actualiza el estado de confirmación de un pedido existente."""
    if isinstance(fila, bool) or not isinstance(fila, int) or fila < 2:
        raise ValueError("La fila del pedido no es válida.")
    if estado not in {ESTADO_PENDIENTE, ESTADO_CONFIRMADO}:
        raise ValueError("El estado del pedido no es válido.")

    libro, hoja = _abrir_libro_pedidos()
    try:
        if fila > hoja.max_row:
            raise ValueError("No se encontró el pedido que se debe actualizar.")
        hoja.cell(row=fila, column=4, value=estado)
        hoja.auto_filter.ref = f"A1:D{hoja.max_row}"
        libro.save(ARCHIVO_PEDIDOS)
    finally:
        libro.close()


def registrar_solicitud(solicitud: str, deliveri: str = "Pendiente") -> str:
    """Guarda una solicitud de pedido y confirma el registro."""
    registrar_pedido(solicitud, deliveri)
    return (
        "Tu solicitud quedó registrada. El registro no confirma que el negocio "
        "la haya recibido o aceptado."
    )
