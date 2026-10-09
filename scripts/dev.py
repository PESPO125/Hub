"""Start the Hub API and web development server from one terminal."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
WEB_DIR = ROOT / "apps" / "web"


def _python() -> str:
    candidates = (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    )
    return str(next((path for path in candidates if path.is_file()), Path(sys.executable)))


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _hub_is_running(api_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{api_url}/api/v1/app/info", timeout=0.5) as response:
            return json.load(response).get("name") == "Hub"
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return False


def _wait_for_api(api_url: str, process: subprocess.Popen, timeout: float = 15) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _hub_is_running(api_url):
            return True
        if process.poll() is not None:
            return False
        time.sleep(0.2)
    return False


def main() -> int:
    node = shutil.which("node")
    vite = WEB_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    if not node or not vite.is_file():
        print("Falta Node.js o apps/web/node_modules. Ejecuta npm install dentro de apps/web.")
        return 1

    api_port = os.environ.get("HUB_API_PORT", "8000")
    web_port = os.environ.get("HUB_WEB_PORT", "5173")
    api_url = f"http://127.0.0.1:{api_port}"
    api_command = [
        _python(), "-m", "uvicorn", "app.main:app",
        "--app-dir", str(API_DIR), "--host", "127.0.0.1", "--port", api_port,
    ]
    web_command = [node, str(vite), "--host", "127.0.0.1", "--port", web_port, "--strictPort"]
    web_environment = os.environ.copy()
    web_environment.setdefault("VITE_API_PROXY", f"http://127.0.0.1:{api_port}")
    processes: list[tuple[str, subprocess.Popen]] = []
    try:
        if _hub_is_running(api_url):
            print(f"API Hub ya activo en {api_url}; se reutiliza.")
        else:
            api_process = subprocess.Popen(api_command, cwd=ROOT)
            processes.append(("API", api_process))
            if not _wait_for_api(api_url, api_process):
                print(f"No se pudo iniciar Hub API en {api_url}; revisa si el puerto está ocupado.")
                return 1
        processes.append(("Web", subprocess.Popen(web_command, cwd=WEB_DIR, env=web_environment)))
        print(f"Hub API: {api_url}")
        print(f"Hub Web: http://127.0.0.1:{web_port}")
        print("Presiona Ctrl+C para detener ambos servidores.")

        while True:
            for name, process in processes:
                result = process.poll()
                if result is not None:
                    print(f"El servidor {name} terminó con código {result}.")
                    return result or 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\nDeteniendo Hub...")
        return 0
    finally:
        for _, process in reversed(processes):
            _stop(process)


if __name__ == "__main__":
    raise SystemExit(main())