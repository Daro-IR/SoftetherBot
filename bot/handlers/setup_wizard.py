"""
setup_wizard.py — Wizard de configuración inicial por Telegram, 7 pasos:
  1. Nombre del servidor
  2. Red VPN (CIDR)
  3. Máximo de jugadores
  4. Puerto VPN
  5. ¿Activar servidor Insurgency?
  6. ¿Configurar firewall automáticamente?
  7. Confirmar y crear configuración

Solo se ejecuta si database.is_setup_completed() es False (ver main.py).
Al terminar el paso 7, dispara softether_setup, network_setup,
firewall_setup e insurgency_setup en orden, y muestra el resultado real
de cada uno (no asume éxito silencioso).
"""

import os
import secrets
import ipaddress

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ConversationHandler, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters,
)

from db import database
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "setup"))
import softether_setup
import network_setup
import firewall_setup
import insurgency_setup
from game_manager import manager as game_manager

(NOMBRE, RED_VPN, MAX_JUGADORES, PUERTO_VPN,
 ACTIVAR_INSURGENCY, FIREWALL_AUTO, CONFIRMAR) = range(7)

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]


def _is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS


async def start_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _is_admin(update):
        await update.message.reply_text(
            "El servidor aún no está configurado. Solo un administrador "
            "puede completar la instalación inicial."
        )
        return ConversationHandler.END

    context.user_data["wizard"] = {}
    await update.message.reply_text(
        "🤖 *SOFTETHERBOT — CONFIGURACIÓN INICIAL*\n\n"
        "Paso 1/7\n\nNombre del servidor:",
        parse_mode="Markdown",
    )
    return NOMBRE


async def step_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wizard"]["server_name"] = update.message.text.strip()
    await update.message.reply_text(
        "Paso 2/7\n\nRed VPN (formato CIDR, ej. 10.20.30.0/24):"
    )
    return RED_VPN


async def step_red_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()
    try:
        ipaddress.ip_network(valor, strict=False)
    except ValueError:
        await update.message.reply_text(
            "Eso no parece un CIDR válido. Ejemplo correcto: 10.20.30.0/24\n"
            "Intenta de nuevo:"
        )
        return RED_VPN

    context.user_data["wizard"]["vpn_network_cidr"] = valor
    await update.message.reply_text("Paso 3/7\n\nMáximo de jugadores:")
    return MAX_JUGADORES


async def step_max_jugadores(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()
    if not valor.isdigit() or int(valor) <= 0:
        await update.message.reply_text("Debe ser un número mayor a 0. Intenta de nuevo:")
        return MAX_JUGADORES

    context.user_data["wizard"]["max_players"] = int(valor)
    await update.message.reply_text("Paso 4/7\n\nPuerto VPN (ej. 443):")
    return PUERTO_VPN


async def step_puerto_vpn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()
    if not valor.isdigit() or not (1 <= int(valor) <= 65535):
        await update.message.reply_text("Debe ser un puerto válido (1-65535). Intenta de nuevo:")
        return PUERTO_VPN

    context.user_data["wizard"]["vpn_port"] = int(valor)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Sí", callback_data="insurgency_si"),
         InlineKeyboardButton("No", callback_data="insurgency_no")]
    ])
    await update.message.reply_text(
        "Paso 5/7\n\n¿Activar servidor Insurgency?", reply_markup=keyboard
    )
    return ACTIVAR_INSURGENCY


async def step_activar_insurgency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["wizard"]["insurgency_enabled"] = (query.data == "insurgency_si")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Sí", callback_data="firewall_si"),
         InlineKeyboardButton("No", callback_data="firewall_no")]
    ])
    await query.edit_message_text(
        "Paso 6/7\n\n¿Configurar firewall automáticamente?", reply_markup=keyboard
    )
    return FIREWALL_AUTO


async def step_firewall_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["wizard"]["firewall_auto"] = (query.data == "firewall_si")

    w = context.user_data["wizard"]
    resumen = (
        "Paso 7/7\n\n*Resumen de configuración:*\n\n"
        f"Nombre del servidor: {w['server_name']}\n"
        f"Red VPN: {w['vpn_network_cidr']}\n"
        f"Máx. jugadores: {w['max_players']}\n"
        f"Puerto VPN: {w['vpn_port']}\n"
        f"Insurgency activo: {'Sí' if w['insurgency_enabled'] else 'No'}\n"
        f"Firewall automático: {'Sí' if w['firewall_auto'] else 'No'}\n\n"
        "¿Confirmar y crear configuración?"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirmar", callback_data="confirmar_si"),
         InlineKeyboardButton("❌ Cancelar", callback_data="confirmar_no")]
    ])
    await query.edit_message_text(resumen, reply_markup=keyboard, parse_mode="Markdown")
    return CONFIRMAR


