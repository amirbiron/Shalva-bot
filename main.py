import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# הפעלת לוגינג
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# קבלת הטוקן ממשתני הסביבה
TOKEN = os.getenv("TELEGRAM_TOKEN")

# פונקציית start מינימלית
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message when the /start command is issued."""
    logger.info("Command /start received. Replying...")
    await update.message.reply_text("שלום עולם! אני עובד!")

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
