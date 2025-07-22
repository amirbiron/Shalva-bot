import json
from datetime import datetime, timezone

USAGE_FILE = "gemini_usage.json"
DAILY_LIMIT = 50
ALERT_THRESHOLD = 49  # התרעה תישלח כאשר נגיע למספר הזה

def get_current_utc_date_str():
    """מחזיר את התאריך הנוכחי בפורמט YYYY-MM-DD לפי שעון UTC."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def increment_and_check_usage():
    """
    מעלה את מונה השימוש ב-1 ובודק אם יש צורך בהתראה.
    מאפס את המונה אם התאריך השתנה.
    מחזיר את ספירת השימוש העדכנית.
    """
    today_str = get_current_utc_date_str()

    try:
        with open(USAGE_FILE, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # אם הקובץ לא קיים או פגום, ניצור אותו מחדש
        data = {"date": today_str, "count": 0}

    # איפוס המונה אם התאריך השתנה
    if data.get("date") != today_str:
        print(f"New day detected. Resetting usage counter from {data.get("date")} to {today_str}.")
        data = {"date": today_str, "count": 0}

    # העלאת המונה
    data["count"] += 1

    # שמירת השינויים בקובץ
    with open(USAGE_FILE, "w") as f:
        json.dump(data, f)

    print(f'Gemini API call count for {today_str}: {data["count"]}')
    return data["count"]
