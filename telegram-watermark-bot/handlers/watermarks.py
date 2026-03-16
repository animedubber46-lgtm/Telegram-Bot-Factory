from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    get_watermarks, get_watermark, delete_watermark, update_watermark,
    is_banned, set_state, get_state, clear_state, update_state
)
from utils.helpers import wm_summary

# Reuse keyboards from add_watermark
from handlers.add_watermark import pos_keyboard, anim_keyboard, color_keyboard, yes_no_keyboard


def _watermark_list_keyboard(watermarks: list, suffix: str = "manage") -> InlineKeyboardMarkup:
    buttons = []
    for i, wm in enumerate(watermarks):
        name = wm.get("name", f"Watermark {i+1}")
        wm_id = str(wm["_id"])
        icon = "🔤" if wm.get("type") == "text" else "🖼"
        buttons.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"wm_{suffix}_{wm_id}")])
    buttons.append([InlineKeyboardButton("➕ Add New Watermark", callback_data="add_watermark")])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="start_menu")])
    return InlineKeyboardMarkup(buttons)


def _edit_fields_keyboard(wm: dict) -> InlineKeyboardMarkup:
    """Show editable fields based on watermark type."""
    wm_id = str(wm["_id"])
    wm_type = wm.get("type", "text")
    rows = []

    if wm_type == "text":
        rows = [
            [InlineKeyboardButton("📝 Text",        callback_data=f"wm_ef_{wm_id}_text")],
            [
                InlineKeyboardButton("🔡 Font Size",  callback_data=f"wm_ef_{wm_id}_font_size"),
                InlineKeyboardButton("🎨 Color",      callback_data=f"wm_ef_{wm_id}_font_color"),
            ],
            [
                InlineKeyboardButton("🔆 Opacity",    callback_data=f"wm_ef_{wm_id}_opacity"),
                InlineKeyboardButton("📍 Position",   callback_data=f"wm_ef_{wm_id}_position"),
            ],
            [
                InlineKeyboardButton("🎬 Animation",  callback_data=f"wm_ef_{wm_id}_animation"),
                InlineKeyboardButton("↔️ Margin",     callback_data=f"wm_ef_{wm_id}_margin"),
            ],
            [
                InlineKeyboardButton("Bold ✏️",       callback_data=f"wm_ef_{wm_id}_bold"),
                InlineKeyboardButton("Shadow 🌑",     callback_data=f"wm_ef_{wm_id}_shadow"),
                InlineKeyboardButton("Box 📦",        callback_data=f"wm_ef_{wm_id}_box"),
            ],
        ]
    else:  # image
        rows = [
            [
                InlineKeyboardButton("📏 Scale %",    callback_data=f"wm_ef_{wm_id}_scale"),
                InlineKeyboardButton("🔆 Opacity",    callback_data=f"wm_ef_{wm_id}_opacity"),
            ],
            [
                InlineKeyboardButton("📍 Position",   callback_data=f"wm_ef_{wm_id}_position"),
                InlineKeyboardButton("🎬 Animation",  callback_data=f"wm_ef_{wm_id}_animation"),
            ],
            [InlineKeyboardButton("↔️ Margin",        callback_data=f"wm_ef_{wm_id}_margin")],
        ]

    rows.append([InlineKeyboardButton("🔙 Back", callback_data=f"wm_manage_{wm_id}")])
    return InlineKeyboardMarkup(rows)


