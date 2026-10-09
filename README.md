# Hub — Plataforma modular de microapps

Plataforma de herramientas independientes (microapps) con sistema de plugins. Esta versión contiene **solo el núcleo**: interfaz, API, registro de plugins, tareas, archivos y configuración. **No incluye ninguna microapp.**

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

## Ejecutar (dos terminales)
```bash
# 1) API  -> http://127.0.0.1:8000  (docs: /api/v1/docs)
cd apps/api && uvicorn app.main:app --host 127.0.0.1 --port 8000
# 2) Web  -> http://localhost:5173  (proxy de /api hacia el backend)
cd apps/web && npm run dev
```

## Pruebas y calidad
```bash
cd apps/api && pytest && ruff check .
cd apps/web && npm run typecheck && npm run lint && npm test && npm run build
```

## Variables de entorno (prefijo `HUB_`)
Ver `.env.example`. Las rutas relativas se resuelven desde la raíz del repo, no desde el directorio de arranque.

## Estructura
`apps/web` (React + Vite + Tailwind) · `apps/api` (FastAPI + SQLAlchemy) · `packages/contracts` (JSON Schema/OpenAPI generados) · `plugins/` (vacía) · `docs/`.
Regenerar contratos: `python scripts/export_contracts.py`.
