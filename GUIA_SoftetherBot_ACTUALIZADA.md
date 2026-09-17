# GUÍA ACTUALIZADA — SoftetherBot

## Servidor Insurgency + SoftEther VPN + Game Server Hub sobre VPS de ETECSA

Esta versión conserva la guía base del proyecto y aterriza la nueva arquitectura de Game Server Hub.

> **Referencia base:** el escenario original usa VPS ETECSA con Ubuntu 20.04, 1 vCPU, 3 GB RAM y 20 GB de disco. Los precios y condiciones de ETECSA deben verificarse antes de contratar porque la guía original los presenta como tarifas vigentes al momento de redactarse.

---

## 1. Arquitectura final

```text
                         TELEGRAM
                            │
              ┌─────────────┴─────────────┐
              │                           │
           CLIENTE                     ADMIN
              │                           │
       registro/pago                 /panel /juegos
              │                           │
              ▼                           ▼
        SoftetherBot              Telegram Mini App
              │                           │
              ├──── SoftEther VPN        │
              │                           ▼
              │                    GameServer API
              │                           │
              │             ┌─────────────┼─────────────┐
              │             │             │             │
              │          SteamCMD     Open Source   GitHub Source
              │             │             │             │
              │       Insurgency       Xonotic       Teeworlds
              │       L4D2             AssaultCube
              │       CS:S
              │       TF2
              │
              └────── LAN virtual de los clientes
```

El objetivo es que Telegram sea el centro operativo. El administrador no tiene que entrar por SSH para las operaciones normales de los servidores.

---

# 2. Recursos dinámicos del VPS

La regla anterior de `1 SteamCMD + 1 no-SteamCMD` **no es una regla permanente del software**.

En el VPS inicial de referencia, 1 CPU / 3 GB / 20 GB, probablemente solo cabrán uno o pocos servidores pequeños dependiendo de lo que ya esté ejecutándose.

SoftetherBot calcula en cada instalación:

- RAM disponible.
- Disco libre.
- CPU disponibles.
- CPU ya reservada por servidores en ejecución.
- Reserva mínima para Ubuntu, SoftEther, bot y servicios.

Si no cabe:

```text
⛔ No cabe en tus recursos actuales
```

La instalación no comienza.

Si el administrador aumenta el VPS, por ejemplo a 4 CPU / 8 GB / 80 GB, el sistema vuelve a calcular automáticamente la capacidad.

---

# 3. Game Server Hub

La Mini App ya no es solamente el HTML de catálogo.

Desde `/juegos` el administrador puede:

1. Ver los juegos disponibles.
2. Ver requisitos.
3. Ver recursos actuales del VPS.
4. Comprobar si cabe un juego.
5. Elegir nombre de instancia.
6. Lanzar instalación real.
7. Ver resultado.
8. Iniciar.
9. Detener.
10. Reiniciar.
11. Cambiar RCON/contraseña de administración.
12. Desinstalar.

---

# 4. Catálogo inicial

## SteamCMD

### Insurgency (2014)

Es el servidor que ya forma parte del proyecto original.

AppID de servidor:

```text
237410
```

El Setup Wizard original puede instalarlo. Después de eso, GameServerManager lo **adopta** para que no exista una segunda instalación duplicada.

### Left 4 Dead 2

```text
Server AppID: 222860
```

### Counter-Strike: Source

```text
Server AppID: 232330
```

### Team Fortress 2

```text
Server AppID: 232250
```

---

# 5. Alternativas Open Source / GitHub

## Xonotic

Proyecto:

```text
xonotic/xonotic
```

Se utiliza la distribución oficial para el servidor, manteniendo el proyecto fuente en GitHub como referencia.

La versión oficial actualmente publicada es Xonotic 0.8.6. La página oficial indica que la distribución ZIP no requiere instalación tradicional.

## AssaultCube

Proyecto:

```text
assaultcube/AC
```

El servidor dedicado funciona en consola y está diseñado para consumir pocos recursos.

El proyecto dispone de servidor dedicado y configuración específica de administrador.

## Teeworlds

Proyecto:

```text
teeworlds/teeworlds
```

Este caso es diferente: el repositorio oficial documenta compilación mediante CMake y genera `teeworlds_srv`.

Por eso SoftetherBot lo instala mediante el provider `github_source`.

En el VPS de 1 CPU la compilación se realiza con un solo trabajo:

```bash
cmake .. -DCMAKE_BUILD_TYPE=Release -DCLIENT=OFF
cmake --build . -j1
```

El servidor se habilita únicamente si la comprobación de recursos permite la operación.

---

# 6. Contraseña RCON / administración

Se decidió utilizar una **contraseña inicial común opcional**, pero cada servidor mantiene su propia contraseña almacenada cifrada.

```env
RCON_DEFAULT_PASSWORD=
```

### Si se configura

Todos los servidores nuevos comienzan con esa contraseña.

Después el administrador puede cambiarla individualmente:

```text
Insurgency → RCON A
L4D2       → RCON B
CS:S       → RCON C
Xonotic    → RCON D
AssaultCube→ contraseña admin E
Teeworlds  → RCON F
```

### Si queda vacía

SoftetherBot genera una contraseña segura automáticamente.

### Almacenamiento

La base de datos no guarda la contraseña en texto plano.

Se almacena cifrada mediante:

```env
SOFTETHERBOT_MASTER_KEY=
```

