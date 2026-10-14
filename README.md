# AI-mairon

Asistente de Café Santo Domingo. Los módulos de la aplicación no almacenan los
datos del negocio: `datos.py` los carga desde sus archivos fuente y los entrega
al agente y a las herramientas.

## Estructura de datos

- `datos.py`: información base del negocio y catálogo de productos empacados
  en `DATOS_NEGOCIO`, además de la carga y normalización del Excel.
- `datos/datos_negocio_cafe_santo_domingo.xlsx`: menú de cafetería y detalles
  complementarios. La hoja `productos` debe incluir `producto`, `precio` y
  `categoria`; la hoja `informacion` debe incluir `tema` y `detalle`.
- `agente.py`: conversación con el modelo.
- `tools.py`: definición y despacho de herramientas del agente y cotización.
- `pedidos.py`: registro de solicitudes en `datos/pedidos.xlsx`.

Para actualizar productos, precios, servicios o contactos que provienen del
Excel, edita el libro dentro de `datos/`. Para actualizar la información base o
el catálogo de productos empacados, edita `DATOS_NEGOCIO` en `datos.py`.
`cargar_datos_negocio()` combina ambas fuentes; los precios de referencia del
menú no se consideran tarifas confirmadas.

## Ejecución

Desde la raíz del proyecto, sincroniza las dependencias y ejecuta la aplicación
con el entorno administrado por `uv`:

```powershell
uv sync
uv run main.py
```

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
