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

    encabezados = (
        "fecha_solicitud",
        "cliente",
        "contacto",
        "detalle",
        "deliveri",
        "estado",
    )
    if hoja.max_row == 1 and all(celda.value is None for celda in hoja[1]):
        for columna, encabezado in enumerate(encabezados, start=1):
            hoja.cell(row=1, column=columna, value=encabezado)
    elif tuple(celda.value for celda in hoja[1][:len(encabezados)]) != encabezados:
        encabezados_anteriores = (
            "fecha_solicitud",
            "solicitud",
            "deliveri",
            "estado",
        )
        encabezados_anteriores_actuales = tuple(
            hoja.cell(row=1, column=columna).value
            for columna in range(1, len(encabezados_anteriores) + 1)
        )
        if (
            encabezados_anteriores_actuales[:2]
            != encabezados_anteriores[:2]
            or encabezados_anteriores_actuales[2:]
            not in (
                encabezados_anteriores[2:],
                ("deliveri", None),
                (None, "estado"),
                (None, None),
            )
        ):
            libro.close()
            raise ValueError(
                "La hoja 'pedidos' no tiene los encabezados esperados."
            )
        hoja.insert_cols(2, amount=2)
        for columna, encabezado in enumerate(encabezados, start=1):
            hoja.cell(row=1, column=columna, value=encabezado)

    for fila in range(2, hoja.max_row + 1):
        if hoja.cell(row=fila, column=6).value is None:
            hoja.cell(row=fila, column=6, value=ESTADO_PENDIENTE)

    return libro, hoja


def preparar_libro_pedidos() -> None:
    """Asegura encabezados y visualización sin añadir ningún pedido."""
    libro, hoja = _abrir_libro_pedidos()
    try:
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = f"A1:F{hoja.max_row}"
        hoja.column_dimensions["A"].width = 28
        hoja.column_dimensions["B"].width = 24
        hoja.column_dimensions["C"].width = 24
        hoja.column_dimensions["D"].width = 80
        hoja.column_dimensions["E"].width = 18
        hoja.column_dimensions["F"].width = 32
        libro.save(ARCHIVO_PEDIDOS)
    finally:
        libro.close()


def registrar_pedido(
    solicitud: str,
    deliveri: str = "Pendiente",
    cliente_id: str = "terminar",
) -> int:
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
        hoja.cell(row=fila, column=2, value=cliente_id)
        hoja.cell(row=fila, column=3, value="")
        celda_solicitud = hoja.cell(row=fila, column=4, value=solicitud.strip())
        celda_solicitud.data_type = "s"
        hoja.cell(row=fila, column=5, value=deliveri)
        hoja.cell(row=fila, column=6, value=ESTADO_PENDIENTE)
        hoja.freeze_panes = "A2"
        hoja.auto_filter.ref = f"A1:F{hoja.max_row}"
        hoja.column_dimensions["A"].width = 28
        hoja.column_dimensions["B"].width = 24
        hoja.column_dimensions["C"].width = 24
        hoja.column_dimensions["D"].width = 80
        hoja.column_dimensions["E"].width = 18
        hoja.column_dimensions["F"].width = 32
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
        hoja.cell(row=fila, column=5, value=deliveri)
        hoja.auto_filter.ref = f"A1:F{hoja.max_row}"
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
        hoja.cell(row=fila, column=6, value=estado)
        hoja.auto_filter.ref = f"A1:F{hoja.max_row}"
        libro.save(ARCHIVO_PEDIDOS)
    finally:
        libro.close()


def registrar_solicitud(
    solicitud: str,
    deliveri: str = "Pendiente",
    cliente_id: str = "terminar",
) -> str:
    """Guarda una solicitud de pedido y confirma el registro."""
    registrar_pedido(solicitud, deliveri, cliente_id)
    return (
        "Tu solicitud quedó registrada. El registro no confirma que el negocio "
        "la haya recibido o aceptado."
    )
