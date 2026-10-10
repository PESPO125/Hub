# Hub

Plataforma de herramientas independientes (microapps) con sistema de plugins. Esta versión contiene **solo el núcleo**: interfaz, API, registro de plugins, tareas, archivos y configuración.

## Estado
- Etapa 1 (arquitectura): `docs/architecture.md`.
- Interfaz gráfica inicial + API de lectura/administración + registro de plugins: implementados y probados.
- Pendiente: ver `docs/status.md`.

## Aviso legal y de uso

Hub es un proyecto personal, pensado para **uso local y personal**. Se ofrece "tal cual", sin garantías de ningún tipo.

- El plugin de YouTube usa [yt-dlp](https://github.com/yt-dlp/yt-dlp). Descargar contenido de YouTube puede incumplir sus Términos del Servicio o las leyes de derechos de autor de tu país. **Eres el único responsable del uso que le des**: descarga solo contenido propio, de dominio público o para el que tengas permiso.
- Los autores no se hacen responsables del mal uso de esta herramienta ni de los daños que pueda causar.
- La API no tiene autenticación y escucha solo en `127.0.0.1`. **No la expongas a internet ni a tu red local.**
- Los plugins de terceros se ejecutan con los permisos de tu usuario. Instala solo plugins en los que confíes.

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
