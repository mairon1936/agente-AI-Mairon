import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parent
WEB_URL = "http://localhost:3000"


def is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def wait_until_ready(name: str, url: str, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                f"El servidor {name} terminó con código {exit_code}. "
                "Revisa los mensajes de la terminal."
            )
        if is_ready(url):
            return
        time.sleep(0.5)
    raise RuntimeError(f"El servidor {name} no respondió en {url}.")


def stop_started_servers(processes: list[subprocess.Popen[bytes]]) -> None:
    for process in reversed(processes):
        if process.poll() is None:
            process.terminate()
    for process in reversed(processes):
        if process.poll() is None:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()


def start_server(
    name: str,
    command: list[str],
    cwd: Path,
    health_url: str,
    processes: list[subprocess.Popen[bytes]],
) -> None:
    if is_ready(health_url):
        print(f"{name} ya está activo.")
        return

    process = subprocess.Popen(command, cwd=cwd)
    processes.append(process)
    wait_until_ready(name, health_url, process)
    print(f"{name} está listo.")


def main() -> None:
    virtualenv_python = (
        ROOT / ".venv" / "Scripts" / "python.exe"
        if os.name == "nt"
        else ROOT / ".venv" / "bin" / "python"
    )
    node = shutil.which("node")
    bridge_directory = ROOT / "puente_whatsapp"

    if not virtualenv_python.is_file():
        raise FileNotFoundError(
            "No se encontró el Python del entorno .venv. "
            "Desde la raíz del proyecto, ejecuta: uv sync"
        )
    if not node:
        raise FileNotFoundError(
            "No se encontró Node.js. Instala Node.js 20 o posterior y vuelve a intentarlo."
        )
    if not (bridge_directory / "node_modules").is_dir():
        raise FileNotFoundError(
            "Faltan dependencias web. Ejecuta 'npm install' dentro de puente_whatsapp."
        )

    processes: list[subprocess.Popen[bytes]] = []
    try:
        start_server(
            "El servicio de la API Python",
            [
                str(virtualenv_python),
                "-m",
                "uvicorn",
                "servidor:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            ROOT,
            "http://127.0.0.1:8000/salud",
            processes,
        )
        start_server(
            "El servicio web",
            [node, "server.js"],
            bridge_directory,
            f"{WEB_URL}/health",
            processes,
        )
        print(f"Abriendo {WEB_URL}")
        if not webbrowser.open(WEB_URL):
            print(f"No se pudo abrir el navegador automáticamente. Visita {WEB_URL}")
        if processes:
            print("Presiona Ctrl+C para detener los servidores iniciados por este programa.")
        else:
            print("Los servicios ya estaban activos; no se detendrán al cerrar este programa.")
        while any(process.poll() is None for process in processes):
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nCerrando los servidores iniciados por este programa...")
    finally:
        stop_started_servers(processes)


if __name__ == "__main__":
    main()
