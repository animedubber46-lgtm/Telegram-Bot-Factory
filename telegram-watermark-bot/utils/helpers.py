import os
import time
import asyncio
import shutil
from pyrogram.types import Message
from config import TEMP_DIR


async def download_file(client, message: Message, progress_msg, label: str = "Downloading") -> str:
    """Download a file from a Telegram message with progress updates."""
    start = time.time()
    last_update = [0.0]

    async def progress(current, total):
        if total == 0:
            return
        pct = int(current / total * 100)
        elapsed = time.time() - start
        speed = current / elapsed if elapsed > 0 else 0
        speed_str = _format_speed(speed)
        eta = int((total - current) / speed) if speed > 0 else 0

        # Throttle updates to every 5%
        if pct - last_update[0] >= 5 or pct >= 99:
            last_update[0] = pct
            bar = _progress_bar(pct)
            try:
                await progress_msg.edit_text(
                    f"**{label}...**\n"
                    f"{bar} `{pct}%`\n"
                    f"Speed: `{speed_str}` | ETA: `{eta}s`"
                )
            except Exception:
                pass

    file_path = await message.download(
        file_name=TEMP_DIR + "/",
        progress=progress,
    )
    return file_path


async def upload_file(client, chat_id: int, file_path: str, progress_msg, caption: str = "") -> bool:
    """Upload a file to Telegram with progress updates."""
    start = time.time()
    last_update = [0.0]

    async def progress(current, total):
        if total == 0:
            return
        pct = int(current / total * 100)
        elapsed = time.time() - start
        speed = current / elapsed if elapsed > 0 else 0
        speed_str = _format_speed(speed)
        eta = int((total - current) / speed) if speed > 0 else 0

        if pct - last_update[0] >= 5 or pct >= 99:
            last_update[0] = pct
            bar = _progress_bar(pct)
            try:
                await progress_msg.edit_text(
                    f"**Uploading...**\n"
                    f"{bar} `{pct}%`\n"
                    f"Speed: `{speed_str}` | ETA: `{eta}s`"
                )
            except Exception:
                pass

    try:
        await client.send_video(
            chat_id=chat_id,
            video=file_path,
            caption=caption,
            progress=progress,
            supports_streaming=True,
        )
        return True
    except Exception as e:
        print(f"[Upload Error] {e}")
        return False


def _progress_bar(pct: int, length: int = 12) -> str:
    filled = int(length * pct / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}]"


def _format_speed(bps: float) -> str:
    if bps < 1024:
        return f"{bps:.0f} B/s"
    elif bps < 1024 ** 2:
        return f"{bps/1024:.1f} KB/s"
    else:
        return f"{bps/1024**2:.1f} MB/s"


def cleanup(*paths: str):
    """Delete temp files safely."""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"[Cleanup] Could not remove {path}: {e}")


def get_output_path(input_path: str, suffix: str = "_wm") -> str:
    """Generate output file path next to input with suffix."""
    base, ext = os.path.splitext(input_path)
    return base + suffix + (ext or ".mp4")


def wm_summary(wm: dict) -> str:
    """Format a watermark dict into a readable summary."""
    wm_type = wm.get("type", "text")
    name = wm.get("name", "Unnamed")
    lines = [f"**{name}**", f"Type: `{wm_type}`"]

    if wm_type == "text":
        lines.append(f"Text: `{wm.get('text', '')}`")
        lines.append(f"Position: `{wm.get('position', 'bottom-right')}`")
        lines.append(f"Font size: `{wm.get('font_size', 36)}`")
        lines.append(f"Color: `{wm.get('font_color', 'white')}`")
        lines.append(f"Opacity: `{wm.get('opacity', 0.8)}`")
        lines.append(f"Animation: `{wm.get('animation', 'static')}`")
        if wm.get("shadow"):
            lines.append("Shadow: ✅")
        if wm.get("box"):
            lines.append("Background box: ✅")
    else:
        lines.append(f"Position: `{wm.get('position', 'bottom-right')}`")
        lines.append(f"Scale: `{wm.get('scale', 15)}%`")
        lines.append(f"Opacity: `{wm.get('opacity', 0.8)}`")
        lines.append(f"Animation: `{wm.get('animation', 'static')}`")

    return "\n".join(lines)
