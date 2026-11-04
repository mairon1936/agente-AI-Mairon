# Informe de continuidad operativa

## Alcance

Se aplicaron al proyecto las medidas de persistencia, recuperación,
supervisión y respaldo solicitadas. Esto prepara una instalación de un solo
servidor; no equivale a un despliegue público y no garantiza disponibilidad
ininterrumpida. Docker no está instalado en el entorno de desarrollo, por lo
que aquí no fue posible construir ni arrancar los contenedores.

## 1. Conversaciones, sesiones y borradores persistentes

- `facturacion/almacen.py` añade un almacén SQLite con modo WAL, espera ante
  contención y confirmación síncrona de escrituras.
- Se persisten los historiales de chat web/WhatsApp, el historial fiscal, los
  clientes y productos verificados y los borradores pendientes.
- Los borradores mantienen una expiración de 30 minutos, incluso tras reinicios.
  Los historiales se purgan tras 90 días sin actividad por defecto; configura
  `AGENT_SESSION_RETENTION_DAYS` para cambiar esa retención.
- `/salud` comprueba la integridad del almacén antes de responder.
- El archivo de SQLite se configura con `AGENT_DATABASE_PATH`; de forma local
  se guarda en `data/agent.sqlite3`. En Compose está en el volumen persistente
  `agent-data`.
- La confirmación de factura conserva su clave de idempotencia existente y el
  resultado de emisión se guarda antes de entregar el PDF.

SQLite está configurado aquí para una sola instancia de la API. Compose usa un
worker Uvicorn y un puente Node; no escales estos servicios a varias réplicas
sin migrar primero las sesiones a un almacén compartido con bloqueo y la cola
a un servicio distribuido.

## 2. Cola durable y recuperación de WhatsApp

- `puente_whatsapp/durable-queue.js` guarda los eventos verificados por Meta en
  `data/bridge/whatsapp-queue` antes de contestar HTTP 200 al webhook. Si no
  puede persistirlos, devuelve HTTP 503 para permitir el reintento de Meta.
- Al reiniciar, los mensajes que estaban en procesamiento vuelven a pendientes.
  Los errores transitorios se reintentan hasta cinco intentos con espera
  exponencial; los eventos agotados quedan en `failed` para revisión.
- Se conservan siete días los eventos completados y fallidos para reconocer
  reintentos de Meta.
- `/health/ready` verifica el almacén del puente y la API Python. `/health` es
  una comprobación básica de vida.
- El procesamiento es **al menos una vez**: si el proceso cae después de que
  WhatsApp acepte una respuesta pero antes de archivar el evento, podría volver
  a procesarse y enviar una respuesta repetida. La emisión fiscal mantiene su
  idempotencia existente.

## 3. Reinicio, salud y supervisión

`compose.yaml` define contenedores separados para Python y Node, con:

- `restart: unless-stopped`, para recuperar un proceso que termine.
- Comprobaciones de salud para la API y el puente; el puente además comprueba
  `/salud` en la API.
- El servidor Python no publica un puerto en el host; solo el puente lo alcanza
  por la red interna de Compose.
- Usuarios sin privilegios, sistemas de archivos de contenedor de solo lectura,
  permisos `no-new-privileges` y montaje persistente solo para los datos.
- El token `AGENT_BRIDGE_TOKEN` y `GROQ_API_KEY` son requeridos por el despliegue
  Compose. La clave puente se valida también cuando la integración fiscal está
  desactivada.

Un contenedor que siga ejecutándose pero esté `unhealthy` **no se reinicia
automáticamente por Docker**. Configura un monitor externo para revisar
`https://<dominio>/health/ready`, generar alertas y activar el procedimiento de
recuperación del proveedor. Vigila también `docker compose ps` y los registros.
Una comprobación local no sustituye un monitor desde fuera del servidor.

## 4. Secretos, permisos y respaldos

