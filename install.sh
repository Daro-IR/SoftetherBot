#!/bin/bash
# ============================================================================
# install.sh — Instalador de SoftetherBot
# ============================================================================
# Detecta qué componentes faltan en el VPS y los instala en orden:
#   1. SoftEther VPN Server
#   2. SteamCMD
#   3. Insurgency Server (App ID 237410) vía SteamCMD
#   4. Firewall (ufw) con las reglas necesarias
#   5. Entorno Python + dependencias del bot
#
# Uso:
#   sudo ./install.sh
#
# Seguro de re-ejecutar: cada paso comprueba si ya está hecho antes de
# repetirlo, así que correr install.sh de nuevo tras una instalación
# parcial (o para actualizar) no rompe nada ya instalado.
# ============================================================================

set -e  # cualquier error detiene el script en vez de seguir a medias

INSTALL_DIR="/opt/softetherbot"
VPNSERVER_DIR="/usr/local/vpnserver"
STEAMCMD_DIR="/opt/steamcmd"
INSURGENCY_DIR="/opt/insurgency-server"
STATE_FILE="$INSTALL_DIR/config/install_state.json"

echo "============================================"
echo " SoftetherBot — Instalador"
echo "============================================"

if [ "$EUID" -ne 0 ]; then
  echo "Este script debe ejecutarse como root (sudo ./install.sh)"
  exit 1
fi

mkdir -p "$INSTALL_DIR"

# ----------------------------------------------------------------------------
# Paso 0 — Dependencias base del sistema
# ----------------------------------------------------------------------------
echo ""
echo "[0/5] Comprobando dependencias base del sistema..."
apt-get update -qq
apt-get install -y -qq curl wget tar lib32gcc-s1 lib32stdc++6 python3 python3-pip python3-venv ufw dnsmasq jq > /dev/null
echo "      Dependencias base OK"

# ----------------------------------------------------------------------------
# Paso 1 — SoftEther VPN Server
# ----------------------------------------------------------------------------
echo ""
if [ -x "$VPNSERVER_DIR/vpnserver" ]; then
  echo "[1/5] SoftEther ya está instalado — se omite"
