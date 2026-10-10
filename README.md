<div align="center">

# Hub
[![HUB](https://raw.githubusercontent.com/PESPO125/Hub/refs/heads/main/.github/banner.svg)](#readme)

</div>


<div align="center">

<!-- Reemplaza esta URL con el enlace raw de tu propio banner/imagen -->
<a href="#readme">
  <img src="https://raw.githubusercontent.com/TU-USUARIO/TU-REPOSITORIO/master/.github/banner.svg" alt="Banner del proyecto">
</a>

<!-- Insignia de última versión (ajusta tu usuario y repositorio) -->
[![Release version](https://img.shields.io/github/v/release/TU-USUARIO/TU-REPOSITORIO?color=brightgreen&label=Latest&style=for-the-badge)](#installation "Installation")

<!-- Insignia de versión de Python (lee el archivo pyproject.toml de tu repo) -->
[![Python Version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FTU-USUARIO%2FTU-REPOSITORIO%2Frefs%2Fheads%2Fmaster%2Fpyproject.toml&style=for-the-badge)](https://github.com/TU-USUARIO/TU-REPOSITORIO/blob/master/pyproject.toml "Python Version")

<!-- Insignia de PyPI (si subiste tu paquete a PyPI, cambia "yt-dlp" por el nombre de tu paquete) -->
[![PyPI](https://img.shields.io/badge/-PyPI-blue.svg?logo=pypi&labelColor=555555&style=for-the-badge)](https://pypi.org/project/TU-PAQUETE-PYPI "PyPI")

<!-- Insignia de Discord (reemplaza el enlace por el de tu invitación de Discord) -->
[![Discord](https://img.shields.io/badge/Discord-%235865F2.svg?&logo=discord&logoColor=white&style=for-the-badge)](https://discord.gg/TU-INVITACION-DISCORD "Discord")

<!-- Insignia de Licencia -->
[![License: Unlicense](https://img.shields.io/badge/-Unlicense-red.svg?style=for-the-badge)](LICENSE "License")

<!-- Insignia de actividad de commits -->
[![Commits](https://img.shields.io/github/commit-activity/m/TU-USUARIO/TU-REPOSITORIO?label=commits&style=for-the-badge)](https://github.com/TU-USUARIO/TU-REPOSITORIO/commits "Commit History")

</div>


Plataforma de herramientas independientes (microapps) con sistema de plugins. Incluye el núcleo, un plugin core de YouTube y la infraestructura común de tareas y archivos.

## Estado
- Etapa 1 (arquitectura): `docs/architecture.md`.
- Interfaz gráfica inicial + API de lectura/administración + registro de plugins: implementados y probados.
- Pendiente: ver `docs/status.md`.

## Requisitos
Python ≥ 3.11 y Node ≥ 20.

## Instalación
```bash
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e "apps/api[dev]"
# Frontend
cd apps/web && npm install
```

## Ejecutar en desarrollo (en terminal)
```bash
python scripts/dev.py
```
Inicia la API en `http://127.0.0.1:8000` y la web en `http://127.0.0.1:5173`. Si ya hay una API Hub activa, la reutiliza. `Ctrl+C` detiene los procesos que inició el script.
Si esos puertos están ocupados, puedes cambiarlos con `HUB_API_PORT` y `HUB_WEB_PORT`.

## Configuración
Edita [`hub.toml`](hub.toml) en la raíz del proyecto para cambiar la versión que muestra Hub y los valores predeterminados del backend (`env`, `database_url`, `plugins_dir`, `data_dir`, `allow_untrusted_plugins`, `cors_origins` y `task_workers`). Las variables de entorno `HUB_*` prevalecen sobre el archivo. Si cambias `version`, regenera también OpenAPI con `python scripts/export_contracts.py`.

## Tests
```bash
cd apps/api && pytest && ruff check .
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```

## Estructura
`apps/web` (React + Vite + Tailwind) · `apps/api` (FastAPI + SQLAlchemy) · `packages/contracts` (JSON Schema/OpenAPI generados) · `plugins/youtube-dl` (plugin core de ejemplo) · `docs/`.
Regenerar contratos: `python scripts/export_contracts.py`.
