import os
import asyncio
from config import POSITION_MAP, DEFAULT_FONT_REGULAR, DEFAULT_FONT_BOLD, FALLBACK_FONT


FFMPEG_ERROR_LOG = "/tmp/ffmpeg_error.log"


def _escape_text(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    text = str(text)
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    text = text.replace(",", "\\,")
    text = text.replace("[", "\\[")
    text = text.replace("]", "\\]")
    return text


def _get_font(bold: bool = False) -> str:
    """Return path to appropriate font file."""
    if bold and os.path.exists(DEFAULT_FONT_BOLD):
        return DEFAULT_FONT_BOLD
    if os.path.exists(DEFAULT_FONT_REGULAR):
        return DEFAULT_FONT_REGULAR
    return FALLBACK_FONT


def _normalize_position_expr(expr: str, axis: str, margin: int) -> str:
    """
    Normalize position expressions so they work with FFmpeg drawtext.
    Supports older values like W-w-10 / H-h-10 and converts them.
    """
    expr = str(expr).strip()

    replacements = {
        "W": "w",
        "H": "h",
        "TEXT_W": "text_w",
        "TEXT_H": "text_h",
        "TW": "text_w",
        "TH": "text_h",
    }

    for old, new in replacements.items():
        expr = expr.replace(old, new)

    expr = expr.replace("w-w", "w-text_w")
    expr = expr.replace("h-h", "h-text_h")
    expr = expr.replace("w-tw", "w-text_w")
    expr = expr.replace("h-th", "h-text_h")

    if axis == "x":
        if expr == "10":
            return str(margin)
        if "w-text_w-10" in expr:
            return expr.replace("w-text_w-10", f"w-text_w-{margin}")
    else:
        if expr == "10":
            return str(margin)
        if "h-text_h-10" in expr:
            return expr.replace("h-text_h-10", f"h-text_h-{margin}")

    return expr


def _position_to_expr(position: str, mx: int, my: int) -> tuple[str, str]:
    """Convert configured position into FFmpeg drawtext x/y expressions."""
    if position in POSITION_MAP:
        x, y = POSITION_MAP[position]
        x = _normalize_position_expr(x, "x", mx)
        y = _normalize_position_expr(y, "y", my)
        return x, y

    if "," in str(position):
        parts = str(position).split(",", 1)
        return parts[0].strip(), parts[1].strip()

    return str(mx), str(my)


def _build_alpha_expr(animation: str, opacity: float) -> str:
    """
    Build alpha expression for drawtext.
    Only uses safe expressions.
    """
    opacity = max(0.0, min(1.0, float(opacity)))

    if animation == "static":
        return ""

    if animation == "fade-in":
        return f"if(lt(t\\,2)\\,(t/2)*{opacity}\\,{opacity})"

    if animation == "blink":
        return f"if(lt(mod(t\\,1.5)\\,0.75)\\,{opacity}\\,0)"

    if animation == "float":
        return f"{opacity}"

    # risky without extra duration handling
    if animation in ("fade-out", "slide-left", "slide-right"):
        return ""

    return ""


def build_text_filter(settings: dict) -> str:
    """Build FFmpeg drawtext filter string from watermark settings."""
    bold = bool(settings.get("bold", True))
    text = _escape_text(settings.get("text", "Watermark"))
    font = _get_font(bold=bold)
    fontsize = int(settings.get("font_size", 36))
    color = str(settings.get("font_color", "white"))
    opacity = max(0.0, min(1.0, float(settings.get("opacity", 0.8))))
    position = settings.get("position", "bottom-right")
    margin_x = int(settings.get("margin_x", 10))
    margin_y = int(settings.get("margin_y", 10))
    shadow = bool(settings.get("shadow", True))
    box = bool(settings.get("box", False))
    box_color = str(settings.get("box_color", "black@0.4"))
    animation = str(settings.get("animation", "static"))

    x_expr, y_expr = _position_to_expr(position, margin_x, margin_y)
    alpha_expr = _build_alpha_expr(animation, opacity)

    parts = [
        f"fontfile={font}",
        f"text='{text}'",
        f"fontsize={fontsize}",
        f"x={x_expr}",
        f"y={y_expr}",
    ]

    if alpha_expr:
        parts.append(f"fontcolor={color}")
        parts.append(f"alpha={alpha_expr}")
    else:
        parts.append(f"fontcolor={color}@{opacity:.2f}")

    if shadow:
        parts.extend([
            "shadowcolor=black@0.5",
            "shadowx=2",
            "shadowy=2",
        ])

    if box:
        parts.extend([
            "box=1",
            f"boxcolor={box_color}",
            "boxborderw=6",
        ])

    return "drawtext=" + ":".join(parts)


def build_text_filter_with_animation(settings: dict) -> str:
    """Build final drawtext filter, including safe slide/float overrides."""
    animation = str(settings.get("animation", "static"))
    base = build_text_filter(settings)

    position = settings.get("position", "bottom-right")
    margin_x = int(settings.get("margin_x", 10))
    margin_y = int(settings.get("margin_y", 10))
    x_final, y_final = _position_to_expr(position, margin_x, margin_y)

    if animation == "slide-left":
        animated_x = f"if(lt(t\\,2)\\,-text_w+(t/2)*(({x_final})+text_w)\\,{x_final})"
        base = base.replace(f"x={x_final}", f"x={animated_x}", 1)

    elif animation == "slide-right":
        animated_x = f"if(lt(t\\,2)\\,w-(t/2)*(w-({x_final}))\\,{x_final})"
        base = base.replace(f"x={x_final}", f"x={animated_x}", 1)

    elif animation == "float":
        animated_y = f"({y_final})+5*sin(2*PI*t/3)"
        base = base.replace(f"y={y_final}", f"y={animated_y}", 1)

    return base


async def apply_text_watermark(
    input_path: str,
    output_path: str,
    settings: dict,
    progress_callback=None,
) -> bool:
    """Apply text watermark using FFmpeg drawtext filter."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    vf = build_text_filter_with_animation(settings)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path,
    ]

    return await _run_ffmpeg(cmd, progress_callback)


async def _run_ffmpeg(cmd: list, progress_callback=None) -> bool:
    """Run FFmpeg command asynchronously with optional progress reporting."""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stderr_lines: list[str] = []
    duration = None
    last_progress = 0

    while True:
        line = await proc.stderr.readline()
        if not line:
            break

        line_str = line.decode("utf-8", errors="replace").rstrip()
        stderr_lines.append(line_str)

        if "Duration:" in line_str and duration is None:
            try:
                dur_str = line_str.split("Duration:")[1].split(",")[0].strip()
                h, m, s = dur_str.split(":")
                duration = int(h) * 3600 + int(m) * 60 + float(s)
            except Exception:
                pass

        if "time=" in line_str and duration and progress_callback:
            try:
                time_str = line_str.split("time=")[1].split(" ")[0].strip()
                h, m, s = time_str.split(":")
                current = int(h) * 3600 + int(m) * 60 + float(s)
                pct = min(int((current / duration) * 100), 99)

                if pct >= last_progress + 5:
                    last_progress = pct
                    await progress_callback(pct)
            except Exception:
                pass

    await proc.wait()

    if proc.returncode != 0:
        error_text = "\n".join(stderr_lines)

        try:
            with open(FFMPEG_ERROR_LOG, "w", encoding="utf-8") as f:
                f.write(error_text)
        except Exception:
            pass

        short_error = "\n".join(stderr_lines[-20:])
        print("[FFmpeg Error]")
        print(short_error)

        raise Exception(
            short_error + f"\n\nFull log saved at: {FFMPEG_ERROR_LOG}"
        )

    if progress_callback:
        try:
            await progress_callback(100)
        except Exception:
            pass

    return True
