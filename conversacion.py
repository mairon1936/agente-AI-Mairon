from agente_facturacion import AgenteFacturacionElectronica
from sistem_prompts import MENSAJE_BIENVENIDA


def iniciar_conversacion(agente: AgenteFacturacionElectronica) -> None:
    print(f"*{MENSAJE_BIENVENIDA}*")
    print(
        "Opciones de consulta:\n"
        "1. Información general sobre facturación electrónica\n"
        "2. Información disponible del sistema\n"
        "3. Consultar qué información oficial está pendiente\n"
        "Escribe un número, haz tu pregunta o escribe 'salir' para terminar."
    )

    try:
        while True:
            try:
                mensaje = input("Tú: ").strip()
            except EOFError:
                print("\nLa terminal no tiene entrada interactiva disponible. Saliendo...")
                break

            if mensaje.lower() == "salir":
                break

            respuesta = agente.responder(mensaje)
            print(f"{agente.nombre_negocio}: {respuesta}")
    except KeyboardInterrupt:
        print("\nInterrupción de la terminal. Saliendo...")
    finally:
        agente.mostrar_historiar()