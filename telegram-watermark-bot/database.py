import time
from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME

# MongoDB client (initialized on first use)
_client = None
_db = None


def get_db():
    global _client, _db
    if _db is None:
        _client = AsyncIOMotorClient(MONGO_URI)
        _db = _client[DB_NAME]
    return _db


# ─── Users ──────────────────────────────────────────────────────────────────

async def add_user(user_id: int, username: str = None, full_name: str = None):
    db = get_db()
    await db.users.update_one(
        {"user_id": user_id},
        {
            "$setOnInsert": {"user_id": user_id, "joined_at": int(time.time())},
            "$set": {"username": username, "full_name": full_name},
        },
        upsert=True,
    )


async def get_user(user_id: int):
    db = get_db()
    return await db.users.find_one({"user_id": user_id})


async def get_all_users():
    db = get_db()
    return await db.users.find({}, {"user_id": 1}).to_list(None)


async def get_total_users() -> int:
    db = get_db()
    return await db.users.count_documents({})


async def ban_user(user_id: int):
    db = get_db()
    await db.bans.update_one(
        {"user_id": user_id},
        {"$set": {"user_id": user_id, "banned_at": int(time.time())}},
        upsert=True,
    )


async def unban_user(user_id: int):
    db = get_db()
    await db.bans.delete_one({"user_id": user_id})


async def is_banned(user_id: int) -> bool:
    db = get_db()
    return await db.bans.find_one({"user_id": user_id}) is not None


# ─── Watermarks ──────────────────────────────────────────────────────────────

async def get_watermarks(user_id: int) -> list:
    db = get_db()
    return await db.watermarks.find({"user_id": user_id}).to_list(None)


async def get_watermark(user_id: int, wm_id: str) -> dict:
    from bson import ObjectId
    db = get_db()
    return await db.watermarks.find_one({"_id": ObjectId(wm_id), "user_id": user_id})


async def add_watermark(user_id: int, data: dict) -> str:
    db = get_db()
    data["user_id"] = user_id
    data["created_at"] = int(time.time())
    data["updated_at"] = int(time.time())
    result = await db.watermarks.insert_one(data)
    return str(result.inserted_id)


async def update_watermark(user_id: int, wm_id: str, data: dict):
    from bson import ObjectId
    db = get_db()
    data["updated_at"] = int(time.time())
    await db.watermarks.update_one(
        {"_id": ObjectId(wm_id), "user_id": user_id},
        {"$set": data},
    )


async def delete_watermark(user_id: int, wm_id: str):
    from bson import ObjectId
    db = get_db()
    await db.watermarks.delete_one({"_id": ObjectId(wm_id), "user_id": user_id})


async def count_watermarks(user_id: int) -> int:
    db = get_db()
    return await db.watermarks.count_documents({"user_id": user_id})


# ─── Tasks ───────────────────────────────────────────────────────────────────

async def log_task(user_id: int, status: str, watermark_type: str = None, error: str = None):
    db = get_db()
    await db.tasks.insert_one({
        "user_id": user_id,
        "status": status,
        "watermark_type": watermark_type,
        "error": error,
        "created_at": int(time.time()),
    })


async def get_total_tasks() -> int:
    db = get_db()
    return await db.tasks.count_documents({"status": "completed"})


# ─── User state (conversation state) ─────────────────────────────────────────

_state: dict = {}


def get_state(user_id: int) -> dict:
    return _state.get(user_id, {})


def set_state(user_id: int, data: dict):
    _state[user_id] = data


def clear_state(user_id: int):
    _state.pop(user_id, None)


def update_state(user_id: int, key: str, value):
    if user_id not in _state:
        _state[user_id] = {}
    _state[user_id][key] = value


# ─── Processing lock (one task per user) ─────────────────────────────────────

_processing: set = set()


def is_processing(user_id: int) -> bool:
    return user_id in _processing


def set_processing(user_id: int):
    _processing.add(user_id)


def clear_processing(user_id: int):
    _processing.discard(user_id)
