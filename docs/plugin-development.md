# Crear un plugin (guía inicial)

Un plugin es una carpeta dentro de `plugins/` con un `plugin.json`. Hub **solo lee** ese archivo al descubrirlo; nunca importa ni ejecuta su código.

## Ejemplo conceptual de manifiesto (NO está instalado)
```json
{
  "id": "ejemplo-herramienta",
  "name": "Ejemplo",
  "description": "Descripción breve.",
  "version": "1.0",
  "contract_version": 1,
  "categories": ["utilities"],
  "icon": "wrench",
  "integration": { "type": "subprocess" },
  "tools": [{ "id": "run", "name": "Ejecutar", "description": "Qué hace." }],
  "permissions": ["files.read", "files.write"],
  "platform": { "min_version": "1.0" }
}
```

## Reglas (validadas por `packages/contracts/plugin-manifest.schema.json`)
- Campos desconocidos se rechazan (`extra=forbid`): un manifiesto no puede aportar JS, HTML ni rutas.
- `icon` solo acepta identificadores de una lista permitida. `categories` y `permissions` también son listas cerradas.
- `id`: minúsculas, números y guiones; único (duplicados invalidan ambos plugins). `plugin.json` ≤ 64 KB.
- Estado: `available`, `incompatible` (contrato/plataforma) o `invalid`. Un plugin roto nunca impide arrancar Hub.

## Flujo
1. Copiar la carpeta a `plugins/`. 2. Configuración → Plugins → **Buscar plugins**. 3. Habilitarlo.

## Importante
Habilitar un plugin **no ejecuta su código**: el runner genérico todavía no existe, y la ejecución de plugins no confiables está deshabilitada (`HUB_ALLOW_UNTRUSTED_PLUGINS=false`). YouTube Downloader es una integración específica mantenida por Hub: la implementación que descarga los videos está en `apps/api/app/api/v1/endpoints/youtube_dl.py` y se registra desde `apps/api/app/api/v1/router.py`; no ejecuta `main.py` desde la carpeta del plugin. Desde el engranaje se puede elegir formato (MP4, WEBM, MOV, MP3 o WAV) y resolución máxima. El launcher permite elegir la carpeta con **Examinar**; en la web, el navegador elige dónde guardar. Las descargas registran progreso, velocidad y resultado en tareas/archivos. Los permisos son declarativos, no una barrera de seguridad.
