import os
import asyncio
import shlex
from config import POSITION_MAP, DEFAULT_FONT_REGULAR, DEFAULT_FONT_BOLD, FALLBACK_FONT, TEMP_DIR


def _escape_text(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def _get_font(bold: bool = False) -> str:
    """Return path to appropriate font file. Bold is achieved by using the bold font variant."""
    if bold:
        if os.path.exists(DEFAULT_FONT_BOLD):
            return DEFAULT_FONT_BOLD
    if os.path.exists(DEFAULT_FONT_REGULAR):
        return DEFAULT_FONT_REGULAR
    return FALLBACK_FONT


def build_text_filter(settings: dict) -> str:
    """Build FFmpeg drawtext filter string from watermark settings."""
    bold = settings.get("bold", True)
    text = _escape_text(settings.get("text", "Watermark"))
    font = _get_font(bold=bold)          # bold selects the bold font file
    fontsize = int(settings.get("font_size", 36))
    color = settings.get("font_color", "white")
    opacity = float(settings.get("opacity", 0.8))
    position = settings.get("position", "bottom-right")
    margin_x = int(settings.get("margin_x", 10))
    margin_y = int(settings.get("margin_y", 10))
    shadow = settings.get("shadow", True)
    box = settings.get("box", False)
    box_color = settings.get("box_color", "black@0.4")
    animation = settings.get("animation", "static")

    # Build alpha expression based on animation
    alpha_expr = _build_alpha_expr(animation, opacity)

    # Build x/y from position
    x_expr, y_expr = _position_to_expr(position, margin_x, margin_y)

    parts = [
        f"fontfile={font}",
        f"text='{text}'",
        f"fontsize={fontsize}",
        f"fontcolor={color}@{opacity:.2f}",
        f"x={x_expr}",
        f"y={y_expr}",
    ]

    if shadow:
        parts += ["shadowcolor=black@0.5", "shadowx=2", "shadowy=2"]

    if box:
        parts += ["box=1", f"boxcolor={box_color}", "boxborderw=6"]

    # NOTE: fontstyle=bold is NOT supported by FFmpeg drawtext.
    # Bold is handled above by selecting the bold font file variant.

    if alpha_expr:
        # Replace fontcolor opacity with animated alpha
        parts = [p for p in parts if not p.startswith("fontcolor")]
        parts.append(f"fontcolor={color}")
        parts.append(f"alpha='{alpha_expr}'")

    return "drawtext=" + ":".join(parts)


def _position_to_expr(position: str, mx: int, my: int) -> tuple:
    if position in POSITION_MAP:
        x, y = POSITION_MAP[position]
        # Add margin
        if "W-w" in x:
            x = f"W-w-{mx}"
        elif x == "10":
            x = str(mx)
        if "H-h" in y:
            y = f"H-h-{my}"
        elif y == "10":
            y = str(my)
        return x, y
    # custom "x,y"
    if "," in str(position):
        parts = str(position).split(",")
        return parts[0].strip(), parts[1].strip()
    return str(mx), str(my)


def _build_alpha_expr(animation: str, opacity: float) -> str:
    if animation == "static":
        return ""
    elif animation == "fade-in":
        return f"if(lt(t,2),t/2,{opacity})"
    elif animation == "fade-out":
        return f"if(gt(t,max(0\\,duration-2)),(duration-t)/2,{opacity})"
    elif animation == "blink":
        return f"if(lt(mod(t\\,1.5)\\,0.75)\\,{opacity}\\,0)"
    elif animation == "slide-left":
        # Slide in from left (handled via x expression instead, return empty)
        return ""
    elif animation == "slide-right":
        return ""
    elif animation == "float":
        return f"{opacity}"
    return ""


def build_text_filter_with_animation(settings: dict) -> tuple:
    """Returns (vf_filter_string, extra_x_override) for animated positions."""
    animation = settings.get("animation", "static")
    base = build_text_filter(settings)

    if animation == "slide-left":
        # Slide from off-screen left to final position
        position = settings.get("position", "bottom-right")
        margin_x = int(settings.get("margin_x", 10))
        margin_y = int(settings.get("margin_y", 10))
        x_final, y_expr = _position_to_expr(position, margin_x, margin_y)
        # Override the x in drawtext
        base = base.replace(f"x={x_final}", f"x=if(lt(t\\,2)\\,W*t/2-w\\,{x_final})")

    elif animation == "slide-right":
        position = settings.get("position", "bottom-left")
        margin_x = int(settings.get("margin_x", 10))
        margin_y = int(settings.get("margin_y", 10))
        x_final, y_expr = _position_to_expr(position, margin_x, margin_y)
        base = base.replace(f"x={x_final}", f"x=if(lt(t\\,2)\\,W-W*t/2\\,{x_final})")

    elif animation == "float":
        # Subtle vertical float
        y_part = [p for p in base.split(":") if p.startswith("y=")]
        if y_part:
            y_val = y_part[0].replace("y=", "")
            base = base.replace(f"y={y_val}", f"y={y_val}+5*sin(2*PI*t/3)")

    return base


async def apply_text_watermark(
    input_path: str,
    output_path: str,
    settings: dict,
    progress_callback=None,
) -> bool:
    """Apply text watermark using FFmpeg drawtext filter."""
    vf = build_text_filter_with_animation(settings)

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path
    ]

    return await _run_ffmpeg(cmd, progress_callback)


async def _run_ffmpeg(cmd: list, progress_callback=None) -> bool:
    """Run FFmpeg command asynchronously with optional progress reporting."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stderr_lines = []
    duration = None
    last_progress = 0

    while True:
        line = await proc.stderr.readline()
        if not line:
            break
        line_str = line.decode("utf-8", errors="replace").strip()
        stderr_lines.append(line_str)

        # Parse duration
        if "Duration:" in line_str and duration is None:
            try:
                dur_str = line_str.split("Duration:")[1].split(",")[0].strip()
                h, m, s = dur_str.split(":")
                duration = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                pass

        # Parse progress
        if "time=" in line_str and duration and progress_callback:
            try:
                time_str = line_str.split("time=")[1].split(" ")[0].strip()
                h, m, s = time_str.split(":")
                current = int(h) * 3600 + int(m) * 60 + float(s)
                pct = min(int((current / duration) * 100), 99)
                if pct > last_progress + 4:
                    last_progress = pct
                    await progress_callback(pct)
            except Exception:
                pass

    await proc.wait()

    if proc.returncode != 0:
        print("[FFmpeg Error]\n" + "\n".join(stderr_lines[-20:]))
        return False
    return True
