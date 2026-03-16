from pyrogram import Client, filters
from pyrogram.types import Message
from database import (
    get_all_users, get_total_users, get_total_tasks,
    ban_user, unban_user, is_banned
)
from config import OWNER_ID


def owner_only(func):
    """Decorator: restrict handler to OWNER_ID only."""
    async def wrapper(client: Client, message: Message):
        if message.from_user.id != OWNER_ID:
            await message.reply_text("❌ This command is for the bot owner only.")
            return
        await func(client, message)
    return wrapper


def register_admin_handlers(app: Client):

    @app.on_message(filters.command("stats") & filters.private)
    @owner_only
    async def stats_handler(client: Client, message: Message):
        total_users = await get_total_users()
        total_tasks = await get_total_tasks()
        await message.reply_text(
            f"📊 **Bot Statistics**\n\n"
            f"👥 Total Users: `{total_users}`\n"
            f"🎬 Videos Processed: `{total_tasks}`\n"
        )

    @app.on_message(filters.command("broadcast") & filters.private)
    @owner_only
    async def broadcast_handler(client: Client, message: Message):
        if not message.reply_to_message:
            await message.reply_text(
                "❌ Reply to a message with /broadcast to send it to all users."
            )
            return

        users = await get_all_users()
        sent = 0
        failed = 0
        status_msg = await message.reply_text(f"📢 Broadcasting to {len(users)} users...")

        for user in users:
            try:
                await message.reply_to_message.copy(user["user_id"])
                sent += 1
            except Exception:
                failed += 1

        await status_msg.edit_text(
            f"📢 **Broadcast complete!**\n\n"
            f"✅ Sent: `{sent}`\n"
            f"❌ Failed: `{failed}`"
        )

    @app.on_message(filters.command("ban") & filters.private)
    @owner_only
    async def ban_handler(client: Client, message: Message):
        args = message.command[1:]
        if not args:
            await message.reply_text("Usage: /ban <user_id>")
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await message.reply_text("❌ Invalid user ID.")
            return
        if target_id == OWNER_ID:
            await message.reply_text("❌ Cannot ban the owner!")
            return
        await ban_user(target_id)
        await message.reply_text(f"✅ User `{target_id}` has been banned.")

    @app.on_message(filters.command("unban") & filters.private)
    @owner_only
    async def unban_handler(client: Client, message: Message):
        args = message.command[1:]
        if not args:
            await message.reply_text("Usage: /unban <user_id>")
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await message.reply_text("❌ Invalid user ID.")
            return
        await unban_user(target_id)
        await message.reply_text(f"✅ User `{target_id}` has been unbanned.")

    @app.on_message(filters.command("users") & filters.private)
    @owner_only
    async def users_handler(client: Client, message: Message):
        total = await get_total_users()
        await message.reply_text(f"👥 Total registered users: `{total}`")

    @app.on_message(filters.command("checkban") & filters.private)
    @owner_only
    async def checkban_handler(client: Client, message: Message):
        args = message.command[1:]
        if not args:
            await message.reply_text("Usage: /checkban <user_id>")
            return
        try:
            target_id = int(args[0])
        except ValueError:
            await message.reply_text("❌ Invalid user ID.")
            return
        banned = await is_banned(target_id)
        status = "🔴 Banned" if banned else "🟢 Not banned"
        await message.reply_text(f"User `{target_id}`: {status}")
