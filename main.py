import logging
import os
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler
import pymongo
from datetime import datetime

# --- הגדרות בסיסיות ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- קבועים ומשתני סביבה ---
TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI") # נוסיף את זה למשתני הסביבה ב-Render

# --- הגדרת מסד הנתונים ---
client = pymongo.MongoClient(MONGO_URI)
db = client.get_database("ShalvaBotDB") # שם מסד הנתונים
users_collection = db.get_collection("users") # אוסף (collection) לשמירת המשתמשים

# --- פונקציית עזר לשמירת משתמש ---
async def ensure_user_in_db(update: Update):
    """בודקת אם המשתמש קיים ב-DB ומוסיפה אותו אם לא."""
    user = update.effective_user
    if not user:
        return

    user_info = {
        "chat_id": user.id,
        "first_name": user.first_name,
        "username": user.username,
    }
    # הפקודה הזו תוסיף את המשתמש רק אם הוא לא קיים, ותעדכן אם הוא קיים
    users_collection.update_one(
        {"chat_id": user.id},
        {"$set": user_info, "$setOnInsert": {"first_seen": datetime.now()}},
        upsert=True
    )

# --- פונקציות הבוט המקוריות שלך ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user_in_db(update) # בדיקת משתמש
    keyboard = [
        [InlineKeyboardButton("מידע על חרדה", callback_data='anxiety_info')],
        [InlineKeyboardButton("דרכי התמודדות", callback_data='coping_methods')],
        [InlineKeyboardButton("קבלת עזרה", callback_data='get_help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('שלום! אני כאן כדי לעזור לך להתמודד עם חרדה. בחר אחת מהאפשרויות:', reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await ensure_user_in_db(update) # בדיקת משתמש
    await query.answer()

    if query.data == 'anxiety_info':
        await query.edit_message_text(text="חרדה היא תגובה טבעית של הגוף למצבי לחץ. היא יכולה להתבטא בתסמינים פיזיים ונפשיים. למידע נוסף, בקר באתר [שם אתר מומלץ].")
    elif query.data == 'coping_methods':
        await query.edit_message_text(text="ישנן דרכים רבות להתמודד עם חרדה, כמו תרגילי נשימה, מדיטציה, ופעילות גופנית. נסה לקחת נשימה עמוקה כעת.")
    elif query.data == 'get_help':
        await query.edit_message_text(text="חשוב לזכור שאתה לא לבד. ניתן לפנות לקו החם של ער\"ן במספר 1201 או לארגונים נוספים לקבלת תמיכה.")

# --- פונקציה ראשית ---
def main() -> None:
    # בדיקה שמשתני הסביבה קיימים
    if not TOKEN or not MONGO_URI:
        logger.fatal("FATAL: BOT_TOKEN or MONGO_URI environment variables are missing!")
        return
        
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    logger.info("Shalva Bot (Anxiety Help) starting with Polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
