# Informe de preparación para despliegue del Asistente de Facturación Electrónica

## Actualización del sistema

La interfaz y el agente se identifican ahora como
`Asistente de Facturación Electrónica` y muestran la bienvenida al Sistema de
Facturación Electrónica RD en negritas.
`datos.py` y los libros de datos del negocio no se modificaron. La nueva ruta
informativa del agente no los consulta. Se agregó una integración opcional con
un contrato interno de facturación y un simulador local con información ficticia.
No se ha conectado un motor e-CF real ni la DGII.

El objetivo de 3,000 usuarios simultáneos no está implementado ni certificado.
Las conversaciones y sesiones fiscales ahora se guardan en SQLite y el puente
usa una cola durable, pero la configuración actual está limitada a una sola
instancia de cada servicio. La capacidad también depende del alojamiento y de
los límites del proveedor del modelo.

## Alcance y estado

Se preparó la interfaz existente para publicarse como sitio web adaptable e
instalable (PWA), con navegación numerada, chat, QR de WhatsApp y recursos de
instalación. El proyecto queda listo para configurar y desplegar en un servicio
de alojamiento; **todavía no tiene una URL pública**. Crear esa dirección
requiere acceso a una cuenta de alojamiento, completar las variables privadas y
publicar el proyecto. Una URL local de desarrollo no es accesible para otras
personas ni puede sustituirse por un dominio real desde el código.

## Cambios realizados

- `puente_whatsapp/public/index.html`: metadatos web, manifiesto, menú numerado
  con enlaces al chat, compartir, WhatsApp e instalación.
- `puente_whatsapp/public/manifest.webmanifest` y
  `puente_whatsapp/public/icons/`: nombre, colores e iconos PNG para la PWA y
  la pantalla de inicio de Apple.
- `puente_whatsapp/public/service-worker.js`: guarda únicamente recursos
  estáticos de la interfaz. Las conversaciones, respuestas y rutas de API no
  se almacenan en caché.
- `puente_whatsapp/public/app.js`: ofrece el botón de instalación en
  navegadores compatibles, registra el service worker y muestra/copia la URL
  cuando se sirve desde un dominio HTTPS público.
- `puente_whatsapp/server.js`: acepta el puerto asignado por el alojamiento y
  escucha en la interfaz de red del contenedor sin anunciar una dirección local;
  admite botones interactivos de confirmación y documentos PDF.
- `facturacion/almacen.py` y `puente_whatsapp/durable-queue.js`: guardan
  historiales/sesiones y webhooks en almacenamiento persistente local. El
  despliegue actual es de una instancia; revisa el
  [informe de continuidad operativa](./informe_continuidad_operativa.md) para
  healthchecks, respaldos y límites.
- `puente_whatsapp/test/bridge.test.js`: prueba que la página y recursos PWA se
  sirven correctamente.
- `facturacion/`: integra consultas de cliente/producto, creación de borradores,
  emisión idempotente por botón, consulta de estado y entrega del PDF en
  WhatsApp. `facturacion.simulador` es solo para pruebas y no emite e-CF válido.
- `facturacion.dgii_flow`: documenta la clasificación RFCE/recepción y los
  estados; firma XML, XSD, certificado, autenticación y llamadas reales DGII
  permanecen sin implementar.

La aplicación instala una PWA desde el navegador; no se generaron instaladores
nativos APK, IPA, MSI ni una publicación en Play Store o App Store. En iPhone y
iPad se agrega desde Safari mediante **Compartir > Agregar a pantalla de
inicio**. En Android, Chrome ofrece **Instalar aplicación** cuando se accede
por HTTPS y se cumplen sus requisitos.

## Publicación y URL HTTPS

Pasos recomendados para publicar usando Render como ejemplo:

1. Sube el repositorio a una cuenta Git privada o pública, sin `.env`, claves,
   tokens ni credenciales.
2. Crea dos servicios en la misma región: un servicio Node para
   `puente_whatsapp` y un servicio Python para la API de `servidor:app`.
3. En el servicio web, usa `npm ci` como comando de compilación y `npm start`
   como comando de inicio. Configura la ruta de salud `/health`.
4. En el servicio Python, instala con `uv sync --frozen` y ejecuta
   `uv run uvicorn servidor:app --host 0.0.0.0 --port $PORT`. Configura la ruta
   de salud `/salud`.
5. En el entorno del servicio Python, define `GROQ_API_KEY` y las demás
   credenciales del agente que realmente uses. En el servicio web, define
   `AGENT_API_URL` con la dirección privada interna de la API terminada en
   `/chat` y configura `WHATSAPP_PUBLIC_NUMBER` con código de país, solo
   dígitos. Para facturación, configura en Python
   `FACTURACION_API_URL`, `FACTURACION_API_KEY` y
   `FACTURACION_NUMEROS_AUTORIZADOS`; establece además el mismo
   `AGENT_BRIDGE_TOKEN` aleatorio en ambos servicios.
