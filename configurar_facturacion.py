"""Configura secretos locales sin mostrarlos ni versionarlos."""

import getpass
import os
import re
import secrets
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parent
ARCHIVO_ENV = RAIZ / ".env"
PLANTILLA_ENV = RAIZ / ".env.example"
PATRON_NUMERO = re.compile(r"[1-9]\d{6,14}\Z")


def _valor_env(valor: str) -> str:
    if "\n" in valor or "\r" in valor:
        raise ValueError("Los valores de configuración no pueden contener saltos de línea.")
    return '"' + valor.replace("\\", "\\\\").replace('"', '\\"') + '"'


def guardar_variables(archivo: Path, cambios: dict[str, str]) -> None:
    """Actualiza las variables indicadas y conserva el resto del archivo."""
    archivo.parent.mkdir(parents=True, exist_ok=True)
    if archivo.exists():
        lineas = archivo.read_text(encoding="utf-8").splitlines()
    else:
        lineas = PLANTILLA_ENV.read_text(encoding="utf-8").splitlines()

    escritas: set[str] = set()
    resultado: list[str] = []
    patron = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for linea in lineas:
        coincidencia = patron.match(linea)
        nombre = coincidencia.group(1) if coincidencia else None
        if nombre not in cambios:
            resultado.append(linea)
            continue
        if nombre in escritas:
            continue
        resultado.append(f"{nombre}={_valor_env(cambios[nombre])}")
        escritas.add(nombre)

    resultado.extend(
        f"{nombre}={_valor_env(valor)}"
        for nombre, valor in cambios.items()
        if nombre not in escritas
    )
    contenido = "\n".join(resultado) + "\n"

    descriptor, temporal = tempfile.mkstemp(
        prefix=".env.",
        suffix=".tmp",
        dir=archivo.parent,
        text=True,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as salida:
            salida.write(contenido)
            salida.flush()
            os.fsync(salida.fileno())
        if os.name == "posix":
            os.chmod(temporal, 0o600)
        os.replace(temporal, archivo)
    finally:
        if os.path.exists(temporal):
            os.unlink(temporal)


def _pedir_secreto(etiqueta: str) -> str:
    valor = getpass.getpass(f"{etiqueta} (entrada oculta): ").strip()
    if not valor:
        raise ValueError(f"{etiqueta} es obligatorio.")
    if "\n" in valor or "\r" in valor:
        raise ValueError(f"{etiqueta} no puede contener saltos de línea.")
    return valor


def _pedir_numero(etiqueta: str) -> str:
    numero = input(f"{etiqueta} (código de país y solo dígitos): ").strip()
    if not PATRON_NUMERO.fullmatch(numero):
        raise ValueError(f"{etiqueta} debe estar en formato internacional sin '+'.")
    return numero


def _pedir_numeros_autorizados() -> str:
    entrada = input(
        "Números autorizados (código de país, dígitos, separados por coma): "
    )
    numeros = [numero.strip() for numero in entrada.split(",") if numero.strip()]
    if not numeros or any(not PATRON_NUMERO.fullmatch(numero) for numero in numeros):
        raise ValueError(
            "Los números autorizados deben estar en formato internacional sin '+'."
        )
    return ",".join(dict.fromkeys(numeros))


def _validar_url_facturacion(valor: str) -> str:
    url = valor.strip().rstrip("/")
    parsed = urlparse(url)
    if (
        parsed.scheme not in {"https", "http"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Indica una URL base HTTP(S) válida, sin credenciales ni query.")
    if parsed.scheme != "https" and parsed.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("La API fiscal debe usar HTTPS fuera de localhost.")
    return url


def _configurar() -> dict[str, str]:
    existentes = dotenv_values(ARCHIVO_ENV if ARCHIVO_ENV.exists() else PLANTILLA_ENV)
    cambios: dict[str, str] = {}
    if not (existentes.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")):
        cambios["GROQ_API_KEY"] = _pedir_secreto("Clave GROQ_API_KEY")

    cambios["FACTURACION_API_URL"] = _validar_url_facturacion(
        input("URL base de la API fiscal (sin /v1): ").strip()
    )
    cambios["FACTURACION_API_KEY"] = _pedir_secreto(
        "Clave de servicio FACTURACION_API_KEY"
    )
    cambios["FACTURACION_NUMEROS_AUTORIZADOS"] = _pedir_numeros_autorizados()
    cambios["AGENT_BRIDGE_TOKEN"] = secrets.token_urlsafe(48)
    if not existentes.get("GROQ_BILLING_MODEL"):
        cambios["GROQ_BILLING_MODEL"] = os.getenv(
            "GROQ_BILLING_MODEL",
            "openai/gpt-oss-safeguard-20b",
        )

    configurar_whatsapp = input(
        "¿Configurar también WhatsApp Cloud API ahora? [s/N]: "
    ).strip().casefold()
    if configurar_whatsapp in {"s", "si", "sí"}:
        cambios["WHATSAPP_PUBLIC_NUMBER"] = _pedir_numero(
            "Número público de WhatsApp"
        )
        cambios["WHATSAPP_PHONE_NUMBER_ID"] = _pedir_secreto(
            "WHATSAPP_PHONE_NUMBER_ID"
        )
        cambios["WHATSAPP_ACCESS_TOKEN"] = _pedir_secreto(
            "WHATSAPP_ACCESS_TOKEN"
        )
        cambios["WHATSAPP_VERIFY_TOKEN"] = _pedir_secreto(
            "WHATSAPP_VERIFY_TOKEN configurado en Meta"
        )
        cambios["META_APP_SECRET"] = _pedir_secreto("META_APP_SECRET")
        version = input(
            "Versión Graph API configurada en Meta (formato vNN.N): "
        ).strip()
        if not re.fullmatch(r"v\d+\.\d+", version):
            raise ValueError("La versión de Graph API debe tener el formato vNN.N.")
        cambios["WHATSAPP_GRAPH_API_VERSION"] = version

    return cambios


def main() -> None:
    cambios = _configurar()
    guardar_variables(ARCHIVO_ENV, cambios)
    print("Configuración local guardada en .env; no se mostraron los secretos.")
    print(
        "AGENT_BRIDGE_TOKEN quedó generado. Para producción, guarda el mismo "
        "valor como secreto privado en los servicios Python y Node."
    )
    print(
        "Reinicia Python y Node para cargar la configuración. La API fiscal "
        "debe tener una ruta /v1 y no debe ser el simulador en producción."
    )


if __name__ == "__main__":
    main()
