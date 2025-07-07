import logging
import sqlite3
import os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from collections import Counter

# הגדרות לוגים
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# טוקן הבוט
BOT_TOKEN = os.getenv('BOT_TOKEN') or "7622868890:AAEnk_PC-hbOJIYWICXgE8F654RlOJxY5Sk"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN לא נמצא!")

# הגדרת בסיס הנתונים
def init_database():
    """יצירת טבלאות בסיס הנתונים"""
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    
    # טבלת דיווחי חרדה
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS anxiety_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        timestamp DATETIME,
        anxiety_level INTEGER,
        description TEXT,
        location TEXT,
        people_around TEXT,
        weather TEXT,
        report_type TEXT DEFAULT 'full',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # טבלת פריקות חופשיות
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS free_venting (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        save_for_analysis BOOLEAN DEFAULT FALSE,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # טבלת הגדרות משתמש
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        daily_reminder BOOLEAN DEFAULT FALSE,
        reminder_time TEXT DEFAULT '20:00',
        preferred_report_type TEXT DEFAULT 'quick'
    )
    ''')
    
    conn.commit()
    conn.close()

# משתני עזר עבור תהליכי שיחה
user_states = {}
temp_data = {}

# אפשרויות מוגדרות מראש
LOCATION_OPTIONS = ['🏠 בית', '🏢 עבודה', '🚗 רחוב', '🛒 קניון', '🚌 תחבורה ציבורית', '📍 אחר']
PEOPLE_OPTIONS = ['👤 לבד', '👥 עם חברים', '👔 קולגות', '👨‍👩‍👧‍👦 משפחה', '👥 זרים', '👥 אחר']
WEATHER_OPTIONS = ['☀️ שמש', '🌧️ גשם', '☁️ מעונן', '🔥 חם', '❄️ קר', '🌤️ אחר']

def get_main_keyboard():
    """יצירת מקלדת ראשית"""
    keyboard = [
        [KeyboardButton("⚡ דיווח מהיר"), KeyboardButton("🔍 דיווח מלא")],
        [KeyboardButton("🗣️ פריקה חופשית"), KeyboardButton("📈 גרפים והיסטוריה")],
        [KeyboardButton("🎵 שירים מרגיעים"), KeyboardButton("💡 עזרה כללית")],
        [KeyboardButton("⚙️ הגדרות")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_anxiety_level_keyboard():
    """יצירת מקלדת לבחירת רמת חרדה"""
    keyboard = []
    row1 = []
    row2 = []
    
    for i in range(1, 6):
        row1.append(InlineKeyboardButton(f"{i}", callback_data=f"anxiety_{i}"))
    
    for i in range(6, 11):
        row2.append(InlineKeyboardButton(f"{i}", callback_data=f"anxiety_{i}"))
    
    keyboard.append(row1)
    keyboard.append(row2)
    
    return InlineKeyboardMarkup(keyboard)

def get_options_keyboard(options, callback_prefix):
    """יצירת מקלדת עבור אפשרויות"""
    keyboard = []
    for option in options:
        keyboard.append([InlineKeyboardButton(option, callback_data=f"{callback_prefix}_{option}")])
    return InlineKeyboardMarkup(keyboard)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פונקציית התחלה"""
    user_id = update.effective_user.id
    
    # בדיקה אם המשתמש קיים במערכת
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        conn.commit()
    conn.close()
    
    welcome_message = """
🤗 שלום ויפה שהגעת! 

אני כאן כדי לעזור לך להבין ולעקוב אחר הרגשות שלך בצורה בטוחה ופרטית. 

זה לא תמיד קל להתמודד עם חרדה ודיכאון, ואני רוצה להיות הכלי שיעזור לך לראות דפוסים ולמצוא דרכים טובות יותר להרגיש.

💙 איך אני יכול לתמוך בך:
⚡ דיווח מהיר - כשאתה מרגיש חרדה עכשיו
🔍 דיווח מפורט - לזהות מה מעורר את הרגשות
🗣️ פריקה חופשית - מקום בטוח לכתוב מה שמטריד
📈 מבט על הדרך - לראות איך אתה מתקדם
💡 כלים לעזרה - טכניקות שיכולות להרגיע

🔒 הכל נשאר רק אצלך ופרטי לחלוטין.

קח את הזמן שלך, ובחר מה מתאים לך עכשיו:
"""
    
    await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard())
    
    # הצעה למוזיקה מרגיעה
    music_keyboard = [
        [InlineKeyboardButton("🎵 כן, אשמח לשיר מרגיע", callback_data="relaxing_music")],
        [InlineKeyboardButton("🚀 לא, בוא נתחיל", callback_data="start_using")]
    ]
    
    await update.message.reply_text(
        "🎶 רוצה לפני שנתחיל לשים שיר מרגיע? יש לי קולקציה של שירים שנמצאו מחקרית הכי מרגיעים במצבי סטרס:",
        reply_markup=InlineKeyboardMarkup(music_keyboard)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בהודעות טקסט"""
    text = update.message.text
    user_id = update.effective_user.id
    
    if text == "⚡ דיווח מהיר":
        await start_quick_report(update, context)
    elif text == "🔍 דיווח מלא":
        await start_full_report(update, context)
    elif text == "🗣️ פריקה חופשית":
        await start_free_venting(update, context)
    elif text == "📈 גרפים והיסטוריה":
        await show_analytics(update, context)
    elif text == "🎵 שירים מרגיעים":
        await show_relaxing_music_message(update, context)
    elif text == "💡 עזרה כללית":
        await show_help(update, context)
    elif text == "⚙️ הגדרות":
        await show_settings(update, context)
    else:
        # טיפול במצבי שיחה
        if user_id in user_states:
            await handle_conversation_state(update, context)
        else:
            await update.message.reply_text("בחר אפשרות מהתפריט למטה:", reply_markup=get_main_keyboard())

async def start_quick_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת דיווח מהיר"""
    user_id = update.effective_user.id
    user_states[user_id] = "quick_description"
    temp_data[user_id] = {"report_type": "quick", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    await update.message.reply_text(
        "⚡ דיווח מהיר\n\nמה קורה עכשיו? (תיאור קצר)",
        reply_markup=None
    )

async def start_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת דיווח מלא"""
    user_id = update.effective_user.id
    user_states[user_id] = "full_description"
    temp_data[user_id] = {"report_type": "full", "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    await update.message.reply_text(
        "🔍 דיווח מלא (שלב 1/4)\n\nמה גורם לחרדה עכשיו? (תאר במפורט)",
        reply_markup=None
    )

async def start_free_venting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת פריקה חופשית"""
    user_id = update.effective_user.id
    user_states[user_id] = "free_venting"
    
    await update.message.reply_text(
        "🗣️ פריקה חופשית\n\nכתב כל מה שאתה מרגיש. אין שאלות, אין לחץ.\nרק תן לזה לצאת...",
        reply_markup=None
    )

async def handle_conversation_state(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול במצבי שיחה שונים"""
    user_id = update.effective_user.id
    state = user_states[user_id]
    text = update.message.text
    
    if state == "quick_description":
        temp_data[user_id]["description"] = text
        user_states[user_id] = "quick_anxiety_level"
        
        await update.message.reply_text(
            "באיזה רמת חרדה? (שלב 2/4)",
            reply_markup=get_anxiety_level_keyboard()
        )
    
    elif state == "full_description":
        temp_data[user_id]["description"] = text
        user_states[user_id] = "full_anxiety_level"
        
        await update.message.reply_text(
            "באיזה רמת חרדה? (1-10)",
            reply_markup=get_anxiety_level_keyboard()
        )
    
    elif state == "free_venting":
        await handle_free_venting_complete(update, context, text)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בלחיצות על כפתורים"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("anxiety_"):
        anxiety_level = int(data.split("_")[1])
        temp_data[user_id]["anxiety_level"] = anxiety_level
        
        if user_states[user_id] == "quick_anxiety_level":
            await complete_quick_report(query, context)
        elif user_states[user_id] == "full_anxiety_level":
            await continue_full_report(query, context)
    
    elif data.startswith("location_"):
        location = data.replace("location_", "")
        temp_data[user_id]["location"] = location
        user_states[user_id] = "full_people"
        
        await query.edit_message_text(
            "מי היה בסביבה? (שלב 4/4)",
            reply_markup=get_options_keyboard(PEOPLE_OPTIONS, "people")
        )
    
    elif data.startswith("people_"):
        people = data.replace("people_", "")
        temp_data[user_id]["people_around"] = people
        user_states[user_id] = "full_weather"
        
        await query.edit_message_text(
            "איך מזג האוויר? (שלב 4/4)",
            reply_markup=get_options_keyboard(WEATHER_OPTIONS, "weather")
        )
    
    elif data.startswith("weather_"):
        weather = data.replace("weather_", "")
        temp_data[user_id]["weather"] = weather
        await complete_full_report(query, context)
    
    elif data == "save_venting_yes":
        await save_venting(query, context, True)
    elif data == "save_venting_no":
        await save_venting(query, context, False)
    
    elif data == "main_menu":
        await query.edit_message_text(
            "בחר אפשרות מהתפריט:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="back_to_main")]])
        )
    
    elif data == "relaxing_music":
        await show_relaxing_music(query, context)
    elif data == "start_using":
        await query.edit_message_text(
            "🎯 מעולה! אני כאן בשבילך.\n\nבחר מה מתאים לך עכשיו דרך התפריט שמופיע למטה בצ'אט:"
        )
    
    # הגדרות
    elif data == "settings_reminders":
        await handle_reminder_settings(query, context)
    elif data == "settings_report_type":
        await handle_report_type_settings(query, context)
    elif data == "settings_export":
        await handle_export_data(query, context)
    elif data == "settings_reset":
        await handle_reset_data(query, context)
    
    # תזכורות
    elif data == "reminder_on":
        await update_reminder_setting(query, context, True)
    elif data == "reminder_off":
        await update_reminder_setting(query, context, False)
    
    # סוג דיווח
    elif data == "report_type_quick":
        await update_report_type(query, context, "quick")
    elif data == "report_type_full":
        await update_report_type(query, context, "full")
    
    # איפוס מאושר
    elif data == "confirm_reset":
        await confirm_reset_data(query, context)
    
    # חזרה להגדרות
    elif data == "back_to_settings":
        await show_settings_inline(query, context)

async def complete_quick_report(query, context):
    """השלמת דיווח מהיר"""
    user_id = query.from_user.id
    data = temp_data[user_id]
    
    # שמירה בבסיס נתונים
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO anxiety_reports (user_id, timestamp, anxiety_level, description, report_type)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, data["timestamp"], data["anxiety_level"], data["description"], "quick"))
    conn.commit()
    conn.close()
    
    # מתן המלצה מיידית
    recommendation = get_immediate_recommendation(data["anxiety_level"])
    
    # הודעת אישור ברורה
    time_formatted = datetime.strptime(data["timestamp"], '%Y-%m-%d %H:%M:%S').strftime("%H:%M")
    
    message = f"""
✅ דיווח נשמר בהצלחה!

📊 סיכום הדיווח:
• רמת חרדה: {data["anxiety_level"]}/10
• זמן: {time_formatted}
• סוג: דיווח מהיר

💡 המלצה מיידית:
{recommendation}

רוצה להוסיף פרטים נוספים או לראות עזרה כללית?
"""
    
    # ניקוי מצב
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🔍 הוסף פרטים", callback_data="add_details")],
        [InlineKeyboardButton("💡 עזרה כללית", callback_data="show_help")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def continue_full_report(query, context):
    """המשך דיווח מלא"""
    user_id = query.from_user.id
    user_states[user_id] = "full_location"
    
    await query.edit_message_text(
        "איפה זה קרה? (שלב 3/4)",
        reply_markup=get_options_keyboard(LOCATION_OPTIONS, "location")
    )

async def complete_full_report(query, context):
    """השלמת דיווח מלא"""
    user_id = query.from_user.id
    data = temp_data[user_id]
    
    # שמירה בבסיס נתונים
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO anxiety_reports (user_id, timestamp, anxiety_level, description, location, people_around, weather, report_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, data["timestamp"], data["anxiety_level"], data["description"], 
          data["location"], data["people_around"], data["weather"], "full"))
    conn.commit()
    conn.close()
    
    # ניתוח ומתן המלצות
    analysis = analyze_user_patterns(user_id)
    recommendation = get_personalized_recommendation(user_id, data)
    
    # הודעת אישור מפורטת
    time_formatted = datetime.strptime(data["timestamp"], '%Y-%m-%d %H:%M:%S').strftime("%H:%M")
    
    message = f"""
✅ דיווח מלא נשמר בהצלחה!

📊 סיכום הדיווח:
• רמת חרדה: {data["anxiety_level"]}/10
• מיקום: {data["location"]}
• אנשים: {data["people_around"]}
• מזג אוויר: {data["weather"]}
• זמן: {time_formatted}

🧠 תובנה אישית:
{analysis}

💡 המלצה מותאמת:
{recommendation}
"""
    
    # ניקוי מצב
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    
    keyboard = [
        [InlineKeyboardButton("📈 ראה גרפים", callback_data="show_analytics")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_free_venting_complete(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """השלמת פריקה חופשית"""
    user_id = update.effective_user.id
    
    keyboard = [
        [InlineKeyboardButton("💾 כן, שמור לניתוח", callback_data="save_venting_yes")],
        [InlineKeyboardButton("🗑️ לא, רק פריקה", callback_data="save_venting_no")]
    ]
    
    await update.message.reply_text(
        f"תודה שחלקת. זה יכול לעזור לפרוק.\n\nהאם לשמור את זה למעקב וניתוח?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    # שמירה זמנית
    temp_data[user_id] = {"venting_content": text}
    user_states[user_id] = "venting_save_choice"

async def save_venting(query, context, save_for_analysis):
    """שמירת פריקה חופשית"""
    user_id = query.from_user.id
    content = temp_data[user_id]["venting_content"]
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO free_venting (user_id, content, save_for_analysis)
    VALUES (?, ?, ?)
    ''', (user_id, content, save_for_analysis))
    conn.commit()
    conn.close()
    
    if save_for_analysis:
        message = "✅ פריקה נשמרה בהצלחה לניתוח! הפריקה שלך תעזור לי להבין טוב יותר את הדפוסים שלך."
    else:
        message = "✅ פריקה הושלמה! אני מקווה שזה עזר לך להרגיש טוב יותר."
    
    # ניקוי מצב
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    
    keyboard = [[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

def get_immediate_recommendation(anxiety_level):
    """המלצה מיידית על פי רמת חרדה"""
    if anxiety_level >= 8:
        return "רמת חרדה גבוהה! נסה טכניקת נשימה 4-4-6 עכשיו. אם זה ממשיך, שקול לפנות לעזרה מקצועית."
    elif anxiety_level >= 6:
        return "חרדה ברמה בינונית. נסה לזהות מה גורם לזה ולהשתמש בטכניקת 5-4-3-2-1."
    elif anxiety_level >= 4:
        return "חרדה קלה. זה הזמן הטוב לנשימה עמוקה ולהזכיר לעצמך שזה יעבור."
    else:
        return "רמת חרדה נמוכה. נהדר שאתה מודע לרגשות שלך!"

def analyze_user_patterns(user_id):
    """ניתוח דפוסים אישיים"""
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    
    # משיכת נתונים של השבועיים האחרונים
    two_weeks_ago = datetime.now() - timedelta(days=14)
    cursor.execute('''
    SELECT anxiety_level, location, people_around, weather, timestamp 
    FROM anxiety_reports 
    WHERE user_id = ? AND timestamp > ?
    ORDER BY timestamp DESC
    ''', (user_id, two_weeks_ago))
    
    reports = cursor.fetchall()
    conn.close()
    
    if len(reports) < 3:
        return "עדיין אוסף נתונים לניתוח דפוסים..."
    
    # ניתוח פשוט
    avg_anxiety = sum(report[0] for report in reports) / len(reports)
    location_counter = Counter(report[1] for report in reports if report[1])
    most_common_location = location_counter.most_common(1)[0][0] if location_counter else "לא ידוע"
    
    return f"הממוצע שלך: {avg_anxiety:.1f}/10. המיקום הבעייתי ביותר: {most_common_location}"

def get_personalized_recommendation(user_id, current_data):
    """המלצה מותאמת אישית"""
    base_recommendation = get_immediate_recommendation(current_data["anxiety_level"])
    
    if current_data.get("location") == "🏢 עבודה":
        return base_recommendation + "\n\nכיוון שזה בעבודה, נסה לקחת הפסקה קצרה או לצאת לאוויר צח."
    
    return base_recommendation

async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת גרפים וניתוחים"""
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT anxiety_level, timestamp, location, people_around 
    FROM anxiety_reports 
    WHERE user_id = ? 
    ORDER BY timestamp DESC LIMIT 30
    ''', (user_id,))
    
    reports = cursor.fetchall()
    conn.close()
    
    if not reports:
        await update.message.reply_text("עדיין אין נתונים לניתוח. התחל לדווח כדי לראות דפוסים!", reply_markup=get_main_keyboard())
        return
    
    # יצירת ניתוח טקסטואלי פשוט
    anxiety_levels = [report[0] for report in reports]
    avg_anxiety = sum(anxiety_levels) / len(anxiety_levels)
    max_anxiety = max(anxiety_levels)
    min_anxiety = min(anxiety_levels)
    
    locations = [report[2] for report in reports if report[2]]
    location_counter = Counter(locations)
    
    analysis_text = f"""
📈 הניתוח שלך (30 הדיווחים האחרונים):

📊 סטטיסטיקות:
• ממוצע חרדה: {avg_anxiety:.1f}/10
• חרדה מקסימלית: {max_anxiety}/10
• חרדה מינימלית: {min_anxiety}/10
• סה"כ דיווחים: {len(reports)}

📍 מיקומים בעייתיים:
"""
    
    for location, count in location_counter.most_common(3):
        percentage = (count / len(locations)) * 100 if locations else 0
        analysis_text += f"• {location}: {count} פעמים ({percentage:.1f}%)\n"
    
    analysis_text += "\n💡 לקבלת המלצות מותאמות, המשך לדווח על אירועי חרדה."
    
    await update.message.reply_text(analysis_text, reply_markup=get_main_keyboard())

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת עזרה כללית"""
    help_text = """
💡 עזרה כללית בהתמודדות עם חרדה:

🫁 טכניקות נשימה:
• נשימה 4-4-6: שאף 4 שניות, עצור 4, נשוף 6
• נשימה עמוקה מהבטן (לא מהחזה)

🧘‍♂️ טכניקות הרגעה:
• 5-4-3-2-1: מצא 5 דברים שאתה רואה, 4 שאתה שומע, 3 שאתה מרגיש, 2 שאתה מריח, 1 שאתה טועם
• הזכר לעצמך: "זה רגש, לא עובדה. זה יעבור"

💪 פעולות מיידיות:
• קום וזוז - תזוזה משחררת מתח
• שתה מים קרים
• שטוף פנים במים קרים
• התקשר לחבר

📞 עזרה מקצועית:
• ער"ן - עזרה רגשית ונפשית: 1201
  💬 צ'אט: https://www.eran.org.il/online-emotional-help/
• סה"ר - סיוע והקשבה: 1800-120-140
  💬 צ'אט 24/7: https://sahar.org.il/help/

⚠️ זכור: הבוט הזה לא מחליף טיפול מקצועי!
"""
    
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

async def show_relaxing_music_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת שירים מרגיעים מהתפריט הראשי"""
    music_text = """
🎵 שירים מרגיעים (מוכחים מחקרית לירידה בסטרס):

🎼 "Someone Like You" - Adele
🎧 יוטיוב: https://youtu.be/hLQl3WQQoQ0
🎶 ספוטיפיי: https://open.spotify.com/track/4gSMuI5TqvCKk0s0iY3I7I

🎼 "Please Don't Go" - Barcelona  
🎧 יוטיוב: https://youtu.be/-kizV91zQ_0
🎶 ספוטיפיי: https://open.spotify.com/track/0lRnbYaPtv0A5OezVahO8e

🎼 "Strawberry Swing" - Coldplay
🎧 יוטיוב: https://youtu.be/h3pJZSTQqIg
🎶 ספוטיפיי: https://open.spotify.com/track/0zVYSaFo1b2v8YDmx0QYEh

🎼 "Watermark" - Enya
🎧 יוטיוב: https://youtu.be/bPCdsa7hS7M
🎶 ספוטיפיי: https://open.spotify.com/track/4vOQ55pOMyE6bQJJzm3kei

🎼 "Weightless" - Marconi Union
🎧 יוטיוב: https://youtu.be/UfcAVejslrU
🎶 ספוטיפיי: https://open.spotify.com/track/6kkwzB6hXLIONkEk9JciA6

💡 מומלץ להאזין עם אוזניות בעוצמה נמוכה-בינונית
🧘‍♂️ נסה לנשום עמוק בזמן ההאזנה
"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 בוא נתחיל עכשיו", callback_data="start_using")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(music_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת גרפים וניתוחים"""
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT anxiety_level, timestamp, location, people_around 
    FROM anxiety_reports 
    WHERE user_id = ? 
    ORDER BY timestamp DESC LIMIT 30
    ''', (user_id,))
    
    reports = cursor.fetchall()
    conn.close()
    
    if not reports:
        await update.message.reply_text("עדיין אין נתונים לניתוח. התחל לדווח כדי לראות דפוסים!", reply_markup=get_main_keyboard())
        return
    
    # יצירת ניתוח טקסטואלי פשוט
    anxiety_levels = [report[0] for report in reports]
    avg_anxiety = sum(anxiety_levels) / len(anxiety_levels)
    max_anxiety = max(anxiety_levels)
    min_anxiety = min(anxiety_levels)
    
    locations = [report[2] for report in reports if report[2]]
    location_counter = Counter(locations)
    
    analysis_text = f"""
📈 הניתוח שלך (30 הדיווחים האחרונים):

📊 סטטיסטיקות:
• ממוצע חרדה: {avg_anxiety:.1f}/10
• חרדה מקסימלית: {max_anxiety}/10
• חרדה מינימלית: {min_anxiety}/10
• סה"כ דיווחים: {len(reports)}

📍 מיקומים בעייתיים:
"""
    
    for location, count in location_counter.most_common(3):
        percentage = (count / len(locations)) * 100 if locations else 0
        analysis_text += f"• {location}: {count} פעמים ({percentage:.1f}%)\n"
    
    analysis_text += "\n💡 לקבלת המלצות מותאמות, המשך לדווח על אירועי חרדה."
    
    await update.message.reply_text(analysis_text, reply_markup=get_main_keyboard())

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת עזרה כללית"""
    help_text = """
💡 עזרה כללית בהתמודדות עם חרדה:

🫁 טכניקות נשימה:
• נשימה 4-4-6: שאף 4 שניות, עצור 4, נשוף 6
• נשימה עמוקה מהבטן (לא מהחזה)

🧘‍♂️ טכניקות הרגעה:
• 5-4-3-2-1: מצא 5 דברים שאתה רואה, 4 שאתה שומע, 3 שאתה מרגיש, 2 שאתה מריח, 1 שאתה טועם
• הזכר לעצמך: "זה רגש, לא עובדה. זה יעבור"

💪 פעולות מיידיות:
• קום וזוז - תזוזה משחררת מתח
• שתה מים קרים
• שטוף פנים במים קרים
• התקשר לחבר

📞 עזרה מקצועית:
• ער"ן - עזרה רגשית ונפשית: 1201
  💬 צ'אט: https://www.eran.org.il/online-emotional-help/
• סה"ר - סיוע והקשבה: 1800-120-140
  💬 צ'אט 24/7: https://sahar.org.il/help/

⚠️ זכור: הבוט הזה לא מחליף טיפול מקצועי!
"""
    
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת תפריט הגדרות פועל"""
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("⚡ סוג דיווח מועדף", callback_data="settings_report_type")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")]
    ]
    
    await update.message.reply_text(
        "⚙️ הגדרות:\n\nבחר מה תרצה לשנות:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_settings_inline(query, context):
    """הצגת תפריט הגדרות בinline"""
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("⚡ סוג דיווח מועדף", callback_data="settings_report_type")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")]
    ]
    
    await query.edit_message_text(
        "⚙️ הגדרות:\n\nבחר מה תרצה לשנות:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_reminder_settings(query, context):
    """הגדרות תזכורות"""
    user_id = query.from_user.id
    
    # קריאת הגדרות נוכחיות
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_reminder, reminder_time FROM user_settings WHERE user_id = ?", (user_id,))
    settings = cursor.fetchone()
    conn.close()
    
    current_status = "מופעלות" if settings[0] else "כבויות"
    current_time = settings[1] if settings[0] else "20:00"
    
    keyboard = [
        [InlineKeyboardButton("🔔 הפעל תזכורות", callback_data="reminder_on")],
        [InlineKeyboardButton("🔕 כבה תזכורות", callback_data="reminder_off")],
        [InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        f"🔔 הגדרות תזכורות:\n\nסטטוס נוכחי: {current_status}\nשעת תזכורת: {current_time}\n\nמה תרצה לשנות?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_report_type_settings(query, context):
    """הגדרות סוג דיווח מועדף"""
    user_id = query.from_user.id
    
    # קריאת הגדרה נוכחית
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT preferred_report_type FROM user_settings WHERE user_id = ?", (user_id,))
    current_type = cursor.fetchone()[0]
    conn.close()
    
    current_desc = "מהיר" if current_type == "quick" else "מלא"
    
    keyboard = [
        [InlineKeyboardButton("⚡ דיווח מהיר", callback_data="report_type_quick")],
        [InlineKeyboardButton("🔍 דיווח מלא", callback_data="report_type_full")],
        [InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        f"⚡ סוג דיווח מועדף:\n\nנוכחי: {current_desc}\n\nאיזה סוג דיווח תעדיף כברירת מחדל?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_export_data(query, context):
    """ייצוא נתונים"""
    user_id = query.from_user.id
    
    try:
        # קריאת כל הנתונים
        conn = sqlite3.connect('anxiety_data.db')
        cursor = conn.cursor()
        
        # דיווחי חרדה
        cursor.execute('''
        SELECT timestamp, anxiety_level, description, location, people_around, weather, report_type
        FROM anxiety_reports WHERE user_id = ? ORDER BY timestamp DESC
        ''', (user_id,))
        reports = cursor.fetchall()
        
        # פריקות חופשיות
        cursor.execute('''
        SELECT timestamp, content FROM free_venting 
        WHERE user_id = ? AND save_for_analysis = 1 ORDER BY timestamp DESC
        ''', (user_id,))
        ventings = cursor.fetchall()
        
        conn.close()
        
        if not reports and not ventings:
            await query.edit_message_text(
                "📊 אין נתונים לייצוא עדיין.\n\nהתחל לדווח כדי שיהיו נתונים לייצא!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
            )
            return
        
        # יצירת קובץ טקסט
        export_text = f"📊 ייצוא נתונים - {datetime.now().strftime('%d/%m/%Y')}\n\n"
        
        if reports:
            export_text += "📈 דיווחי חרדה:\n" + "="*30 + "\n"
            for report in reports:
                export_text += f"תאריך: {report[0]}\n"
                export_text += f"רמת חרדה: {report[1]}/10\n"
                export_text += f"תיאור: {report[2]}\n"
                if report[3]: export_text += f"מיקום: {report[3]}\n"
                if report[4]: export_text += f"אנשים: {report[4]}\n"
                if report[5]: export_text += f"מזג אוויר: {report[5]}\n"
                export_text += f"סוג: {report[6]}\n\n"
        
        if ventings:
            export_text += "🗣️ פריקות שנשמרו:\n" + "="*30 + "\n"
            for venting in ventings:
                export_text += f"תאריך: {venting[0]}\n"
                export_text += f"תוכן: {venting[1]}\n\n"
        
        # שליחת הקובץ
        file_buffer = io.BytesIO(export_text.encode('utf-8'))
        file_buffer.name = f"anxiety_data_{datetime.now().strftime('%Y%m%d')}.txt"
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_buffer,
            filename=f"נתוני_חרדה_{datetime.now().strftime('%d_%m_%Y')}.txt",
            caption="✅ הנתונים שלך יוצאו בהצלחה!\n\n🔒 זכור: זה מידע רגיש, שמור במקום בטוח."
        )
        
        await query.edit_message_text(
            "✅ הנתונים נשלחו אליך כקובץ!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
        )
        
    except Exception as e:
        await query.edit_message_text(
            "❌ שגיאה בייצוא הנתונים. נסה שוב מאוחר יותר.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
        )

async def handle_reset_data(query, context):
    """איפוס נתונים"""
    keyboard = [
        [InlineKeyboardButton("⚠️ כן, מחק הכל", callback_data="confirm_reset")],
        [InlineKeyboardButton("❌ ביטול", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        "🗑️ איפוס נתונים:\n\n⚠️ פעולה זו תמחק את כל הנתונים שלך:\n• כל דיווחי החרדה\n• כל הפריקות\n• ההיסטוריה והגרפים\n\nהאם אתה בטוח?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def update_reminder_setting(query, context, enabled):
    """עדכון הגדרת תזכורות"""
    user_id = query.from_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE user_settings SET daily_reminder = ? WHERE user_id = ?", (enabled, user_id))
    conn.commit()
    conn.close()
    
    status = "הופעלו" if enabled else "בוטלו"
    await query.edit_message_text(
        f"✅ תזכורות {status} בהצלחה!",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
    )

async def update_report_type(query, context, report_type):
    """עדכון סוג דיווח מועדף"""
    user_id = query.from_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE user_settings SET preferred_report_type = ? WHERE user_id = ?", (report_type, user_id))
    conn.commit()
    conn.close()
    
    type_desc = "מהיר" if report_type == "quick" else "מלא"
    await query.edit_message_text(
        f"✅ סוג דיווח מועדף עודכן ל: {type_desc}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
    )

async def confirm_reset_data(query, context):
    """אישור איפוס נתונים"""
    user_id = query.from_user.id
    
    try:
        conn = sqlite3.connect('anxiety_data.db')
        cursor = conn.cursor()
        
        # מחיקת כל הנתונים של המשתמש
        cursor.execute("DELETE FROM anxiety_reports WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM free_venting WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            "✅ כל הנתונים נמחקו בהצלחה!\n\nאתה יכול להתחיל מחדש עם דיווחים חדשים.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]])
        )
        
    except Exception as e:
        await query.edit_message_text(
            "❌ שגיאה במחיקת הנתונים. נסה שוב מאוחר יותר.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
        )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """לוג שגיאות"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """פונקציה ראשית"""
    try:
        # יצירת בסיס נתונים
        init_database()
        
        # יצירת האפליקציה
        application = Application.builder().token(BOT_TOKEN).build()
        
        # הוספת handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        
        # הוספת error handler
        application.add_error_handler(error_handler)
        
        # הרצת הבוט
        logger.info("🤖 הבוט מתחיל לרוץ...")
        application.run_polling()
            
    except Exception as e:
        logger.error(f"שגיאה בהפעלת הבוט: {e}")
        raise

if __name__ == '__main__':
    main()

🎼 "Watermark" - Enya
🎧 יוטיוב: https://youtu.be/bPCdsa7hS7M
🎶 ספוטיפיי: https://open.spotify.com/track/4vOQ55pOMyE6bQJJzm3kei

🎼 "Weightless" - Marconi Union
🎧 יוטיוב: https://youtu.be/UfcAVejslrU
🎶 ספוטיפיי: https://open.spotify.com/track/6kkwzB6hXLIONkEk9JciA6

💡 מומלץ להאזין עם אוזניות בעוצמה נמוכה-בינונית
🧘‍♂️ נסה לנשום עמוק בזמן ההאזנה
"""
    
    await update.message.reply_text(music_text, reply_markup=get_main_keyboard())

async def show_relaxing_music(query, context):
    """הצגת רשימת שירים מרגיעים"""
    music_text = """
🎵 שירים מרגיעים (מוכחים מחקרית לירידה בסטרס):

🎼 "Someone Like You" - Adele
🎧 יוטיוב: https://youtu.be/hLQl3WQQoQ0
🎶 ספוטיפיי: https://open.spotify.com/track/4gSMuI5TqvCKk0s0iY3I7I

🎼 "Please Don't Go" - Barcelona  
🎧 יוטיוב: https://youtu.be/-kizV91zQ_0
🎶 ספוטיפיי: https://open.spotify.com/track/0lRnbYaPtv0A5OezVahO8e

🎼 "Strawberry Swing" - Coldplay
🎧 יוטיוב: https://youtu.be/h3pJZSTQqIg
🎶 ספוטיפיי: https://open.spotify.com/track/0zVYSaFo1b2v8YDmx0QYEh

🎼 "Watermark" - Enya
🎧 יוטיוב: https://youtu.be/bPCdsa7hS7M
🎶 ספוטיפיי: https://open.spotify.com/track/4vOQ55pOMyE6bQJJzm3kei

🎼 "Weightless" - Marconi Union
🎧 יוטיוב: https://youtu.be/UfcAVejslrU
🎶 ספוטיפיי: https://open.spotify.com/track/6kkwzB6hXLIONkEk9JciA6

💡 מומלץ להאזין עם אוזניות בעוצמה נמוכה-בינונית
🧘‍♂️ נסה לנשום עמוק בזמן ההאזנה
"""
    
    keyboard = [
        [InlineKeyboardButton("🚀 בוא נתחיל עכשיו", callback_data="start_using")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(music_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת תפריט הגדרות פועל"""
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("⚡ סוג דיווח מועדף", callback_data="settings_report_type")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")]
    ]
    
    await update.message.reply_text(
        "⚙️ הגדרות:\n\nבחר מה תרצה לשנות:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_reminder_settings(query, context):
    """הגדרות תזכורות"""
    user_id = query.from_user.id
    
    # קריאת הגדרות נוכחיות
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_reminder, reminder_time FROM user_settings WHERE user_id = ?", (user_id,))
    settings = cursor.fetchone()
    conn.close()
    
    current_status = "מופעלות" if settings[0] else "כבויות"
    current_time = settings[1] if settings[0] else "20:00"
    
    keyboard = [
        [InlineKeyboardButton("🔔 הפעל תזכורות", callback_data="reminder_on")],
        [InlineKeyboardButton("🔕 כבה תזכורות", callback_data="reminder_off")],
        [InlineKeyboardButton("⏰ שנה שעת תזכורת", callback_data="reminder_time")],
        [InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        f"🔔 הגדרות תזכורות:\n\nסטטוס נוכחי: {current_status}\nשעת תזכורת: {current_time}\n\nמה תרצה לשנות?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_report_type_settings(query, context):
    """הגדרות סוג דיווח מועדף"""
    user_id = query.from_user.id
    
    # קריאת הגדרה נוכחית
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT preferred_report_type FROM user_settings WHERE user_id = ?", (user_id,))
    current_type = cursor.fetchone()[0]
    conn.close()
    
    current_desc = "מהיר" if current_type == "quick" else "מלא"
    
    keyboard = [
        [InlineKeyboardButton("⚡ דיווח מהיר", callback_data="report_type_quick")],
        [InlineKeyboardButton("🔍 דיווח מלא", callback_data="report_type_full")],
        [InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        f"⚡ סוג דיווח מועדף:\n\nנוכחי: {current_desc}\n\nאיזה סוג דיווח תעדיף כברירת מחדל?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_export_data(query, context):
    """ייצוא נתונים"""
    user_id = query.from_user.id
    
    try:
        # קריאת כל הנתונים
        conn = sqlite3.connect('anxiety_data.db')
        cursor = conn.cursor()
        
        # דיווחי חרדה
        cursor.execute('''
        SELECT timestamp, anxiety_level, description, location, people_around, weather, report_type
        FROM anxiety_reports WHERE user_id = ? ORDER BY timestamp DESC
        ''', (user_id,))
        reports = cursor.fetchall()
        
        # פריקות חופשיות
        cursor.execute('''
        SELECT timestamp, content FROM free_venting 
        WHERE user_id = ? AND save_for_analysis = 1 ORDER BY timestamp DESC
        ''', (user_id,))
        ventings = cursor.fetchall()
        
        conn.close()
        
        if not reports and not ventings:
            await query.edit_message_text(
                "📊 אין נתונים לייצוא עדיין.\n\nהתחל לדווח כדי שיהיו נתונים לייצא!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
            )
            return
        
        # יצירת קובץ טקסט
        export_text = f"📊 ייצוא נתונים - {datetime.now().strftime('%d/%m/%Y')}\n\n"
        
        if reports:
            export_text += "📈 דיווחי חרדה:\n" + "="*30 + "\n"
            for report in reports:
                export_text += f"תאריך: {report[0]}\n"
                export_text += f"רמת חרדה: {report[1]}/10\n"
                export_text += f"תיאור: {report[2]}\n"
                if report[3]: export_text += f"מיקום: {report[3]}\n"
                if report[4]: export_text += f"אנשים: {report[4]}\n"
                if report[5]: export_text += f"מזג אוויר: {report[5]}\n"
                export_text += f"סוג: {report[6]}\n\n"
        
        if ventings:
            export_text += "🗣️ פריקות שנשמרו:\n" + "="*30 + "\n"
            for venting in ventings:
                export_text += f"תאריך: {venting[0]}\n"
                export_text += f"תוכן: {venting[1]}\n\n"
        
        # שליחת הקובץ
        import io
        file_buffer = io.BytesIO(export_text.encode('utf-8'))
        file_buffer.name = f"anxiety_data_{datetime.now().strftime('%Y%m%d')}.txt"
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_buffer,
            filename=f"נתוני_חרדה_{datetime.now().strftime('%d_%m_%Y')}.txt",
            caption="✅ הנתונים שלך יוצאו בהצלחה!\n\n🔒 זכור: זה מידע רגיש, שמור במקום בטוח."
        )
        
        await query.edit_message_text(
            "✅ הנתונים נשלחו אליך כקובץ!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
        )
        
    except Exception as e:
        await query.edit_message_text(
            "❌ שגיאה בייצוא הנתונים. נסה שוב מאוחר יותר.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 חזור להגדרות", callback_data="back_to_settings")]])
        )

async def handle_reset_data(query, context):
    """איפוס נתונים"""
    keyboard = [
        [InlineKeyboardButton("⚠️ כן, מחק הכל", callback_data="confirm_reset")],
        [InlineKeyboardButton("❌ ביטול", callback_data="back_to_settings")]
    ]
    
    await query.edit_message_text(
        "🗑️ איפוס נתונים:\n\n⚠️ פעולה זו תמחק את כל הנתונים שלך:\n• כל דיווחי החרדה\n• כל הפריקות\n• ההיסטוריה והגרפים\n\nהאם אתה בטוח?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """לוג שגיאות"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main():
    """פונקציה ראשית"""
    try:
        # יצירת בסיס נתונים
        init_database()
        
        # יצירת האפליקציה
        application = Application.builder().token(BOT_TOKEN).build()
        
        # הוספת handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        
        # הוספת error handler
        application.add_error_handler(error_handler)
        
        # הרצת הבוט
        logger.info("🤖 הבוט מתחיל לרוץ...")
        application.run_polling()
            
    except Exception as e:
        logger.error(f"שגיאה בהפעלת הבוט: {e}")
        raise

if __name__ == '__main__':
    main()
