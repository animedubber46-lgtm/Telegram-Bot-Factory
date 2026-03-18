import os
from watermark.ffmpeg_text import _run_ffmpeg


def _position_to_overlay(position: str, margin_x: int, margin_y: int) -> tuple[str, str]:
    """Convert position name to FFmpeg overlay x/y expressions."""
    pos_map = {
        "top-left": ("10", "10"),
        "top-right": ("main_w-overlay_w-10", "10"),
        "bottom-left": ("10", "main_h-overlay_h-10"),
        "bottom-right": ("main_w-overlay_w-10", "main_h-overlay_h-10"),
        "center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
    }

    if position in pos_map:
        x, y = pos_map[position]

        if x == "10":
            x = str(margin_x)
        elif "main_w-overlay_w-10" in x:
            x = x.replace("main_w-overlay_w-10", f"main_w-overlay_w-{margin_x}")

        if y == "10":
            y = str(margin_y)
        elif "main_h-overlay_h-10" in y:
            y = y.replace("main_h-overlay_h-10", f"main_h-overlay_h-{margin_y}")

        return x, y

    if "," in str(position):
        parts = str(position).split(",", 1)
        return parts[0].strip(), parts[1].strip()

    return str(margin_x), str(margin_y)


def _build_image_alpha(animation: str, opacity: float) -> str:
    """Return alpha multiplier expression for safe image animations."""
    opacity = max(0.0, min(1.0, float(opacity)))

    if animation == "fade-in":
        return f"if(lt(t\\,2)\\,(t/2)*{opacity}\\,{opacity})"

    if animation == "blink":
        return f"if(lt(mod(t\\,1.5)\\,0.75)\\,{opacity}\\,0)"

    # fade-out disabled here because duration is not safely available
    return ""


def build_image_filter(settings: dict) -> str:
    """Build FFmpeg filter_complex for image watermark overlay."""
    position = settings.get("position", "bottom-right")
    opacity = max(0.0, min(1.0, float(settings.get("opacity", 0.8))))
    scale_pct = int(settings.get("scale", 15))
    margin_x = int(settings.get("margin_x", 10))
    margin_y = int(settings.get("margin_y", 10))
    animation = str(settings.get("animation", "static"))
    rotation = float(settings.get("rotation", 0))

    x_expr, y_expr = _position_to_overlay(position, margin_x, margin_y)

    # Scale logo relative to input video width
    logo_chain = f"[1:v]scale=iw*{scale_pct}/100:-1"

    if rotation != 0:
        logo_chain += (
            f",rotate={rotation}*PI/180:"
            f"ow=rotw({rotation}*PI/180):"
            f"oh=roth({rotation}*PI/180)"
        )

    logo_chain += ",format=rgba"

    alpha_expr = _build_image_alpha(animation, opacity)
    if alpha_expr:
        logo_chain += f",colorchannelmixer=aa=1,lut=a='val*({alpha_expr})'"
    else:
        logo_chain += f",colorchannelmixer=aa={opacity}"

    logo_chain += "[logo]"

    # Safe animation overrides
    if animation == "slide-left":
        x_expr = f"if(lt(t\\,2)\\,-overlay_w+(t/2)*(({x_expr})+overlay_w)\\,{x_expr})"
    elif animation == "slide-right":
        x_expr = f"if(lt(t\\,2)\\,main_w-(t/2)*(main_w-({x_expr}))\\,{x_expr})"
    elif animation == "float":
        y_expr = f"({y_expr})+5*sin(2*PI*t/3)"

    filter_complex = f"{logo_chain};[0:v][logo]overlay={x_expr}:{y_expr}"

    return filter_complex


async def apply_image_watermark(
    input_path: str,
    output_path: str,
    logo_path: str,
    settings: dict,
    progress_callback=None,
) -> bool:
    """Apply image watermark using FFmpeg overlay filter."""
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input video not found: {input_path}")

    if not os.path.exists(logo_path):
        raise FileNotFoundError(f"Logo not found: {logo_path}")

    filter_complex = build_image_filter(settings)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-i", logo_path,
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-crf", "18",
        "-preset", "fast",
        "-c:a", "copy",
        "-movflags", "+faststart",
        output_path
    ]

    return await _run_ffmpeg(cmd, progress_callback)
