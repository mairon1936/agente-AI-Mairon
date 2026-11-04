"""Contrato documentado del motor e-CF; no sustituye la integración oficial."""

from dataclasses import dataclass
from decimal import Decimal

AMBIENTES = {"pre": "testecf", "cert": "certecf", "prod": "ecf"}
BASE_ECF = "https://ecf.dgii.gov.do/{ambiente}"
BASE_RFCE = "https://fc.dgii.gov.do/{ambiente}"
UMBRAL_RFCE = Decimal("250000.00")
ESTADOS_RESULTADO = {
    0: "NO_ENCONTRADO",
    1: "ACEPTADO",
    2: "RECHAZADO",
    3: "EN_PROCESO",
    4: "ACEPTADO_CONDICIONAL",
}


class IntegracionDGIIpendiente(NotImplementedError):
    """Falta completar y certificar el motor e-CF oficial."""


@dataclass
class ResultadoEnvio:
    track_id: str | None
    error: str | None
    mensaje: str | None


def decidir_ruta(tipo_ecf: str, total: Decimal) -> str:
    if tipo_ecf not in {"31", "32"}:
        raise ValueError("Solo se soportan los tipos e-CF 31 y 32.")
    if not total.is_finite() or total < 0:
        raise ValueError("El total debe ser un monto decimal no negativo.")
    return "rfce" if tipo_ecf == "32" and total < UMBRAL_RFCE else "recepcion"


def obtener_semilla(ambiente: str) -> str:
    raise IntegracionDGIIpendiente(
        "Falta implementar la obtención de semilla según la versión vigente de DGII."
    )


def firmar_xml(xml: bytes, p12_path: str, p12_password: str) -> bytes:
    raise IntegracionDGIIpendiente(
        "Falta integrar XMLDSig con el certificado digital custodiado fuera del código."
    )


def obtener_token(ambiente: str) -> str:
    raise IntegracionDGIIpendiente(
        "Falta integrar autenticación DGII y renovación segura del token."
    )


def enviar_ecf(xml_firmado: bytes, token: str, ambiente: str) -> ResultadoEnvio:
    raise IntegracionDGIIpendiente(
        "Falta integrar el envío e-CF con los XSD y endpoints oficiales vigentes."
    )


def enviar_rfce(xml_firmado: bytes, token: str, ambiente: str) -> dict:
    raise IntegracionDGIIpendiente(
        "Falta integrar el servicio RFCE de DGII y validar su respuesta oficial."
    )


def consultar_resultado(track_id: str, token: str, ambiente: str) -> str:
    raise IntegracionDGIIpendiente(
        "Falta integrar la consulta del resultado DGII y mapear estados oficiales."
    )
