# Registro paso a paso: agente web y WhatsApp

Guía operativa para instalar, configurar, iniciar y comprobar el agente de
Café Santo Domingo en Windows. El chat web y el puente se ejecutan en Node.js;
la API del agente y las conversaciones siguen ejecutándose en Python.

> **Importante:** el QR generado por la web abre una conversación `wa.me` con
> el número público del negocio. No inicia una sesión de WhatsApp Web ni conecta
> por sí solo el agente. Para respuestas automáticas por WhatsApp también hay
> que configurar WhatsApp Cloud API y publicar el webhook mediante HTTPS.

## 1. Reunir los requisitos y accesos

Antes de comenzar, confirma que tienes:

- Acceso a este repositorio y a una terminal PowerShell.
- Una clave válida de Groq para `GROQ_API_KEY`.
- Node.js LTS 20 o posterior, que instala también npm.
- Python 3.14 y `uv`, requeridos por el proyecto.
- Para conectar WhatsApp: una aplicación de Meta for Developers configurada
  con WhatsApp Cloud API, un número de negocio, su ID y un token de acceso.
- Para recibir mensajes de Meta desde Internet: un dominio con HTTPS o un túnel
  HTTPS público temporal.

No escribas claves o tokens en el chat, en capturas, en archivos de código ni
en este registro.

## 2. Instalar o comprobar Node.js y npm

En PowerShell, comprueba si ya están disponibles:

```powershell
node --version
npm --version
```

Si `node` no se reconoce, instala Node.js LTS con `winget`:

```powershell
winget install --id OpenJS.NodeJS.LTS --exact
```

Cierra y vuelve a abrir PowerShell y comprueba otra vez ambos comandos. La
versión de Node debe ser 20 o posterior. Si `winget` no está disponible,
instala la versión LTS desde <https://nodejs.org/> y vuelve a abrir la terminal.

## 3. Instalar o comprobar Python y uv

Desde la raíz del repositorio:

```powershell
uv --version
uv python find
```

El proyecto declara Python 3.14 en `.python-version`. Si `uv` no está
instalado, sigue las instrucciones oficiales de <https://docs.astral.sh/uv/>.
Después, sincroniza el entorno del proyecto:

```powershell
uv sync
```

No uses el Python global para arrancar la API: ejecuta los comandos de Python
con `uv run` para utilizar las dependencias del proyecto.

## 4. Crear y completar el archivo de entorno

Desde la raíz del repositorio, crea `.env` solo si todavía no existe:

```powershell
if (-not (Test-Path .env)) {
    Copy-Item .env.example .env
} else {
    Write-Output ".env ya existe; se conserva sin sobrescribir."
}
notepad .env
```

Completa como mínimo:

```dotenv
GROQ_API_KEY=TU_CLAVE_GROQ
WHATSAPP_PUBLIC_NUMBER=NUMERO_INTERNACIONAL_SOLO_DIGITOS
WHATSAPP_GRAPH_API_VERSION=VERSION_VIGENTE_DE_GRAPH_API
BRIDGE_PORT=3000
AGENT_API_URL=http://127.0.0.1:8000/chat
```

El número público debe incluir el código de país y solo dígitos, sin `+`,
espacios ni guiones. Ejemplo de formato: `18095550101`. Sustituye el ejemplo
por el número real del negocio.

Para pedidos que requieran verificar productos externos, completa también
`GOOGLE_CSE_API_KEY` y `GOOGLE_CSE_ID` según la configuración existente del
proyecto. Las variables de WhatsApp Cloud API se completan en el paso 7.

Guarda y cierra el archivo. `.env` está excluido de Git; conserva las claves
únicamente allí o en el gestor de secretos del servidor.

## 5. Instalar las dependencias de Node

Desde la raíz del repositorio:

```powershell
Set-Location puente_whatsapp
npm install
```

Esto instala Express, el generador del QR y las demás dependencias declaradas
en `package.json`. Para volver a la raíz del proyecto:

```powershell
Set-Location ..
```

