"""
softether_setup.py — Configura SoftEther a partir de las respuestas
del Setup Wizard, generando y ejecutando un archivo de comandos vpncmd
vía "/IN:", en vez de tener los comandos hardcodeados en Python.

Esto es justo el enfoque acordado: el bot NO conoce los detalles internos
de SoftEther, solo rellena una plantilla y le pide a vpncmd que la ejecute.
"""

import subprocess
import os

VPNSERVER_DIR = "/usr/local/vpnserver"
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "softether_setup.template.txt")
GENERATED_PATH = os.path.join(os.path.dirname(__file__), "softether_setup.generated.txt")

TAP_DEVICE_NAME = "bfp2tap"


def render_template(context: dict) -> str:
    with open(TEMPLATE_PATH, "r") as f:
        content = f.read()
    for key, value in context.items():
        content = content.replace("{{" + key + "}}", str(value))
    return content


def run_softether_setup(hub_name: str, softether_admin_password: str,
                         softether_hub_password: str, contract_duration_days: int):
    """
    Genera softether_setup.generated.txt con los valores reales y lo
    ejecuta con vpncmd vía /IN:. Lanzar solo la PRIMERA vez (Setup Wizard).

    Devuelve (ok: bool, output: str) para que el bot pueda mostrarle al
    admin el resultado real del comando, no solo asumir éxito.
    """
    context = {
        "SOFTETHER_ADMIN_PASSWORD": softether_admin_password,
        "HUB_NAME": hub_name,
        "SOFTETHER_HUB_PASSWORD": softether_hub_password,
        "TAP_DEVICE_NAME": TAP_DEVICE_NAME,
        "CONTRACT_DURATION_DAYS": contract_duration_days,
    }
    rendered = render_template(context)

    with open(GENERATED_PATH, "w") as f:
        f.write(rendered)
    os.chmod(GENERATED_PATH, 0o600)  # contiene contraseñas, permisos restrictivos

    vpncmd_path = os.path.join(VPNSERVER_DIR, "vpncmd")
    result = subprocess.run(
        [vpncmd_path, "localhost", "/SERVER", f"/IN:{GENERATED_PATH}"],
        capture_output=True, text=True, timeout=60,
    )

    ok = result.returncode == 0
    output = result.stdout + result.stderr

    # El archivo generado queda con contraseñas en texto plano — se borra
    # tras ejecutarlo, ya quedaron aplicadas dentro de SoftEther.
    if os.path.exists(GENERATED_PATH):
        os.remove(GENERATED_PATH)

    return ok, output


def get_tap_device_name() -> str:
    return TAP_DEVICE_NAME
