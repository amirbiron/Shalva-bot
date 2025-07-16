import logging
import os
import sys
import asyncio
import json
import datetime
import traceback
from typing import List, Dict, Any, Optional
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, Message, Chat
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackContext
)

# הגדרות לוגינג
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# משתני סביבה
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

# קבועים למצבי שיחה
SUPPORT_CHAT, MAIN_MENU, WAITING_FOR_INPUT = range(3)

# היסטוריית שיחה לכל משתמש
user_histories: Dict[int, List[Dict[str, str]]] = {}

# פונקציות עזר

def get_user_history(user_id: int) -> List[Dict[str, str]]:
    return user_histories.setdefault(user_id, [])

def add_to_history(user_id: int, role: str, content: str):
    user_histories.setdefault(user_id, []).append({"role": role, "content": content})

def clear_history(user_id: int):
    user_histories[user_id] = []

# פונקציות בוט
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"User {user.id} started the bot.")
    await update.message.reply_text(
        "שלום וברוך הבא לבוט התמיכה!\nבחר באפשרות מהתפריט הראשי.",
        reply_markup=ReplyKeyboardMarkup(
            [["תמיכה"], ["אודות"]], resize_keyboard=True, one_time_keyboard=True
        )
    )
    return MAIN_MENU

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "בוט תמיכה לדוגמה. נבנה עם Python ו-Telegram Bot API."
    )
    return MAIN_MENU

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "תפריט ראשי:\nבחר באפשרות:",
        reply_markup=ReplyKeyboardMarkup(
            [["תמיכה"], ["אודות"]], resize_keyboard=True, one_time_keyboard=True
        )
    )
    return MAIN_MENU

async def support_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"User {user.id} entered support chat.")
    await update.message.reply_text(
        "אנא כתוב את הודעתך לצוות התמיכה. תוכל לכתוב בעברית או באנגלית.",
        reply_markup=ReplyKeyboardRemove()
    )
    clear_history(user.id)
    return SUPPORT_CHAT

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_message = update.message.text
    logger.info(f"Support message from {user.id}: {user_message}")
    add_to_history(user.id, "user", user_message)
    chat_history = get_user_history(user.id)

    # כאן תבוא קריאה ל-Gemini או מודל אחר
    # לדוגמה:
    # try:
    #     chat = model.start_chat(history=chat_history)
    #     response = await chat.send_message_async(user_message)
    #     bot_response = response.text
    #     add_to_history(user.id, "assistant", bot_response)
    #     await update.message.reply_text(bot_response)
    # except Exception as e:
    #     logger.error(f"Gemini error: {e}\n{traceback.format_exc()}")
    #     await update.message.reply_text("אירעה שגיאה זמנית. נסה שוב מאוחר יותר.")

    # תגובת בדיקה קבועה
    await update.message.reply_text("מצב התמיכה עובד, אך ה-AI מנוטרל זמנית לבדיקה.")
    return SUPPORT_CHAT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    logger.info(f"User {user.id} canceled the conversation.")
    await update.message.reply_text(
        "השיחה בוטלה. תוכל לחזור לתפריט הראשי בכל עת על ידי שליחת /start.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    if not TOKEN:
        logger.error("FATAL: TELEGRAM_TOKEN not found in environment variables!")
        return

    # יצירת האפליקציה
    application = Application.builder().token(TOKEN).build()

    # רישום פקודת ה-start
    application.add_handler(CommandHandler("start", start))

    # הפעלת הבוט
    logger.info("Starting minimal bot polling...")
    application.run_polling()
    logger.info("Bot polling stopped.")


if __name__ == "__main__":
    main()
