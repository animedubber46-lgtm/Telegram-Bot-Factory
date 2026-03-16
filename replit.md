# Workspace

## Overview

pnpm workspace monorepo using TypeScript, plus a production-ready Python Telegram watermark bot.

## Stack

- **Monorepo tool**: pnpm workspaces
- **Node.js version**: 24
- **Package manager**: pnpm
- **TypeScript version**: 5.9
- **API framework**: Express 5
- **Database**: PostgreSQL + Drizzle ORM
- **Validation**: Zod (`zod/v4`), `drizzle-zod`
- **API codegen**: Orval (from OpenAPI spec)
- **Build**: esbuild (CJS bundle)

## Telegram Watermark Bot (Python)

Located in `telegram-watermark-bot/`. A production-ready Telegram bot for adding watermarks to videos.

### Bot Stack
- **Language**: Python 3.11
- **Telegram library**: Pyrogram 2.0.106 + TgCrypto
- **Database**: MongoDB (motor async driver)
- **Video processing**: FFmpeg
- **Config**: python-dotenv

### Bot Features
- Text watermarks with font, color, size, opacity, bold, shadow, box, animation
- Image/logo watermarks with transparency (PNG), scale, opacity, animation
- Saved watermark presets (up to 10 per user)
- 7 animations: static, fade-in, fade-out, blink, slide-left, slide-right, float
- Videos up to 2 GB
- Quality-preserving encoding (CRF 18, audio stream copied)
- Download/upload progress bars
- Admin commands: broadcast, ban/unban, stats
- One-task-per-user processing lock

### Bot File Structure
```
telegram-watermark-bot/
├── main.py              # Entry point
├── config.py            # Environment variable config
├── database.py          # MongoDB + in-memory state
├── requirements.txt
├── Procfile
├── .env.example
├── handlers/
│   ├── start.py         # /start, /help, /cancel
│   ├── add_watermark.py # /addwatermark conversation flow
│   ├── watermarks.py    # /mywatermarks, edit, rename, delete
│   ├── video.py         # Video handler + watermark application
│   └── admin.py         # Owner-only admin commands
├── watermark/
│   ├── ffmpeg_text.py   # FFmpeg drawtext filter
│   └── ffmpeg_image.py  # FFmpeg overlay filter
└── utils/
    └── helpers.py       # Progress, cleanup, formatting
```

### Required Environment Variables (Secrets)
- `API_ID` — Telegram App ID (my.telegram.org)
- `API_HASH` — Telegram App Hash (my.telegram.org)
- `BOT_TOKEN` — From @BotFather
- `OWNER_ID` — Your Telegram user ID
- `MONGO_URI` — MongoDB connection string

## Structure

```text
artifacts-monorepo/
├── artifacts/              # Deployable applications
│   └── api-server/         # Express API server
├── telegram-watermark-bot/ # Python Telegram bot
├── lib/                    # Shared libraries
│   ├── api-spec/           # OpenAPI spec + Orval codegen config
│   ├── api-client-react/   # Generated React Query hooks
│   ├── api-zod/            # Generated Zod schemas from OpenAPI
│   └── db/                 # Drizzle ORM schema + DB connection
├── scripts/                # Utility scripts
├── pnpm-workspace.yaml
├── tsconfig.base.json
├── tsconfig.json
└── package.json
```

## Root Scripts

- `pnpm run build` — runs `typecheck` first, then recursively runs `build` in all packages that define it
- `pnpm run typecheck` — runs `tsc --build --emitDeclarationOnly` using project references
