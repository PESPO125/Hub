# Estado y limitaciones conocidas

## Implementado y verificado
- API `/api/v1`: health, ready, app/info, diagnostics, plugins (listar, detalle, refrescar, habilitar/deshabilitar), catálogo (búsqueda, categoría, favoritos), tareas (listar, cancelar), archivos (listar), configuración (tema), favoritos.
- Registro de plugins: validación estricta, duplicados, incompatibilidad, symlinks/traversal, límite de tamaño, aislamiento de errores, sin ejecución de código.
- Interfaz: sidebar colapsable, topbar con buscador (`/` o Ctrl/⌘K) e indicador de tareas, inicio, catálogo, favoritos, detalle de plugin, tareas (polling adaptativo), archivos, configuración (tema, administración de plugins, sistema), tema claro/oscuro/sistema, estados vacío/carga/error, diálogos de confirmación.

## Pendiente (no simulado)
- **Runner de plugins y ejecución de tareas**: no hay `TaskExecutor` ni forma de crear tareas; la UI no ofrece botones de ejecutar.
- **Descarga de archivos** y almacenamiento (`FileStorage`): solo existe el listado y el modelo.
- **Migraciones Alembic**: hoy se usa `create_all`. Debe reemplazarse antes de cualquier uso real.
- **Control de acceso**: no hay `ADMIN_TOKEN`; la API asume uso local en 127.0.0.1. No exponer a la red.
- **Tipos TS**: escritos a mano (`apps/web/src/types/api.ts`); falta tipar las respuestas con `response_model` y generarlos desde OpenAPI.
- Docker/Compose, instalación/actualización/desinstalación de plugins, pruebas de accesibilidad automatizadas, pruebas visuales en navegador real.
