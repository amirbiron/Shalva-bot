import os
import asyncio
import google.generativeai as genai
from google.api_core import exceptions
from dotenv import load_dotenv
from usage_tracker import increment_and_check_usage, ALERT_THRESHOLD
from telegram_alerter import send_telegram_alert

# Load environment variables
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Initialize model
gemini_model = genai.GenerativeModel("gemini-pro")

async def generate_content_with_monitoring(prompt: str):
    """Wrap Gemini API call with daily usage tracking and Telegram alerting."""
    current_count = increment_and_check_usage()
    if current_count == ALERT_THRESHOLD:
        await send_telegram_alert(
            f"⚠️ התראה: התקרבות למכסת Gemini!\nשימוש נוכחי: {current_count}/{ALERT_THRESHOLD + 1}."
        )

    try:
        print("Sending request to Gemini API...")
        response = await gemini_model.generate_content_async(prompt)
        print("Successfully received response from Gemini.")
        return response.text
    except exceptions.ResourceExhausted:
        print("ERROR: Gemini API rate limit exceeded (429).")
        await send_telegram_alert(
            "⛔️ חריגה ממכסת Gemini!\nהתקבלה שגיאת 429 (Rate Limit Exceeded). הבוט לא יוכל להשתמש ב-API עד חצות."
        )
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        await send_telegram_alert(f"שגיאה לא צפויה בעת קריאה ל-Gemini: {e}")
        return None

async def _demo():
    print("--- Running wrapper demo ---")
    prompt_example = "כתוב בדיחה קצרה על מתכנתים"
    result = await generate_content_with_monitoring(prompt_example)
    if result:
        print("\nתוצאה שהתקבלה:\n", result)
    else:
        print("\nלא התקבלה תוצאה מה-API.")

if __name__ == "__main__":
    asyncio.run(_demo())
