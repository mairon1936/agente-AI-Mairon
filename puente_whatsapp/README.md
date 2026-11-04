# Asistente de Facturación Electrónica: chat web y puente WhatsApp

Este directorio contiene la interfaz web y el puente de WhatsApp de
Asistente de Facturación Electrónica. La atención informativa funciona sin datos
fiscales. El flujo opcional solo atiende números autorizados y requiere una API
interna de facturación; el simulador local no emite comprobantes válidos ni se
conecta con la DGII.

La interfaz también es una PWA: en navegadores compatibles se puede instalar
desde la opción **Instalar aplicación**. En iPhone y iPad, abre la página en
Safari, pulsa **Compartir** y selecciona **Agregar a pantalla de inicio**. Para
la instalación y el acceso público, despliega el servicio bajo HTTPS; el
procedimiento está en [informe_despliegue_agente.md](../informe_despliegue_agente.md).

## Requisitos

- Node.js 20 o posterior (incluye npm): <https://nodejs.org/>.
- Python 3.14 y `uv`, como requiere el proyecto.
- Una clave `GROQ_API_KEY` válida.
- Una cuenta configurada en Meta for Developers para WhatsApp Cloud API si se
  desea habilitar la atención por WhatsApp.

## Configuración inicial en Windows

1. Desde la raíz del proyecto, crea `.env` a partir de la plantilla:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Edita `.env` y completa `GROQ_API_KEY`. Para mostrar el QR, indica
   `WHATSAPP_PUBLIC_NUMBER` con el número real del negocio, código de país y
   solo dígitos (sin `+`, espacios ni guiones). Sin este dato, no se puede
   generar un QR que lleve a una cuenta real.
3. Entra en esta carpeta e instala las dependencias de npm:

   ```powershell
   Set-Location puente_whatsapp
   npm install
   ```

## Iniciar los servicios y abrir la web

Abre dos terminales PowerShell en la carpeta raíz del proyecto.

**Terminal 1 — API del agente Python:**

```powershell
uv sync
uv run uvicorn servidor:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — web y puente Node.js:**

```powershell
Set-Location puente_whatsapp
npm start
```

Abre la dirección local de desarrollo en el navegador. También puedes iniciar
el puente en modo de desarrollo con recarga al cambiar `server.js`:

```powershell
npm run dev
```

Los servicios deben permanecer ejecutándose en sus terminales. La interfaz web
y el QR son accesibles desde el mismo servidor Node.

## Activar WhatsApp Business

El QR de la web contiene un enlace `wa.me` al número público del negocio. Al
escanearlo, cada cliente abre WhatsApp en su propio teléfono y envía el primer
mensaje. Para contestar esos mensajes automáticamente:

1. En Meta for Developers, configura WhatsApp Cloud API y obtén el identificador
   del número, un token de acceso y el secreto de la aplicación.
2. Completa en `.env` `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`,
   `WHATSAPP_VERIFY_TOKEN`, `META_APP_SECRET` y
   `WHATSAPP_GRAPH_API_VERSION` con una versión de Graph API vigente en tu app
   de Meta. El token de verificación lo eliges tú y debe coincidir con el
   configurado en Meta. No publiques estos valores ni los envíes al navegador.
3. Publica el puente en un servicio con HTTPS y configura la
   URL de webhook como `https://TU-DOMINIO/webhook`. Usa el mismo
   `WHATSAPP_VERIFY_TOKEN` al validar el webhook y suscribe el campo
   `messages`.
4. Comprueba `https://TU-DOMINIO/health` y escanea el QR desde un teléfono que
   pueda llegar al número configurado.
5. Si activarás la facturación, configura `FACTURACION_API_URL`,
   `FACTURACION_API_KEY`, `FACTURACION_NUMEROS_AUTORIZADOS` y
   `AGENT_BRIDGE_TOKEN` en los entornos privados de Python y Node. El token de
   puente debe ser idéntico en ambos servicios. Fuera de localhost, usa HTTPS
   para la API fiscal.
6. Comprueba que el sistema fiscal valide clientes, productos, importes,
   impuestos, e-NCF e idempotencia. La emisión solo se solicita mediante el
   botón **Emitir**; nunca por decisión del modelo.

