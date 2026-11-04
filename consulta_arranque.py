"""Consulta de arranque: URL base de la API fiscal.

Este campo solicita la dirección base de la API de tu sistema de facturación,
no la dirección de la DGII. El agente agrega /v1 automáticamente y utiliza
rutas como /clientes y /facturas.

Para probar con el simulador local:
1. En otra terminal, inicia primero el simulador:
   uv run uvicorn facturacion.simulador:app --host 127.0.0.1 --port 19001
2. Cuando el configurador pregunte la URL base, escribe:
   http://127.0.0.1:19001

Para conectar el sistema real:
Escribe la URL HTTPS que te proporcione quien administra el sistema, por
ejemplo https://api.tu-dominio.com, sin agregar /v1.

Si solo tienes acceso a la base de datos, pero no una API HTTP que exponga esos
servicios, no pongas una dirección inventada: primero hace falta la URL de esa
API.
"""


if __name__ == "__main__":
    print(__doc__)