6. Si vas a habilitar mensajes entrantes automáticos de WhatsApp Cloud API,
   configura también `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_ACCESS_TOKEN`,
   `WHATSAPP_VERIFY_TOKEN`, `META_APP_SECRET` y
   `WHATSAPP_GRAPH_API_VERSION` como variables privadas en el servidor.
7. Despliega ambos servicios. El proveedor asignará una dirección HTTPS pública
   al servicio web, por ejemplo `https://nombre-del-servicio.onrender.com`.
   Comprueba esa dirección en `/health`, abre la página y escanea el QR con un
   teléfono. Si se usa un dominio propio, configúralo en el panel del proveedor
   y completa su verificación DNS.
8. Para el webhook de Meta, registra `https://<dominio-publicado>/webhook`,
   valida el token y suscribe el campo `messages`. Meta debe poder alcanzar el
   dominio por HTTPS.

La URL de ejemplo no representa un dominio ya reservado ni un despliegue
realizado. El repositorio no incluye credenciales de alojamiento, dominio ni
acceso a una cuenta de Render, por lo que no es posible publicar desde este
entorno ni emitir una URL pública en nombre del usuario.

## QR de WhatsApp

El QR se genera al abrir la página y apunta a `https://wa.me/<número>`. Se
requiere completar `WHATSAPP_PUBLIC_NUMBER` con el número público correcto. No
se inventó ni se incorporó un número de ejemplo como destino. Sin él, la página
informa que WhatsApp no está disponible y no muestra un QR que pudiera llevar
a una cuenta incorrecta.

El QR abre WhatsApp para que el cliente inicie la conversación; no equivale por
sí mismo a una integración automática de mensajes. Para responder desde el
agente se requiere configurar WhatsApp Cloud API y su webhook.

## Seguridad, persistencia y límites

- Guarda claves únicamente en el entorno privado del proveedor; nunca en el
  navegador, el repositorio ni el informe.
- Usa HTTPS para el acceso público y el webhook de Meta.
- Las conversaciones y sesiones fiscales se guardan en SQLite en el volumen
  persistente configurado; los pedidos continúan usando los archivos Excel del
  proyecto. La configuración actual no debe escalarse a varias réplicas.
- El service worker almacena solo la estructura estática de la web. El chat
  requiere conectividad con los servicios y no funciona sin conexión.
- Antes de abrir el servicio a clientes, verifica límites de uso, políticas de
  retención de datos, configuración de Meta y las cuotas del proveedor de IA.
- El flujo de facturación requiere configurar `FACTURACION_API_URL`,
  `FACTURACION_API_KEY`, `FACTURACION_NUMEROS_AUTORIZADOS` y
  `AGENT_BRIDGE_TOKEN`. Fuera de localhost, usa HTTPS. La API fiscal debe usar
  autenticación propia, persistir auditoría/origen e implementar idempotencia.
- La emisión depende del botón firmado por Meta, no de una respuesta del modelo.
  La cola local es durable pero no distribuida. Para varias réplicas se requiere
  Redis/base de datos compartida, una cola de trabajos y almacenamiento
  persistente de XML, respuestas DGII y auditoría.
- No habilites la API simulada en producción. Antes de emitir comprobantes reales
  faltan proveedor/motor fiscal, certificado digital, integración y pruebas en
  `testecf` y `certecf`, y certificación vigente como emisor electrónico.

## Verificación realizada

- `npm test` dentro de `puente_whatsapp`: 10 pruebas pasaron, incluidas las de
  persistencia, recuperación y reintentos de la cola.
- `python -m unittest discover -s tests`: 24 pruebas pasaron, incluidas
  persistencia, healthcheck, autenticación puente y verificación del respaldo.
- `node --check` pasó para el servidor, el cliente y el service worker.
- Para las pruebas de persistencia, cola durable, respaldo, reinicio y healthcheck,
  consulta el [informe de continuidad operativa](./informe_continuidad_operativa.md).
- Se comprobó la interfaz en navegador con ancho móvil: muestra la lista
  numerada, no expone una dirección local como enlace para compartir y el
  service worker queda activo.
- No se escaneó un QR real: para generarlo se necesita configurar
  `WHATSAPP_PUBLIC_NUMBER`.
- Publicación, URL HTTPS, instalación en dispositivos físicos y webhook:
  pendientes de cuenta de alojamiento, credenciales, número de WhatsApp y
  configuración de Meta.
