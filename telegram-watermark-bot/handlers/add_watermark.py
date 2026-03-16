import os
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    add_watermark, count_watermarks, is_banned,
    set_state, get_state, clear_state, update_state
)
from config import TEMP_DIR

MAX_WATERMARKS = 10

# ─── Step flow helpers ───────────────────────────────────────────────────────

POSITIONS = ["top-left", "top-right", "bottom-left", "bottom-right", "center"]
ANIMATIONS = ["static", "fade-in", "fade-out", "blink", "slide-left", "slide-right", "float"]

ANIMATION_LABELS = {
    "static":     "None (No Animation)",
    "fade-in":    "Fade In",
    "fade-out":   "Fade Out",
    "blink":      "Blink",
    "slide-left": "Slide Left",
    "slide-right":"Slide Right",
    "float":      "Float",
}
COLORS = ["white", "black", "red", "yellow", "blue", "green", "cyan", "magenta", "orange"]


def pos_keyboard(cb_prefix: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for p in POSITIONS:
        row.append(InlineKeyboardButton(p.replace("-", " ").title(), callback_data=f"{cb_prefix}_{p}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✏️ Custom x,y", callback_data=f"{cb_prefix}_custom")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_creation")])
    return InlineKeyboardMarkup(rows)


def anim_keyboard(cb_prefix: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for a in ANIMATIONS:
        label = ANIMATION_LABELS.get(a, a.replace("-", " ").title())
        row.append(InlineKeyboardButton(label, callback_data=f"{cb_prefix}_{a}"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_creation")])
    return InlineKeyboardMarkup(rows)


def color_keyboard(cb_prefix: str) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for c in COLORS:
        row.append(InlineKeyboardButton(c.title(), callback_data=f"{cb_prefix}_{c}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("✏️ Custom hex (#RRGGBB)", callback_data=f"{cb_prefix}_custom")])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_creation")])
    return InlineKeyboardMarkup(rows)


def yes_no_keyboard(yes_cb: str, no_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Yes", callback_data=yes_cb),
            InlineKeyboardButton("❌ No", callback_data=no_cb),
        ]
    ])


def register_add_watermark_handlers(app: Client):

    # ─── Entry points ─────────────────────────────────────────────────────

    @app.on_message(filters.command("addwatermark") & filters.private)
    async def addwatermark_cmd(client: Client, message: Message):
        if await is_banned(message.from_user.id):
            return
        await start_creation(client, message.from_user.id, message.chat.id)

    @app.on_callback_query(filters.regex("^add_watermark$"))
    async def add_watermark_cb(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        await start_creation(client, user_id, callback_query.message.chat.id, callback_query.message)

    async def start_creation(client, user_id, chat_id, edit_msg=None):
        count = await count_watermarks(user_id)
        if count >= MAX_WATERMARKS:
            text = f"❌ You already have {MAX_WATERMARKS} watermarks saved (max). Delete some first."
            if edit_msg:
                await edit_msg.edit_text(text)
            else:
                await client.send_message(chat_id, text)
            return

        set_state(user_id, {"step": "choose_type", "chat_id": chat_id})
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔤 Text Watermark", callback_data="wm_type_text"),
                InlineKeyboardButton("🖼 Image Watermark", callback_data="wm_type_image"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_creation")],
        ])
        text = "➕ **Create New Watermark**\n\nWhat type of watermark do you want to create?"
        if edit_msg:
            await edit_msg.edit_text(text, reply_markup=keyboard)
        else:
            await client.send_message(chat_id, text, reply_markup=keyboard)

    @app.on_callback_query(filters.regex("^cancel_creation$"))
    async def cancel_creation(client: Client, callback_query: CallbackQuery):
        clear_state(callback_query.from_user.id)
        await callback_query.message.edit_text("❌ Watermark creation cancelled.")

    # ─── Type selection ────────────────────────────────────────────────────

    @app.on_callback_query(filters.regex("^wm_type_(text|image)$"))
    async def choose_type(client: Client, callback_query: CallbackQuery):
        wm_type = callback_query.matches[0].group(1)
        user_id = callback_query.from_user.id
        update_state(user_id, "type", wm_type)

        if wm_type == "text":
            update_state(user_id, "step", "ask_name")
            await callback_query.message.edit_text(
                "🔤 **Text Watermark — Step 1/8**\n\n"
                "Send me the **name** for this watermark preset (e.g. \"My Logo\").\n\n"
                "/cancel to abort."
            )
        else:
            update_state(user_id, "step", "ask_name")
            await callback_query.message.edit_text(
                "🖼 **Image Watermark — Step 1/6**\n\n"
                "Send me the **name** for this watermark preset (e.g. \"Company Logo\").\n\n"
                "/cancel to abort."
            )

    # ─── Text watermark flow ───────────────────────────────────────────────

    @app.on_message(filters.text & filters.private)
    async def text_input_handler(client: Client, message: Message):
        user_id = message.from_user.id
        if message.text.startswith("/"):
            return
        if await is_banned(user_id):
            return
        state = get_state(user_id)
        if not state:
            return

        step = state.get("step")
        wm_type = state.get("type", "text")

        # ── Common: name ──
        if step == "ask_name":
            name = message.text.strip()
            if len(name) > 50:
                await message.reply_text("❌ Name too long (max 50 chars). Try again.")
                return
            update_state(user_id, "name", name)
            if wm_type == "text":
                update_state(user_id, "step", "ask_text")
                await message.reply_text(
                    f"✅ Name set: **{name}**\n\n"
                    "🔤 **Step 2/8** — Send me the **watermark text** to display on the video."
                )
            else:
                update_state(user_id, "step", "ask_image")
                await message.reply_text(
                    f"✅ Name set: **{name}**\n\n"
                    "🖼 **Step 2/6** — Send me the **logo/image** (PNG preferred for transparency)."
                )

        elif step == "ask_text":
            text_val = message.text.strip()
            if len(text_val) > 200:
                await message.reply_text("❌ Text too long (max 200 chars). Try again.")
                return
            update_state(user_id, "text", text_val)
            update_state(user_id, "step", "ask_fontsize")
            await message.reply_text(
                f"✅ Text set: `{text_val}`\n\n"
                "**Step 3/8** — Send the **font size** (number, e.g. `36`). Range: 10–200."
            )

        elif step == "ask_fontsize":
            try:
                fs = int(message.text.strip())
                if not (10 <= fs <= 200):
                    raise ValueError
            except ValueError:
                await message.reply_text("❌ Please send a number between 10 and 200.")
                return
            update_state(user_id, "font_size", fs)
            update_state(user_id, "step", "ask_color")
            await message.reply_text(
                f"✅ Font size: `{fs}`\n\n"
                "**Step 4/8** — Choose a **font color**:",
                reply_markup=color_keyboard("wm_color"),
            )

        elif step == "ask_custom_color":
            color = message.text.strip().lstrip("#")
            if not (len(color) == 6 and all(c in "0123456789abcdefABCDEF" for c in color)):
                await message.reply_text("❌ Invalid hex color. Send 6-digit hex like `FF5500`.")
                return
            update_state(user_id, "font_color", f"#{color}")
            await _after_color(client, message, user_id)

        elif step == "ask_opacity":
            try:
                op = float(message.text.strip())
                if not (0.0 < op <= 1.0):
                    raise ValueError
            except ValueError:
                await message.reply_text("❌ Please send a number between 0.1 and 1.0 (e.g. `0.8`).")
                return
            update_state(user_id, "opacity", op)
            update_state(user_id, "step", "ask_position")
            await message.reply_text(
                f"✅ Opacity: `{op}`\n\n"
                "**Step 6/8** — Choose **position**:",
                reply_markup=pos_keyboard("wm_pos"),
            )

        elif step == "ask_custom_pos":
            try:
                parts = message.text.strip().split(",")
                x, y = int(parts[0].strip()), int(parts[1].strip())
                if x < 0 or y < 0:
                    raise ValueError
            except Exception:
                await message.reply_text("❌ Invalid format. Send like `50,30` (x,y in pixels).")
                return
            update_state(user_id, "position", f"{x},{y}")
            await _after_position(client, message, user_id)

        elif step == "ask_margin":
            try:
                parts = message.text.strip().split(",")
                mx = int(parts[0].strip())
                my = int(parts[1].strip()) if len(parts) > 1 else mx
            except Exception:
                await message.reply_text("❌ Invalid format. Send like `10,10` or just `10`.")
                return
            update_state(user_id, "margin_x", mx)
            update_state(user_id, "margin_y", my)
            if wm_type == "text":
                await _finish_text_watermark(client, message, user_id)
            else:
                await _finish_image_watermark(client, message, user_id)

        elif step == "ask_image_scale":
            try:
                sc = int(message.text.strip())
                if not (1 <= sc <= 80):
                    raise ValueError
            except ValueError:
                await message.reply_text("❌ Please send a number between 1 and 80 (percent).")
                return
            update_state(user_id, "scale", sc)
            update_state(user_id, "step", "ask_opacity")
            await message.reply_text(
                f"✅ Scale: `{sc}%`\n\n"
                "**Step 4/6** — Send the **opacity** (0.1–1.0, e.g. `0.8`)."
            )

        elif step == "ask_opacity_image":
            try:
                op = float(message.text.strip())
                if not (0.0 < op <= 1.0):
                    raise ValueError
            except ValueError:
                await message.reply_text("❌ Please send a number between 0.1 and 1.0.")
                return
            update_state(user_id, "opacity", op)
            update_state(user_id, "step", "ask_position")
            await message.reply_text(
                f"✅ Opacity: `{op}`\n\n"
                "**Step 5/6** — Choose **position**:",
                reply_markup=pos_keyboard("wm_pos"),
            )

    # ─── Color callback ────────────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^wm_color_(.+)$"))
    async def choose_color(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        color = callback_query.matches[0].group(1)
        if color == "custom":
            update_state(user_id, "step", "ask_custom_color")
            await callback_query.message.edit_text(
                "✏️ Send a custom color as 6-digit hex (without #).\nExample: `FF5500` for orange."
            )
        else:
            update_state(user_id, "font_color", color)
            await _after_color(client, callback_query.message, user_id, is_callback=True)

    async def _after_color(client, msg_or_cb, user_id, is_callback=False):
        update_state(user_id, "step", "ask_bold")
        keyboard = yes_no_keyboard("wm_bold_yes", "wm_bold_no")
        text = "✅ Color set!\n\n**Step 5/8** — Do you want the text to be **bold**?"
        if is_callback:
            await msg_or_cb.edit_text(text, reply_markup=keyboard)
        else:
            await msg_or_cb.reply_text(text, reply_markup=keyboard)

    @app.on_callback_query(filters.regex("^wm_bold_(yes|no)$"))
    async def choose_bold(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        bold = callback_query.matches[0].group(1) == "yes"
        update_state(user_id, "bold", bold)
        update_state(user_id, "step", "ask_shadow")
        keyboard = yes_no_keyboard("wm_shadow_yes", "wm_shadow_no")
        await callback_query.message.edit_text(
            f"✅ Bold: {'✅' if bold else '❌'}\n\n**Step 5.5** — Add a **shadow** under the text?"
            , reply_markup=keyboard
        )

    @app.on_callback_query(filters.regex("^wm_shadow_(yes|no)$"))
    async def choose_shadow(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        shadow = callback_query.matches[0].group(1) == "yes"
        update_state(user_id, "shadow", shadow)
        update_state(user_id, "step", "ask_box")
        keyboard = yes_no_keyboard("wm_box_yes", "wm_box_no")
        await callback_query.message.edit_text(
            f"✅ Shadow: {'✅' if shadow else '❌'}\n\n**Step 5.7** — Add a **background box** behind the text?"
            , reply_markup=keyboard
        )

    @app.on_callback_query(filters.regex("^wm_box_(yes|no)$"))
    async def choose_box(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        box = callback_query.matches[0].group(1) == "yes"
        update_state(user_id, "box", box)
        update_state(user_id, "step", "ask_opacity")
        await callback_query.message.edit_text(
            f"✅ Box: {'✅' if box else '❌'}\n\n**Step 6/8** — Send the **opacity** (0.1–1.0, e.g. `0.8`).\n"
            "`1.0` = fully visible, `0.1` = nearly transparent."
        )

    # ─── Position callback ────────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^wm_pos_(.+)$"))
    async def choose_position(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        pos = callback_query.matches[0].group(1)
        if pos == "custom":
            update_state(user_id, "step", "ask_custom_pos")
            await callback_query.message.edit_text(
                "✏️ Send custom position as `x,y` in pixels (from top-left).\nExample: `50,30`"
            )
        else:
            update_state(user_id, "position", pos)
            await _after_position(client, callback_query.message, user_id, is_callback=True)

    async def _after_position(client, msg, user_id, is_callback=False):
        update_state(user_id, "step", "ask_animation")
        text = "✅ Position set!\n\n**Step 7/8** — Choose an **animation**:"
        keyboard = anim_keyboard("wm_anim")
        if is_callback:
            await msg.edit_text(text, reply_markup=keyboard)
        else:
            await msg.reply_text(text, reply_markup=keyboard)

    # ─── Animation callback ───────────────────────────────────────────────

    @app.on_callback_query(filters.regex(r"^wm_anim_(.+)$"))
    async def choose_animation(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        anim = callback_query.matches[0].group(1)
        update_state(user_id, "animation", anim)
        update_state(user_id, "step", "ask_margin")
        await callback_query.message.edit_text(
            f"✅ Animation: `{anim}`\n\n**Step 8/8** — Send **margin** as `x,y` in pixels (e.g. `10,10`).\n"
            "This is the padding from the edge of the video."
        )

    # ─── Image watermark: photo upload ────────────────────────────────────

    @app.on_message(filters.photo & filters.private)
    async def photo_input_handler(client: Client, message: Message):
        user_id = message.from_user.id
        if await is_banned(user_id):
            return
        state = get_state(user_id)
        if not state or state.get("step") != "ask_image":
            return

        progress_msg = await message.reply_text("⬇️ Downloading your logo...")
        logo_path = await message.download(file_name=f"{TEMP_DIR}/logo_{user_id}.png")
        update_state(user_id, "logo_path", logo_path)
        update_state(user_id, "step", "ask_image_scale")
        await progress_msg.edit_text(
            "✅ Logo received!\n\n"
            "**Step 3/6** — Send the **scale** as a percentage of video width.\n"
            "Example: `15` means 15% of video width. Range: 1–80."
        )

    @app.on_message(filters.document & filters.private)
    async def doc_input_handler(client: Client, message: Message):
        """Accept PNG/image documents as logo."""
        user_id = message.from_user.id
        if await is_banned(user_id):
            return
        state = get_state(user_id)
        if not state or state.get("step") != "ask_image":
            return

        mime = message.document.mime_type or ""
        if not mime.startswith("image/"):
            await message.reply_text("❌ Please send an image file (PNG preferred for transparency).")
            return

        progress_msg = await message.reply_text("⬇️ Downloading your logo...")
        logo_path = await message.download(file_name=f"{TEMP_DIR}/logo_{user_id}.png")
        update_state(user_id, "logo_path", logo_path)
        update_state(user_id, "step", "ask_image_scale")
        await progress_msg.edit_text(
            "✅ Logo received!\n\n"
            "**Step 3/6** — Send the **scale** as a percentage of video width.\n"
            "Example: `15` means 15% of video width. Range: 1–80."
        )

    # ─── Image opacity handler (separate step key) ────────────────────────

    # Note: ask_opacity_image handled in text_input_handler above

    # ─── Finalize ─────────────────────────────────────────────────────────

    async def _finish_text_watermark(client, message, user_id):
        state = get_state(user_id)
        wm_data = {
            "type": "text",
            "name": state.get("name", "Watermark"),
            "text": state.get("text", "Watermark"),
            "font_size": state.get("font_size", 36),
            "font_color": state.get("font_color", "white"),
            "bold": state.get("bold", True),
            "shadow": state.get("shadow", True),
            "box": state.get("box", False),
            "opacity": state.get("opacity", 0.8),
            "position": state.get("position", "bottom-right"),
            "margin_x": state.get("margin_x", 10),
            "margin_y": state.get("margin_y", 10),
            "animation": state.get("animation", "static"),
        }
        wm_id = await add_watermark(user_id, wm_data)
        clear_state(user_id)
        from utils.helpers import wm_summary
        summary = wm_summary(wm_data)
        await message.reply_text(
            f"✅ **Watermark saved!**\n\n{summary}\n\n"
            "Send me a video to apply it, or use /mywatermarks to manage your presets."
        )

    async def _finish_image_watermark(client, message, user_id):
        state = get_state(user_id)
        wm_data = {
            "type": "image",
            "name": state.get("name", "Image Watermark"),
            "logo_path": state.get("logo_path", ""),
            "scale": state.get("scale", 15),
            "opacity": state.get("opacity", 0.8),
            "position": state.get("position", "bottom-right"),
            "margin_x": state.get("margin_x", 10),
            "margin_y": state.get("margin_y", 10),
            "animation": state.get("animation", "static"),
        }
        wm_id = await add_watermark(user_id, wm_data)
        clear_state(user_id)
        from utils.helpers import wm_summary
        summary = wm_summary(wm_data)
        await message.reply_text(
            f"✅ **Watermark saved!**\n\n{summary}\n\n"
            "Send me a video to apply it, or use /mywatermarks to manage your presets."
        )

    # ─── Image watermark: opacity handled in text step handler ────────────
    # Re-use the same step key, route by wm_type

    @app.on_message(filters.text & filters.private)
    async def image_opacity_handler(client: Client, message: Message):
        """Handle opacity step for image watermarks separately."""
        pass  # Handled in the combined text_input_handler above
