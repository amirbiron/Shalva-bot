```yaml
name: "Shalva Bot - בוט תמיכה רגשית"
repo: "https://github.com/amirbiron/Shalva-bot"
status: "פעיל (בייצור)"

one_liner: "בוט טלגרם חכם לתמיכה רגשית וניהול חרדה, מבוסס על Google Gemini AI, עם מעקב מצב רוח והמלצות מותאמות אישית."

stack:
  - Python 3.8+
  - python-telegram-bot (עם job-queue)
  - Google Generative AI (Gemini)
  - MongoDB (pymongo)
  - Flask (keep-alive)
  - python-dotenv

key_features:
  - "שיחת תמיכה אישית ואמפתית מבוססת Gemini AI"
  - "דיווח מהיר ומפורט של מצב חרדה"
  - "גרפים והיסטוריה - מעקב התקדמות לאורך זמן"
  - "פריקה חופשית - מקום בטוח לכתיבה חופשית"
  - "שירים מרגיעים - קולקציה מבוססת מחקר"
  - "טכניקות הרגעה מעשיות"
  - "המלצות מותאמות אישית בהתבסס על נתוני המשתמש"
  - "מעקב שימוש והתראות צריכה (usage_tracker)"

architecture:
  summary: |
    בוט טלגרם מבוסס python-telegram-bot עם Gemini AI לשיחות אמפתיות.
    MongoDB לשמירת נתוני משתמשים והיסטוריית חרדה. שרת Flask מינימלי
    לשמירה על חיות השירות ב-Render. כולל מערכת מעקב שימוש והתראות.
  entry_points:
    - "main.py - נקודת כניסה ראשית, כל הלוגיקה של הבוט"
    - "gemini_wrapper.py - עטיפה ל-Google Gemini AI"
    - "usage_tracker.py - מעקב צריכה והתראות"
    - "telegram_alerter.py - שליחת התראות אדמין"
    - "activity_reporter.py - דיווח פעילות למערכת Suspended"
    - "simple.py - גרסה פשוטה/בדיקות"

demo:
  live_url: "" # TODO: בדוק ידנית
  video_url: "" # TODO: בדוק ידנית

setup:
  quickstart: |
    1. pip install -r requirements.txt
    2. הגדר משתני סביבה: BOT_TOKEN, MONGO_URI, GEMINI_API_KEY
    3. python main.py

your_role: "פיתוח מלא - ארכיטקטורה, אינטגרציה עם Gemini AI, לוגיקת תמיכה רגשית, מעקב חרדה"

tradeoffs:
  - "Gemini AI במקום GPT - עלות נמוכה יותר עם ביצועים טובים לעברית"
  - "כל הלוגיקה ב-main.py אחד - פשטות על חשבון מודולריות"
  - "MongoDB לנתוני חרדה - גמישות סכמה לנתונים מגוונים"

metrics: {} # TODO: בדוק ידנית

faq:
  - q: "האם השיחות נשמרות?"
    a: "שיחות התמיכה לא נשמרות, רק נתוני מעקב חרדה"
  - q: "איך הבוט מגיב לחרדה?"
    a: "הבוט משתמש ב-Gemini AI עם פרומפט מותאם לתמיכה רגשית אמפתית"
```
