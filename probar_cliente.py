from dotenv import load_dotenv

from cliente import definir_agente

load_dotenv()

maria, _ = definir_agente("maria")
maria_otra_vez, _ = definir_agente("maria")
pedro, _ = definir_agente("pedro")

print(maria is maria_otra_vez)
print(maria is pedro)
