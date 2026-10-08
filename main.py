from agente import Agente
from conversacion import iniciar_conversacion
from sistem_prompts import SYSTEM_PROMPT


def main() -> None:
	"""Punto de entrada de la aplicacion."""
	agente = Agente(SYSTEM_PROMPT)
	iniciar_conversacion(agente)


if __name__ == "__main__":
	main()
