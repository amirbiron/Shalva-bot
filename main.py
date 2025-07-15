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
MONGO_URI = os.environ.get("MONGO_URI")

# --- הגדרת מסד הנתונים ---
client = pymongo.MongoClient(MONGO_URI)
db = client.get_database("ShalvaBotDB")
users_collection = db.get_collection("users")

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
    users_collection.update_one(
        {"chat_id": user.id},
        {"$set": user_info, "$setOnInsert": {"first_seen": datetime.now()}},
        upsert=True
    )

# --- פונקציות הבוט ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await ensure_user_in_db(update) # בדיקת משתמש
    keyboard = [
        [InlineKeyboardButton("מידע על העמותה", callback_data='about')],
        [InlineKeyboardButton("תרומה", callback_data='donate')],
        [InlineKeyboardButton("צור קשר", callback_data='contact')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('שלום! ברוכים הבאים לעמותת "שלוה". במה נוכל לעזור?', reply_markup=reply_markup)

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await ensure_user_in_db(update) # בדיקת משתמש
    await query.answer()

    if query.data == 'about':
        await query.edit_message_text(text="עמותת 'שלוה' פועלת למען ילדים עם מוגבלויות ובני משפחותיהם. לפרטים נוספים, בקר באתרנו: [קישור לאתר]")
    elif query.data == 'donate':
        await query.edit_message_text(text="תרומתך חשובה לנו! ניתן לתרום בקישור הבא: [קישור לתרומה]")
    elif query.data == 'contact':
        await query.edit_message_text(text="ליצירת קשר, ניתן להתקשר למספר: 123-4567890 או לשלוח אימייל ל: contact@shalva.org")

# --- פונקציה ראשית ---
def main() -> None:
    if not TOKEN or not MONGO_URI:
        logger.fatal("FATAL: BOT_TOKEN or MONGO_URI environment variables are missing!")
        return
        
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button))

    logger.info("Shalva Bot starting with Polling...")
    application.run_polling()

if __name__ == '__main__':
    main()
