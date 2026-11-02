from copy import deepcopy
from datetime import datetime
from pathlib import Path
import threading
from typing import Any

from openpyxl import load_workbook
from openpyxl.workbook.workbook import Workbook
from openpyxl.worksheet.worksheet import Worksheet

CARPETA_DATOS = Path(__file__).with_name("datos")
ARCHIVO_HOJA_CALCULO = CARPETA_DATOS / "datos_negocio_cafe_santo_domingo.xlsx"
ARCHIVO_PEDIDOS = CARPETA_DATOS / "pedidos.xlsx"

ESTADO_PENDIENTE = "Pendiente de confirmación"
ESTADO_CONFIRMADO = "Confirmado por el cliente"
_candado_pedido = threading.Lock()

DATOS_NEGOCIO: dict[str, Any] = {
    "negocio": {
        "nombre": "Café Santo Domingo",
        "idioma_atencion": "español",
        "descripcion": "Negocio de café, productos y servicios relacionados.",
    },
    "menu_atencion": {
        "titulo": "Menú de atención",
        "opciones": [
            {
                "id": 1,
                "nombre": "Ver productos y presentaciones",
                "intencion": "catalogo",
            },
            {
                "id": 2,
                "nombre": "Consultar precios",
                "intencion": "precios",
            },
            {
                "id": 3,
                "nombre": "Recibir una recomendación de café",
                "intencion": "recomendacion",
            },
            {
                "id": 4,
                "nombre": "Consultar sucursales y teléfonos",
                "intencion": "sucursales",
            },
            {
                "id": 5,
                "nombre": "Consultar servicios para oficinas o eventos",
                "intencion": "servicios",
            },
            {
                "id": 6,
                "nombre": "Redactar una sugerencia",
                "intencion": "sugerencias",
            },
            {
                "id": 7,
                "nombre": "Ver menú de cafetería",
                "intencion": "menu_cafeteria",
            },
            {
                "id": 8,
                "nombre": "Realizar un pedido",
                "intencion": "pedidos",
            },
            {
                "id": 9,
                "nombre": "Solicitar delivery",
                "intencion": "delivery",
            },
        ],
        "comando_salida": "salir",
        "instruccion": "El menú de cafetería muestra bebidas y acompañamientos agrupados por categoría. El catálogo de productos de café muestra los productos empacados agrupados por familia. El menú principal muestra estas opciones de atención.",
    },
    "catalogo": {
        "fuente_catalogo_oficial": "https://www.induban.com/es/productos/item/cafe-santo-domingo",
        "nota": "Los nombres aparecen en el catálogo oficial de INDUBAN. La publicación no confirma existencias ni disponibilidad actual.",
        "fecha_consulta_referencias_de_precio": "2026-09-29",
        "fuentes_de_precio": [
            {
                "id": "almacen_do",
                "nombre": "Almacén.do",
                "url": "https://almacen.do/marca/cafe-santo-domingo/",
            },
            {
                "id": "supermercados_consultados",
                "nombre": "SupermercadosRD",
                "url": "https://supermercadosrd.com/grupos/cafe-molido",
                "nota": "Compara precios en línea de distintos comercios; no es el fabricante ni garantiza precios en sucursales de Café Santo Domingo.",
            },
        ],
        "moneda": "DOP",
        "productos": [
            {
                "familia": "Clásico",
                "nombre": "Café Santo Domingo Clásico molido",
                "presentacion": "1 lb",
                "precio": {
                    "minimo": 420,
                    "maximo": 420,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Clásico",
                "nombre": "Café Santo Domingo molido",
                "presentacion": "8 oz (226.8 g)",
                "precio": {
                    "minimo": 209,
                    "maximo": 220,
                    "fuente": "supermercados_consultados",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Clásico",
                "nombre": "Café Santo Domingo molido en lata",
                "presentacion": "10 oz (283.5 g)",
                "precio": {
                    "minimo": 369.95,
                    "maximo": 370,
                    "fuente": "supermercados_consultados",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Clásico",
                "nombre": "Café Santo Domingo molido en sobres",
                "presentacion": "12 unidades (340.2 g)",
                "precio": {
                    "minimo": 380,
                    "maximo": 410,
                    "fuente": "supermercados_consultados",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Clásico",
                "nombre": "Café Santo Domingo Hard Pack",
                "presentacion": None,
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Clásico",
                "nombre": "Café Santo Domingo Clásico en grano",
                "presentacion": "1 lb",
                "precio": {
                    "minimo": 460,
                    "maximo": 460,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Clásico",
                "nombre": "Café Santo Domingo Clásico en grano",
                "presentacion": "3 lb",
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Clásico",
                "nombre": "Cápsula de Espresso Café Santo Domingo Clásico",
                "presentacion": "10 unidades",
                "precio": {
                    "minimo": 335,
                    "maximo": 335,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Clásico",
                "nombre": "Cápsula de Espresso Café Santo Domingo Lungo",
                "presentacion": "10 unidades",
                "precio": {
                    "minimo": 335,
                    "maximo": 335,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Suardí molido",
                "presentacion": "12 oz (340.2 g)",
                "precio": {
                    "minimo": 614,
                    "maximo": 615,
                    "fuente": "supermercados_consultados",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Suardí en grano",
                "presentacion": None,
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Gran Origen",
                "nombre": "Cápsula de Espresso Gran Origen Suardí",
                "presentacion": "10 unidades",
                "precio": {
                    "minimo": 375,
                    "maximo": 375,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Perla Roja molido",
                "presentacion": "12 oz (340.2 g)",
                "precio": {
                    "minimo": 614,
                    "maximo": 615,
                    "fuente": "supermercados_consultados",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Perla Roja en grano",
                "presentacion": None,
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Gran Origen",
                "nombre": "Cápsula de Espresso Gran Origen Perla Roja",
                "presentacion": "10 unidades",
                "precio": {
                    "minimo": 375,
                    "maximo": 375,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Gran Sierra molido",
                "presentacion": "12 oz (340.2 g)",
                "precio": {
                    "minimo": 614,
                    "maximo": 615,
                    "fuente": "supermercados_consultados",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Gran Sierra en grano",
                "presentacion": None,
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Gran Origen",
                "nombre": "Cápsula de Espresso Gran Origen Gran Sierra",
                "presentacion": "10 unidades",
                "precio": {
                    "minimo": 375,
                    "maximo": 375,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Barrancolí molido",
                "presentacion": None,
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Gran Origen",
                "nombre": "Gran Origen Barrancolí en grano",
                "presentacion": None,
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Caracolillo",
                "nombre": "Café Santo Domingo Caracolillo molido",
                "presentacion": "1 lb",
                "precio": {
                    "minimo": 470,
                    "maximo": 470,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Caracolillo",
                "nombre": "Café Santo Domingo Caracolillo tostado en grano",
                "presentacion": "1 lb",
                "precio": {
                    "minimo": 470,
                    "maximo": 470,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Caracolillo",
                "nombre": "Cápsula de Espresso Café Santo Domingo Caracolillo",
                "presentacion": "10 unidades",
                "precio": {
                    "minimo": 335,
                    "maximo": 335,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Descafeinado",
                "nombre": "Café Santo Domingo Descafeinado molido",
                "presentacion": "10 oz (283.5 g)",
                "precio": {
                    "minimo": 509,
                    "maximo": 510,
                    "fuente": "supermercados_consultados",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Descafeinado",
                "nombre": "Cápsula de Espresso Café Santo Domingo Descafeinado",
                "presentacion": None,
                "precio": None,
                "estado_precio": "no_encontrado",
            },
            {
                "familia": "Espresso e Intenso",
                "nombre": "Café Santo Domingo Espresso molido",
                "presentacion": "1 lb",
                "precio": {
                    "minimo": 450,
                    "maximo": 450,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
            {
                "familia": "Espresso e Intenso",
                "nombre": "Cápsula de Espresso Café Santo Domingo Intenso",
                "presentacion": "10 unidades",
                "precio": {
                    "minimo": 335,
                    "maximo": 335,
                    "fuente": "almacen_do",
                    "estado": "referencia_de_tercero",
                },
            },
        ],
    },
    "servicios": [
        {
            "nombre": "Recomendación de molienda y método de preparación",
            "precio": {
                "valor": 0,
                "moneda": "DOP",
                "estado": "sin_costo",
            },
        },
        {
            "nombre": "Preparación de pedidos para regalo",
            "precio": {
                "desde": 150,
                "moneda": "DOP",
                "estado": "provisional_no_confirmado",
                "condiciones": "Depende del empaque.",
            },
        },
        {
            "nombre": "Suministro de café para oficinas",
            "precio": {
                "estado": "requiere_cotizacion",
                "condiciones": "Depende del volumen y la frecuencia.",
            },
        },
        {
            "nombre": "Barra de café para eventos",
            "precio": {
                "desde": 250,
                "moneda": "DOP",
                "unidad": "persona",
                "estado": "provisional_no_confirmado",
                "condiciones": "Depende de la cantidad de personas, ubicación y selección de bebidas; requiere cotización.",
            },
        },
        {
            "nombre": "Entrega",
            "precio": {
                "estado": "por_confirmar",
                "condiciones": "Costo y cobertura dependen de la dirección.",
            },
        },
    ],
    "sucursales_y_contacto": {
        "sucursales": [
            {
                "nombre": "Café Santo Domingo - Sambil Santo Domingo",
                "direccion": "Avenida John F. Kennedy, esquina Paseo de los Aviadores, Santo Domingo, D.N.; Nivel Galería, local G-88.",
                "telefono_publicado": "829-547-4242",
                "fuente": "https://sambil.do/tiendas/cafe-santo-domingo/",
                "tipo_fuente": "directorio_oficial_del_centro_comercial",
                "nota": "Dirección clara publicada por el directorio del centro comercial. Confirmar vigencia antes de asegurar horarios, teléfono o disponibilidad.",
            },
            {
                "nombre": "Café Santo Domingo - ficha de Megacentro",
                "direccion": None,
                "telefono_publicado": "809-565-3121",
                "ubicacion_publicada_ambigua": "Paseo Caribe | Plaza de las Estrellas",
                "fuente": "https://www.megacentro.com.do/directorio/cafe-santo-domingo/",
                "tipo_fuente": "directorio_oficial_del_centro_comercial",
                "nota": "La ubicación de la ficha es ambigua. No usarla para dar una dirección ni para recomendar la sucursal más cercana.",
            },
        ],
        "buzon_sugerencias": {
            "estado": "pendiente_de_verificacion",
            "nota": "No afirmar que una sugerencia fue enviada, guardada o recibida.",
        },
        "reglas": [
            "Los datos proceden de directorios de centros comerciales, no de un directorio central de la marca.",
            "No afirmar que la lista incluya todas las sucursales ni que los teléfonos sigan vigentes sin confirmación.",
            "No inventar teléfonos, direcciones, correos, horarios ni otros canales de contacto.",
        ],
    },
}


def _leer_hoja(libro: Workbook, nombre_hoja: str) -> list[dict[str, Any]]:
    if nombre_hoja not in libro.sheetnames:
        raise ValueError(f"No existe la hoja '{nombre_hoja}' en el archivo de negocio.")

    filas = libro[nombre_hoja].iter_rows(values_only=True)
    encabezados_originales = next(filas, None)
    if encabezados_originales is None:
        raise ValueError(f"La hoja '{nombre_hoja}' está vacía.")

    encabezados = [
        str(encabezado).strip() if encabezado is not None else ""
        for encabezado in encabezados_originales
    ]
    if any(not encabezado for encabezado in encabezados):
        raise ValueError(f"La hoja '{nombre_hoja}' tiene encabezados vacíos.")

    registros = []
    for fila in filas:
        if all(valor is None for valor in fila):
            continue
        registros.append(dict(zip(encabezados, fila)))
    return registros


def _texto_requerido(registro: dict[str, Any], campo: str, hoja: str) -> str:
    valor = registro.get(campo)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"El campo '{campo}' de la hoja '{hoja}' debe ser texto.")
    return valor.strip()


def _cargar_menu(registros: list[dict[str, Any]]) -> dict[str, Any]:
    productos = []
    for registro in registros:
        nombre = _texto_requerido(registro, "producto", "productos")
        familia = _texto_requerido(registro, "categoria", "productos")
        precio = registro.get("precio")
        if isinstance(precio, bool) or not isinstance(precio, (int, float)):
            raise ValueError(f"El precio de '{nombre}' debe ser numérico.")

        productos.append(
            {
                "nombre": nombre,
                "presentacion": None,
                "familia": familia,
                "precio": {
                    "minimo": precio,
                    "maximo": precio,
                    "fuente": "hoja_de_calculo",
                    "estado": "referencial_no_confirmado",
                },
            }
        )

    return {
        "fuente": ARCHIVO_HOJA_CALCULO.name,
        "moneda": "DOP",
        "nota": (
            "Los precios provienen de la hoja de cálculo y no están confirmados "
            "como tarifas vigentes."
        ),
        "productos": productos,
    }


def _cargar_informacion_adicional(
    registros: list[dict[str, Any]],
) -> dict[str, Any]:
    temas = [
        {
            "tema": _texto_requerido(registro, "tema", "informacion"),
            "detalle": _texto_requerido(registro, "detalle", "informacion"),
        }
        for registro in registros
    ]
    if not temas:
        raise ValueError("La hoja 'informacion' no contiene temas.")

    return {
        "fuente": ARCHIVO_HOJA_CALCULO.name,
        "temas": temas,
    }


def cargar_datos_negocio() -> dict[str, Any]:
    """Combina la información base en Python con los datos actuales del Excel."""
    informacion = deepcopy(DATOS_NEGOCIO)

    libro = load_workbook(ARCHIVO_HOJA_CALCULO, read_only=True, data_only=True)
    try:
        registros_productos = _leer_hoja(libro, "productos")
        registros_informacion = _leer_hoja(libro, "informacion")
    finally:
        libro.close()

    informacion["menu_cafeteria"] = _cargar_menu(registros_productos)
    informacion["informacion_adicional"] = _cargar_informacion_adicional(
        registros_informacion
    )
    return informacion


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
    with _candado_pedido:
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
    contacto: str = "",
) -> int:
    """Guarda un pedido y devuelve la fila donde quedó registrado."""
    with _candado_pedido:
        if not isinstance(solicitud, str) or not solicitud.strip():
            raise ValueError("La solicitud no puede estar vacía.")
        if deliveri not in {"Delivery", "Retiro", "Pendiente"}:
            raise ValueError("La modalidad debe ser Delivery, Retiro o Pendiente.")
        if not isinstance(contacto, str):
            raise ValueError("El contacto debe ser texto.")

        libro, hoja = _abrir_libro_pedidos()
        try:
            fecha = datetime.now().astimezone().isoformat(timespec="seconds")
            fila = hoja.max_row + 1
            hoja.cell(row=fila, column=1, value=fecha)
            hoja.cell(row=fila, column=2, value=cliente_id)
            hoja.cell(row=fila, column=3, value=contacto)
            celda_solicitud = hoja.cell(
                row=fila,
                column=4,
                value=solicitud.strip(),
            )
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

    with _candado_pedido:
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

    with _candado_pedido:
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
    contacto: str = "",
) -> str:
    """Guarda una solicitud de pedido y confirma el registro."""
    registrar_pedido(solicitud, deliveri, cliente_id, contacto)
    return (
        "Tu solicitud quedó registrada. El registro no confirma que el negocio "
        "la haya recibido o aceptado."
    )
