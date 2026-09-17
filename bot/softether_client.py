"""
softether_client.py — Cliente JSON-RPC para SoftEther VPN Server.

Basado en el protocolo real de administración de SoftEther (JSON-RPC 2.0
sobre HTTPS, autenticación HTTP Basic con hubname/password contra /api).

IMPORTANTE DE SEGURIDAD:
Este cliente debe apuntar SIEMPRE a 127.0.0.1 (localhost), porque el bot
corre en el mismo VPS que SoftEther. El puerto de gestión (443/5555) NO
debe estar expuesto a internet en el firewall — solo el puerto de
conexión VPN de los clientes debe estarlo. Ver notas en softether_setup.txt.

El certificado de SoftEther suele ser autofirmado, por eso se desactiva
la verificación SSL (verify=False) — esto es aceptable únicamente porque
la conexión es a localhost, nunca lo hagas así contra un host remoto.
"""

import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Tipos de autenticación de usuario en SoftEther
AUTH_TYPE_ANONYMOUS = 0
AUTH_TYPE_PASSWORD = 1

GROUP_PENDIENTES = "pendientes"
GROUP_APROBADOS = "aprobados"


class SoftEtherAPIError(Exception):
    pass


class SoftEtherClient:
    def __init__(self, base_url: str, hub_name: str, admin_password: str):
        """
        base_url: ej. "https://127.0.0.1:5555/api/"
        hub_name: nombre de usuario para la autenticación Basic
                  (SoftEther usa el hub/servidor como "usuario" en Basic Auth
                  cuando se administra en modo servidor completo)
        admin_password: contraseña de administrador del servidor
        """
        self.url = base_url
        self.session = requests.Session()
        self.session.verify = False
        self.session.auth = (hub_name, admin_password)
        self._rpc_id = 0

    def _call(self, method: str, params: dict = None):
        self._rpc_id += 1
        payload = {
            "jsonrpc": "2.0",
            "id": f"rpc_{self._rpc_id}",
            "method": method,
            "params": params or {},
        }
        resp = self.session.post(self.url, json=payload, timeout=10)
        if resp.status_code != 200:
            raise SoftEtherAPIError(
                f"HTTP {resp.status_code} al llamar {method}: {resp.text}"
            )
        data = resp.json()
        if "error" in data:
            raise SoftEtherAPIError(f"{method} devolvió error: {data['error']}")
        return data.get("result", {})

    def test_connection(self) -> bool:
        try:
            self._call("Test", {"IntValue_u32": 0})
            return True
        except SoftEtherAPIError:
            return False

    # ------------------------------------------------------------------
    # Gestión de usuarios (lo que usa el bot para el flujo de pagos)
    # ------------------------------------------------------------------

    def create_user(self, hub_name: str, username: str, password: str,
                     group_name: str = GROUP_PENDIENTES, real_name: str = "",
                     note: str = ""):
        """
        Crea un usuario nuevo en el Hub, en el grupo indicado (por defecto
        'pendientes', sin acceso a la LAN hasta que el admin lo apruebe).
        """
        self._call("CreateUser", {
            "HubName_str": hub_name,
            "Name_str": username,
            "GroupName_str": group_name,
            "Realname_utf": real_name,
            "Note_utf": note,
            "AuthType_u32": AUTH_TYPE_PASSWORD,
        })
        # SoftEther separa la creación del usuario del establecimiento de
        # la contraseña — se hace con SetUser pasando la contraseña en
        # texto plano, que el servidor hashea internamente.
        self.set_user_password(hub_name, username, password)

    def set_user_password(self, hub_name: str, username: str, password: str):
        self._call("SetUser", {
            "HubName_str": hub_name,
            "Name_str": username,
            "AuthType_u32": AUTH_TYPE_PASSWORD,
            "Auth_Password_utf": password,
        })

    def move_user_to_group(self, hub_name: str, username: str, group_name: str):
        """
        Mueve un usuario existente a otro grupo (pendientes <-> aprobados).
        Esto es lo que ejecuta el bot al validar un pago o al vencer un
        contrato — no requiere recrear el usuario ni reiniciar nada.
        """
        self._call("SetUser", {
            "HubName_str": hub_name,
            "Name_str": username,
            "GroupName_str": group_name,
        })

    def delete_user(self, hub_name: str, username: str):
        """Usado cuando el admin rechaza un pago inicial (cuenta nunca aprobada)."""
        self._call("DeleteUser", {
            "HubName_str": hub_name,
            "Name_str": username,
        })

    def get_user(self, hub_name: str, username: str):
        return self._call("GetUser", {
            "HubName_str": hub_name,
            "Name_str": username,
        })

    def enum_users(self, hub_name: str):
        result = self._call("EnumUser", {"HubName_str": hub_name})
        return result.get("UserList", [])

    # ------------------------------------------------------------------
    # Estado del servidor / hub (para el dashboard del bot)
    # ------------------------------------------------------------------

    def get_server_info(self):
        return self._call("GetServerInfo")

    def get_server_status(self):
        return self._call("GetServerStatus")

    def get_hub_status(self, hub_name: str):
        return self._call("GetHubStatus", {"HubName_str": hub_name})

    def enum_connections(self, hub_name: str):
        """Sesiones VPN activas — útil para saber cuántos jugadores están conectados ahora."""
        result = self._call("EnumConnection", {"HubName_str": hub_name})
        return result.get("ConnectionList", [])
