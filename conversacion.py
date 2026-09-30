from agente import Agente


def iniciar_conversacion(agente: Agente) -> None:
    print(f"¡Bienvenido a {agente.nombre_negocio}! Escribe 'sali' para terminar.")

    while True:
        mensaje = input("Tú: ").strip()
        if mensaje.lower() == "sali":
            break

        respuesta = agente.responder(mensaje)
        print(f"{agente.nombre_negocio}: {respuesta}")

    agente.mostrar_historiar()