## 6. Iniciar y probar el chat web local

Abre dos terminales PowerShell en la raíz del repositorio. Mantén ambas
abiertas mientras uses la aplicación.

**Terminal 1 — API Python del agente:**

```powershell
uv run uvicorn servidor:app --host 127.0.0.1 --port 8000
```

La API debe permanecer ejecutándose. Para verificarla desde otra terminal:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/salud
```

La respuesta esperada es `estado: ok`.

**Terminal 2 — web y puente Node.js:**

```powershell
Set-Location puente_whatsapp
npm start
```

Abre la interfaz en el navegador:

```powershell
Start-Process "http://localhost:3000"
```

Comprueba también el estado del puente:

```powershell
Invoke-RestMethod http://localhost:3000/health
```

Debe responder `estado: ok`. En la página:

1. Confirma que aparece el código QR y el botón **Abrir WhatsApp**.
2. Escribe un mensaje de prueba en el chat web y envíalo.
3. Comprueba que aparece una respuesta del agente.
4. Si el QR no aparece, verifica `WHATSAPP_PUBLIC_NUMBER` en `.env` y reinicia
   el proceso de Node.
5. Si el chat web no responde, verifica que la API Python siga ejecutándose y
   que `GROQ_API_KEY` sea válida.

El indicador "Agente configurado" solo informa que el puente tiene una URL de
API; envía un mensaje de prueba para confirmar la conexión efectiva.

Para detener un servicio, selecciona su terminal y pulsa `Ctrl+C`.

## 7. Configurar WhatsApp Cloud API en Meta

Los nombres y la disposición de las pantallas de Meta pueden cambiar. En la
aplicación de Meta for Developers del negocio:

1. Añade o selecciona el producto **WhatsApp** y completa la configuración de
   WhatsApp Cloud API.
2. En la sección de API/setup de WhatsApp, identifica el **Phone Number ID**
   del número que enviará y recibirá mensajes. No lo confundas con el número de
   teléfono público.
3. Genera u obtén un token de acceso con los permisos requeridos por la
   configuración de WhatsApp Business. Para operación continua, utiliza las
   credenciales y permisos de producción recomendados por Meta; el token de
   prueba puede caducar.
4. Obtén el **App Secret** en la configuración de la aplicación de Meta.
5. Selecciona una cadena de verificación privada para el webhook. Debe ser
   idéntica en Meta y en `.env`. Si la aplicación Python está disponible, puedes
   generar una cadena con:

   ```powershell
   uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

6. Completa estas variables en `.env`; nunca las copies a la interfaz web:

   ```dotenv
   WHATSAPP_PHONE_NUMBER_ID=ID_DEL_NUMERO_EN_META
   WHATSAPP_ACCESS_TOKEN=TOKEN_PRIVADO_DE_META
   WHATSAPP_VERIFY_TOKEN=CADENA_PRIVADA_GENERADA
   META_APP_SECRET=SECRETO_DE_LA_APLICACION_META
   WHATSAPP_GRAPH_API_VERSION=VERSION_VIGENTE_DE_GRAPH_API
   ```

   Usa una versión de Graph API vigente para la aplicación y la cuenta de
   Meta. Reinicia Node después de editar `.env`.
7. Si la aplicación de Meta está en modo de desarrollo, añade los teléfonos de
   prueba como destinatarios autorizados en la configuración de WhatsApp. Para
   atender al público, completa los pasos de publicación/verificación que Meta
   requiera para el negocio.

## 8. Publicar el webhook con HTTPS

Meta debe poder acceder al webhook desde Internet. Una dirección
`localhost` no es pública y no sirve como URL de callback.

1. Mantén el puente Node escuchando localmente en el puerto `3000`.
2. Publica el puerto mediante un servicio de alojamiento con HTTPS o un túnel
   HTTPS de desarrollo autorizado. El destino del túnel local debe ser
   `http://127.0.0.1:3000`.
