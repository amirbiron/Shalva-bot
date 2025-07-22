import os
import telegram

async def send_telegram_alert(message: str) -> None:
    """Send a text alert via Telegram bot to the admin chat."""
    try:
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id = os.getenv("OWNER_USER_ID")

        if not bot_token or not chat_id:
            print("ERROR: Telegram token or chat_id not found in environment variables.")
            return

        bot = telegram.Bot(token=bot_token)
        await bot.send_message(chat_id=chat_id, text=message)
        print(f"Telegram alert sent: {message}")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
