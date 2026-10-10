# Estado y limitaciones conocidas

## Implementado y verificado
- API `/api/v1`: health, ready, app/info, diagnostics, plugins (listar, detalle, refrescar, habilitar/deshabilitar y configuración genérica), catálogo (búsqueda, categoría, favoritos), tareas (crear, listar, cancelar), archivos (listar y descargar), configuración (tema), favoritos.
- Registro de plugins: validación estricta, duplicados, incompatibilidad, symlinks/traversal, límite de tamaño, aislamiento de errores y validación de `entrypoint`.
- Ejecución: `POST /tasks` valida `params_schema`, crea tarea `pending` y la encola; el `TaskExecutor` limita el pool según `task_workers` y respeta `max_concurrency`/`timeout_seconds`. El adaptador subprocess usa JSON Lines, entorno reducido, límite de salida, cancelación y timeout. Al reiniciar, tareas `running` fallan con `interrupted_by_restart` y las `pending` se reencolan.
- Archivos: las salidas declaradas dentro de `work_dir` se copian a almacenamiento administrado por Hub y se asocian a la tarea.
- YouTube: plugin core de ejemplo sobre el runner; el web y launcher crean tareas y consultan `/tasks`, y los resultados quedan disponibles en Archivos.
- Interfaz: sidebar colapsable, topbar con buscador (`/` o Ctrl/⌘K) e indicador de tareas, inicio, catálogo, favoritos, detalle de plugin, tareas (polling adaptativo), archivos, configuración (tema, administración de plugins, sistema), tema claro/oscuro/sistema, estados vacío/carga/error, diálogos de confirmación.

## Pendiente
- Instalación explícita y administración de entornos/dependencias por plugin. Plugins de terceros necesitan su propio `.venv`; Hub no instala dependencias durante el descubrimiento.
- Aislamiento real de plugins de terceros y límites de CPU/memoria/sistema operativo. `subprocess` no es un sandbox; mantener `ALLOW_UNTRUSTED_PLUGINS=false` salvo para desarrollo local de plugins confiables.
- Adaptadores `python_inprocess` y `remote_api`; hoy solo se ejecuta `subprocess`.
- Formularios declarativos web generados desde JSON Schema; por ahora YouTube mantiene un formulario específico.
- **Migraciones Alembic**: hoy se usa `create_all`. Debe reemplazarse antes de cualquier uso real.
- **Control de acceso**: no hay `ADMIN_TOKEN`; la API asume uso local en 127.0.0.1. No exponer a la red.
- **Tipos TS**: escritos a mano (`apps/web/src/types/api.ts`); falta tipar las respuestas con `response_model` y generarlos desde OpenAPI.
- Docker/Compose, instalación/actualización/desinstalación de plugins, pruebas de accesibilidad automatizadas, pruebas visuales en navegador real.

## Lanzador (apps/launcher)
`hub_launcher.py`: ventana Tkinter (solo librería estándar) que lista las herramientas habilitadas desde `/api/v1/catalog`, crea tareas y consulta su progreso desde `/api/v1/tasks`; las descargas registradas se copian a la carpeta elegida. Ejecutar: `python apps/launcher/hub_launcher.py`.
