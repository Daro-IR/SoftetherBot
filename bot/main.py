"""
main.py — Punto de entrada de SoftetherBot.

Al arrancar:
  1. Inicializa la base de datos (crea tablas si no existen).
  2. Si el Setup Wizard NUNCA se completó -> solo registra los handlers
     del wizard (el bot "no funciona" para nada más hasta terminarlo).
  3. Si el Setup Wizard ya se completó -> registra los handlers normales
     (registro de clientes, pagos, admin, dashboard) y arranca el
     scheduler de vencimientos de contrato.
"""

import os
import logging
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder

from db import database
from handlers import setup_wizard, client_flow, admin_flow, dashboard
from scheduler import start_scheduler

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    database.init_db()

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Falta TELEGRAM_BOT_TOKEN en el .env")

    app = ApplicationBuilder().token(token).build()

    if not database.is_setup_completed():
        logger.info("Setup Wizard no completado — arrancando en modo instalación")
        setup_wizard.register_handlers(app)
    else:
        logger.info("Setup Wizard ya completado — arrancando en modo normal")
        client_flow.register_handlers(app)
        admin_flow.register_handlers(app)
        dashboard.register_handlers(app)
        start_scheduler(app)

    app.run_polling()


if __name__ == "__main__":
    main()
