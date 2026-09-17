# SoftetherBot

SoftetherBot es el proyecto de Telegram + SoftEther VPN para ofrecer acceso temporal a una LAN virtual de juegos desde un VPS. La guía de operación de referencia mantiene el escenario base de ETECSA: Ubuntu 20.04, 1 vCPU, 3 GB RAM y 20 GB de disco.

## Arquitectura actual

```text
Telegram
  │
  ├── Clientes: registro → pago → validación → acceso VPN
  │
  └── Admin
       │
       └── /juegos → Telegram Mini App
                         │
                         ▼
                   GameServer API
                         │
             ┌───────────┼────────────┐
             │           │            │
          SteamCMD    Open Source   Source build
             │           │            │
       Insurgency      Xonotic      Teeworlds
       L4D2            AssaultCube
       CS:S
       TF2
```

El bot sigue usando el modelo de SoftEther del proyecto: SecureNAT deshabilitado, DHCP mediante dnsmasq y grupos `pendientes`/`aprobados`. El puerto de gestión JSON-RPC de SoftEther solo se usa localmente.

## Game Server Hub: instalación REAL

La Mini App ya no es un catálogo estático. Desde Telegram el administrador puede:

- consultar RAM, disco y CPU disponibles;
- comprobar si un juego cabe antes de instalarlo;
- iniciar una instalación real en el VPS;
- iniciar, detener y reiniciar servidores;
- desinstalar una instancia;
- cambiar la contraseña de administración/RCON de cada servidor;
- ver errores de instalación.

### Límite de servidores

No existe una regla fija de `1 SteamCMD + 1 no-SteamCMD`. El límite depende de los recursos reales en el momento de la operación.

Antes de instalar se comprueba:

- RAM disponible;
- disco libre;
- CPU disponible frente al peso de los servidores activos;
- reserva de recursos para Ubuntu/SoftEther/bot.

Si no cabe, la operación se rechaza con un mensaje explícito:

> ⛔ No cabe en tus recursos actuales

Al aumentar el VPS, el mismo código puede aceptar más servidores sin cambiar un número hardcodeado.

## Catálogo inicial

### SteamCMD

- Insurgency (2014) — AppID servidor `237410`.
- Left 4 Dead 2 — AppID servidor `222860`.
- Counter-Strike: Source — AppID servidor `232330`.
- Team Fortress 2 — AppID servidor `232250`.

### Open Source / GitHub

- Xonotic — proyecto `xonotic/xonotic`; el paquete oficial 0.8.6 se distribuye como ZIP y la página oficial indica que no requiere instalación tradicional.
- AssaultCube — proyecto `assaultcube/AC`; el servidor dedicado funciona en consola y consume pocos recursos.
- Teeworlds — proyecto `teeworlds/teeworlds`; el repositorio oficial documenta CMake y la generación de `teeworlds_srv`, por lo que SoftetherBot lo trata como instalación `github_source`, no como descarga binaria SteamCMD.

## RCON / contraseña de administración

La política del proyecto es:

```text
RCON_DEFAULT_PASSWORD (opcional)
            │
            ▼
      nueva instalación
            │
            ▼
  contraseña inicial del servidor
            │
            ├── Insurgency → server.cfg
            ├── Source      → server.cfg
            ├── Xonotic     → server.cfg
            ├── Teeworlds   → server.cfg
            └── AssaultCube → serverpwd.cfg

Cada servidor guarda su credencial cifrada en SQLite y puede cambiarla
individualmente desde la Mini App.
```

Si `RCON_DEFAULT_PASSWORD` queda vacío, SoftetherBot genera una contraseña segura para la instalación.

## Mini App

`web/index.html` se abre mediante el botón `/juegos` del bot. El backend escucha por defecto en `127.0.0.1:8090`. Para publicar la Mini App en Telegram se necesita una URL HTTPS pública/reverse proxy que apunte a ese backend.

La API valida `Telegram WebApp initData` y comprueba que el usuario pertenece a `ADMIN_TELEGRAM_IDS`.

## Instalación base

### Instalación en un solo comando

En un VPS Ubuntu/Debian con acceso root (sudo), ejecuta:

```bash
curl -fsSL https://raw.githubusercontent.com/Daro-IR/SoftetherBot/main/install-from-github.sh | sudo bash
```

El script clona el repositorio, detecta automáticamente la última build estable de SoftEther y instala todas las dependencias (SoftEther VPN, SteamCMD, Insurgency, firewall y el entorno Python) dejando softetherbot preparado.

Después, solo queda completar la configuración:

```bash
cd /opt/softetherbot
cp .env.example .env
nano .env
./venv/bin/python bot/main.py
```

Si prefieres fijar una build concreta de SoftEther, puedes pasarla antes: `SOFTETHER_URL="<URL>" curl -fsSL https://raw.githubusercontent.com/Daro-IR/SoftetherBot/main/install-from-github.sh | sudo bash`.

La guía de referencia establece este flujo inicial: contratar/desplegar VPS, comprobar `uname`, `/etc/os-release`, `df -h`, `free -h` y `nproc`, preparar el proyecto y ejecutar `install.sh`.

```bash
sudo ./install.sh
cd /opt/softetherbot
cp .env.example .env
nano .env
./venv/bin/python bot/main.py
```

La guía original indica que el Setup Wizard crea SoftEther, red, firewall e Insurgency y muestra una sola vez las credenciales iniciales.

## Variables nuevas

```env
RCON_DEFAULT_PASSWORD=
GAME_RESERVE_RAM_MB=700
GAME_RESERVE_DISK_MB=2048
STEAMCMD_DIR=/opt/steamcmd
GAME_SERVERS_ROOT=/opt/softetherbot/game-servers
MINIAPP_PORT=8090
MINIAPP_PUBLIC_URL=https://TU-DOMINIO/juegos
SOFTETHERBOT_MASTER_KEY=
```

`SOFTETHERBOT_MASTER_KEY` protege las credenciales RCON almacenadas en SQLite. No debe publicarse ni enviarse al repositorio.

## Servicios

- `vpnserver.service` — SoftEther.
- `insurgency-server.service` — Insurgency del Setup Wizard.
- `softetherbot-games.service` — API de la Mini App/Game Server Hub.
- Las instancias adicionales se administran mediante unidades `softetherbot-game-*.service`.

## Comandos de Telegram

Clientes:

- `/registrar`
- `/renovar`
- `/estado`

Administradores:

- `/setup`
- `/panel`
- `/juegos`
- `/rcon_regenerar [nombre]`

La documentación de referencia original conserva `/rcon_regenerar` para Insurgency.

## Importante antes de producción

La instalación real de un juego debe probarse primero en el VPS de ETECSA. El skill de instalación exige verificar el entorno antes de ejecutar `install.sh` y no declarar éxito sin evidencia real del servicio. La Mini App sigue ese mismo principio: registra errores de instalación y no los convierte en un falso estado `ONLINE`.
