"""
insurgency_setup.py — Registra el servidor Insurgency (instalado por
install.sh vía SteamCMD) como servicio systemd, para que arranque solo
y se pueda encender/apagar/reiniciar desde el bot igual que SoftEther.

También genera y escribe la contraseña RCON en server.cfg — esto es
independiente de la herramienta externa de administración remota que
ya tienes: aquí solo se GENERA la contraseña y se aplica al archivo de
configuración real de Insurgency; tu herramienta la usa para conectarse,
pero no se invoca desde este módulo.
"""

import subprocess
import os
import re
import secrets

INSURGENCY_DIR = os.getenv("INSURGENCY_DIR", "/opt/insurgency-server")
SERVICE_NAME = "insurgency-server"

# Ruta real del server.cfg según la documentación oficial de Valve
# Developer Community para Insurgency 2014 Dedicated Server
SERVER_CFG_PATH = os.path.join(INSURGENCY_DIR, "insurgency", "cfg", "server.cfg")


def _run(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Comando falló: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def create_systemd_service(max_players: int, port: int):
    """
    Crea (o sobrescribe) el servicio systemd del servidor Insurgency,
    con los parámetros elegidos en el Setup Wizard.
    """
    service_content = f"""[Unit]
Description=Insurgency (2014) Dedicated Server
After=network.target

[Service]
Type=simple
WorkingDirectory={INSURGENCY_DIR}
ExecStart={INSURGENCY_DIR}/srcds_run -game insurgency +map ministry +maxplayers {max_players} -port {port}
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
"""
    service_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
    with open(service_path, "w") as f:
        f.write(service_content)

    _run(["systemctl", "daemon-reload"])
    _run(["systemctl", "enable", SERVICE_NAME])

    return service_path


def start_server():
    _run(["systemctl", "start", SERVICE_NAME])


def stop_server():
    _run(["systemctl", "stop", SERVICE_NAME])


def restart_server():
    _run(["systemctl", "restart", SERVICE_NAME])


def get_status() -> str:
    result = subprocess.run(
        ["systemctl", "is-active", SERVICE_NAME],
        capture_output=True, text=True,
    )
    return result.stdout.strip()  # "active" | "inactive" | "failed" ...


# ---------------------------------------------------------------------------
# Contraseña RCON (administración remota) — server.cfg
# ---------------------------------------------------------------------------

def generate_rcon_password(length: int = 20) -> str:
    """
    Genera una contraseña RCON aleatoria y segura. 20 caracteres alfanuméricos
    + símbolos seguros para línea de comandos de Source engine (sin comillas
    dobles, que romperían la sintaxis de server.cfg).
    """
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#%^&*-_"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def set_rcon_password(password: str = None) -> str:
    """
    Escribe (o reemplaza) la línea rcon_password en insurgency/cfg/server.cfg,
    tal como documenta Valve Developer Community para Insurgency 2014
    Dedicated Server. Si server.cfg no existe todavía, lo crea con la
    estructura mínima recomendada.

    También fija las variables de protección anti fuerza bruta de RCON
    (sv_rcon_maxfailures, etc.), práctica estándar documentada para
    servidores Source expuestos.

    Requiere reiniciar el servidor (restart_server()) para que aplique
    — SRCDS solo lee server.cfg al arrancar.

    Devuelve la contraseña efectivamente aplicada (útil si se generó
    automáticamente, para mostrársela al admin).
    """
    if password is None:
        password = generate_rcon_password()

    os.makedirs(os.path.dirname(SERVER_CFG_PATH), exist_ok=True)

    if os.path.exists(SERVER_CFG_PATH):
        with open(SERVER_CFG_PATH, "r") as f:
            content = f.read()
    else:
        content = (
            '// server.cfg generado por SoftetherBot\n'
            'hostname "Insurgency Server"\n'
            'sv_password ""\n'
            'sv_minrate 30000\n'
        )

    rcon_line = f'rcon_password "{password}"'

    if re.search(r'^\s*rcon_password\s+".*"\s*$', content, flags=re.MULTILINE):
        content = re.sub(
            r'^\s*rcon_password\s+".*"\s*$', rcon_line, content, flags=re.MULTILINE
        )
    else:
        content += f"\n{rcon_line}\n"

    # Protección anti fuerza bruta de RCON — solo se agrega si no está ya
    proteccion = (
        "sv_rcon_banpenalty 60\n"
        "sv_rcon_maxfailures 10\n"
        "sv_rcon_minfailures 5\n"
        "sv_rcon_minfailuretime 45\n"
    )
    if "sv_rcon_maxfailures" not in content:
        content += f"\n{proteccion}"

    with open(SERVER_CFG_PATH, "w") as f:
        f.write(content)

    # server.cfg queda con la contraseña en texto plano — restringir permisos
    os.chmod(SERVER_CFG_PATH, 0o600)

    return password


def get_rcon_password() -> str:
    """Lee la contraseña RCON actualmente configurada en server.cfg (si existe)."""
    if not os.path.exists(SERVER_CFG_PATH):
        return None
    with open(SERVER_CFG_PATH, "r") as f:
        content = f.read()
    match = re.search(r'^\s*rcon_password\s+"(.*)"\s*$', content, flags=re.MULTILINE)
    return match.group(1) if match else None
