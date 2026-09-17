"""
client_flow.py — Flujo del lado del cliente:
  /registrar -> elige usuario/contraseña -> se crea en SoftEther (grupo
  pendientes) -> se le muestran los datos de pago -> el cliente envía
  captura -> se reenvía al admin para validar/rechazar.

  /renovar -> mismo flujo de pago pero sobre una cuenta ya existente.
"""

import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, ConversationHandler, CommandHandler, MessageHandler,
    ContextTypes, filters,
)

from db import database
from softether_client import SoftEtherClient, GROUP_PENDIENTES

USERNAME, PASSWORD, ESPERANDO_CAPTURA = range(3)

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]


def _get_softether_client() -> SoftEtherClient:
    return SoftEtherClient(
        base_url=os.getenv("SOFTETHER_JSONRPC_URL"),
        hub_name=os.getenv("SOFTETHER_HUB_NAME"),
        admin_password=os.getenv("SOFTETHER_ADMIN_PASSWORD"),
    )


# ---------------------------------------------------------------------------
# /registrar — alta nueva
# ---------------------------------------------------------------------------

async def start_registrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = database.get_client_by_telegram_id(update.effective_user.id)
    if existing:
        await update.message.reply_text(
            f"Ya tienes una cuenta registrada (usuario: {existing['softether_username']}, "
            f"estado: {existing['status']}). Usa /estado para ver el detalle, "
            "o /renovar si tu contrato está por vencer o ya venció."
        )
        return ConversationHandler.END

    await update.message.reply_text("Elige un nombre de usuario para tu acceso VPN:")
    return USERNAME


async def step_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["reg_username"] = update.message.text.strip()
    await update.message.reply_text("Ahora elige una contraseña:")
    return PASSWORD


async def step_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = context.user_data["reg_username"]
    password = update.message.text.strip()

    client = _get_softether_client()
    hub_name = os.getenv("SOFTETHER_HUB_NAME")

    try:
        client.create_user(hub_name, username, password, group_name=GROUP_PENDIENTES)
    except Exception as e:
        await update.message.reply_text(
            f"No se pudo crear el usuario en el servidor VPN: {e}\n"
            "Contacta al administrador."
        )
        return ConversationHandler.END

    client_id = database.create_client(update.effective_user.id, username)
    context.user_data["client_id"] = client_id
    context.user_data["is_renewal"] = False

    await _pedir_comprobante(update, context)
    return ESPERANDO_CAPTURA


# ---------------------------------------------------------------------------
# /renovar — renovación de una cuenta existente
# ---------------------------------------------------------------------------

async def start_renovar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    existing = database.get_client_by_telegram_id(update.effective_user.id)
    if not existing:
        await update.message.reply_text(
            "No tienes una cuenta registrada todavía. Usa /registrar para crear una."
        )
        return ConversationHandler.END

    context.user_data["client_id"] = existing["id"]
    context.user_data["is_renewal"] = True

    await _pedir_comprobante(update, context)
    return ESPERANDO_CAPTURA


async def _pedir_comprobante(update: Update, context: ContextTypes.DEFAULT_TYPE):
    cuenta = os.getenv("PAYMENT_ACCOUNT_NUMBER")
    telefono = os.getenv("PAYMENT_PHONE_NUMBER")
    instrucciones = os.getenv("PAYMENT_INSTRUCTIONS")

    await update.message.reply_text(
        "Para activar tu acceso, realiza el pago a estos datos:\n\n"
        f"📇 Cuenta: `{cuenta}`\n"
        f"📱 Teléfono de contacto: `{telefono}`\n\n"
        f"{instrucciones}\n\n"
        "Cuando termines, envía aquí mismo una *captura de pantalla* "
        "del comprobante de pago.",
        parse_mode="Markdown",
    )


async def step_recibir_captura(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text(
            "Necesito una captura de pantalla (foto), no texto. Envíala como imagen."
        )
        return ESPERANDO_CAPTURA

    client_id = context.user_data["client_id"]
    is_renewal = context.user_data.get("is_renewal", False)
    photo_file_id = update.message.photo[-1].file_id  # la de mayor resolución

    payment_id = database.create_payment(client_id, photo_file_id, is_renewal)

    await update.message.reply_text(
        "Comprobante recibido. Un administrador lo revisará pronto. "
        "Te avisaremos aquí cuando se valide."
    )

    # Reenviar al chat del admin con botones Validar/Rechazar
    client_data = database.get_client_by_id(client_id)
    tipo = "Renovación" if is_renewal else "Alta nueva"

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Validar", callback_data=f"pago_validar_{payment_id}"),
         InlineKeyboardButton("❌ Rechazar", callback_data=f"pago_rechazar_{payment_id}")]
    ])

    for admin_id in ADMIN_IDS:
        await context.bot.send_photo(
            chat_id=admin_id,
            photo=photo_file_id,
            caption=(
                f"💳 *{tipo} de pago*\n\n"
                f"Usuario VPN: `{client_data['softether_username']}`\n"
                f"Telegram ID: `{client_data['telegram_id']}`\n"
                f"Pago ID: {payment_id}"
            ),
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    context.user_data.pop("client_id", None)
    context.user_data.pop("is_renewal", None)
    context.user_data.pop("reg_username", None)
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# /estado — consulta rápida del propio cliente
# ---------------------------------------------------------------------------

async def estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    client_data = database.get_client_by_telegram_id(update.effective_user.id)
    if not client_data:
        await update.message.reply_text("No tienes una cuenta registrada. Usa /registrar.")
        return

    estado_txt = {
        "pendiente": "⏳ Pendiente de validación de pago",
        "activo": "🟢 Activo",
        "por_vencer": "🟡 Activo (por vencer pronto)",
        "bloqueado": "🔴 Bloqueado (contrato vencido)",
    }.get(client_data["status"], client_data["status"])

    mensaje = f"Usuario VPN: `{client_data['softether_username']}`\nEstado: {estado_txt}\n"
    if client_data.get("expires_at"):
        mensaje += f"Vence: {client_data['expires_at'][:10]}\n"

    await update.message.reply_text(mensaje, parse_mode="Markdown")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


def register_handlers(app: Application):
    conv_registrar = ConversationHandler(
        entry_points=[CommandHandler("registrar", start_registrar)],
        states={
            USERNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_username)],
            PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, step_password)],
            ESPERANDO_CAPTURA: [MessageHandler(filters.PHOTO, step_recibir_captura)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    conv_renovar = ConversationHandler(
        entry_points=[CommandHandler("renovar", start_renovar)],
        states={
            ESPERANDO_CAPTURA: [MessageHandler(filters.PHOTO, step_recibir_captura)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_registrar)
    app.add_handler(conv_renovar)
    app.add_handler(CommandHandler("estado", estado))
