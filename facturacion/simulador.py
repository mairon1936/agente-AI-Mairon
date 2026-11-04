"""API de facturación simulada para desarrollo; nunca conectarla a producción."""

import hmac
import itertools
import os
import threading
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("FACTURACION_API_KEY", "dev-key")
app = FastAPI(
    title="Simulador local de facturación",
    docs_url=None,
    redoc_url=None,
)

CLIENTES = {
    "131000001": {
        "rnc": "131000001",
        "razon_social": "Cliente de Prueba SRL",
    }
}
PRODUCTOS = {
    "P001": {
        "codigo": "P001",
        "descripcion": "Consultoría (hora)",
        "precio": Decimal("3500.00"),
        "itbis": Decimal("0.18"),
    },
    "P002": {
        "codigo": "P002",
        "descripcion": "Licencia mensual de software",
        "precio": Decimal("1200.00"),
        "itbis": Decimal("0.18"),
    },
}
BORRADORES: dict[str, dict] = {}
FACTURAS: dict[str, dict] = {}
EMITIDAS: dict[str, str] = {}
CONSULTAS: dict[str, int] = {}
_borrador_seq = itertools.count(1)
_factura_seq = itertools.count(1)
_candado = threading.RLock()


class LineaEntrada(BaseModel):
    codigo: str = Field(min_length=1, max_length=80)
    cantidad: Decimal = Field(gt=0, max_digits=12, decimal_places=4)


class BorradorEntrada(BaseModel):
    tipo_ecf: Literal["31", "32"]
    cliente: str | None = None
    lineas: list[LineaEntrada] = Field(min_length=1, max_length=50)
    forma_pago: Literal["contado", "credito", "transferencia"] = "contado"
    origen: dict[str, str]


def autenticar(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    if not API_KEY or not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(status_code=401, detail="API key inválida")


def _dinero(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pdf_simulado(e_ncf: str) -> bytes:
    texto = f"Comprobante simulado {e_ncf}".replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    contenido = (
        "BT /F1 14 Tf 50 740 Td ("
        + texto
        + ") Tj ET"
    ).encode("ascii")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(contenido)).encode("ascii")
        + b" >>\nstream\n"
        + contenido
        + b"\nendstream",
    ]
    salida = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for numero, objeto in enumerate(objetos, 1):
        offsets.append(len(salida))
        salida.extend(f"{numero} 0 obj\n".encode("ascii"))
        salida.extend(objeto)
        salida.extend(b"\nendobj\n")
    xref_offset = len(salida)
    salida.extend(f"xref\n0 {len(objetos) + 1}\n".encode("ascii"))
    salida.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        salida.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    salida.extend(
        (
            f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(salida)


@app.get("/v1/clientes/{documento}", dependencies=[Depends(autenticar)])
def buscar_cliente(documento: str) -> dict:
    cliente = CLIENTES.get(documento)
    if cliente is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
    return cliente


@app.get("/v1/productos", dependencies=[Depends(autenticar)])
def buscar_producto(q: str = "") -> list[dict]:
    consulta = q.casefold()
    return [
        {
            "codigo": producto["codigo"],
            "descripcion": producto["descripcion"],
            "precio": str(producto["precio"]),
        }
        for producto in PRODUCTOS.values()
        if consulta in producto["descripcion"].casefold()
        or consulta in producto["codigo"].casefold()
    ]


@app.post("/v1/facturas/borradores", dependencies=[Depends(autenticar)])
def crear_borrador(entrada: BorradorEntrada) -> dict:
    if entrada.tipo_ecf == "31" and entrada.cliente not in CLIENTES:
        raise HTTPException(
            status_code=422,
            detail="El tipo 31 requiere un cliente válido.",
        )
    if (
        entrada.origen.get("canal") != "whatsapp"
        or not entrada.origen.get("telefono", "").isdigit()
    ):
        raise HTTPException(
            status_code=422,
            detail="El origen de la solicitud no es válido.",
        )

    lineas = []
    subtotal = Decimal("0.00")
    itbis = Decimal("0.00")
    for item in entrada.lineas:
        producto = PRODUCTOS.get(item.codigo)
        if producto is None:
            raise HTTPException(
                status_code=422,
                detail=f"Producto no encontrado: {item.codigo}",
            )
        monto = _dinero(producto["precio"] * item.cantidad)
        subtotal += monto
        itbis += _dinero(monto * producto["itbis"])
        lineas.append(
            {
                "codigo": producto["codigo"],
                "descripcion": producto["descripcion"],
                "cantidad": str(item.cantidad),
                "precio_unitario": str(producto["precio"]),
                "monto": str(monto),
            }
        )

    with _candado:
        borrador_id = f"B{next(_borrador_seq):05d}"
        cliente = CLIENTES.get(entrada.cliente or "")
        borrador = {
            "id": borrador_id,
            "tipo_ecf": entrada.tipo_ecf,
            "cliente_nombre": cliente["razon_social"] if cliente else None,
            "lineas": lineas,
            "subtotal": str(_dinero(subtotal)),
            "itbis": str(_dinero(itbis)),
            "total": str(_dinero(subtotal + itbis)),
        }
        BORRADORES[borrador_id] = {
            **borrador,
            "forma_pago": entrada.forma_pago,
            "origen": entrada.origen,
        }
        return borrador


@app.post(
    "/v1/facturas/borradores/{borrador_id}/emitir",
    dependencies=[Depends(autenticar)],
)
def emitir(
    borrador_id: str,
    idempotency_key: str = Header(default="", alias="Idempotency-Key"),
) -> dict:
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Falta el header Idempotency-Key.",
        )
    with _candado:
        factura_existente = EMITIDAS.get(borrador_id)
        if factura_existente is not None:
            return FACTURAS[factura_existente]
        if idempotency_key != f"emitir:{borrador_id}":
            raise HTTPException(
                status_code=409,
                detail="La clave de idempotencia no corresponde al borrador.",
            )
        borrador = BORRADORES.get(borrador_id)
        if borrador is None:
            raise HTTPException(status_code=404, detail="Borrador no encontrado")
        numero = next(_factura_seq)
        factura = {
            "id": f"F{numero:05d}",
            "e_ncf": f"E{borrador['tipo_ecf']}{numero:010d}",
            "estado": "EN_PROCESO",
            "total": borrador["total"],
        }
        FACTURAS[factura["id"]] = factura
        EMITIDAS[borrador_id] = factura["id"]
        return factura


@app.get("/v1/facturas/{factura_id}", dependencies=[Depends(autenticar)])
def estado(factura_id: str) -> dict:
    with _candado:
        factura = FACTURAS.get(factura_id)
        if factura is None:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        CONSULTAS[factura_id] = CONSULTAS.get(factura_id, 0) + 1
        if CONSULTAS[factura_id] >= 2:
            factura["estado"] = "ACEPTADO"
        return dict(factura)


@app.get(
    "/v1/facturas/{factura_id}/pdf",
    dependencies=[Depends(autenticar)],
)
def pdf(factura_id: str) -> Response:
    with _candado:
        factura = FACTURAS.get(factura_id)
        if factura is None:
            raise HTTPException(status_code=404, detail="Factura no encontrada")
        if factura["estado"] not in {"ACEPTADO", "ACEPTADO_CONDICIONAL"}:
            raise HTTPException(
                status_code=409,
                detail="El PDF estará disponible cuando la factura sea aceptada.",
            )
        contenido = _pdf_simulado(factura["e_ncf"])
    return Response(content=contenido, media_type="application/pdf")
