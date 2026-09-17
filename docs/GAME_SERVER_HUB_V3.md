# SoftetherBot Game Server Hub v3

Esta versión aterriza las recomendaciones seleccionadas: **1, 2, 3, 6, 7, 9, 11, 12, 13, 14 y 15**.

## 1–3. Jobs, progreso y concurrencia

- `/api/install` ya no mantiene la petición HTTP abierta durante SteamCMD/compilación.
- Devuelve un `job_id` y el frontend consulta `/api/jobs/{job_id}`.
- Se almacena estado, porcentaje, etapa, mensaje, error y hasta 30 KB de log.
- Un bloqueo global evita dos instalaciones simultáneas desde la Mini App.
- El chequeo de RAM/disco/CPU se vuelve a ejecutar dentro del worker.

## 6–7. Diagnóstico y health checks

- `/api/diagnostics` devuelve recursos, servicios, servidores, jobs y backups.
- `/api/health` comprueba `vpnserver`, `softetherbot-games`, base de datos y servicios de juegos.
- El Setup Wizard hace una comprobación final antes de declarar terminado el proceso.

## 9. Backup + actualización + rollback

- Antes de actualizar un servidor se crea un `.tar.gz` en `GAME_BACKUP_ROOT`.
- La actualización usa el provider correspondiente.
- Si falla, intenta restaurar automáticamente la instancia desde el backup.
- El diagnóstico lista los últimos backups.

## 11. Catálogo con metadatos

Cada entrada declara, además del juego:

- `server_app_id` cuando aplica.
- `game_id` cuando aplica.
- RAM, disco y peso CPU.
- proveedor real.
- puerto.
- etiqueta de contraseña de administración.
- soporte de actualización.
- dependencias/build cuando corresponde.

Los valores de recursos son **estimaciones de planificación**, no una garantía de rendimiento.

## 12. Providers

La instalación se separa por provider:

- `SteamCMDProvider`
- `DirectReleaseProvider`
- `AptProvider`
- `GitHubSourceProvider`

Esto permite añadir juegos sin convertir `manager.py` en un bloque monolítico.

## 13. Contraseña de administración

La Mini App ya no llama a todo “RCON”. Cada juego declara `admin_password_label`:

- Source/Teeworlds/Xonotic: RCON.
- AssaultCube: Administración.

La credencial se conserva cifrada en SQLite mediante Fernet y nunca se devuelve en `/api/status`.

## 14. Setup Wizard estilo Jellyfin

El asistente conserva sus pasos guiados y ahora termina con verificación real de servicios. La Mini App incluye además una pantalla de **Asistente** que explica el flujo: datos → SoftEther → red/firewall → juegos → verificación.

## 15. Priorización aplicada

### Alta
- Jobs + bloqueo.
- Progreso consultable.
- Servicios sin root para nuevas instancias.
- Health checks.

### Media
- Diagnóstico.
- Backups y rollback.
- Catálogo/provider más estructurado.

### Experiencia
- Etiquetas genéricas de administración.
- Wizard visual y operativo.

## Seguridad

Las nuevas instancias de juego se ejecutan con un usuario de sistema propio, `NoNewPrivileges=true` y `PrivateTmp=true`. Insurgency conserva su servicio existente por compatibilidad con la instalación original.

El endpoint API sigue escuchando en `127.0.0.1:8090`; se debe publicar mediante HTTPS/reverse proxy antes de registrarlo como Mini App de Telegram.