No debe publicarse esta clave.

---

# 7. Diferencias entre RCON y administración

No todos los juegos utilizan exactamente el mismo sistema.

SoftetherBot utiliza un modelo abstracto:

```text
GameServerManager
       │
       ├── SteamCMD provider
       ├── GitHub/source provider
       ├── APT provider
       │
       └── Game configuration
               │
               ├── RCON
               ├── server.cfg
               ├── serverpwd.cfg
               └── consola/API futura
```

Por ejemplo, AssaultCube utiliza contraseña de administrador del servidor en lugar del `rcon_password` de Source.

La Mini App puede seguir mostrando una operación uniforme:

```text
🔐 Cambiar contraseña
```

pero el backend aplica el mecanismo correcto para cada juego.

---

# 8. Instalación inicial del VPS

Se mantiene el procedimiento de la guía original.

Verificar:

```bash
uname -a
cat /etc/os-release
nproc
free -h
df -h
```

Después:

```bash
export SOFTETHER_URL="<URL_REAL_DE_LA_BUILD_LINUX_X64>"
sudo ./install.sh
```

El instalador prepara:

- dependencias;
- SoftEther;
- SteamCMD;
- Insurgency inicial;
- UFW;
- entorno Python;
- servicio de Game Server API.

---

# 9. `.env` actualizado

Además de las variables originales:

```env
TELEGRAM_BOT_TOKEN=
ADMIN_TELEGRAM_IDS=
SOFTETHER_JSONRPC_URL=https://127.0.0.1:5555/api/
SOFTETHER_ADMIN_PASSWORD=
SOFTETHER_HUB_NAME=BFP2_LAN
SOFTETHER_HUB_PASSWORD=

CONTRACT_DURATION_DAYS=31
CONTRACT_WARNING_DAYS_BEFORE=4
DATABASE_PATH=./bot/db/softetherbot.sqlite3

INSURGENCY_DIR=/opt/insurgency-server
INSURGENCY_MAX_PLAYERS=12
INSURGENCY_PORT=27015

RCON_DEFAULT_PASSWORD=
SOFTETHERBOT_MASTER_KEY=

STEAMCMD_DIR=/opt/steamcmd
GAME_SERVERS_ROOT=/opt/softetherbot/game-servers
GAME_RESERVE_RAM_MB=700
GAME_RESERVE_DISK_MB=2048

MINIAPP_PORT=8090
MINIAPP_PUBLIC_URL=https://TU-DOMINIO/juegos
```

---

# 10. Primer arranque

```bash
./venv/bin/python bot/main.py
```

El Setup Wizard conserva los siete pasos originales.

Al activar Insurgency, además de crear el servidor, SoftetherBot lo registra en `game_servers`.

Así el servidor original aparece después en:

```text
Telegram
→ /juegos
→ Insurgency
→ Estado
```

No se descarga otra copia.

---

# 11. Mini App

El administrador utiliza:

```text
/juegos
```

y recibe:

```text
🎮 Abrir Game Server Hub
```

La Mini App utiliza `Telegram WebApp initData` para identificar al usuario y comprueba que pertenece a `ADMIN_TELEGRAM_IDS`.

El backend escucha localmente:

```text
127.0.0.1:8090
```

Para usarlo como Telegram Mini App se necesita publicar una URL HTTPS que haga reverse proxy hacia ese puerto.

---

# 12. Flujo real de instalación

```text
Admin
  ↓
Abrir /juegos
  ↓
Seleccionar juego
  ↓
SoftetherBot mide VPS
  ↓
¿Cabe?
 ┌───────┴───────┐
 NO              SÍ
 ↓                ↓
Bloquear       pedir nombre
                  ↓
             confirmar
                  ↓
          provider de instalación
                  ↓
        SteamCMD / GitHub / APT
                  ↓
          configurar servidor
                  ↓
          aplicar contraseña
                  ↓
          registrar systemd
                  ↓
                STOPPED
```

El administrador decide cuándo arrancarlo.

---

# 13. Seguridad

No se abre el puerto de administración JSON-RPC de SoftEther a Internet.

La Mini App se autentica mediante Telegram.

Las contraseñas RCON se cifran en SQLite.

Los servicios de juegos deben quedar accesibles a los clientes mediante la LAN/VPN según el diseño original, no mediante una apertura pública innecesaria.

---

# 14. Escalado futuro

Cuando aumente la cantidad de clientes:

```text
1 CPU / 3 GB / 20 GB
       ↓
      demanda
       ↓
4 CPU / 8 GB / 80 GB
       ↓
      demanda
       ↓
8 CPU / 16 GB / 160 GB
```

No se modifica la regla del programa.

Se vuelve a medir la capacidad real.

Esto permite convertir SoftetherBot progresivamente en un pequeño **Game Server Hub comercial**, manteniendo Telegram como panel de administración.

---

# 15. Regla importante antes de producción

El código permite iniciar instalaciones reales, pero cada provider debe validarse en el VPS real antes de vender ese juego a clientes.

Especialmente:

- conectividad de SteamCMD desde ETECSA;
- espacio real disponible;
- dependencias de Ubuntu 20.04;
- comandos de arranque;
- puertos dentro de la LAN VPN;
- configuración RCON/administración;
- consumo de RAM con jugadores reales.

La guía original ya establece como principio verificar el VPS y no declarar que el sistema funciona únicamente porque el instalador terminó sin error.