def register_watermark_handlers(app: Client):

    # ─── /mywatermarks ────────────────────────────────────────────────────

    @app.on_message(filters.command("mywatermarks") & filters.private)
    async def my_watermarks_cmd(client: Client, message: Message):
        if await is_banned(message.from_user.id):
            return
        await show_watermarks(client, message.from_user.id, message.chat.id)

    @app.on_callback_query(filters.regex("^my_watermarks$"))
    async def my_watermarks_cb(client: Client, callback_query: CallbackQuery):
        await show_watermarks(client, callback_query.from_user.id,
                              callback_query.message.chat.id, callback_query.message)

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

    # ─── Manage (view detail) ──────────────────────────────────────────────

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

    # ─── Edit (field picker) ───────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^wm_edit_(.+)$"))
    async def edit_watermark(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        user_id = callback_query.from_user.id
        wm = await get_watermark(user_id, wm_id)
        if not wm:
            await callback_query.answer("Watermark not found!", show_alert=True)
            return

        await callback_query.message.edit_text(
            f"✏️ **Edit Watermark: {wm.get('name', 'Unnamed')}**\n\nWhich setting do you want to change?",
            reply_markup=_edit_fields_keyboard(wm),
        )

    # ─── Edit field selected → prompt user ────────────────────────────────

    @app.on_callback_query(filters.regex(r"^wm_ef_([^_]+)_(.+)$"))
    async def edit_field_selected(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        wm_id = callback_query.matches[0].group(1)
        field = callback_query.matches[0].group(2)

        wm = await get_watermark(user_id, wm_id)
        if not wm:
            await callback_query.answer("Watermark not found!", show_alert=True)
            return

        current = wm.get(field, "—")
        set_state(user_id, {"step": "editing_field", "wm_id": wm_id, "field": field})

        # Fields that use inline keyboards
        if field == "position":
            await callback_query.message.edit_text(
                f"📍 **Edit Position** (current: `{current}`)\n\nChoose a new position:",
                reply_markup=pos_keyboard(f"wm_ef_update_{wm_id}_position"),
            )
        elif field == "animation":
            await callback_query.message.edit_text(
                f"🎬 **Edit Animation** (current: `{current}`)\n\nChoose a new animation:",
                reply_markup=anim_keyboard(f"wm_ef_update_{wm_id}_animation"),
            )
        elif field == "font_color":
            await callback_query.message.edit_text(
                f"🎨 **Edit Color** (current: `{current}`)\n\nChoose a new color:",
                reply_markup=color_keyboard(f"wm_ef_update_{wm_id}_font_color"),
            )
        elif field == "bold":
            await callback_query.message.edit_text(
                f"**Edit Bold** (current: `{'Yes' if current else 'No'}`)\n\nEnable bold text?",
                reply_markup=yes_no_keyboard(
                    f"wm_ef_update_{wm_id}_bold_yes",
                    f"wm_ef_update_{wm_id}_bold_no"
                ),
            )
        elif field == "shadow":
            await callback_query.message.edit_text(
                f"**Edit Shadow** (current: `{'Yes' if current else 'No'}`)\n\nEnable text shadow?",
                reply_markup=yes_no_keyboard(
                    f"wm_ef_update_{wm_id}_shadow_yes",
                    f"wm_ef_update_{wm_id}_shadow_no"
                ),
            )
        elif field == "box":
            await callback_query.message.edit_text(
                f"**Edit Background Box** (current: `{'Yes' if current else 'No'}`)\n\nEnable background box?",
                reply_markup=yes_no_keyboard(
                    f"wm_ef_update_{wm_id}_box_yes",
                    f"wm_ef_update_{wm_id}_box_no"
                ),
            )
        else:
            # Text input fields
            hints = {
                "text":      "Send the new **watermark text**.",
                "font_size": "Send the new **font size** (10–200).",
                "opacity":   "Send the new **opacity** (0.1–1.0).",
                "scale":     "Send the new **scale** in % (1–80).",
                "margin":    "Send **margin** as `x,y` (e.g. `10,10`).",
            }
            hint = hints.get(field, f"Send the new value for **{field}**.")
            await callback_query.message.edit_text(
                f"✏️ Current value: `{current}`\n\n{hint}\n\n/cancel to abort."
            )

    # ─── Edit field update via inline (position / animation / color / bool) ─

    @app.on_callback_query(filters.regex(r"^wm_ef_update_([^_]+)_position_(.+)$"))
    async def update_position(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        value = callback_query.matches[0].group(2)
        user_id = callback_query.from_user.id
        if value == "custom":
            update_state(user_id, "step", "editing_field")
            update_state(user_id, "field", "position")
            update_state(user_id, "wm_id", wm_id)
            await callback_query.message.edit_text(
                "✏️ Send custom position as `x,y` in pixels (e.g. `50,30`).\n/cancel to abort."
            )
            return
        await _save_field(callback_query, user_id, wm_id, "position", value)

    @app.on_callback_query(filters.regex(r"^wm_ef_update_([^_]+)_animation_(.+)$"))
    async def update_animation(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        value = callback_query.matches[0].group(2)
        user_id = callback_query.from_user.id
        await _save_field(callback_query, user_id, wm_id, "animation", value)

    @app.on_callback_query(filters.regex(r"^wm_ef_update_([^_]+)_font_color_(.+)$"))
    async def update_color(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        value = callback_query.matches[0].group(2)
        user_id = callback_query.from_user.id
        if value == "custom":
            update_state(user_id, "step", "editing_field")
            update_state(user_id, "field", "font_color_hex")
            update_state(user_id, "wm_id", wm_id)
            await callback_query.message.edit_text(
                "✏️ Send a custom color as 6-digit hex (e.g. `FF5500` for orange).\n/cancel to abort."
            )
            return
        await _save_field(callback_query, user_id, wm_id, "font_color", value)

    @app.on_callback_query(filters.regex(r"^wm_ef_update_([^_]+)_(bold|shadow|box)_(yes|no)$"))
    async def update_bool_field(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        field = callback_query.matches[0].group(2)
        value = callback_query.matches[0].group(3) == "yes"
        user_id = callback_query.from_user.id
        await _save_field(callback_query, user_id, wm_id, field, value)

    async def _save_field(callback_query, user_id, wm_id, field, value):
        """Save a single field to MongoDB and show confirmation."""
        clear_state(user_id)
        await update_watermark(user_id, wm_id, {field: value})
        wm = await get_watermark(user_id, wm_id)
        await callback_query.answer(f"✅ {field.replace('_', ' ').title()} updated!", show_alert=False)
        await callback_query.message.edit_text(
            f"✏️ **Edit Watermark: {wm.get('name', 'Unnamed')}**\n\nWhich setting do you want to change?",
            reply_markup=_edit_fields_keyboard(wm),
        )

    # ─── Edit field update via text message ───────────────────────────────

    @app.on_message(filters.text & filters.private)
    async def text_state_handler(client: Client, message: Message):
        user_id = message.from_user.id
        if message.text.startswith("/"):
            return
        if await is_banned(user_id):
            return
        state = get_state(user_id)
        if not state:
            return

        step = state.get("step")

        # ── Rename ──
        if step == "renaming":
            wm_id = state.get("wm_id")
            new_name = message.text.strip()
            if len(new_name) > 50:
                await message.reply_text("❌ Name too long (max 50 chars). Try again.")
                return
            await update_watermark(user_id, wm_id, {"name": new_name})
            clear_state(user_id)
            await message.reply_text(f"✅ Watermark renamed to **{new_name}**!")

        # ── Edit field (text input) ──
        elif step == "editing_field":
            wm_id = state.get("wm_id")
            field = state.get("field")
            raw = message.text.strip()

            if field == "text":
                if len(raw) > 200:
                    await message.reply_text("❌ Too long (max 200 chars).")
                    return
                await update_watermark(user_id, wm_id, {"text": raw})
                clear_state(user_id)
                await message.reply_text(f"✅ Watermark text updated to: `{raw}`")

            elif field == "font_size":
                try:
                    val = int(raw)
                    if not (10 <= val <= 200):
                        raise ValueError
                except ValueError:
                    await message.reply_text("❌ Send a number between 10 and 200.")
                    return
                await update_watermark(user_id, wm_id, {"font_size": val})
                clear_state(user_id)
                await message.reply_text(f"✅ Font size updated to: `{val}`")

            elif field == "opacity":
                try:
                    val = float(raw)
                    if not (0.0 < val <= 1.0):
                        raise ValueError
                except ValueError:
                    await message.reply_text("❌ Send a number between 0.1 and 1.0 (e.g. `0.8`).")
                    return
                await update_watermark(user_id, wm_id, {"opacity": val})
                clear_state(user_id)
                await message.reply_text(f"✅ Opacity updated to: `{val}`")

            elif field == "scale":
                try:
                    val = int(raw)
                    if not (1 <= val <= 80):
                        raise ValueError
                except ValueError:
                    await message.reply_text("❌ Send a number between 1 and 80.")
                    return
                await update_watermark(user_id, wm_id, {"scale": val})
                clear_state(user_id)
                await message.reply_text(f"✅ Scale updated to: `{val}%`")

            elif field == "margin":
                try:
                    parts = raw.split(",")
                    mx = int(parts[0].strip())
                    my = int(parts[1].strip()) if len(parts) > 1 else mx
                    if mx < 0 or my < 0:
                        raise ValueError
                except Exception:
                    await message.reply_text("❌ Send as `x,y` (e.g. `10,10`).")
                    return
                await update_watermark(user_id, wm_id, {"margin_x": mx, "margin_y": my})
                clear_state(user_id)
                await message.reply_text(f"✅ Margin updated to: `{mx},{my}`")

            elif field == "position":
                try:
                    parts = raw.split(",")
                    x, y = int(parts[0].strip()), int(parts[1].strip())
                    if x < 0 or y < 0:
                        raise ValueError
                except Exception:
                    await message.reply_text("❌ Send as `x,y` (e.g. `50,30`).")
                    return
                await update_watermark(user_id, wm_id, {"position": f"{x},{y}"})
                clear_state(user_id)
                await message.reply_text(f"✅ Position updated to: `{x},{y}`")

            elif field == "font_color_hex":
                color = raw.lstrip("#")
                if not (len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color)):
                    await message.reply_text("❌ Invalid hex. Send 6-digit hex like `FF5500`.")
                    return
                await update_watermark(user_id, wm_id, {"font_color": f"#{color}"})
                clear_state(user_id)
                await message.reply_text(f"✅ Color updated to: `#{color}`")

            else:
                clear_state(user_id)

    # ─── Rename ───────────────────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^wm_rename_(.+)$"))
    async def rename_start(client: Client, callback_query: CallbackQuery):
        wm_id = callback_query.matches[0].group(1)
        user_id = callback_query.from_user.id
        set_state(user_id, {"step": "renaming", "wm_id": wm_id})
        await callback_query.message.edit_text(
            "🏷 **Rename Watermark**\n\nSend me the new name.\n\n/cancel to abort."
        )

    # ─── Delete ───────────────────────────────────────────────────────────

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
                InlineKeyboardButton("❌ Cancel",      callback_data=f"wm_manage_{wm_id}"),
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
        await show_watermarks(client, callback_query.from_user.id,
                              callback_query.message.chat.id, callback_query.message)
