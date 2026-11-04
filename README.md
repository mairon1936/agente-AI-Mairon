# Asistente de Facturación Electrónica

Asistente del Sistema de Facturación Electrónica RD. Sin configurar la
integración opcional, responde consultas informativas y no accede a los libros
del negocio. El flujo de facturación implementado se conecta a una API interna
por contrato; el simulador local solo sirve para pruebas y no emite comprobantes
fiscales válidos ni se conecta a la DGII.

## Estado de la información

- `sistem_prompts.py`: identidad, saludo e instrucciones del asistente.
- `agente_facturacion.py`: modo informativo, sin acceso a los archivos del
  negocio.
- `facturacion/`: herramientas de búsqueda, creación de borradores, botones de
  confirmación/cancelación, idempotencia, consulta de estado, envío de PDF y
  contrato pendiente de integración con el motor e-CF.
- `facturacion/simulador.py`: API local de prueba; sus clientes, productos,
  montos y PDF son ficticios.
- `datos.py` y los archivos dentro de `datos/`: datos de la aplicación anterior,
  conservados sin cambios y fuera de la ruta del nuevo asistente.

La conexión a una API de facturación real solo se activa cuando se configuran
todas las variables `FACTURACION_*`, los números autorizados y
`AGENT_BRIDGE_TOKEN`. Sin ellas, el asistente conserva el modo informativo. El
motor DGII y la certificación oficial no están implementados; el simulador nunca
debe configurarse para producción.

## Ejecución

Desde la raíz del proyecto, sincroniza las dependencias y ejecuta la aplicación
con el entorno administrado por `uv`:

```powershell
uv sync
uv run main.py
```

Para iniciar la API HTTP, ejecuta:

```powershell
uv run uvicorn servidor:app --reload
```

La API del agente admite hasta 500 solicitudes de chat procesándose en paralelo
por proceso; las solicitudes adicionales esperan turno. Esto no aumenta las
cuotas del proveedor del modelo ni reemplaza el escalado de la infraestructura.
En producción, utiliza HTTPS y valida capacidad y límites del proveedor antes
de recibir tráfico real. Las conversaciones y sesiones fiscales se guardan en
SQLite, con retención predeterminada de 90 días. El puente guarda los webhooks
pendientes en disco y reintenta errores transitorios; utiliza una sola instancia
del puente y un solo worker de API para este almacenamiento local.

Para desplegar los dos servicios en Docker con reinicio automático, healthchecks
y volumen persistente, consulta [informe_continuidad_operativa.md](./informe_continuidad_operativa.md).
En el servidor, protege `.env`, crea el directorio `backups` con acceso
restringido y programa `scripts/backup.sh` (Linux) o `scripts/backup.ps1`
(Windows). El respaldo online de SQLite y la cola se ejecutan con:

```powershell
docker compose run --rm backup
```

Los healthchecks detectan fallas y `restart: unless-stopped` recupera procesos
que terminan, pero Docker no reinicia automáticamente un contenedor solo por
marcarlo como `unhealthy`; configura además un monitor externo con alertas y un
procedimiento de recuperación.

Para probar el flujo de facturación únicamente con datos ficticios, configura
en `.env` la URL `http://127.0.0.1:19001`, una clave de prueba compartida para
`FACTURACION_API_KEY`, un token aleatorio para `AGENT_BRIDGE_TOKEN` y números
de prueba separados por coma en `FACTURACION_NUMEROS_AUTORIZADOS`. Luego
inicia en terminales separadas:

```powershell
uv run uvicorn facturacion.simulador:app --host 127.0.0.1 --port 19001
uv run uvicorn servidor:app --port 8000
```

El simulador acepta el cliente `131000001` y los productos `P001` y `P002`.
Úsalo solo en pruebas: los datos, aceptación DGII y comprobantes PDF son
simulados. Para probar botones y documentos de WhatsApp también hacen falta las
credenciales Cloud API ya descritas en esta guía.

Para configurar el flujo con una API fiscal real en el equipo local, ejecuta
`uv run python configurar_facturacion.py`. El programa pide la URL, números
autorizados y claves ocultando la entrada de secretos; genera el token de
puente y actualiza `.env` sin mostrar sus valores. `.env` no se debe subir a
Git. En producción, guarda los mismos valores directamente como secretos
privados en el proveedor de alojamiento: este asistente no publica servicios ni
crea secretos en una cuenta de hosting.

Para iniciar el chat web y el puente de WhatsApp, sigue las
instrucciones de [puente_whatsapp/README.md](./puente_whatsapp/README.md). El
registro de instalación, configuración de Meta y pruebas está en
[puente_whatsapp/PROCEDIMIENTOS_PUESTA_EN_MARCHA.md](./puente_whatsapp/PROCEDIMIENTOS_PUESTA_EN_MARCHA.md).
La interfaz incluye un menú numerado, chat, QR de WhatsApp y soporte para
instalarse como PWA. Para generar una URL HTTPS pública, sigue el
[informe de despliegue](./informe_despliegue_agente.md) y configura el número
real de WhatsApp en el entorno del servidor.

Para iniciar la API y la interfaz web desde una sola terminal y abrir el
navegador automáticamente, ejecuta desde la raíz:

```powershell
python open.py
```

Pulsa `Ctrl+C` en esa terminal para detener los servicios que inició el programa.
Si ya estaban activos, el programa los reutiliza y no los detiene.

También puedes iniciar la aplicación desde PowerShell con:

```powershell
.\run.ps1
```

No ejecutes `python main.py` con el Python global: debe usarse el entorno
`.venv` del proyecto. En VS Code, las terminales nuevas activan ese entorno
automáticamente. La aplicación requiere la variable de entorno `GROQ_API_KEY`.

## Protección de credenciales

Guarda la clave únicamente en `.env` o como variable de entorno. Git ignora
`.env` y sus variantes; `.env.example` es solo una plantilla y nunca debe
contener credenciales reales. No pegues claves en el chat, código, capturas ni
registros. La aplicación no añade la clave al historial enviado al modelo ni la
imprime en sus mensajes de error.

El hook `.githooks/pre-commit` bloquea commits que incluyan archivos `.env`
(incluso si se agregaron forzadamente) o patrones conocidos de credenciales en
los cambios preparados. Para activarlo en cada clon, ejecuta una vez:

```powershell
git config --local core.hooksPath .githooks
```

Este control local puede saltarse deliberadamente con `git commit --no-verify` o
desactivando el hook; para imponer una prohibición que nadie pueda omitir se
requiere una regla del servidor del repositorio, como push protection o una
política de rama protegida.

Si la aplicación informa que Groq rechazó la clave, revisa que `GROQ_API_KEY`
esté vigente en `.env`; no compartas el valor de esa clave. Si informa un límite
de solicitudes, espera o revisa la cuota de la cuenta. Ante un error de conexión,
comprueba el acceso a internet e inténtalo de nuevo.
