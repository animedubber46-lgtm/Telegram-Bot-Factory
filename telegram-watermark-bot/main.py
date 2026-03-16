import asyncio
import logging
from pyrogram import Client
from config import API_ID, API_HASH, BOT_TOKEN

# Import all handlers
from handlers.start import register_start_handlers
from handlers.add_watermark import register_add_watermark_handlers
from handlers.watermarks import register_watermark_handlers
from handlers.video import register_video_handlers
from handlers.admin import register_admin_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_bot() -> Client:
    app = Client(
        "watermark_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
    )
    return app


async def main():
    logger.info("Starting WatermarkBot...")

    app = create_bot()

    # Register all handlers
    register_start_handlers(app)
    register_add_watermark_handlers(app)
    register_watermark_handlers(app)
    register_video_handlers(app)
    register_admin_handlers(app)

    logger.info("All handlers registered. Bot is starting...")

    async with app:
        me = await app.get_me()
        logger.info(f"Bot started as @{me.username} (ID: {me.id})")
        await asyncio.Event().wait()  # Run forever


if __name__ == "__main__":
    asyncio.run(main())
