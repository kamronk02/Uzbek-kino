import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import BOT_TOKEN, WEBHOOK_URL, WEB_ADMIN_ENABLED
from database import init_db
from handlers import router
from web_admin import create_web_app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


async def main():
    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    if WEBHOOK_URL:
        app = create_web_app(bot, dp) if WEB_ADMIN_ENABLED else web.Application()
        SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
        setup_application(app, dp, bot=bot)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.getenv("PORT", "10000"))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await bot.set_webhook(WEBHOOK_URL.rstrip("/") + "/webhook")
        await site.start()
        log.info("Webhook va web-admin server port %s da ishga tushdi", port)
        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()
            await bot.delete_webhook()
            await bot.session.close()
    else:
        # Render Web Service ochiq port kutadi. Polling bilan birga
        # oddiy health-check serverini ham ishga tushiramiz.
        app = web.Application()

        async def health_check(request):
            return web.Response(text="Telegram bot ishlayapti.")

        app.router.add_get("/", health_check)
        app.router.add_get("/health", health_check)

        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.getenv("PORT", "10000"))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        log.info("Health-check server %s-portda ishga tushdi; bot polling rejimida.", port)

        try:
            await dp.start_polling(bot)
        finally:
            await runner.cleanup()
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