3. Comprueba que la dirección pública de HTTPS puede abrir:

   ```text
   https://TU-DOMINIO/health
   ```

   Debe devolver `{"estado":"ok"}`. Sustituye `TU-DOMINIO` por el dominio o
   subdominio HTTPS proporcionado por el alojamiento/túnel.
4. En la configuración del webhook de la aplicación Meta, introduce:
   - **Callback URL:** `https://TU-DOMINIO/webhook`
   - **Verify token:** el mismo valor de `WHATSAPP_VERIFY_TOKEN` en `.env`
5. Verifica y guarda la suscripción del webhook. Suscribe el campo/evento
   `messages` para la cuenta de WhatsApp Business.
6. Mantén el túnel y los dos servicios activos. Si cambia la URL del túnel,
   actualiza el callback en Meta.

El puente valida la firma `X-Hub-Signature-256` del cuerpo original con
`META_APP_SECRET`. No desactives esa validación. En producción, usa HTTPS
estable, configura el dominio y protege los secretos en el gestor de secretos
del alojamiento.

## 9. Probar el recorrido completo por WhatsApp

1. Abre `http://localhost:3000` (o la dirección web HTTPS de producción).
2. Escanea el QR con la cámara o la aplicación WhatsApp de un teléfono.
3. Confirma que el enlace abre un chat con el número correcto del negocio.
4. Envía un mensaje de texto desde el teléfono. En modo de pruebas de Meta,
   usa un destinatario autorizado.
5. Comprueba que el puente recibe el webhook, que la API Python genera la
   respuesta y que WhatsApp la entrega al teléfono.
6. Si no llega respuesta, revisa los registros de ambas terminales sin copiar
   tokens ni datos privados. Sigue la tabla de diagnóstico de abajo.

## 10. Ejecutar las pruebas del puente

Desde PowerShell:

```powershell
Set-Location puente_whatsapp
npm test
```

Las pruebas validan el formato del enlace QR, la entrada del chat, la firma de
Meta y la extracción de mensajes de texto. No sustituyen la prueba real con una
cuenta de Meta, un webhook público y credenciales vigentes.

## 11. Diagnóstico de problemas comunes

| Síntoma | Qué comprobar |
| --- | --- |
| `node` o `npm` no se reconoce | Instala Node.js LTS y vuelve a abrir PowerShell. |
| No aparece el QR | Revisa que `WHATSAPP_PUBLIC_NUMBER` tenga código de país y solo dígitos; reinicia Node. |
| La web abre pero el chat no responde | Comprueba `http://127.0.0.1:8000/salud`, la terminal Python y `GROQ_API_KEY`. |
| `/health` no responde | Confirma que Node esté activo en el puerto configurado en `BRIDGE_PORT`. |
| Meta rechaza la verificación | Confirma la URL `/webhook`, HTTPS, que el puente sea accesible y que el token coincida exactamente. |
| Meta acepta el webhook pero no hay respuesta | Revisa la suscripción `messages`, el token de acceso, `Phone Number ID`, el App Secret y los permisos de envío. |
| Respuesta "Firma de webhook inválida" | Verifica que `META_APP_SECRET` sea el App Secret de esa aplicación y reinicia Node después de cambiarlo. |
| Solo funcionan los teléfonos de prueba | La aplicación puede seguir en modo de desarrollo; revisa publicación, permisos y configuración del negocio en Meta. |

## 12. Límites operativos de esta versión

- El agente acepta mensajes de texto; audio, imágenes y otros adjuntos no se
  envían al agente.
- El historial de conversación reside en memoria del proceso Python y se pierde
  al reiniciar. Esta configuración está pensada para una única instancia.
- El QR inicia un chat con el número del negocio. Compartir la web en Internet
  requiere alojar la interfaz; ejecutar `localhost` solo la hace visible en el
  equipo local.
- El webhook solo puede ser verificado y usado por Meta cuando está publicado
  mediante HTTPS y tiene configuradas las credenciales de Cloud API.
- Antes de uso público, configura HTTPS, token permanente/adecuado, permisos,
  límites del proveedor y una política de privacidad acorde al negocio.
