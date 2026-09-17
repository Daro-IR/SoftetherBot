# Game Server Hub — decisiones implementadas

## Reglas

1. Instalaciones reales desde Telegram Mini App.
2. Capacidad dinámica: no existe límite fijo de servidores.
3. Cada operación comprueba recursos actuales.
4. Si no cabe, se bloquea antes de descargar.
5. RCON/contraseña inicial configurable con `RCON_DEFAULT_PASSWORD`.
6. Cada instancia guarda su propia credencial cifrada.
7. La credencial puede cambiarse por servidor.
8. Insurgency instalado por el wizard se adopta en `game_servers`.
9. SteamCMD, distribución Open Source y compilación desde GitHub son providers distintos.
10. La Mini App nunca debe considerarse prueba de instalación: el backend registra el resultado real.

## Providers

- `steamcmd`: instala mediante AppID de servidor.
- `direct_release`: distribución binaria oficial; Xonotic conserva su referencia GitHub.
- `apt`: instala paquetes del sistema; AssaultCube conserva referencia al proyecto GitHub.
- `github_source`: clona y compila; Teeworlds usa CMake con `CLIENT=OFF` y `-j1`.

## Seguridad

- Telegram WebApp `initData` se valida mediante HMAC-SHA256.
- Solo IDs incluidos en `ADMIN_TELEGRAM_IDS` pueden usar la API.
- El backend se liga a `127.0.0.1`.
- `SOFTETHERBOT_MASTER_KEY` protege credenciales RCON en SQLite.
- No se abre el puerto JSON-RPC de SoftEther al exterior.
