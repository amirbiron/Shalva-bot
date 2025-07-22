import os
import telegram

async def send_telegram_alert(message: str):
    """שולח הודעת התראה ל-chat_id המוגדר."""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("OWNER_USER_ID")

        if not bot_token or not chat_id:
            print("ERROR: Telegram token or OWNER_USER_ID not found in environment variables.")
            return

        bot = telegram.Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message)
        print("Telegram alert sent to OWNER_USER_ID.")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
