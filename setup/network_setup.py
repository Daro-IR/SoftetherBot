"""
network_setup.py — Configura el DHCP externo (dnsmasq) sobre la interfaz
TAP que crea SoftEther, y asigna la IP de gateway.

Por qué dnsmasq y no "DhcpSet" de vpncmd: "DhcpSet" pertenece a la función
Virtual DHCP de SecureNAT, que dejamos deshabilitado a propósito (el
proyecto requiere "sin tráfico a internet, solo LAN"). Con Local Bridge +
TAP, el reparto de IPs debe hacerlo un servicio del sistema operativo.
Ver la nota dejada en softether_setup.template.txt para el detalle
completo de esta decisión.
"""

import subprocess
import ipaddress

DNSMASQ_CONF_PATH = "/etc/dnsmasq.d/softetherbot.conf"


def _run(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Comando falló: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def derive_network_params(vpn_network_cidr: str):
    """
    A partir del CIDR ingresado en el Setup Wizard (ej. "10.20.30.0/24"),
    calcula: IP de gateway (.1), inicio y fin del rango DHCP, máscara.
    """
    network = ipaddress.ip_network(vpn_network_cidr, strict=False)
    hosts = list(network.hosts())
    gateway_ip = str(hosts[0])              # primer IP utilizable -> gateway
    dhcp_start = str(hosts[1])               # segunda IP utilizable
    dhcp_end = str(hosts[-1])                # última IP utilizable
    netmask = str(network.netmask)
    return {
        "gateway_ip": gateway_ip,
        "dhcp_start": dhcp_start,
        "dhcp_end": dhcp_end,
        "netmask": netmask,
    }


def configure_network(tap_device_name: str, vpn_network_cidr: str, max_players: int):
    """
    1. Asigna la IP de gateway a la interfaz TAP.
    2. Escribe la config de dnsmasq escuchando SOLO en esa interfaz.
    3. Reinicia dnsmasq.

    max_players se usa para no ofrecer más IPs por DHCP de las que el
    proyecto está dimensionado a soportar (12 en el caso base).
    """
    params = derive_network_params(vpn_network_cidr)

    # 1. IP de gateway sobre la interfaz TAP
    prefix_len = ipaddress.ip_network(vpn_network_cidr, strict=False).prefixlen
    _run(["ip", "addr", "add", f"{params['gateway_ip']}/{prefix_len}", "dev", tap_device_name])
    _run(["ip", "link", "set", tap_device_name, "up"])

    # 2. Rango DHCP acotado al número de jugadores configurado, con margen
    #    pequeño para reconexiones (max_players + 5)
    network = ipaddress.ip_network(vpn_network_cidr, strict=False)
    hosts = list(network.hosts())
    dhcp_end_limited = str(hosts[min(1 + max_players + 5, len(hosts) - 1)])

    dnsmasq_conf = f"""# Generado por SoftetherBot — network_setup.py
# NO editar a mano; se regenera si se vuelve a correr el Setup Wizard.
interface={tap_device_name}
bind-interfaces
dhcp-range={params['dhcp_start']},{dhcp_end_limited},{params['netmask']},12h
dhcp-option=3,{params['gateway_ip']}
dhcp-option=6,{params['gateway_ip']}
"""

    with open(DNSMASQ_CONF_PATH, "w") as f:
        f.write(dnsmasq_conf)

    # 3. Reiniciar dnsmasq para aplicar
    _run(["systemctl", "restart", "dnsmasq"])
    _run(["systemctl", "enable", "dnsmasq"])

    return params
