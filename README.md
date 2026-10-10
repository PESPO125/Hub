# Hub
=======

<!-- Reemplaza esta URL con el enlace raw de tu propio banner/imagen -->
<a href="#readme">
  <img src="https://github.com/PESPO125/Hub/raw/readme/.github/banner.png" alt="Banner del proyecto">
</a>

<!-- Insignia de última versión (ajusta tu usuario y repositorio) -->
[![Release version](https://img.shields.io/github/v/release/PESPO125/Hub?color=brightgreen&label=Latest&style=for-the-badge)](#installation "Installation")

<!-- Insignia de versión de Python (lee el archivo pyproject.toml de tu repo) -->
[![Python Version](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2FTU-USUARIO%2FTU-REPOSITORIO%2Frefs%2Fheads%2Fmaster%2Fpyproject.toml&style=for-the-badge)](https://github.com/PESPO125/Hub/blob/main/apps/api/pyproject.toml "Python Version")

<!-- Insignia de Licencia -->
[![License: Unlicense](https://img.shields.io/badge/-Unlicense-red.svg?style=for-the-badge)](LICENSE "License")

<!-- Insignia de actividad de commits -->
[![Commits](https://github.com/PESPO125/Hub/activity?label=commits&style=for-the-badge)](https://github.com/PESPO125/Hub/commits "Commit History")

</div>


Plataforma de herramientas independientes (microapps) con sistema de plugins. Incluye el núcleo, un plugin core de YouTube y la infraestructura común de tareas y archivos.
>>>>>>> parent of 9a4f47f (Edited: README.md)

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

## Configuración (variables de entorno, prefijo `HUB_`)
| Variable | Por defecto | Descripción |
|---|---|---|
| `HUB_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Hosts aceptados por la API (protección contra DNS rebinding). |
| `HUB_OUTPUT_ROOTS` | *(vacío)* | Carpetas extra permitidas para descargas, separadas por `;` en Windows o `:` en Linux/macOS. Por defecto solo se permiten rutas dentro de tu carpeta de usuario y de `data/`. |
| `HUB_CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos por CORS. |

## Tests
```bash
cd apps/api && pytest && ruff check .
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```

## Estructura
`apps/web` (React + Vite + Tailwind) · `apps/api` (FastAPI + SQLAlchemy) · `packages/contracts` (JSON Schema/OpenAPI generados) · `plugins/` (vacía) · `docs/`.
Regenerar contratos: `python scripts/export_contracts.py`.

## Licencia
[MIT](LICENSE)
