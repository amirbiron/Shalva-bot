# test_alert.py
import asyncio
from dotenv import load_dotenv
from telegram_alerter import send_telegram_alert

async def run_test():
    """
    טוען את משתני הסביבה ושולח הודעת בדיקה אחת.
    """
    print("Loading environment variables from .env file...")
    load_dotenv()
    
    print("Attempting to send a test alert...")
    test_message = "✅ בדיקת מערכת ההתראות עובדת!"
    await send_telegram_alert(test_message)
    print("Test finished.")

if __name__ == "__main__":
    # הרצת פונקציית הבדיקה
    asyncio.run(run_test())