async def step_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "confirmar_no":
        await query.edit_message_text("Configuración cancelada. Envía /setup para reiniciar.")
        context.user_data.pop("wizard", None)
        return ConversationHandler.END

    w = context.user_data["wizard"]
    await query.edit_message_text("Creando configuración... esto puede tardar un momento.")

    # Contraseñas de administración de SoftEther generadas automáticamente
    # (no se piden por Telegram por seguridad: no queremos contraseñas de
    # alto privilegio viajando como texto plano en el chat innecesariamente)
    softether_admin_password = secrets.token_urlsafe(16)
    softether_hub_password = secrets.token_urlsafe(16)

    resultados = []

    # 1) SoftEther: Hub, grupos, políticas, bridge/TAP
    ok, output = softether_setup.run_softether_setup(
        hub_name=os.getenv("SOFTETHER_HUB_NAME", "BFP2_LAN"),
        softether_admin_password=softether_admin_password,
        softether_hub_password=softether_hub_password,
        contract_duration_days=int(os.getenv("CONTRACT_DURATION_DAYS", "31")),
    )
    resultados.append(("SoftEther (Hub/grupos/políticas/bridge)", ok))
    if not ok:
        await query.message.reply_text(
            f"⚠️ Falló la configuración de SoftEther:\n```\n{output[:1500]}\n```",
            parse_mode="Markdown",
        )

    # 2) Red: dnsmasq sobre la interfaz TAP
    try:
        tap_device = softether_setup.get_tap_device_name()
        network_setup.configure_network(
            tap_device_name=tap_device,
            vpn_network_cidr=w["vpn_network_cidr"],
            max_players=w["max_players"],
        )
        resultados.append(("Red / DHCP (dnsmasq)", True))
    except Exception as e:
        resultados.append(("Red / DHCP (dnsmasq)", False))
        await query.message.reply_text(f"⚠️ Falló la configuración de red: {e}")

    # 3) Firewall (si el admin lo pidió)
    if w["firewall_auto"]:
        try:
            firewall_setup.configure_firewall(vpn_port=w["vpn_port"])
            resultados.append(("Firewall", True))
        except Exception as e:
            resultados.append(("Firewall", False))
            await query.message.reply_text(f"⚠️ Falló la configuración de firewall: {e}")
    else:
        resultados.append(("Firewall", None))  # omitido a propósito

    # 4) Insurgency Server (si el admin lo activó)
    insurgency_rcon_password = None
    if w["insurgency_enabled"]:
        try:
            insurgency_setup.create_systemd_service(
                max_players=w["max_players"],
                port=int(os.getenv("INSURGENCY_PORT", "27015")),
            )
            # server.cfg debe existir con la contraseña ANTES del primer
            # arranque — SRCDS solo lo lee al iniciar.
            insurgency_rcon_password = insurgency_setup.set_rcon_password()
            insurgency_setup.start_server()
            # Adoptar Insurgency en el GameServerManager para que desde la Mini App
            # sea el mismo servidor y no una segunda instalación duplicada.
            try:
                if not database.get_game_server("insurgency"):
                    spec = game_manager.GAMES["insurgency"]
                    database.create_game_server(
                        "insurgency", spec["name"], spec["method"], "insurgency",
                        os.getenv("INSURGENCY_DIR", "/opt/insurgency-server"),
                        int(os.getenv("INSURGENCY_PORT", "27015")),
                        insurgency_rcon_password, spec["ram_mb"], spec["disk_mb"],
                        __import__("json").dumps(spec)
                    )
                    database.mark_game_server_installed("insurgency")
            except Exception as adopt_error:
                resultados.append(("Registro en Game Server Hub", False))
                await query.message.reply_text(f"⚠️ Insurgency funciona, pero no se pudo registrar en Game Server Hub: {adopt_error}")
            resultados.append(("Insurgency Server", True))
        except Exception as e:
            resultados.append(("Insurgency Server", False))
            await query.message.reply_text(f"⚠️ Falló el arranque de Insurgency: {e}")
    else:
        resultados.append(("Insurgency Server", None))

    # Guardar config final en la base de datos
    database.save_server_config(
        server_name=w["server_name"],
        vpn_network_cidr=w["vpn_network_cidr"],
        max_players=w["max_players"],
        vpn_port=w["vpn_port"],
        insurgency_enabled=w["insurgency_enabled"],
        firewall_auto=w["firewall_auto"],
    )

    # Verificación final real: no declaramos el wizard listo sin comprobar servicios.
    try:
        final_health = game_manager.health()
        vpn_ok = final_health.get("vpnserver") == "active"
        bot_api_ok = final_health.get("softetherbot-games") == "active"
        resultados.append(("Verificación final de servicios", vpn_ok and bot_api_ok))
    except Exception as health_error:
        resultados.append(("Verificación final de servicios", False))
        await query.message.reply_text(f"⚠️ No se pudo completar el diagnóstico final: {health_error}")

    def emoji(v):
        if v is True:
            return "🟢"
        if v is False:
            return "🔴"
        return "⚪ (omitido)"

    reporte = "\n".join(f"{emoji(ok)} {nombre}" for nombre, ok in resultados)

    contrasenas = (
        f"Admin servidor SoftEther: `{softether_admin_password}`\n"
        f"Admin Hub SoftEther: `{softether_hub_password}`\n"
    )
    if insurgency_rcon_password:
        contrasenas += f"RCON Insurgency: `{insurgency_rcon_password}`\n"

    await query.message.reply_text(
        f"✅ *CONFIGURACIÓN COMPLETADA*\n\n{reporte}\n\n"
        "Guarda estas contraseñas en un lugar seguro (no se volverán a "
        "mostrar):\n\n"
        f"{contrasenas}\n"
        "Las contraseñas de administración se aplicaron durante el proceso.\n\n"
        "El estado final fue verificado; si aparece un paso en rojo, usa /panel y la sección Diagnóstico antes de operar el servidor.",
        parse_mode="Markdown",
    )

    context.user_data.pop("wizard", None)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("wizard", None)
    await update.message.reply_text("Configuración cancelada.")
    return ConversationHandler.END


def register_handlers(app: Application):
    conv = ConversationHandler(
        entry_points=[CommandHandler("setup", start_setup)],
        states={
            NOMBRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_nombre)],
            RED_VPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_red_vpn)],
            MAX_JUGADORES: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_max_jugadores)],
            PUERTO_VPN: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_puerto_vpn)],
            ACTIVAR_INSURGENCY: [CallbackQueryHandler(step_activar_insurgency)],
            FIREWALL_AUTO: [CallbackQueryHandler(step_firewall_auto)],
            CONFIRMAR: [CallbackQueryHandler(step_confirmar)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
