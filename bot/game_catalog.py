"""Fuente única de verdad del catálogo de servidores de SoftetherBot.

Los requisitos son conservadores: representan una reserva mínima aproximada
para decidir si una instalación cabe en el VPS. El GameServerManager vuelve a
medir RAM/disco en tiempo real antes de instalar.
"""

GAMES = {
    "insurgency": {
        "name": "Insurgency (2014)", "category": "SteamCMD", "method": "steamcmd",
        "server_app_id": "237410", "game_id": "222880",
        "ram_mb": 1200, "disk_mb": 8000, "cpu_weight": 1,
        "provider_label": "SteamCMD", "admin_password_label": "RCON", "update_supported": True,
        "default_port": 27015, "rcon": True,
        "command": "./srcds_run -console -game insurgency +map ministry",
        "notes": "Servidor dedicado Source/SteamCMD.", "platform": "Linux", "players": "Configurable", "install_size_mb": 8000, "update_method": "SteamCMD validate"
    },
    "l4d2": {
        "name": "Left 4 Dead 2", "category": "SteamCMD", "method": "steamcmd",
        "server_app_id": "222860", "game_id": "550",
        "ram_mb": 1400, "disk_mb": 15000, "cpu_weight": 1,
        "provider_label": "SteamCMD", "admin_password_label": "RCON", "update_supported": True,
        "default_port": 27016, "rcon": True,
        "command": "./srcds_run -console -game left4dead2 +map c1m1_hotel",
        "notes": "Reserva conservadora; comprobar espacio antes de instalar.", "platform": "Linux", "players": "Configurable", "install_size_mb": 15000, "update_method": "SteamCMD validate"
    },
    "css": {
        "name": "Counter-Strike: Source", "category": "SteamCMD", "method": "steamcmd",
        "server_app_id": "232330", "game_id": "240",
        "ram_mb": 900, "disk_mb": 10000, "cpu_weight": 1,
        "provider_label": "SteamCMD", "admin_password_label": "RCON", "update_supported": True,
        "default_port": 27017, "rcon": True,
        "command": "./srcds_run -console -game cstrike +map de_dust2",
        "notes": "Servidor dedicado Source.", "platform": "Linux", "players": "Configurable", "install_size_mb": 10000, "update_method": "SteamCMD validate"
    },
    "tf2": {
        "name": "Team Fortress 2", "category": "SteamCMD", "method": "steamcmd",
        "server_app_id": "232250", "game_id": "440",
        "ram_mb": 1200, "disk_mb": 25000, "cpu_weight": 1,
        "provider_label": "SteamCMD", "admin_password_label": "RCON", "update_supported": True,
        "default_port": 27018, "rcon": True,
        "command": "./srcds_run -console -game tf +map cp_dustbowl",
        "notes": "El disco es el principal limitante en el VPS de referencia.", "platform": "Linux", "players": "Configurable", "install_size_mb": 25000, "update_method": "SteamCMD validate"
    },
    "xonotic": {
        "name": "Xonotic", "category": "Open Source", "method": "direct_release",
        "repo": "xonotic/xonotic", "source": "https://github.com/xonotic/xonotic",
        "download_url": "https://dl.xonotic.org/xonotic-0.8.6.zip",
        "ram_mb": 350, "disk_mb": 1800, "cpu_weight": 1,
        "provider_label": "Release oficial", "admin_password_label": "Administración", "update_supported": False,
        "default_port": 26000, "rcon": True,
        "command": "./xonotic-linux64-dedicated +serverconfig server.cfg",
        "notes": "Binario dedicado ligero; fuente/proyecto disponible en GitHub.", "platform": "Linux", "players": "Configurable", "install_size_mb": 1800, "update_method": "Nueva release"
    },
    "assaultcube": {
        "name": "AssaultCube", "category": "Open Source", "method": "apt",
        "repo": "assaultcube/AC", "source": "https://github.com/assaultcube/AC",
        "package": "assaultcube",
        "ram_mb": 250, "disk_mb": 500, "cpu_weight": 1,
        "provider_label": "Paquete Ubuntu", "admin_password_label": "Administración", "update_supported": True,
        "default_port": 28763, "rcon": True,
        "command": "/usr/games/assaultcube-server -mlocalhost",
        "notes": "Se instala desde paquete Ubuntu; proyecto fuente en GitHub.", "platform": "Linux", "players": "Configurable", "install_size_mb": 500, "update_method": "APT"
    },
    "teeworlds": {
        "name": "Teeworlds", "category": "Open Source", "method": "github_source",
        "repo": "teeworlds/teeworlds", "source": "https://github.com/teeworlds/teeworlds",
        "ram_mb": 300, "disk_mb": 1500, "cpu_weight": 1,
        "provider_label": "GitHub + CMake", "admin_password_label": "RCON", "update_supported": True,
        "build_dependencies": ["git", "cmake", "build-essential", "libpnglite-dev", "libwavpack-dev", "python3"],
        "cmake_args": ["-DCMAKE_BUILD_TYPE=Release", "-DCLIENT=OFF"], "binary": "teeworlds_srv",
        "default_port": 8303, "rcon": True,
        "command": "./build/teeworlds_srv -f server.cfg",
        "notes": "Requiere compilar; se permite si los recursos disponibles pasan la validación.", "platform": "Linux", "players": "Configurable", "install_size_mb": 1500, "update_method": "Git pull + CMake"
    },
}
