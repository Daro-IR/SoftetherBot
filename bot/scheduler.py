"""
scheduler.py — Job periódico (cada hora) que:
  1. Avisa a los clientes cuyo contrato vence en <= 4 días
     (día 27 de 31, según CONTRACT_WARNING_DAYS_BEFORE) y aún no
     se les avisó.
  2. Bloquea automáticamente (mueve a grupo 'pendientes' en SoftEther
     y marca 'bloqueado' en la BD) a los clientes cuyo contrato ya venció
     y no renovaron.
"""

import os
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram.ext import Application

from db import database
from softether_client import SoftEtherClient, GROUP_PENDIENTES
from game_manager.manager import backup_server

logger = logging.getLogger(__name__)

WARNING_DAYS_BEFORE = int(os.getenv("CONTRACT_WARNING_DAYS_BEFORE", "4"))


def _get_softether_client() -> SoftEtherClient:
    return SoftEtherClient(
        base_url=os.getenv("SOFTETHER_JSONRPC_URL"),
        hub_name=os.getenv("SOFTETHER_HUB_NAME"),
        admin_password=os.getenv("SOFTETHER_ADMIN_PASSWORD"),
    )


async def _job_avisos_y_bloqueos(app: Application):
    # --- Avisos de vencimiento próximo (día 27) ---
    por_avisar = database.get_clients_needing_warning(WARNING_DAYS_BEFORE)
    for client_data in por_avisar:
        try:
            await app.bot.send_message(
                chat_id=client_data["telegram_id"],
                text=(
                    "🟡 Tu contrato de acceso VPN está por vencer pronto "
                    f"(vence el {client_data['expires_at'][:10]}). "
                    "Usa /renovar para no perder el acceso."
                ),
            )
            database.mark_warning_sent(client_data["id"])
        except Exception as e:
            logger.warning(f"No se pudo avisar a {client_data['telegram_id']}: {e}")

    # --- Bloqueo automático de contratos vencidos ---
    vencidos = database.get_clients_expired()
    if vencidos:
        hub_name = os.getenv("SOFTETHER_HUB_NAME")
        try:
            client = _get_softether_client()
        except Exception as e:
            logger.error(f"No se pudo conectar a SoftEther para bloquear vencidos: {e}")
            client = None

        for client_data in vencidos:
            if client:
                try:
                    client.move_user_to_group(
                        hub_name, client_data["softether_username"], GROUP_PENDIENTES
                    )
                except Exception as e:
                    logger.error(
                        f"No se pudo bloquear en SoftEther a "
                        f"{client_data['softether_username']}: {e}"
                    )
                    continue  # no marcar bloqueado en BD si falló en SoftEther

            database.block_client(client_data["id"])
            try:
                await app.bot.send_message(
                    chat_id=client_data["telegram_id"],
                    text=(
                        "🔴 Tu contrato venció y tu acceso a la LAN fue bloqueado. "
                        "Usa /renovar para recuperar el acceso."
                    ),
                )
            except Exception as e:
                logger.warning(f"No se pudo notificar bloqueo a {client_data['telegram_id']}: {e}")


async def _job_backup_diario(app: Application):
    try:
        result = await __import__('asyncio').to_thread(backup_server, None, True)
        logger.info('Backup automático creado: %s (%s)', result['name'], result.get('telegram'))
    except Exception as e:
        logger.error('Backup automático falló: %s', e)



def start_scheduler(app: Application):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _job_avisos_y_bloqueos,
        "interval",
        hours=1,
        args=[app],
        id="avisos_y_bloqueos",
        next_run_time=None,  # arranca en el primer intervalo, no inmediatamente
    )
    scheduler.add_job(
        _job_backup_diario,
        "interval",
        hours=int(os.getenv("BACKUP_INTERVAL_HOURS", "24")),
        args=[app],
        id="backup_diario",
        next_run_time=None,
    )
    scheduler.start()
    logger.info("Scheduler de avisos/bloqueos iniciado (cada 1 hora)")
