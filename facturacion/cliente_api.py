import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .config import ConfiguracionFacturacion


class ErrorFacturacion(RuntimeError):
    def __init__(self, estado: int, detalle: str) -> None:
        super().__init__(f"{estado}: {detalle}")
        self.estado = estado
        self.detalle = detalle


class _NoSeguirRedirecciones(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        return None


class ClienteFacturacion:
    """Única puerta del agente hacia el sistema de facturación."""

    _MAX_RESPUESTA_BYTES = 12 * 1024 * 1024

    def __init__(
        self,
        configuracion: ConfiguracionFacturacion,
        timeout: float = 20,
    ) -> None:
        self._base_url = f"{configuracion.api_url}/v1"
        self._api_key = configuracion.api_key
        self._timeout = timeout
        self._opener = build_opener(_NoSeguirRedirecciones)

    def _solicitar(
        self,
        metodo: str,
        ruta: str,
        *,
        consulta: dict[str, str] | None = None,
        cuerpo: dict | None = None,
        idempotency_key: str | None = None,
        aceptar_pdf: bool = False,
    ) -> dict | list | bytes:
        url = f"{self._base_url}{ruta}"
        if consulta:
            url = f"{url}?{urlencode(consulta)}"
        headers = {"X-API-Key": self._api_key, "Accept": "application/json"}
        datos = None
        if cuerpo is not None:
            datos = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        if aceptar_pdf:
            headers["Accept"] = "application/pdf"
        solicitud = Request(url, data=datos, headers=headers, method=metodo)
        try:
            with self._opener.open(solicitud, timeout=self._timeout) as respuesta:
                contenido = respuesta.read(self._MAX_RESPUESTA_BYTES + 1)
                tipo = respuesta.headers.get_content_type()
                if len(contenido) > self._MAX_RESPUESTA_BYTES:
                    raise ErrorFacturacion(
                        502,
                        "La respuesta del sistema de facturación excede el límite.",
                    )
        except HTTPError as error:
            try:
                cuerpo_error = json.loads(error.read().decode("utf-8"))
                detalle = (
                    cuerpo_error.get(
                        "detail",
                        "Error del sistema de facturación",
                    )
                    if isinstance(cuerpo_error, dict)
                    else "Error del sistema de facturación"
                )
            except (UnicodeDecodeError, json.JSONDecodeError):
                detalle = "Error del sistema de facturación"
            raise ErrorFacturacion(error.code, str(detalle)[:300]) from error
        except TimeoutError as error:
            raise ErrorFacturacion(
                504,
                "El sistema de facturación no respondió a tiempo.",
            ) from error
        except (URLError, OSError) as error:
            raise ErrorFacturacion(
                503,
                "No se pudo contactar al sistema de facturación.",
            ) from error

        if aceptar_pdf:
            if tipo != "application/pdf" or not contenido.startswith(b"%PDF-"):
                raise ErrorFacturacion(
                    502,
                    "El sistema de facturación devolvió un PDF inválido.",
                )
            return contenido
        try:
            resultado = json.loads(contenido.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ErrorFacturacion(
                502,
                "El sistema de facturación devolvió una respuesta inválida.",
            ) from error
        if not isinstance(resultado, (dict, list)):
            raise ErrorFacturacion(
                502,
                "El sistema de facturación devolvió una respuesta inválida.",
            )
        return resultado

    def buscar_cliente(self, rnc_o_cedula: str) -> dict:
        documento = quote(rnc_o_cedula, safe="")
        resultado = self._solicitar("GET", f"/clientes/{documento}")
        if not isinstance(resultado, dict):
            raise ErrorFacturacion(502, "Respuesta inválida al buscar el cliente.")
        return resultado

    def buscar_producto(self, texto: str) -> dict:
        resultado = self._solicitar(
            "GET",
            "/productos",
            consulta={"q": texto},
        )
        if not isinstance(resultado, list):
            raise ErrorFacturacion(502, "Respuesta inválida al buscar productos.")
        return {"productos": resultado}

    def crear_borrador(self, payload: dict) -> dict:
        resultado = self._solicitar(
            "POST",
            "/facturas/borradores",
            cuerpo=payload,
        )
        if not isinstance(resultado, dict):
            raise ErrorFacturacion(502, "Respuesta inválida al crear el borrador.")
        return resultado

    def emitir(self, borrador_id: str) -> dict:
        resultado = self._solicitar(
            "POST",
            f"/facturas/borradores/{quote(borrador_id, safe='')}/emitir",
            idempotency_key=f"emitir:{borrador_id}",
        )
        if not isinstance(resultado, dict):
            raise ErrorFacturacion(502, "Respuesta inválida al emitir la factura.")
        return resultado

    def estado(self, factura_id: str) -> dict:
        resultado = self._solicitar(
            "GET",
            f"/facturas/{quote(factura_id, safe='')}",
        )
        if not isinstance(resultado, dict):
            raise ErrorFacturacion(502, "Respuesta inválida al consultar la factura.")
        return resultado

    def descargar_pdf(self, factura_id: str) -> bytes:
        resultado = self._solicitar(
            "GET",
            f"/facturas/{quote(factura_id, safe='')}/pdf",
            aceptar_pdf=True,
        )
        if not isinstance(resultado, bytes):
            raise ErrorFacturacion(502, "Respuesta inválida al descargar el PDF.")
        return resultado
