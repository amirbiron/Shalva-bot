 – מעבר הבוט “שלווה 🩵" מ-Render ל-Railway

מדריך זה מנחה אותך כיצד לפרוס את הבוט בטיר החינמי של Railway, כך שישאר זמין (כמעט) 24/7 ללא עלות.

---

## 1. מגבלות הטיר החינמי של Railway

| משאב                | מגבלה חודשית        | הערה שימושית לבוט |
|---------------------|----------------------|-------------------|
| **500 שעות חישוב**  | נספרות רק כשהקונטיינר “ער”. במצב Sleep לא נספר. | בבוט המבוסס Webhook לרוב תשתמש ~200–300 שעות. |
| **512 MB RAM / 0.2 vCPU** | לשירות יחיד | די והותר לבוט טלגרם. |
| **1 GB Volume**     | כלול בחינם          | מתאים ל־SQLite או PicklePersistence. |

> לחרוג מ-500 שעות אפשר רק אם הקונטיינר רץ רצוף כל החודש.  
> במצב Webhook הקונטיינר מתעורר רק כשיש עדכון מטלגרם ולכן שעות החישוב נמוכות משמעותית.

---

## 2. שלבי הפריסה

### 2.1 ייבוא הריפו
1. כניסה ל-Railway → **New Project → Deploy from GitHub**.  
2. לבחור את הריפו שבו נמצאים הקבצים `main.py`, `requirements.txt`, `README.md`.

### 2.2 משתני סביבה  
Dashboard → **Variables** → הוספת המשתנים הבאים:

| Key | Value |
|-----|-------|
| `BOT_TOKEN`    | הטוקן שקיבלת מ-BotFather |
| `PUBLIC_URL`   | `https://<project>.up.railway.app` |
| `GROQ_KEY` / `OPENAI_KEY` | לפי הצורך |
| `MONGO_URI`    | אם אתה משתמש ב-MongoDB |

### 2.3 יצירת Volume מתמשך
1. בלשונית **Storage** → **Add Volume** → נתיב ‎`/data` (1 GB).  
2. עדכון בקוד:  
   ```python
   persistence = PicklePersistence(filepath="/data/bot_data.pkl")

2.4 מעבר ל-Webhook (חוסך שעות חישוב)

application.run_webhook(
    listen="0.0.0.0",
    port=int(os.getenv("PORT", 8080)),
    webhook_url=f"{os.environ['PUBLIC_URL']}/telegram"
)

> הלולאה הראשית רדומה; Railway מפעילה את הקונטיינר רק כשטלגרם שולח עדכון.



2.5 Scheduler (רשות)

אם דרוש Job קבוע (למשל בניית אינדקס):
Railway Scheduler מריץ פקודות קצרות בזמנים קבועים ואינו סופר זמן ריצה ממושך.


---

3. דפלוי ראשון

git push         # ודא שכל הקוד מעודכן
# Railway יבנה ויפרס אוטומטית

1. המתן ל-Status Running בלשונית Deployments.


2. בדפדפן: https://<project>.up.railway.app/telegram → אמור להחזיר 404 (תקין).


3. בטלגרם: שלח ‎/start לבוט “שלווה 🩵” → קבל מענה. ✔️




---

4. שאלות נפוצות

- מה יקרה אם אגיע ל-500 שעות?

Railway ישהה את השירות עד החודש הבא או עד שתשדרג לטיר $5.
אפשר גם לצמצם Idle Time (Scale to Zero) או להעביר משימות כבדות ל-GitHub Actions חינמי.

- למה Webhook ולא Polling?

Polling דורש תהליך רץ כל הזמן ולכן סביר לחרוג מהמכסה.
Webhook משתמש ב-CPU רק כשמגיעה הודעת טלגרם → חסכוני בדקות.


---

בהצלחה! 🚀

הבוט “שלווה 🩵” מוכן לעבוד בענן החינמי של Railway – ולשמח את המשתמשת הקבועה בלי הפסקות 😉



