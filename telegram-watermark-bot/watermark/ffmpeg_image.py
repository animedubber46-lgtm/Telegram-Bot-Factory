import os
import asyncio
from config import POSITION_MAP, TEMP_DIR
from watermark.ffmpeg_text import _run_ffmpeg


def _position_to_overlay(position: str, margin_x: int, margin_y: int) -> str:
    """Convert position name to FFmpeg overlay x:y expression."""
    pos_map = {
        "top-left":     f"{margin_x}:{margin_y}",
        "top-right":    f"main_w-overlay_w-{margin_x}:{margin_y}",
        "bottom-left":  f"{margin_x}:main_h-overlay_h-{margin_y}",
        "bottom-right": f"main_w-overlay_w-{margin_x}:main_h-overlay_h-{margin_y}",
        "center":       "(main_w-overlay_w)/2:(main_h-overlay_h)/2",
    }
    if position in pos_map:
        return pos_map[position]
    # custom "x,y"
    if "," in str(position):
        parts = str(position).split(",")
        return f"{parts[0].strip()}:{parts[1].strip()}"
    return f"{margin_x}:{margin_y}"


def build_image_filter(settings: dict, logo_path: str) -> tuple:
    """
    Build FFmpeg filter_complex for image watermark overlay.
    Returns (filter_complex_str, map_arg)
    """
    position = settings.get("position", "bottom-right")
    opacity = float(settings.get("opacity", 0.8))
    scale_pct = int(settings.get("scale", 15))  # % of video width
    margin_x = int(settings.get("margin_x", 10))
    margin_y = int(settings.get("margin_y", 10))
    animation = settings.get("animation", "static")
    rotation = float(settings.get("rotation", 0))

    overlay_pos = _position_to_overlay(position, margin_x, margin_y)

    # Build the logo processing chain
    logo_chain = f"[1:v]scale=iw*{scale_pct}/100:-1"

    if rotation != 0:
        logo_chain += f",rotate={rotation}*PI/180:ow=rotw({rotation}*PI/180):oh=roth({rotation}*PI/180)"

    logo_chain += f",format=rgba,colorchannelmixer=aa={opacity}"

    # Animation
    alpha_anim = _build_image_alpha(animation, opacity)
    overlay_xy = overlay_pos

    if animation == "slide-left":
        overlay_xy = f"if(lt(t\\,2)\\,W*t/2-overlay_w\\,{overlay_pos.split(':')[0]}):{overlay_pos.split(':')[1] if ':' in overlay_pos else margin_y}"
    elif animation == "slide-right":
        x_final = overlay_pos.split(":")[0] if ":" in overlay_pos else str(margin_x)
        overlay_xy = f"if(lt(t\\,2)\\,W-W*t/2\\,{x_final}):{overlay_pos.split(':')[1] if ':' in overlay_pos else margin_y}"
    elif animation == "float":
        y_part = overlay_pos.split(":")[1] if ":" in overlay_pos else str(margin_y)
        x_part = overlay_pos.split(":")[0] if ":" in overlay_pos else str(margin_x)
        overlay_xy = f"{x_part}:{y_part}+5*sin(2*PI*t/3)"

    if alpha_anim:
        logo_chain += f",lut=a='val*{alpha_anim}'"

    logo_chain += "[logo]"

    filter_complex = f"{logo_chain};[0:v][logo]overlay={overlay_xy}"

    return filter_complex


def _build_image_alpha(animation: str, opacity: float) -> str:
    """Return alpha multiplier expression for image animations."""
    if animation == "fade-in":
        return f"if(lt(t\\,2)\\,t/2*255\\,{int(opacity*255)})/255"
    elif animation == "fade-out":
        return f"if(gt(t\\,max(0\\,duration-2))\\,(duration-t)/2*255\\,{int(opacity*255)})/255"
    elif animation == "blink":
        return f"if(lt(mod(t\\,1.5)\\,0.75)\\,{int(opacity*255)}\\,0)/255"
    return ""


async def apply_image_watermark(
    input_path: str,
    output_path: str,
    logo_path: str,
    settings: dict,
    progress_callback=None,
) -> bool:
    """Apply image watermark using FFmpeg overlay filter."""
    if not os.path.exists(logo_path):
        print(f"[Error] Logo not found: {logo_path}")
        return False

    filter_complex = build_image_filter(settings, logo_path)

    cmd = [
        "ffmpeg", "-y",
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
