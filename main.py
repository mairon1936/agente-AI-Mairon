import sys

from agente_facturacion import AgenteFacturacionElectronica
from conversacion import iniciar_conversacion


def main() -> None:
	"""Punto de entrada de la aplicacion."""
	sys.stdout.reconfigure(encoding="utf-8")
	sys.stderr.reconfigure(encoding="utf-8")
	agente = AgenteFacturacionElectronica()
	iniciar_conversacion(agente)


if __name__ == "__main__":
	
	main()
