"""
admin_flow.py — Botones "Validar"/"Rechazar" que recibe el admin cuando
un cliente envía un comprobante de pago (ver client_flow.py).

Lógica de expiración al validar (ver /areas/bot-softether-vps.md):
  - Si la cuenta está bloqueada o es alta nueva -> nueva expiración =
    ahora + CONTRACT_DURATION_DAYS.
  - Si la cuenta sigue activa/por_vencer (renovó antes de vencer) ->
    nueva expiración = expiración actual + CONTRACT_DURATION_DAYS
    (se acumula, no se reinicia).
"""

import os
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

from db import database
from softether_client import SoftEtherClient, GROUP_APROBADOS

CONTRACT_DURATION_DAYS = int(os.getenv("CONTRACT_DURATION_DAYS", "31"))
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]


def _get_softether_client() -> SoftEtherClient:
    return SoftEtherClient(
        base_url=os.getenv("SOFTETHER_JSONRPC_URL"),
        hub_name=os.getenv("SOFTETHER_HUB_NAME"),
        admin_password=os.getenv("SOFTETHER_ADMIN_PASSWORD"),
    )


async def handle_payment_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id not in ADMIN_IDS:
        await query.answer("Solo un administrador puede hacer esto.", show_alert=True)
        return

    action, payment_id_str = query.data.rsplit("_", 1)
    payment_id = int(payment_id_str)
    payment = database.get_payment(payment_id)

    if not payment:
        await query.edit_message_caption(caption="Este pago ya no existe.")
        return

    if payment["decision"] != "pendiente":
        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n(Ya fue {payment['decision']} anteriormente)"
        )
        return

    client_data = database.get_client_by_id(payment["client_id"])
    hub_name = os.getenv("SOFTETHER_HUB_NAME")

    if query.data.startswith("pago_validar_"):
        database.decide_payment(payment_id, "validado", query.from_user.id)

        # La cuenta estaba bloqueada/pendiente (nunca tuvo acceso, o venció)
        # si status NO es 'activo'/'por_vencer' -> no se acumula, se cuenta
        # desde ahora. Si YA estaba activa (renovación anticipada) -> se
        # suma al vencimiento vigente.
        estaba_activa = client_data["status"] in ("activo", "por_vencer")

        nueva_expiracion = database.activate_client_contract(
            client_id=client_data["id"],
            duration_days=CONTRACT_DURATION_DAYS,
            extend_from_expiry=estaba_activa,
        )

        # Dar acceso real a la LAN moviendo el usuario al grupo "aprobados"
        try:
            client = _get_softether_client()
            client.move_user_to_group(hub_name, client_data["softether_username"], GROUP_APROBADOS)
        except Exception as e:
            await query.message.reply_text(
                f"⚠️ Pago validado en la base de datos, pero falló darle "
                f"acceso en SoftEther: {e}\nRevisar manualmente."
            )

        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n✅ VALIDADO por {query.from_user.first_name}"
        )

        await context.bot.send_message(
            chat_id=client_data["telegram_id"],
            text=(
                "✅ Tu pago fue validado. Ya tienes acceso a la LAN.\n"
                f"Tu contrato vence el: {nueva_expiracion.strftime('%Y-%m-%d')}"
            ),
        )

    elif query.data.startswith("pago_rechazar_"):
        database.decide_payment(payment_id, "rechazado", query.from_user.id)

        # Si era un alta nueva (cuenta nunca aprobada) y se rechaza, se
        # elimina la cuenta huérfana de SoftEther. Si era una renovación
        # sobre una cuenta ya aprobada antes, NO se toca su acceso actual
        # (rechazar la renovación no debe quitarle lo que ya tenía).
        if not payment["is_renewal"] and client_data["status"] == "pendiente":
            try:
                client = _get_softether_client()
                client.delete_user(hub_name, client_data["softether_username"])
            except Exception as e:
                await query.message.reply_text(
                    f"⚠️ No se pudo eliminar la cuenta huérfana en SoftEther: {e}"
                )

        await query.edit_message_caption(
            caption=f"{query.message.caption}\n\n❌ RECHAZADO por {query.from_user.first_name}"
        )

        await context.bot.send_message(
            chat_id=client_data["telegram_id"],
            text="❌ Tu pago no pudo ser validado. Contacta al administrador si crees que es un error.",
        )


def register_handlers(app: Application):
    app.add_handler(CallbackQueryHandler(handle_payment_decision, pattern=r"^pago_(validar|rechazar)_\d+$"))