- `.env`, `data/` y `backups/` están excluidos de Git; ambos contextos Docker
  excluyen `.env`, datos locales y dependencias.
- Compose inyecta a cada servicio solo las variables que necesita. No copia
  `.env` a las imágenes.
- En Linux, SQLite queda con permisos `0600`, sus directorios y los archivos de
  cola con `0700`/`0600`. En Windows, restringe el acceso mediante ACL. En
  producción guarda secretos en el gestor de secretos del proveedor, no en
  Git, capturas, informes o logs.
- `facturacion/backup.py` usa la API de respaldo online de SQLite y verifica
  `integrity_check`; también archiva la cola durable. Rota respaldos locales
  después de 30 días.
- Para un respaldo manual con Docker, ejecuta:

  ```powershell
  docker compose run --rm backup
  ```

- Programa esa orden diariamente en el Programador de tareas de Windows
  ejecutando `powershell.exe` con los argumentos
  `-NoProfile -ExecutionPolicy Bypass -File "<ruta-del-proyecto>\scripts\backup.ps1"`.
  En Linux, crea un cron diario para
  `cd <ruta-del-proyecto> && sh scripts/backup.sh`. El usuario del servicio debe
  poder escribir en `backups/`.
- Los respaldos contienen conversaciones y pueden incluir datos personales.
  Almacénalos en disco cifrado, limita quién puede leerlos y copia otra versión
  cifrada fuera del servidor. La rotación local no protege contra pérdida del
  disco o de la cuenta del servidor.

### Recuperación

Prueba periódicamente la restauración en un entorno aislado. Detén ambos
servicios antes de restaurar para evitar escrituras concurrentes. Recupera
`agent.sqlite3` desde el directorio fechado `backups/respaldo-*` y, si hace
falta recuperar eventos en cola, extrae `whatsapp-queue.tar.gz` bajo la ruta
`data/bridge/`. Inicia primero `agent` y luego `bridge`; sus comprobaciones de
salud deben volver a estar listas. No restaures un respaldo de un origen no
confiable.

## 5. Puesta en marcha con Docker

En un host con Docker Compose, crea `.env` sin sobrescribir uno existente,
completa `GROQ_API_KEY` y genera un token de puente aleatorio (guárdalo
directamente en el gestor de secretos o en `.env`; no lo pegues en el chat):

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
uv run python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Configura además las credenciales de WhatsApp Cloud API para habilitar las
respuestas automáticas. Publica el puerto web únicamente detrás de un proxy o
proveedor con HTTPS y registra el webhook de Meta en
`https://<dominio>/webhook`.

Desde la raíz del proyecto:

```powershell
docker compose up --build -d
docker compose ps
Invoke-RestMethod http://localhost:3000/health/ready
docker compose logs --tail 100 agent bridge
```

Para detener: `docker compose down` (conserva el volumen de datos). No uses
`docker compose down -v` salvo que quieras eliminar deliberadamente la base de
datos y la cola.

## Validación efectuada

- `python -m unittest discover -s tests`: 24 pruebas Python pasan, incluidas
  persistencia después de reiniciar el almacén, expiración de borrador, control
  de token y lectura/verificación del respaldo.
- `npm test` en `puente_whatsapp`: 10 pruebas pasan, incluidas persistencia de
  eventos, deduplicación, recuperación tras interrupción y reintento.
- Pylance y `node --check` validaron los archivos principales.
- `docker compose config` y el build de imágenes no se pudieron ejecutar: el
  comando Docker no está instalado en este equipo.

## Límites pendientes

Una sola máquina, región, volumen, instancia de cada servicio y proveedor de IA
siguen siendo puntos únicos de falla. La disponibilidad real depende de
alojamiento, energía, DNS/HTTPS, Meta, el proveedor del modelo, cuotas y
restauraciones probadas. Para alta disponibilidad con varias réplicas se
requieren base de datos y cola administradas/compartidas, más despliegue
redundante y pruebas de carga/recuperación.
