from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from database import add_user, is_banned, clear_state
from config import OWNER_ID


START_TEXT = """
👋 **Welcome to WatermarkBot!**

I can add professional watermarks to your videos — both **text** and **image/logo** watermarks.

**What I can do:**
• Save multiple watermark presets
• Apply text watermarks with custom fonts, colors, animations
• Apply image/logo overlays with transparency
• Preserve your video quality

**How to use:**
1. Set up a watermark with /addwatermark
2. Send me any video
3. Choose which watermark to apply
4. Receive your watermarked video!

**Commands:**
/start — This message
/help — Detailed help
/mywatermarks — View & manage your saved watermarks
/addwatermark — Create a new watermark preset
/settings — Bot settings
/cancel — Cancel current operation
"""

HELP_TEXT = """
**📖 WatermarkBot Help**

**Creating a watermark:**
Use /addwatermark and follow the steps. You can create:
- **Text watermarks** — custom text with font, color, size, opacity, position, and animation
- **Image watermarks** — upload a PNG logo, set position, scale, and opacity

**Watermark options:**
• **Position:** top-left, top-right, bottom-left, bottom-right, center, or custom x,y
• **Opacity:** 0.1 (barely visible) to 1.0 (fully opaque)
• **Animations:** static, fade-in, fade-out, blink, slide-left, slide-right, float
• **Text only:** font size, color, bold, shadow, background box

**Applying a watermark:**
Just send a video! I'll ask which saved watermark to use.

**Managing watermarks:**
Use /mywatermarks to view, edit, rename, or delete your presets.

**Video support:**
• Formats: MP4, MKV, MOV (and most others)
• Max size: 2 GB
• Quality is preserved — I use CRF 18 encoding
"""


def register_start_handlers(app: Client):

    @app.on_message(filters.command("start") & filters.private)
    async def start_handler(client: Client, message: Message):
        user = message.from_user
        if await is_banned(user.id):
            await message.reply_text("❌ You are banned from using this bot.")
            return

        await add_user(user.id, user.username, user.full_name)
        clear_state(user.id)

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Add Watermark", callback_data="add_watermark"),
                InlineKeyboardButton("📋 My Watermarks", callback_data="my_watermarks"),
            ],
            [
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ])

        await message.reply_text(START_TEXT, reply_markup=keyboard)

    @app.on_message(filters.command("help") & filters.private)
    async def help_handler(client: Client, message: Message):
        if await is_banned(message.from_user.id):
            return
        await message.reply_text(HELP_TEXT)

    @app.on_message(filters.command("cancel") & filters.private)
    async def cancel_handler(client: Client, message: Message):
        clear_state(message.from_user.id)
        await message.reply_text("✅ Operation cancelled. Send a video or use /addwatermark to start.")

    @app.on_callback_query(filters.regex("^help$"))
    async def help_callback(client: Client, callback_query):
        await callback_query.message.edit_text(HELP_TEXT)

    @app.on_callback_query(filters.regex("^start_menu$"))
    async def start_menu_callback(client: Client, callback_query):
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("➕ Add Watermark", callback_data="add_watermark"),
                InlineKeyboardButton("📋 My Watermarks", callback_data="my_watermarks"),
            ],
            [InlineKeyboardButton("❓ Help", callback_data="help")],
        ])
        await callback_query.message.edit_text(START_TEXT, reply_markup=keyboard)