else
  echo "[1/5] Instalando SoftEther VPN Server..."
  cd /tmp
  # Si SOFTETHER_URL no viene dada, se detecta automáticamente la última
  # build RTM estable linux-x64 desde el Download Center de SoftEther.
  if [ -z "${SOFTETHER_URL:-}" ]; then
    echo "      Detectando la última build estable de SoftEther..."
    SOFTETHER_TREE=$(curl -fsSL "https://www.softether-download.com/files/softether/" \
      | grep -oE '/files/softether/v[0-9.]+-[0-9]+-rtm-[0-9.]+-tree/' \
      | sort -V | tail -1 | xargs -n1 basename)
    [ -z "$SOFTETHER_TREE" ] && { echo "ERROR: no se pudo detectar la versión de SoftEther" >&2; exit 1; }
    SOFTETHER_DIR="https://www.softether-download.com/files/softether/${SOFTETHER_TREE}/Linux/SoftEther_VPN_Server/64bit_-_Intel_x64_or_AMD64/"
    SOFTETHER_FILE=$(curl -fsSL "$SOFTETHER_DIR" \
      | grep -oE 'softether-vpnserver-[^"]+-linux-x64-64bit\.tar\.gz' | head -1)
    [ -z "$SOFTETHER_FILE" ] && { echo "ERROR: no se pudo localizar el tarball linux-x64 de SoftEther" >&2; exit 1; }
    SOFTETHER_URL="${SOFTETHER_DIR}${SOFTETHER_FILE}"
    echo "      SoftEther detectado: $SOFTETHER_FILE"
  fi
  wget -q "$SOFTETHER_URL" -O softether-vpnserver.tar.gz
  tar xzf softether-vpnserver.tar.gz
  cd vpnserver
  make >/dev/null
  cd /tmp
  mkdir -p "$VPNSERVER_DIR"
  cp -r vpnserver/* "$VPNSERVER_DIR/"
  chmod 600 "$VPNSERVER_DIR"/*
  chmod +x "$VPNSERVER_DIR/vpnserver" "$VPNSERVER_DIR/vpncmd"

  # Servicio systemd
  cat > /etc/systemd/system/vpnserver.service <<EOF
[Unit]
Description=SoftEther VPN Server
After=network.target auditd.service
ConditionPathExists=!$VPNSERVER_DIR/do_not_run

[Service]
Type=forking
ExecStart=$VPNSERVER_DIR/vpnserver start
ExecStop=$VPNSERVER_DIR/vpnserver stop
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable vpnserver
  systemctl start vpnserver
  sleep 3
  echo "      SoftEther instalado y arrancado"
fi

# ----------------------------------------------------------------------------
# Paso 2 — SteamCMD
# ----------------------------------------------------------------------------
echo ""
if [ -x "$STEAMCMD_DIR/steamcmd.sh" ]; then
  echo "[2/5] SteamCMD ya está instalado — se omite"
else
  echo "[2/5] Instalando SteamCMD..."
  mkdir -p "$STEAMCMD_DIR"
  cd "$STEAMCMD_DIR"
  wget -q https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz
  tar xzf steamcmd_linux.tar.gz
  rm steamcmd_linux.tar.gz
  echo "      SteamCMD instalado"
fi

# ----------------------------------------------------------------------------
# Paso 3 — Insurgency Server (App ID 237410)
# ----------------------------------------------------------------------------
echo ""
if [ -f "$INSURGENCY_DIR/srcds_run" ]; then
  echo "[3/5] Insurgency Server ya está instalado — se omite"
else
  echo "[3/5] Instalando Insurgency Server vía SteamCMD (esto puede tardar)..."
  mkdir -p "$INSURGENCY_DIR"
  "$STEAMCMD_DIR/steamcmd.sh" +force_install_dir "$INSURGENCY_DIR" \
    +login anonymous \
    +app_update 237410 validate \
    +quit
  echo "      Insurgency Server instalado en $INSURGENCY_DIR"
fi

# ----------------------------------------------------------------------------
# Paso 4 — Firewall (ufw)
# ----------------------------------------------------------------------------
# Reglas mínimas: SSH (para no perder acceso), puerto VPN de SoftEther
# (el puerto real lo define el Setup Wizard, aquí solo se deja el
# esqueleto — network_setup.py aplica el puerto específico después).
# IMPORTANTE: el puerto de gestión JSON-RPC de SoftEther NO se abre
# aquí a propósito — el bot lo llama por localhost.
echo ""
echo "[4/5] Configurando firewall base (ufw)..."
ufw allow OpenSSH >/dev/null 2>&1 || true
ufw --force enable >/dev/null 2>&1
echo "      Firewall base activo (reglas específicas de VPN las aplica el Setup Wizard)"

# ----------------------------------------------------------------------------
# Paso 5 — Entorno Python del bot
# ----------------------------------------------------------------------------
echo ""
echo "[5/5] Preparando entorno Python del bot..."
cd "$(dirname "$0")"
python3 -m venv venv
source venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt
deactivate
echo "      Entorno Python listo"

echo ""
echo "============================================"
echo " Instalación de componentes completada."
echo " Ejecuta ahora: ./venv/bin/python bot/main.py"
echo " para iniciar SoftetherBot y completar el"
echo " Setup Wizard desde Telegram."
echo "============================================"

# ----------------------------------------------------------------------------
# Servicio Game Server API / Mini App
# ----------------------------------------------------------------------------
mkdir -p /opt/softetherbot/game-servers
cat >/etc/systemd/system/softetherbot-games.service <<EOF
[Unit]
Description=SoftetherBot Game Server API
After=network.target
[Service]
WorkingDirectory=$INSTALL_DIR
Environment=PYTHONPATH=$INSTALL_DIR
EnvironmentFile=-$INSTALL_DIR/.env
ExecStart=$INSTALL_DIR/venv/bin/python -m bot.game_manager.api
Restart=on-failure
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable softetherbot-games
systemctl enable softetherbot-games >/dev/null 2>&1 || true
if [ -f "$INSTALL_DIR/.env" ]; then systemctl restart softetherbot-games || true; else echo "      Mini App preparada; se arrancará después de crear .env"; fi

# ----------------------------------------------------------------------------
# Extras Game Server Hub v3
# ----------------------------------------------------------------------------
mkdir -p /opt/softetherbot/game-servers /opt/softetherbot/backups
chmod 750 /opt/softetherbot/backups
# El catálogo/manager compila Teeworlds y necesita estas herramientas cuando
# el administrador lo seleccione; instalarlas ahora evita fallos a mitad del job.
apt-get install -y -qq git cmake build-essential libpnglite-dev libwavpack-dev > /dev/null 2>&1 || true

# Reinicio limpio del servicio si ya existe .env.
systemctl daemon-reload
if [ -f "$INSTALL_DIR/.env" ]; then
  systemctl restart softetherbot-games || true
fi
