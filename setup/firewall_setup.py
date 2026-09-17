"""
firewall_setup.py — Reglas de firewall (ufw) específicas del proyecto,
aplicadas después de que el Setup Wizard conoce el puerto VPN real.

Regla de seguridad central de todo el proyecto:
  - Puerto VPN (el que elige el admin en el wizard): ABIERTO a internet.
    Es por donde entran los 12 jugadores.
  - Puerto de gestión JSON-RPC de SoftEther (mismo 443/5555): NUNCA se
    abre aquí. El bot lo llama por 127.0.0.1 porque corre en el mismo VPS.
  - Puerto del servidor Insurgency (27015 típico): abierto solo si
    quieres que también sea alcanzable fuera de la VPN — normalmente
    NO hace falta abrirlo a internet si todos los jugadores entran vía
    SoftEther, así que por defecto se deja cerrado y solo alcanzable
    dentro de la LAN virtual.
"""

import subprocess


def _run(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Comando falló: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def configure_firewall(vpn_port: int, expose_insurgency_port: bool = False,
                        insurgency_port: int = 27015):
    """
    Aplica las reglas de ufw. Se asume que install.sh ya habilitó ufw
    y permitió OpenSSH — aquí solo se agregan las reglas del proyecto.
    """
    # Puerto VPN de SoftEther — necesario para que los clientes conecten
    _run(["ufw", "allow", f"{vpn_port}/tcp"])

    if expose_insurgency_port:
        # Solo si el admin decide que el servidor de juego sea alcanzable
        # también fuera de la VPN (no es el diseño por defecto del proyecto)
        _run(["ufw", "allow", f"{insurgency_port}/tcp"])
        _run(["ufw", "allow", f"{insurgency_port}/udp"])

    # Recordatorio explícito (no ejecutable): el puerto de gestión JSON-RPC
    # de SoftEther NO se abre aquí a propósito. El bot lo llama por
    # 127.0.0.1, nunca desde fuera del VPS.

    _run(["ufw", "reload"])

    return {
        "vpn_port_opened": vpn_port,
        "insurgency_port_opened": insurgency_port if expose_insurgency_port else None,
    }
