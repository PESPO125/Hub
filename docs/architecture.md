# Arquitectura — Etapa 1

## 1. Alcance de la v1
Núcleo + API + registro de plugins + tareas + archivos + configuración + UI. Incluye YouTube como plugin core de ejemplo.
Modelo de uso: **un único usuario local** (sin cuentas). El esquema reserva `owner_id` nullable en tareas/archivos/preferencias para añadir auth después sin migraciones destructivas.
La API escucha por defecto solo en `127.0.0.1` y no incluye autenticación: está pensada para uso local y no debe exponerse a la red.

## 2. Decisiones técnicas
| Tema | Decisión | Motivo |
|---|---|---|
| Estilo | Monolito modular (apps/api + apps/web) | Simple; límites claros por módulo |
| Fuente de verdad de contratos | `packages/contracts/plugin-manifest.schema.json` (JSON Schema) es la fuente del manifiesto; OpenAPI generado por FastAPI es la fuente de la API; el frontend genera tipos TS desde OpenAPI (`openapi-typescript`) | Evita duplicar tipos a mano |
| BD | SQLAlchemy 2 + Alembic; SQLite en dev, PostgreSQL en prod; sin SQL específico de motor | Portabilidad |
| Tareas | `TaskExecutor` con pool local limitado. Al reiniciar, tareas `running` pasan a `failed` (`interrupted_by_restart`) y `pending` se reencolan desde sus parámetros persistidos | Comportamiento documentado, sin fingir durabilidad |
| Archivos | Interfaz `FileStorage` + `LocalFileStorage`; el plugin nunca elige rutas, recibe un `FileHandle` | Migrable a S3 |
| Polling | TanStack Query con `refetchInterval` adaptativo (solo si hay tareas activas) | Sin SSE/WebSocket hasta necesitarlos |
| UI de plugins | Formularios **declarativos** (JSON Schema acotado + `ui_hints`) renderizados por componentes de la plataforma. Nada de JS/HTML del plugin | Seguridad y coherencia visual |
| Iconos | Identificadores en allowlist de Lucide | Sin recursos arbitrarios |

## 3. Módulos del backend (`apps/api/app/modules`)
- `plugins`: manifest (Pydantic, generado/validado contra el schema), scanner, registry, lifecycle, compatibilidad, servicio admin.
- `catalog`: vista de lectura del catálogo (solo plugins `available`/`enabled`).
- `files`: metadatos, `FileStorage`, expiración/limpieza, descargas controladas.
- `settings`: preferencias e información de plataforma.
- `health`: `/health` (liveness) y `/ready` (BD + almacenamiento).
- `execution`: contrato `PluginRunner`, validación acotada de JSON Schema y adaptador `SubprocessRunner` con protocolo JSON Lines.
- `tasks`: cola local limitada, transición de estados y coordinación entre runner, almacenamiento y `StoredFile`.

## 4. Ciclo de vida de plugins
Estado **operativo** (calculado por el registro): `discovered → validated → available | incompatible | invalid | error`.
Estado **administrativo** (en BD): `enabled | disabled` (por defecto `disabled`).
Un plugin solo es ejecutable si operativo=`available` Y administrativo=`enabled` Y su nivel de confianza permite ejecución.

```
carpeta → [scan: lee plugin.json, NO ejecuta nada]
        → discovered → validate(schema+reglas) → invalid
                                              → validated → compat check → incompatible
                                                                         → available ⇄ (admin) enabled/disabled
        cualquier fallo en runtime → error (aislado, el núcleo sigue)
```

## 5. Confianza y aislamiento (seguridad)
- Escaneo: solo directorios configurados; `resolve()` + verificación de que el path queda dentro de la raíz; rechazo de symlinks que escapan; límite de tamaño del manifiesto (64 KB) y de profundidad/nº de archivos.
- IDs de plugin únicos e inmutables; duplicados → ambos marcados `invalid` (`duplicate_id`), no se elige uno al azar.
- Los permisos declarados son **informativos/solicitados**, no una barrera por sí solos.
- Niveles de confianza: plugins core identificados por código del Hub y plugins externos. Los externos requieren `ALLOW_UNTRUSTED_PLUGINS=true`; el valor predeterminado es `false`. El built-in YouTube usa un subprocess con el intérprete y dependencias del Hub. Un subprocess externo no es un sandbox y ejecuta con los permisos del usuario.
- Tipos de adaptador previstos: `python_inprocess` (solo `core`), `subprocess`, `remote_api`. Hoy se implementa `subprocess`.
- Operaciones administrativas → tabla `audit_events`. Errores al cliente sin trazas ni rutas; detalle en logs con `request_id`.

## 6. Modelo de datos (v1)
`plugin_records` (id, admin_state, config JSON, first_seen, updated_at) · `tasks` · `stored_files` · `user_preferences` · `audit_events`. El manifiesto **no** se duplica en BD (se relee de la carpeta); se guarda solo un hash para detectar cambios.

## 7. API `/api/v1` (v1)
`GET /health`, `/ready`, `/app/info`, `/plugins`, `/plugins/{id}`, `POST /plugins/refresh`, `PATCH /plugins/{id}/state`, `GET/PUT /plugins/{id}/config`, `GET /catalog`, `GET/POST /tasks`, `POST /tasks/{id}/cancel`, `GET /files`, `GET /files/{id}/download`, `GET/PUT /settings`, `GET /diagnostics`.
`POST /tasks` recibe `{plugin_id, tool_id, params}` y responde `202` con una tarea `pending`. El núcleo verifica estado administrativo y operativo, confianza y `params_schema`; el executor aplica concurrencia por pool (`task_workers` en `hub.toml`)/herramienta y timeout. Los eventos JSON Lines se traducen a estado de tarea; outputs relativos dentro de `work_dir` se guardan con `LocalFileStorage`.

El manifiesto define `integration.entrypoint` y, por herramienta, `params_schema`, `max_concurrency` y `timeout_seconds`. El validador implementa un subconjunto acotado de JSON Schema (`object`, `array`, primitivas, required/properties, enum, límites de longitud/items y URI). La UI sigue usando formulario específico para YouTube; la generación de formularios declarativos queda pendiente.

## 8. Frontend
Estructura por features (dashboard, catalog, plugin-details, tasks, files, settings). Layout con sidebar colapsable, topbar con buscador y contador de tareas activas, estados vacío/carga/error en todas las vistas, tema claro/oscuro/sistema. Favoritos se guardan en backend (`user_preferences`).

## 9. Riesgos detectados
1. Permisos declarativos ≠ seguridad → plugins externos deshabilitados por defecto.
2. Tareas de subprocess no sobreviven reinicios → tareas `running` fallan y `pending` se reencolan al iniciar.
3. SQLite y concurrencia de escritura → WAL habilitado; validar carga antes de ampliar la concurrencia.
4. Deriva de tipos front/back → generación desde OpenAPI en CI.
5. Escritura concurrente del registro durante `refresh` → lock + swap atómico del snapshot.

## 10. Plan de implementación
Etapas 2–7 según el brief: base → núcleo → plugins → frontend → integración/seguridad → docs. Cada etapa termina con tests ejecutados.

## 11. Preguntas abiertas (no bloqueantes; asumo lo indicado)
- Un solo usuario local con token de admin (asumido).
- Idioma de la UI: español (asumido).
