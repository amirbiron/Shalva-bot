# telegram_alerter.py
import os
import telegram
from dotenv import load_dotenv

# טעינת משתני סביבה כדי שנוכל להשתמש בהם
load_dotenv()

async def send_telegram_alert(message: str):
    """
    שולח הודעת התראה ל-chat_id של הבעלים המוגדר במשתני הסביבה.
    """
    try:
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        # שימוש במשתנה הקיים שלך כפי שביקשת
        owner_id = os.getenv('OWNER_USER_ID') 
        
        if not bot_token or not owner_id:
            print("ERROR: TELEGRAM_BOT_TOKEN or OWNER_USER_ID not found in environment variables.")
            return

        bot = telegram.Bot(token=bot_token)
        await bot.send_message(chat_id=owner_id, text=message)
        print(f"Telegram alert sent successfully to OWNER_USER_ID.")
        
    except Exception as e:
        print(f"FATAL: Failed to send Telegram alert: {e}")
