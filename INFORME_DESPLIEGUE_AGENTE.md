# Informe: propuesta para desplegar el agente en un servidor

## Resumen ejecutivo

El agente actual se inicia desde la terminal y mantiene el estado de una
conversación dentro de una instancia de `Agente`. Para atender a varias personas
desde Internet, se recomienda exponerlo como un servicio web: una API recibe los
mensajes, una interfaz de chat permite a los clientes conversar y cada
conversación conserva su propio historial y estado.

La recomendación es avanzar por etapas y comenzar con una sola instancia del
servicio. Antes de ejecutar varias instancias, conviene trasladar las sesiones y
los pedidos a una base de datos compartida.

## Situación actual

- `main.py` inicia una conversación interactiva en la terminal.
- `conversacion.py` utiliza `input()` y `print()` para el intercambio de mensajes.
- `agente.py` guarda el historial y el estado del flujo de pedidos en memoria
  dentro de cada objeto `Agente`.
- `datos.py` registra y actualiza pedidos en un archivo Excel, con sincronización
  entre operaciones concurrentes dentro del proceso.
- El agente requiere `GROQ_API_KEY` para comunicarse con el proveedor del modelo.

El modo de terminal es apropiado para uso local, pero no proporciona por sí solo
una entrada web, aislamiento de sesiones entre visitantes ni almacenamiento
compartido para un despliegue escalable.

## Arquitectura propuesta

```text
Navegador del cliente
        |
        | HTTPS
        v
Proxy inverso / balanceador
        |
        v
API web (FastAPI)
        |
        +---- Agente existente ---- API de Groq
        |
        +---- PostgreSQL: sesiones y pedidos
```

La interfaz web puede servirse desde la misma aplicación en una primera etapa.
La API recibe cada mensaje junto con el identificador de conversación y devuelve
la respuesta del agente. Cada petición debe recuperar y actualizar solamente el
estado de esa conversación.

## Componentes recomendados

| Componente | Responsabilidad |
| --- | --- |
| API web | Recibir mensajes, validar solicitudes y coordinar el agente. |
| Interfaz de chat | Permitir que cada cliente converse desde un navegador. |
| Gestión de sesiones | Aislar historial y estado de pedidos por conversación. |
| PostgreSQL | Persistir sesiones y pedidos y permitir compartirlos entre procesos. |
| Docker | Empaquetar la aplicación y sus dependencias de forma reproducible. |
| Proxy inverso con HTTPS | Proteger el tráfico y publicar el servicio de forma segura. |
| Variables secretas del servidor | Proveer `GROQ_API_KEY` sin incorporarla al repositorio. |

## Plan de implementación por etapas

1. **Separar la lógica de entrada:** conservar la terminal y añadir una API que
   invoque el agente sin depender de `input()` o `print()`.
2. **Crear sesiones aisladas:** generar identificadores impredecibles y mantener
   un agente o contexto independiente por cliente.
3. **Añadir una interfaz web:** incluir un chat sencillo conectado a la API.
4. **Persistir datos:** migrar pedidos del Excel a PostgreSQL y guardar allí el
   historial y los datos necesarios para retomar las conversaciones.
5. **Empaquetar y desplegar:** usar Docker y configurar la clave de Groq como
   secreto en el entorno del servidor.
6. **Publicar y observar:** configurar HTTPS, registros operativos sin
   credenciales ni datos sensibles, monitoreo y límites de solicitudes.
7. **Escalar cuando sea necesario:** ejecutar más de una instancia una vez que
   el estado no dependa de la memoria o del disco local de un contenedor.

## Riesgos y decisiones importantes

- **Mezcla de conversaciones:** compartir un único objeto de agente entre
  visitantes podría mezclar historiales y estados de pedidos. La API debe aislar
  cada sesión.
- **Reinicios del servicio:** las sesiones guardadas solo en memoria se pierden
  al reiniciar. Para retomar conversaciones, deben persistirse.
- **Escrituras concurrentes:** el Excel actual no es una buena fuente de verdad
  para varios procesos o solicitudes simultáneas. PostgreSQL es preferible para
  pedidos y estados operativos.
- **Escalado horizontal:** una sesión guardada solo en una instancia puede no
  estar disponible si la siguiente petición llega a otra instancia.
- **Exposición de credenciales:** `GROQ_API_KEY` debe configurarse en el
  proveedor del servidor y nunca enviarse al navegador ni guardarse en Git.
- **Exposición pública:** antes de publicar, se deben usar HTTPS, límites de
  solicitudes y validación de entradas. También hay que definir cuánto tiempo se
  conservan los historiales y quién puede consultar los pedidos.

## Recomendación final

Para una primera versión, desplegar una API web y un chat detrás de HTTPS en una
sola instancia, con sesiones aisladas. Si el uso será real o habrá varios
clientes simultáneos, priorizar desde el inicio la migración de pedidos y
sesiones a PostgreSQL. Mantener el Excel como medio de exportación o reporte,
no como almacenamiento compartido de producción.

Este informe es una propuesta arquitectónica; no implementa ni configura el
despliegue.
