"""
dashboard.py — Panel de estado tipo el propuesto en el documento de
arquitectura: SoftEther/VPN/Juego online-offline, conteo de usuarios,
jugadores conectados.
"""

import os
import subprocess
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes

from db import database
from softether_client import SoftEtherClient
from game_manager.manager import rcon_password

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "setup"))
import insurgency_setup

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]


def _get_softether_client() -> SoftEtherClient:
    return SoftEtherClient(
        base_url=os.getenv("SOFTETHER_JSONRPC_URL"),
        hub_name=os.getenv("SOFTETHER_HUB_NAME"),
        admin_password=os.getenv("SOFTETHER_ADMIN_PASSWORD"),
    )


def _insurgency_status() -> str:
    result = subprocess.run(
        ["systemctl", "is-active", "insurgency-server"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


async def panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo un administrador puede ver el panel.")
        return

    hub_name = os.getenv("SOFTETHER_HUB_NAME")

    # Estado de SoftEther
    try:
        client = _get_softether_client()
        vpn_online = client.test_connection()
        conexiones = client.enum_connections(hub_name) if vpn_online else []
    except Exception:
        vpn_online = False
        conexiones = []

    # Estado del servidor de juego
    insurgency_active = _insurgency_status() == "active"

    # Conteo de clientes por estado
    counts = database.count_clients_by_status()

    def emoji(v):
        return "🟢" if v else "🔴"

    mensaje = (
        "🟢 *SoftetherBot*\n\n"
        f"Servidor VPN: {emoji(vpn_online)} {'ONLINE' if vpn_online else 'OFFLINE'}\n"
        f"Juego (Insurgency): {emoji(insurgency_active)} "
        f"{'ONLINE' if insurgency_active else 'OFFLINE'}\n\n"
        f"👥 Usuarios totales: {sum(counts.values())}\n"
        f"🟢 Activos: {counts.get('activo', 0)}\n"
        f"🟡 Por vencer: {counts.get('por_vencer', 0)}\n"
        f"⏳ Pendientes: {counts.get('pendiente', 0)}\n"
        f"🔴 Bloqueados: {counts.get('bloqueado', 0)}\n\n"
        f"🎮 Conectados ahora vía VPN: {len(conexiones)}"
    )

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def juegos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo un administrador puede abrir este panel.")
        return
    url=os.getenv("MINIAPP_PUBLIC_URL")
    if not url:
        await update.message.reply_text("⚠️ Falta MINIAPP_PUBLIC_URL en .env")
        return
    kb=InlineKeyboardMarkup([[InlineKeyboardButton("🎮 Abrir Game Server Hub", web_app=WebAppInfo(url=url))]])
    await update.message.reply_text("Panel de instalación y administración real de servidores:", reply_markup=kb)


async def rcon_regenerar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Solo un administrador puede hacer esto.")
        return
    try:
        nombre = (context.args[0] if context.args else "insurgency")
        nueva = rcon_password(nombre)
        await update.message.reply_text(
            f"✅ RCON de {nombre} cambiada.\n\nNueva contraseña (guárdala):\n`{nueva}`",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ No se pudo cambiar la RCON: {e}")


def register_handlers(app: Application):
    app.add_handler(CommandHandler("panel", panel))
    app.add_handler(CommandHandler("rcon_regenerar", rcon_regenerar))
    app.add_handler(CommandHandler("juegos", juegos))
