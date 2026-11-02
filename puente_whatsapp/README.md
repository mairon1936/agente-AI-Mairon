# Chat web y puente WhatsApp Business

Este directorio contiene una aplicación Node.js que sirve la interfaz web, crea
el código QR para iniciar un chat con el número de WhatsApp Business y recibe
los mensajes de WhatsApp Cloud API. El agente de Python continúa atendiendo los
mensajes y conserva el flujo de pedidos existente.

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
   `WHATSAPP_PUBLIC_NUMBER` con código de país y solo dígitos, por ejemplo
   `18095550101` (sin `+`, espacios ni guiones).
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

Abre `http://localhost:3000` en el navegador. También puedes iniciar el puente
en modo de desarrollo con recarga al cambiar `server.js`:

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
3. Publica el puerto del puente detrás de un dominio con HTTPS y configura la
   URL de webhook como `https://TU-DOMINIO/webhook`. Usa el mismo
   `WHATSAPP_VERIFY_TOKEN` al validar el webhook y suscribe el campo
   `messages`.
4. Comprueba `https://TU-DOMINIO/health` y escanea el QR desde un teléfono que
   pueda llegar al número configurado.

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
| `AGENT_API_URL` | URL interna de la API Python; valor inicial `http://127.0.0.1:8000/chat`. |

El endpoint `/api/chat` limita los mensajes a 2000 caracteres y 30 solicitudes
por minuto por IP. Las conversaciones se mantienen en memoria por proceso en
el agente Python; al reiniciar el servidor, se reinicia su historial. Para uso
con múltiples instancias se necesita almacenamiento compartido de sesiones y
pedidos. Esta versión procesa mensajes entrantes de texto; los mensajes con
audio, imágenes u otros adjuntos no se envían al agente.

## Pruebas

Desde esta carpeta, ejecuta:

```powershell
npm test
```
