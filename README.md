<div align="center">

[![Banner del proyecto](https://github.com/rosaura01/Hub/blob/master/.github/banner.png)](https://github.com/rosaura01/Hub)

[![Release version](https://img.shields.io/github/v/release/rosaura01/Hub?color=brightgreen&label=Latest&style=for-the-badge)](https://github.com/rosaura01/Hub/releases/latest "Latest release") [![Python Version](https://img.shields.io/badge/PYTHON-%E2%89%A5_1.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://github.com/rosaura01/Hub/raw/master/apps/api/pyproject.toml "Python Version") [![Node.js Version](https://img.shields.io/badge/NODE-%E2%89%A5_20-339933?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://github.com/rosaura01/Hub "Node.js Version") [![License: Unlicense](https://img.shields.io/badge/-unlicense-red.svg?style=for-the-badge)](LICENSE "License") [![Commits](https://img.shields.io/badge/COMMITS-Activo-brightgreen?style=for-the-badge)](https://github.com/rosaura01/Hub/commits "Commit History")

</div>

Plataforma de herramientas independientes conectadas mediante un sistema de plugins. Incluye el núcleo, un plugin core de YouTube y la infraestructura común de tareas y archivos.

## Estado

- Etapa 1 (arquitectura): `docs/architecture.md`.
- Interfaz gráfica inicial + API de lectura/administración + registro de plugins: implementados y probados.
- Pendiente: ver `docs/status.md`.

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
| --- | --- | --- |
| `HUB_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Hosts aceptados por la API (protección contra DNS rebinding). |
| `HUB_OUTPUT_ROOTS` | *(vacío)* | Carpetas extra permitidas para descargas, separadas por `;` en Windows o `:` en Linux/macOS. Por defecto solo se permiten rutas dentro de tu carpeta de usuario y de `data/`. |
| `HUB_CORS_ORIGINS` | `http://localhost:5173` | Orígenes permitidos por CORS. |

## Tests

```bash
cd apps/api && pytest && ruff check .
```

```bash
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```

## Estructura

`apps/web` (React + Vite + Tailwind) · `apps/api` (FastAPI + SQLAlchemy) · `packages/contracts` (JSON Schema/OpenAPI generados) · `plugins/` (vacía) · `docs/`.

Regenerar contratos: `python scripts/export_contracts.py`.
