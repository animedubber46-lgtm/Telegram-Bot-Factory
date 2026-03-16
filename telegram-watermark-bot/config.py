import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API credentials
API_ID = int(os.environ.get("API_ID", 0))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

# Owner/Admin
OWNER_ID = int(os.environ.get("OWNER_ID", 0))

# MongoDB
MONGO_URI = os.environ.get("MONGO_URI", "")
DB_NAME = "watermark_bot"

# File limits
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB in bytes

# Temp directory for processing
TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Watermark position map for FFmpeg
POSITION_MAP = {
    "top-left":     ("10", "10"),
    "top-right":    ("W-w-10", "10"),
    "bottom-left":  ("10", "H-h-10"),
    "bottom-right": ("W-w-10", "H-h-10"),
    "center":       ("(W-w)/2", "(H-h)/2"),
}

# Fonts for text watermarks
DEFAULT_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
DEFAULT_FONT_BOLD    = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FALLBACK_FONT = "Arial"