Para desarrollo local, el proveedor necesita poder alcanzar el webhook desde
Internet por HTTPS. `localhost` no basta; utiliza un túnel HTTPS temporal o un
servidor desplegado. No publiques la app sin HTTPS y sin configurar el secreto
de Meta: el puente comprueba la firma `X-Hub-Signature-256` antes de procesar
mensajes.

## Variables disponibles

| Variable | Uso |
| --- | --- |
| `WHATSAPP_PUBLIC_NUMBER` | Número de destino incluido en el QR. |
| `WHATSAPP_PHONE_NUMBER_ID` | ID del número de WhatsApp Cloud API. |
| `WHATSAPP_ACCESS_TOKEN` | Token privado de acceso de Meta. |
| `WHATSAPP_VERIFY_TOKEN` | Secreto elegido para verificar el webhook de Meta. |
| `META_APP_SECRET` | Secreto privado usado para verificar la firma del webhook. |
| `WHATSAPP_GRAPH_API_VERSION` | Versión vigente de Graph API configurada para la app de Meta. |
| `BRIDGE_PORT` | Puerto local de Node; valor inicial `3000`. |
| `PORT` | Puerto asignado por la plataforma de alojamiento; tiene prioridad sobre `BRIDGE_PORT`. |
| `HOST` | Interfaz de red de escucha. En despliegue, se usa `0.0.0.0` cuando la plataforma define `PORT`. |
| `AGENT_API_URL` | URL interna de la API Python; valor inicial `http://127.0.0.1:8000/chat`. |
| `AGENT_BRIDGE_TOKEN` | Secreto compartido Node→Python; obligatorio en el despliegue Compose. |
| `AGENT_DATABASE_PATH` | Ruta del SQLite persistente; valor local `data/agent.sqlite3`. |
| `AGENT_SESSION_RETENTION_DAYS` | Días desde la última actividad antes de purgar conversaciones; valor inicial `90`. |
| `AGENT_BACKUP_DIR` | Directorio de respaldos; valor local `backups`. |
| `BRIDGE_DATA_DIR` | Directorio persistente de la cola de WhatsApp; valor local `data/bridge`. |
| `FACTURACION_API_URL` | URL de la API interna de facturación; HTTPS fuera de localhost. |
| `FACTURACION_API_KEY` | Clave de servicio para la API interna de facturación. |
| `FACTURACION_NUMEROS_AUTORIZADOS` | Números E.164 sin `+`, separados por coma. |
| `GROQ_BILLING_MODEL` | Modelo Groq de herramientas; inicial `openai/gpt-oss-safeguard-20b`. |

El endpoint `/api/chat` limita los mensajes a 2000 caracteres y 30 solicitudes
por minuto por IP. El webhook valida la firma de Meta, guarda el evento en una
cola durable antes de confirmarlo y reintenta fallas transitorias hasta cinco
veces. Los eventos procesados y fallidos se conservan siete días para evitar
duplicados ante reintentos de Meta. Los PDF se descargan del sistema fiscal y
solo se entregan por WhatsApp tras aceptación. Las conversaciones y sesiones
fiscales se guardan en SQLite; para varias réplicas hace falta migrar a una base
de datos compartida y una cola distribuida. Audio, imágenes y otros adjuntos no
se envían al agente.

`/health` comprueba que el puente responde y `/health/ready` comprueba también
que la API Python y la cola estén disponibles. Configura un monitor externo
para consultar la ruta de preparación y alertar; los healthchecks de Docker no
reinician por sí solos un contenedor que siga ejecutándose pero esté `unhealthy`.

La integración DGII real no está completada ni certificada. No uses el
simulador de desarrollo en producción; antes hacen falta el motor e-CF o un
proveedor certificado y las pruebas oficiales descritas en el informe de
despliegue.

## Pruebas

Desde esta carpeta, ejecuta:

```powershell
npm test
```

Para despliegue con almacenamiento persistente, reinicio supervisado y
respaldos, consulta el [informe de continuidad operativa](../informe_continuidad_operativa.md).
