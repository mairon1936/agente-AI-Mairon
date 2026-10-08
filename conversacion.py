from agente import Agente


def iniciar_conversacion(agente: Agente) -> None:
    print(f"¡Hola! Te damos la bienvenida a {agente.nombre_negocio}.")
    print(
        "Menú de atención:\n"
        "1. Ver productos y presentaciones\n"
        "2. Consultar precios\n"
        "3. Recibir una recomendación de café\n"
        "4. Consultar sucursales y teléfonos\n"
        "5. Consultar servicios para oficinas o eventos\n"
        "6. Redactar una sugerencia\n"
        "Escribe un número, haz tu pregunta o escribe 'sali' para terminar."
    )

    while True:
        mensaje = input("Tú: ").strip()
        if mensaje.lower() == "sali":
            break

        respuesta = agente.responder(mensaje)
        print(f"{agente.nombre_negocio}: {respuesta}")

    agente.mostrar_historiar()