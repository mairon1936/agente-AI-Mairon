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
        "7. Ver menú de cafetería\n"
        "8. Realizar un pedido\n"
        "9. Solicitar delivery\n"
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