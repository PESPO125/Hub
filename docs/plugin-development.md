# Crear un plugin

Un plugin es una carpeta dentro de `plugins/` con un `plugin.json`. El registro lee y valida el manifiesto durante el descubrimiento; no ejecuta el punto de entrada hasta que se envía una tarea.

## Manifiesto y parámetros

```json
{
  "id": "ejemplo-herramienta",
  "name": "Ejemplo",
  "version": "1.0",
  "integration": { "type": "subprocess", "entrypoint": "main.py" },
  "tools": [{
    "id": "convertir",
    "name": "Convertir",
    "max_concurrency": 1,
    "timeout_seconds": 300,
    "params_schema": {
      "type": "object",
      "required": ["text"],
      "properties": { "text": { "type": "string", "maxLength": 10000 } },
      "additionalProperties": false
    }
  }]
}
```

`entrypoint` debe ser una ruta relativa a la carpeta del plugin y no puede resolver fuera de ella. `params_schema` implementa un subconjunto pequeño de JSON Schema: objetos, arrays, tipos primitivos, `required`, `properties`, `additionalProperties`, `enum`, límites de longitud/elementos, rangos numéricos y `format: uri`. Las reglas no soportadas se rechazan al descubrir el manifiesto.

## Protocolo subprocess

Hub ejecuta el Python del `.venv` del plugin y manda una línea JSON UTF-8 por stdin:

```json
{"tool":"convertir","params":{"text":"hola"},"work_dir":"...","config":{}}
```

El plugin solo debe escribir eventos JSON Lines UTF-8 en stdout. El stderr va a los logs de Hub.

```json
{"type":"progress","value":0.42,"message":"Convirtiendo"}
{"type":"output","path":"resultado.txt","display_name":"resultado.txt"}
{"type":"done"}
```

Eventos admitidos: `progress` (0 a 1), `output` (ruta relativa a `work_dir`), `error` (`code` y `message`) y `done`. `done` es obligatorio. Hub limita stdout, mata el árbol del proceso al cancelar o vencer `timeout_seconds`, valida que las salidas sigan dentro de `work_dir` y las copia al almacenamiento administrado. El plugin nunca elige la ruta de almacenamiento final.

## Instalar y habilitar

1. Crea un `.venv` local dentro de la carpeta del plugin e instala sus dependencias desde `requirements.txt`.
2. Copia el plugin a `plugins/` y usa Configuración → Plugins → **Buscar plugins**.
3. Habilítalo.

La instalación de dependencias es explícita; descubrir el plugin nunca instala ni ejecuta código. Para ejecutar plugins externos, configura `allow_untrusted_plugins = true` en `hub.toml` o `HUB_ALLOW_UNTRUSTED_PLUGINS=true`. Un subprocess no es un sandbox y corre con los permisos del usuario; déjalo desactivado salvo para desarrollo local de plugins confiables.

## Plugin core YouTube

`plugins/youtube-dl` es el único plugin subprocess confiable por defecto; su confianza está fijada en el código de Hub y no se puede declarar en un manifiesto. Usa `POST /api/v1/tasks` igual que otros plugins y guarda los resultados en Archivos. El formulario de preferencias sigue siendo específico de YouTube; su configuración se guarda mediante `GET/PUT /api/v1/plugins/youtube-dl/config`.

Los permisos del manifiesto son informativos; no sustituyen aislamiento. El esquema completo del manifiesto está en `packages/contracts/plugin-manifest.schema.json`.
