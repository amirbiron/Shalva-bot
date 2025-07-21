from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Telegram token must be provided via environment variable for security reasons
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("⚠️  אנא הגדר את המשתנה הסביבתי TELEGRAM_BOT_TOKEN עם הטוקן של הבוט שלך.")

# MongoDB connection string must be provided via environment variable for security reasons
# (e.g. mongodb+srv://<user>:<pass>@cluster.mongodb.net/)
MONGO_URI: str | None = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise RuntimeError("⚠️  אנא הגדר Environment Variable בשם 'MONGO_URI' עם מחרוזת החיבור ל-MongoDB.")

# Database/Collection names
DB_NAME: str = "ShalvaBotDB"
COLLECTION_NAME: str = "users"

# Only the owner will be able to use admin commands
try:
    OWNER_USER_ID: int = int(os.getenv("OWNER_USER_ID", "0"))
except ValueError:
    OWNER_USER_ID = 0

if OWNER_USER_ID == 0:
    raise RuntimeError("⚠️  אנא הגדר Environment Variable בשם 'OWNER_USER_ID' עם ה-chat-id המספרי שלך בטלגרם.")

# -----------------------------------------------------------------------------
# MongoDB Setup
# -----------------------------------------------------------------------------

client: MongoClient = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

# Ensure indexes for efficient queries
collection.create_index([("user_id", ASCENDING)], unique=True)
collection.create_index([("last_activity", DESCENDING)])

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------

def human_timedelta_hebrew(past: datetime, now: Optional[datetime] = None) -> str:
    """Return a human-readable relative time difference in Hebrew."""

    now = now or datetime.utcnow()
    delta = now - past
    minutes = int(delta.total_seconds() // 60)

    if minutes < 60:
        return f"לפני {minutes} דקות" if minutes != 1 else "לפני דקה"

    hours = minutes // 60
    if hours < 24:
        return f"לפני {hours} שעות" if hours != 1 else "לפני שעה"

    days = hours // 24
    return f"לפני {days} ימים" if days != 1 else "לפני יום"


def owner_only(func):
    """Decorator that allows only the bot owner to execute the wrapped command."""

    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if user and user.id == OWNER_USER_ID:
            return await func(update, context, *args, **kwargs)

        # No permission → send a friendly denial message
        if update.message:
            await update.message.reply_text("🚫 אין לך הרשאות להשתמש בפקודה זו.")
        elif update.callback_query:
            await update.callback_query.answer("🚫 אין לך הרשאות.", show_alert=True)
        return

    return wrapped

# -----------------------------------------------------------------------------
# Message Listener – tracks every non-bot message
# -----------------------------------------------------------------------------

async def track_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Store every incoming user message in MongoDB (except bots)."""

    # Ignore bots (including ourselves)
    if update.effective_user is None or update.effective_user.is_bot:
        return

    user = update.effective_user
    username_display = user.username or f"{user.first_name} {user.last_name or ''}".strip()

    payload = {
        "$set": {
            "username": username_display,
            "last_activity": datetime.utcnow(),
        },
        "$inc": {"total_messages": 1},
    }
    collection.update_one({"user_id": user.id}, payload, upsert=True)

# -----------------------------------------------------------------------------
# Command Handlers (Owner-only)
# -----------------------------------------------------------------------------

@owner_only
async def recent_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/recent_users <days> – Show users active within the last X days (default 7)."""

    # Parse optional <days> argument
    try:
        days = int(context.args[0]) if context.args else 7
        days = max(days, 1)
    except ValueError:
        days = 7

    threshold = datetime.utcnow() - timedelta(days=days)
    cursor = (
        collection
        .find({"last_activity": {"$gte": threshold}})
        .sort("last_activity", DESCENDING)
    )
    users: List[dict] = list(cursor)

    if not users:
        await update.message.reply_text("לא נמצאו משתמשים פעילים בטווח הזמן המבוקש.")
        return

    # Build a nicely formatted text message
    lines = [f"🟢 משתמשים פעילים ב־{days} הימים האחרונים:"]
    for user in users:
        last_activity = user.get("last_activity")
        relative = human_timedelta_hebrew(last_activity)
        lines.append(
            f"• {user.get('username', user['user_id'])} — {relative} | סה\"כ הודעות: {user.get('total_messages', 0)}"
        )

    await update.message.reply_text("\n".join(lines))


@owner_only
async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/user_info [user_id] – Display stored activity for a specific user (default: self)."""

    # Determine target user ID
    target_user_id: Optional[int] = None
    if context.args:
        try:
            target_user_id = int(context.args[0])
        except ValueError:
            pass  # Invalid ID provided – fall back to self

    if target_user_id is None:
        target_user_id = update.effective_user.id

    record = collection.find_one({"user_id": target_user_id})
    if record is None:
        await update.message.reply_text("לא נמצאה פעילות עבור המשתמש.")
        return

    # Craft response text
    text = (
        f"👤 מידע על {record.get('username', target_user_id)}\n"
        f"מזהה: {record['user_id']}\n"
        f"הודעה אחרונה: {human_timedelta_hebrew(record['last_activity'])}\n"
        f"סה\"כ הודעות: {record.get('total_messages', 0)}"
    )

    await update.message.reply_text(text)


@owner_only
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send an inline admin menu with quick-access buttons."""

    keyboard = [
        [
            InlineKeyboardButton("🟢 משתמשים פעילים", callback_data="menu_recent_users"),
            InlineKeyboardButton("👤 מידע עליי", callback_data="menu_my_info"),
        ],
        [
            InlineKeyboardButton("📊 סטטיסטיקות", callback_data="menu_stats"),
            InlineKeyboardButton("🗑️ נקה ישנים", callback_data="menu_cleanup"),
        ],
    ]
    markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("תפריט ניהול:", reply_markup=markup)


# -----------------------------------------------------------------------------
# CallbackQuery (Inline Button) Handler
# -----------------------------------------------------------------------------

@owner_only
async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""

    if data == "menu_recent_users":
        # Reuse recent_users logic (no args → default 7 days)
        context.args = []
        await recent_users(update, context)

    elif data == "menu_my_info":
        context.args = []
        await user_info(update, context)

    elif data == "menu_stats":
        # Placeholder for future functionality
        await query.edit_message_text("📊 פיצ'ר סטטיסטיקות טרם יושם.")

    elif data == "menu_cleanup":
        # Delete users inactive for more than 1 year (365 days)
        threshold = datetime.utcnow() - timedelta(days=365)
        result = collection.delete_many({"last_activity": {"$lt": threshold}})
        await query.edit_message_text(f"🗑️ נמחקו {result.deleted_count} משתמשים לא פעילים.")

    else:
        await query.edit_message_text("❓ פעולה לא מוכרת.")

# -----------------------------------------------------------------------------
# Application Setup
# -----------------------------------------------------------------------------

def main() -> None:
    """Entry-point of the Telegram bot."""

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, track_activity))
    application.add_handler(CommandHandler("recent_users", recent_users))
    application.add_handler(CommandHandler("user_info", user_info))
    application.add_handler(CommandHandler("admin_menu", admin_menu))
    application.add_handler(CallbackQueryHandler(admin_menu_callback))

    # Run the bot (will block until interrupted)
    application.run_polling()


if __name__ == "__main__":
    main()