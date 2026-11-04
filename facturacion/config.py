import os
import re
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class ConfiguracionFacturacion:
    api_url: str
    api_key: str
    token_puente: str
    numeros_autorizados: frozenset[str]
    modelo: str

    def autoriza(self, cliente_id: str) -> bool:
        coincidencia = re.fullmatch(r"whatsapp:([1-9]\d{6,14})", cliente_id)
        return (
            coincidencia is not None
            and coincidencia.group(1) in self.numeros_autorizados
        )


def cargar_configuracion() -> ConfiguracionFacturacion | None:
    """Devuelve None solo cuando la integración está completamente desactivada."""
    variables = {
        "FACTURACION_API_URL": os.getenv("FACTURACION_API_URL", "").strip(),
        "FACTURACION_API_KEY": os.getenv("FACTURACION_API_KEY", "").strip(),
        "FACTURACION_NUMEROS_AUTORIZADOS": os.getenv(
            "FACTURACION_NUMEROS_AUTORIZADOS",
            "",
        ).strip(),
        "AGENT_BRIDGE_TOKEN": os.getenv("AGENT_BRIDGE_TOKEN", "").strip(),
    }
    if not any(
        valor
        for nombre, valor in variables.items()
        if nombre != "AGENT_BRIDGE_TOKEN"
    ):
        return None

    faltantes = [nombre for nombre, valor in variables.items() if not valor]
    if faltantes:
        raise RuntimeError(
            "La integración de facturación está incompleta. Configura: "
            + ", ".join(faltantes)
            + "."
        )

    parsed_url = urlparse(variables["FACTURACION_API_URL"])
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise RuntimeError("FACTURACION_API_URL debe ser una URL HTTP(S) válida.")
    if (
        parsed_url.username is not None
        or parsed_url.password is not None
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise RuntimeError(
            "FACTURACION_API_URL no debe incluir credenciales, consulta ni fragmento."
        )
    if parsed_url.scheme != "https" and parsed_url.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise RuntimeError(
            "FACTURACION_API_URL debe usar HTTPS fuera del entorno local."
        )

    numeros_candidatos = {
        re.sub(r"\D", "", numero)
        for numero in variables["FACTURACION_NUMEROS_AUTORIZADOS"].split(",")
    }
    numeros = frozenset(
        numero
        for numero in numeros_candidatos
        if re.fullmatch(r"[1-9]\d{6,14}", numero)
    )
    if not numeros:
        raise RuntimeError(
            "FACTURACION_NUMEROS_AUTORIZADOS debe incluir al menos un número."
        )

    return ConfiguracionFacturacion(
        api_url=variables["FACTURACION_API_URL"].rstrip("/"),
        api_key=variables["FACTURACION_API_KEY"],
        token_puente=variables["AGENT_BRIDGE_TOKEN"],
        numeros_autorizados=numeros,
        modelo=os.getenv("GROQ_BILLING_MODEL", "openai/gpt-oss-safeguard-20b"),
    )
