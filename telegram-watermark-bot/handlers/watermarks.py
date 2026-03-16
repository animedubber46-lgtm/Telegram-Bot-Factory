from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    get_watermarks, get_watermark, delete_watermark, update_watermark,
    count_watermarks, is_banned, set_state, get_state, clear_state, update_state
)
from utils.helpers import wm_summary


def _watermark_list_keyboard(watermarks: list, suffix: str = "manage") -> InlineKeyboardMarkup:
    buttons = []
    for i, wm in enumerate(watermarks):
        name = wm.get("name", f"Watermark {i+1}")
        wm_id = str(wm["_id"])
        buttons.append([InlineKeyboardButton(f"{'🔤' if wm.get('type') == 'text' else '🖼'} {name}", callback_data=f"wm_{suffix}_{wm_id}")])
    buttons.append([InlineKeyboardButton("➕ Add New Watermark", callback_data="add_watermark")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="start_menu")])
    return InlineKeyboardMarkup(buttons)


def register_watermark_handlers(app: Client):

    @app.on_message(filters.command("mywatermarks") & filters.private)
    async def my_watermarks_cmd(client: Client, message: Message):
        if await is_banned(message.from_user.id):
            return
        await show_watermarks(client, message.from_user.id, message.chat.id)

    @app.on_callback_query(filters.regex("^my_watermarks$"))
    async def my_watermarks_cb(client: Client, callback_query: CallbackQuery):
        await show_watermarks(client, callback_query.from_user.id, callback_query.message.chat.id, callback_query.message)

    async def show_watermarks(client, user_id, chat_id, edit_msg=None):
        watermarks = await get_watermarks(user_id)
        if not watermarks:
            text = "📋 **Your Watermarks**\n\nYou have no saved watermarks yet.\nUse /addwatermark to create one!"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("➕ Add Watermark", callback_data="add_watermark")],
                [InlineKeyboardButton("🔙 Back", callback_data="start_menu")],
            ])
        else:
            text = f"📋 **Your Watermarks** ({len(watermarks)} saved)\n\nSelect a watermark to manage:"
            keyboard = _watermark_list_keyboard(watermarks, suffix="manage")

        if edit_msg:
            await edit_msg.edit_text(text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text, reply_markup=keyboard)

    @app.on_callback_query(filters.regex(r"^wm_manage_(.+)$"))
    async def manage_watermark(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        user_id = callback_query.from_user.id
        wm = await get_watermark(user_id, wm_id)
        if not wm:
            await callback_query.answer("Watermark not found!", show_alert=True)
            return

        summary = wm_summary(wm)
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✏️ Edit", callback_data=f"wm_edit_{wm_id}"),
                InlineKeyboardButton("🏷 Rename", callback_data=f"wm_rename_{wm_id}"),
            ],
            [InlineKeyboardButton("🗑 Delete", callback_data=f"wm_delete_confirm_{wm_id}")],
            [InlineKeyboardButton("🔙 Back", callback_data="my_watermarks")],
        ])
        await callback_query.message.edit_text(
            f"**Watermark Details**\n\n{summary}",
            reply_markup=keyboard,
        )

    @app.on_callback_query(filters.regex(r"^wm_delete_confirm_(.+)$"))
    async def delete_confirm(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        wm = await get_watermark(callback_query.from_user.id, wm_id)
        if not wm:
            await callback_query.answer("Not found!", show_alert=True)
            return
        name = wm.get("name", "this watermark")
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"wm_delete_do_{wm_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"wm_manage_{wm_id}"),
            ]
        ])
        await callback_query.message.edit_text(
            f"⚠️ Are you sure you want to delete **{name}**?",
            reply_markup=keyboard,
        )

    @app.on_callback_query(filters.regex(r"^wm_delete_do_(.+)$"))
    async def delete_do(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        await delete_watermark(callback_query.from_user.id, wm_id)
        await callback_query.answer("✅ Watermark deleted!", show_alert=True)
        await show_watermarks(client, callback_query.from_user.id, callback_query.message.chat.id, callback_query.message)

    @app.on_callback_query(filters.regex(r"^wm_rename_(.+)$"))
    async def rename_start(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        user_id = callback_query.from_user.id
        set_state(user_id, {"step": "renaming", "wm_id": wm_id})
        await callback_query.message.edit_text(
            "✏️ **Rename Watermark**\n\nSend me the new name for this watermark.\n\n/cancel to abort."
        )

    @app.on_message(filters.text & filters.private)
    async def text_state_handler(client: Client, message: Message):
        user_id = message.from_user.id
        if await is_banned(user_id):
            return
        state = get_state(user_id)
        if not state:
            return

        step = state.get("step")

        if step == "renaming":
            wm_id = state.get("wm_id")
            new_name = message.text.strip()
            if len(new_name) > 50:
                await message.reply_text("❌ Name too long (max 50 chars). Try again.")
                return
            await update_watermark(user_id, wm_id, {"name": new_name})
            clear_state(user_id)
            await message.reply_text(f"✅ Watermark renamed to **{new_name}**!")

        elif step == "editing_field":
            # Handled by add_watermark flow
            pass
