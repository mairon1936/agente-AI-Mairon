from pathlib import Path

from agente import Agente
from conversacion import iniciar_conversacion


def main() -> None:
	"""Punto de entrada de la aplicacion."""
	prompt = Path(__file__).with_name("SISTEM_PROMPTS.md").read_text(encoding="utf-8")
	agente = Agente(prompt)
	iniciar_conversacion(agente)


if __name__ == "__main__":
	main()

