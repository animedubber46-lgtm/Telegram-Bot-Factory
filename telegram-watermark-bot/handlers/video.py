import os
import time
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database import (
    get_watermarks, get_watermark, is_banned, is_processing,
    set_processing, clear_processing, log_task, add_user,
    get_state, set_state, clear_state
)
from utils.helpers import upload_file, cleanup, get_output_path, wm_summary
from watermark.ffmpeg_text import apply_text_watermark
from watermark.ffmpeg_image import apply_image_watermark
from config import MAX_FILE_SIZE, TEMP_DIR


def _progress_bar(pct: int, length: int = 12) -> str:
    filled = int(length * pct / 100)
    return "[" + "█" * filled + "░" * (length - filled) + "]"


def register_video_handlers(app: Client):

    @app.on_message((filters.video | filters.document) & filters.private)
    async def video_received(client: Client, message: Message):
        user_id = message.from_user.id

        # Guard: ignore if we're in a watermark creation step
        state = get_state(user_id)
        if state and state.get("step") in (
            "ask_image", "ask_image_scale", "ask_opacity_image",
        ):
            return

        if await is_banned(user_id):
            await message.reply_text("❌ You are banned from using this bot.")
            return

        # Check file type for documents — only accept video MIME
        if message.document:
            mime = message.document.mime_type or ""
            if not mime.startswith("video/"):
                return

        # Check size
        file_size = (message.video.file_size if message.video else message.document.file_size) or 0
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                f"❌ File too large! Maximum supported size is **2 GB**.\n"
                f"Your file: `{file_size / 1024**3:.2f} GB`"
            )
            return

        # One active task per user
        if is_processing(user_id):
            await message.reply_text(
                "⏳ You already have a video being processed. Please wait for it to finish."
            )
            return

        u = message.from_user
        full_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
        await add_user(user_id, u.username, full_name)

        # Get saved watermarks
        watermarks = await get_watermarks(user_id)
        if not watermarks:
            await message.reply_text(
                "📋 You have no saved watermarks yet!\n\n"
                "Use /addwatermark to create your first watermark preset, then send this video again."
            )
            return

        # Save the message ID so we can re-fetch it when the user picks a watermark
        set_state(user_id, {
            "step": "awaiting_wm_selection",
            "video_message_id": message.id,
            "chat_id": message.chat.id,
        })

        # Build watermark selection keyboard
        buttons = []
        for i, wm in enumerate(watermarks):
            name = wm.get("name", f"Watermark {i+1}")
            icon = "🔤" if wm.get("type") == "text" else "🖼"
            wm_id = str(wm["_id"])
            buttons.append([InlineKeyboardButton(f"{icon} {name}", callback_data=f"apply_wm_{wm_id}")])

        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel_apply")])

        await message.reply_text(
            "🎬 **Video received!**\n\nWhich watermark would you like to apply?",
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    @app.on_callback_query(filters.regex("^cancel_apply$"))
    async def cancel_apply(client: Client, callback_query: CallbackQuery):
        clear_state(callback_query.from_user.id)
        await callback_query.message.edit_text("❌ Watermark application cancelled.")

    @app.on_callback_query(filters.regex(r"^apply_wm_(.+)$"))
    async def apply_wm_callback(client: Client, callback_query: CallbackQuery):
        user_id = callback_query.from_user.id
        wm_id = callback_query.matches[0].group(1)

        state = get_state(user_id)
        if not state or state.get("step") != "awaiting_wm_selection":
            await callback_query.answer("Session expired. Please send the video again.", show_alert=True)
            return

        if is_processing(user_id):
            await callback_query.answer("Already processing! Please wait.", show_alert=True)
            return

        wm = await get_watermark(user_id, wm_id)
        if not wm:
            await callback_query.answer("Watermark not found!", show_alert=True)
            return

        video_message_id = state.get("video_message_id")
        chat_id = state.get("chat_id")
        clear_state(user_id)
        set_processing(user_id)

        progress_msg = await callback_query.message.edit_text(
            f"⬇️ **Downloading video...**\n{_progress_bar(0)} `0%`"
        )

        input_path = None
        output_path = None

        try:
            # Re-fetch the original video message
            video_msg = await client.get_messages(chat_id, video_message_id)

            # Build a safe destination path with .mp4 extension
            ts = int(time.time())
            input_path = os.path.join(TEMP_DIR, f"input_{user_id}_{ts}.mp4")

            # Track last reported percent to avoid Telegram flood
            last_pct = [-1]

            async def dl_progress(current, total):
                if not total:
                    return
                pct = int(current / total * 100)
                if pct - last_pct[0] >= 5 or pct >= 99:
                    last_pct[0] = pct
                    try:
                        await progress_msg.edit_text(
                            f"⬇️ **Downloading video...**\n{_progress_bar(pct)} `{pct}%`"
                        )
                    except Exception:
                        pass

            # Single download into our explicit temp path
            await video_msg.download(file_name=input_path, progress=dl_progress)

            if not os.path.exists(input_path):
                raise FileNotFoundError(f"Download failed — file not found at {input_path}")

            await progress_msg.edit_text(
                f"⚙️ **Processing video...**\n{_progress_bar(0)} `0%`\n_Applying watermark..._"
            )

            output_path = os.path.join(TEMP_DIR, f"output_{user_id}_{ts}.mp4")

            last_proc_pct = [-1]

            async def proc_progress(pct):
                if pct - last_proc_pct[0] >= 5:
                    last_proc_pct[0] = pct
                    try:
                        await progress_msg.edit_text(
                            f"⚙️ **Processing video...**\n{_progress_bar(pct)} `{pct}%`\n_Applying watermark..._"
                        )
                    except Exception:
                        pass

            wm_type = wm.get("type", "text")
            success = False

            if wm_type == "text":
                success = await apply_text_watermark(input_path, output_path, wm, proc_progress)
            elif wm_type == "image":
                logo_path = wm.get("logo_path", "")
                if not os.path.exists(logo_path):
                    await progress_msg.edit_text(
                        "❌ The logo file for this watermark is missing.\n"
                        "Please re-create the image watermark with /addwatermark."
                    )
                    await log_task(user_id, "failed", wm_type, "logo missing")
                    return
                success = await apply_image_watermark(input_path, output_path, logo_path, wm, proc_progress)

            if not success:
                await progress_msg.edit_text(
                    "❌ **Processing failed!**\n\n"
                    "FFmpeg could not apply the watermark. Please try again or use /addwatermark to recreate your preset."
                )
                await log_task(user_id, "failed", wm_type, "ffmpeg error")
                return

            await progress_msg.edit_text(
                f"⬆️ **Uploading video...**\n{_progress_bar(0)} `0%`"
            )

            wm_name = wm.get("name", "Watermark")
            uploaded = await upload_file(
                client,
                chat_id,
                output_path,
                progress_msg,
                caption=f"✅ Watermark applied: **{wm_name}**",
            )

            if uploaded:
                await progress_msg.delete()
                await log_task(user_id, "completed", wm_type)
            else:
                await progress_msg.edit_text(
                    "❌ **Upload failed!**\n\nCould not send the video back. Please try again."
                )
                await log_task(user_id, "failed", wm_type, "upload error")

        except Exception as e:
            print(f"[Video Handler Error] {e}")
            await log_task(user_id, "failed", error=str(e))
            try:
                await progress_msg.edit_text(
                    f"❌ **An error occurred:**\n`{str(e)[:300]}`\n\nPlease try again."
                )
            except Exception:
                pass
        finally:
            clear_processing(user_id)
            cleanup(input_path, output_path)
