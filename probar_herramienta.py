from tools import ejecutar_herramientas


def main() -> None:
    for deliveri in ("Delivery", "Retiro"):
        resultado = ejecutar_herramientas(
            "registrar_solicitud",
            {
                "solicitud": "pedido de prueba",
                "deliveri": deliveri,
            },
            "cliente_prueba",
        )
        print(f"ejecutar_herramientas ({deliveri}): {resultado}")


if __name__ == "__main__":
    main()
