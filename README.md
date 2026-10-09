# Hub — Plataforma modular de microapps

Plataforma de herramientas independientes (microapps) con sistema de plugins. Esta versión contiene **solo el núcleo**: interfaz, API, registro de plugins, tareas, archivos y configuración.

## Estado
- Etapa 1 (arquitectura): `docs/architecture.md`.
- Interfaz gráfica inicial + API de lectura/administración + registro de plugins: implementados y probados.
- Pendiente: ver `docs/status.md`.

## Requisitos
Python ≥ 3.11 y Node ≥ 20.

## Instalación
```bash
cp .env.example .env
# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e "apps/api[dev]"
# Frontend
cd apps/web && npm install
```

## Ejecutar en desarrollo (una terminal)
```bash
python scripts/dev.py
```
Inicia la API en `http://127.0.0.1:8000` y la web en `http://127.0.0.1:5173`. Si ya hay una API Hub activa, la reutiliza. `Ctrl+C` detiene los procesos que inició el script.
Si esos puertos están ocupados, puedes cambiarlos con `HUB_API_PORT` y `HUB_WEB_PORT`.

## Pruebas y calidad
```bash
cd apps/api && pytest && ruff check .
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```

## Variables de entorno (prefijo `HUB_`)
Ver `.env`. Las rutas relativas se resuelven desde la raíz del repo, no desde el directorio de arranque.

## Estructura
`apps/web` (React + Vite + Tailwind) · `apps/api` (FastAPI + SQLAlchemy) · `packages/contracts` (JSON Schema/OpenAPI generados) · `plugins/` (vacía) · `docs/`.
Regenerar contratos: `python scripts/export_contracts.py`.
