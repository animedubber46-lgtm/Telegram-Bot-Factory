# WatermarkBot — Telegram Video Watermark Bot

A production-ready Telegram bot that adds high-quality watermarks to videos without noticeably reducing visual quality.

## Features

- **Text watermarks** — custom font, size, color, opacity, bold, shadow, background box, position, animation
- **Image watermarks** — PNG logo overlay with transparency, scale, opacity, position, animation
- **Saved presets** — save up to 10 watermark presets per user, reuse them any time
- **Animations** — static, fade-in, fade-out, blink, slide-left, slide-right, float
- **Quality preservation** — CRF 18 encoding, audio stream copied, fast preset
- **Large file support** — up to 2 GB
- **Admin features** — ban/unban users, broadcast, stats

---

## Project Structure

```
telegram-watermark-bot/
├── main.py              # Entry point
├── config.py            # Configuration from environment variables
├── database.py          # MongoDB async operations + in-memory state
├── requirements.txt     # Python dependencies
├── Procfile             # For Heroku/Render deployment
├── .env.example         # Sample environment variables
├── handlers/
│   ├── start.py         # /start, /help, /cancel handlers
│   ├── add_watermark.py # /addwatermark conversation flow
│   ├── watermarks.py    # /mywatermarks, edit, rename, delete
│   ├── video.py         # Video receiving + watermark application
│   └── admin.py         # Owner-only admin commands
├── watermark/
│   ├── ffmpeg_text.py   # FFmpeg drawtext filter builder
│   └── ffmpeg_image.py  # FFmpeg overlay filter builder
├── utils/
│   └── helpers.py       # Download/upload progress, cleanup
└── temp/                # Temporary files (auto-cleaned)
```

---

## Requirements

- Python 3.10+
- FFmpeg installed on system (`apt install ffmpeg` / `brew install ffmpeg`)
- MongoDB (Atlas free tier works)
- Telegram API credentials

---

## Setup

### 1. Clone and install dependencies

```bash
cd telegram-watermark-bot
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

| Variable    | Description                          | Where to get                |
|-------------|--------------------------------------|-----------------------------|
| `API_ID`    | Telegram App ID                      | https://my.telegram.org     |
| `API_HASH`  | Telegram App Hash                    | https://my.telegram.org     |
| `BOT_TOKEN` | Bot token                            | @BotFather on Telegram      |
| `OWNER_ID`  | Your Telegram user ID                | @userinfobot on Telegram    |
| `MONGO_URI` | MongoDB connection string            | MongoDB Atlas               |

### 3. Run the bot

```bash
python main.py
```

---

## Deployment

### VPS (recommended)

```bash
# Install FFmpeg
apt update && apt install -y ffmpeg

# Install Python deps
pip install -r requirements.txt

# Run with screen or systemd
screen -S watermarkbot python main.py
```

### Heroku / Render

The `Procfile` is set up for worker dynos:

```
worker: python main.py
```

Set environment variables in the platform's dashboard and deploy.

### Docker

```dockerfile
FROM python:3.11-slim
RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
```

---

## Bot Commands

| Command          | Description                    | Who       |
|------------------|--------------------------------|-----------|
| `/start`         | Welcome message                | Everyone  |
| `/help`          | Detailed usage guide           | Everyone  |
| `/mywatermarks`  | Manage saved watermarks        | Everyone  |
| `/addwatermark`  | Create a new watermark preset  | Everyone  |
| `/cancel`        | Cancel current operation       | Everyone  |
| `/stats`         | Bot statistics                 | Owner     |
| `/broadcast`     | Broadcast message to all users | Owner     |
| `/ban <id>`      | Ban a user                     | Owner     |
| `/unban <id>`    | Unban a user                   | Owner     |
| `/users`         | Total user count               | Owner     |
| `/checkban <id>` | Check ban status               | Owner     |

---

## FFmpeg Details

### Text watermark
```
ffmpeg -i input.mp4 -vf "drawtext=fontfile=...:text='...':fontsize=36:fontcolor=white@0.8:x=W-w-10:y=H-h-10:shadowcolor=black@0.5:shadowx=2:shadowy=2" -c:v libx264 -crf 18 -preset fast -c:a copy output.mp4
```

### Image watermark
```
ffmpeg -i input.mp4 -i logo.png -filter_complex "[1:v]scale=iw*15/100:-1,format=rgba,colorchannelmixer=aa=0.8[logo];[0:v][logo]overlay=W-w-10:H-h-10" -c:v libx264 -crf 18 -preset fast -c:a copy output.mp4
```

**Key quality settings:**
- `-crf 18` — near-lossless (lower = better quality, larger file)
- `-preset fast` — good balance of speed vs compression
- `-c:a copy` — audio stream copied without re-encoding

---

## MongoDB Schema

### `users` collection
```json
{
  "user_id": 123456789,
  "username": "john_doe",
  "full_name": "John Doe",
  "joined_at": 1700000000
}
```

### `watermarks` collection
```json
{
  "user_id": 123456789,
  "type": "text",
  "name": "My Logo",
  "text": "© MyBrand",
  "font_size": 36,
  "font_color": "white",
  "bold": true,
  "shadow": true,
  "box": false,
  "opacity": 0.8,
  "position": "bottom-right",
  "margin_x": 10,
  "margin_y": 10,
  "animation": "fade-in",
  "created_at": 1700000000,
  "updated_at": 1700000000
}
```

### `tasks` collection
```json
{
  "user_id": 123456789,
  "status": "completed",
  "watermark_type": "text",
  "error": null,
  "created_at": 1700000000
}
```

### `bans` collection
```json
{
  "user_id": 123456789,
  "banned_at": 1700000000
}
```
