import gettext
import asyncio
import os
import logging
from aiogram import BaseMiddleware
from aiogram.types import Update
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web
from tortoise import Tortoise
from tortoise.contrib.aiohttp import register_tortoise
from aiogram.utils.i18n import I18n
from pathlib import Path


from middlewares import CustomI18nMiddleware
from models import *
from db_config import TORTOISE_ORM
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_TOKEN = '7326893496:AAGb7q9DFtquWq0yEj5qM9q6pRmd0ZYV3Ok'
I18N_DOMAIN = 'messages'
LOCALES_DIR = os.path.join(os.path.dirname(__file__), 'locale')



i18n = I18n(domain=I18N_DOMAIN, path=LOCALES_DIR)


bot = Bot(token=API_TOKEN)
storage = MemoryStorage()

dp = Dispatcher(bot=bot, storage=storage,)
CustomI18nMiddleware(i18n).setup(dp)


# dp.update.middleware(CustomI18nMiddleware(i18n))
# dp.update.outer_middleware(CustomI18nMiddleware(i18n))

async def on_startup(app):
    await Tortoise.init(config=TORTOISE_ORM)
    await Tortoise.generate_schemas()
    logger.info("Database initialized successfully")
    await start_all()


async def on_shutdown(app):
    await Tortoise.close_connections()


async def start_all():
    from data.scheduler import start_scheduler
    await start_scheduler()


app = web.Application()
app.on_startup.append(on_startup)
app.on_cleanup.append(on_shutdown)

register_tortoise(app, config=TORTOISE_ORM)


async def main():
    logger.info("Starting bot")
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()
    logger.info("Bot started and listening for updates")

    from data import gift, language, location, verify
    from handlers import profile, profiles, registration, start
    dp.include_router(router)
    dp.include_router(start.router)
    dp.include_router(registration.router)
    dp.include_router(profiles.router)
    dp.include_router(profile.router)
    dp.include_router(gift.router)
    dp.include_router(language.router)
    dp.include_router(location.router)
    dp.include_router(verify.router)
    logger.info("Starting polling")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"An error occurred in the main loop: {e}", exc_info=True)
