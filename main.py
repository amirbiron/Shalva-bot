import logging
import sqlite3
import os
import json
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from collections import Counter

# הגדרות לוגים
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# טוקן הבוט - עבור לקובץ .env או משתני סביבה!
BOT_TOKEN = os.getenv('BOT_TOKEN', "7622868890:AAEnk_PC-hbOJIYWICXgE8F654RlOJxY5Sk")

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
        timestamp TEXT,
        anxiety_level INTEGER,
        description TEXT,
        location TEXT,
        people_around TEXT,
        weather TEXT,
        report_type TEXT DEFAULT 'full',
        created_at TEXT DEFAULT (datetime('now'))
    )
    ''')
    
    # טבלת פריקות חופשיות
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS free_venting (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        save_for_analysis BOOLEAN DEFAULT FALSE,
        timestamp TEXT DEFAULT (datetime('now'))
    )
    ''')
    
    # טבלת הגדרות משתמש - מורחבת
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY,
        daily_reminder BOOLEAN DEFAULT FALSE,
        reminder_time TEXT DEFAULT '20:00',
        preferred_report_type TEXT DEFAULT 'quick',
        notifications_enabled BOOLEAN DEFAULT TRUE,
        language TEXT DEFAULT 'he'
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

# שלבי הדיווח המלא
FULL_REPORT_STEPS = {
    'full_description': {'step': 1, 'total': 4, 'next': 'full_anxiety_level'},
    'full_anxiety_level': {'step': 2, 'total': 4, 'next': 'full_location'},
    'full_location': {'step': 3, 'total': 4, 'next': 'full_people'},
    'full_people': {'step': 4, 'total': 4, 'next': 'full_weather'},
}

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

def get_progress_indicator(current_step, total_steps):
    """יצירת מחוון התקדמות"""
    filled = "●" * current_step
    empty = "○" * (total_steps - current_step)
    return f"{filled}{empty} ({current_step}/{total_steps})"

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
        await show_settings_menu(update, context)
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
    temp_data[user_id] = {
        "report_type": "quick", 
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    await update.message.reply_text(
        "⚡ דיווח מהיר\n\n🔄 שלב 1/2: תיאור המצב\n\nמה קורה עכשיו? (תיאור קצר)",
        reply_markup=None
    )

async def start_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת דיווח מלא"""
    user_id = update.effective_user.id
    user_states[user_id] = "full_description"
    temp_data[user_id] = {
        "report_type": "full", 
        "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    progress = get_progress_indicator(1, 5)
    await update.message.reply_text(
        f"🔍 דיווח מלא\n\n{progress} תיאור המצב\n\nמה גורם לחרדה עכשיו? (תאר במפורט)",
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
        
        progress = get_progress_indicator(2, 2)
        await update.message.reply_text(
            f"⚡ דיווח מהיר\n\n{progress} רמת חרדה\n\nבאיזה רמת חרדה? (1-10)",
            reply_markup=get_anxiety_level_keyboard()
        )
    
    elif state == "full_description":
        temp_data[user_id]["description"] = text
        user_states[user_id] = "full_anxiety_level"
        
        progress = get_progress_indicator(2, 5)
        await update.message.reply_text(
            f"🔍 דיווח מלא\n\n{progress} רמת חרדה\n\nבאיזה רמת חרדה? (1-10)",
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
        
        progress = get_progress_indicator(4, 5)
        await query.edit_message_text(
            f"🔍 דיווח מלא\n\n{progress} אנשים בסביבה\n\nמי היה בסביבה?",
            reply_markup=get_options_keyboard(PEOPLE_OPTIONS, "people")
        )
    
    elif data.startswith("people_"):
        people = data.replace("people_", "")
        temp_data[user_id]["people_around"] = people
        user_states[user_id] = "full_weather"
        
        progress = get_progress_indicator(5, 5)
        await query.edit_message_text(
            f"🔍 דיווח מלא\n\n{progress} מזג אוויר\n\nאיך מזג האוויר?",
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
    
    # הגדרות חדשות
    elif data.startswith("settings_"):
        await handle_settings_callback(query, context)
    
    elif data == "main_menu":
        await query.edit_message_text(
            "🏠 חזרת לתפריט הראשי\n\nבחר אפשרות מהתפריט למטה:",
        )
    
    elif data == "relaxing_music":
        await show_relaxing_music(query, context)
    elif data == "start_using":
        await query.edit_message_text(
            "🎯 מעולה! אני כאן בשבילך.\n\nבחר מה מתאים לך עכשיו דרך התפריט שמופיע למטה בצ'אט:"
        )

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
    
    message = f"""
✅ דיווח נשמר בהצלחה!

📊 הדיווח שלך:
• רמת חרדה: {data["anxiety_level"]}/10
• זמן: {datetime.strptime(data["timestamp"], '%Y-%m-%d %H:%M:%S').strftime("%H:%M")}
• תיאור: {data["description"][:50]}{'...' if len(data["description"]) > 50 else ''}

💡 המלצה מיידית:
{recommendation}

🎯 המערכת למדה משהו חדש עליך!
"""
    
    # ניקוי מצב
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🔍 הוסף פרטים נוספים", callback_data="add_details")],
        [InlineKeyboardButton("📈 ראה גרפים", callback_data="show_analytics")],
        [InlineKeyboardButton("💡 עזרה כללית", callback_data="show_help")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def continue_full_report(query, context):
    """המשך דיווח מלא"""
    user_id = query.from_user.id
    user_states[user_id] = "full_location"
    
    progress = get_progress_indicator(3, 5)
    await query.edit_message_text(
        f"🔍 דיווח מלא\n\n{progress} מיקום\n\nאיפה זה קרה?",
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
    
    message = f"""
🎉 דיווח מלא נשמר בהצלחה!

📊 הדיווח שלך:
• רמת חרדה: {data["anxiety_level"]}/10
• מיקום: {data["location"]}
• אנשים: {data["people_around"]}
• מזג אוויר: {data["weather"]}
• זמן: {datetime.strptime(data["timestamp"], '%Y-%m-%d %H:%M:%S').strftime("%H:%M")}

🧠 תובנה אישית:
{analysis}

💡 המלצה מותאמת:
{recommendation}

✨ כל הכבוד על השלמת הדיווח המלא!
"""
    
    # ניקוי מצב
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    
    keyboard = [
        [InlineKeyboardButton("📈 ראה גרפים והיסטוריה", callback_data="show_analytics")],
        [InlineKeyboardButton("🎵 שיר מרגיע", callback_data="relaxing_music")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_free_venting_complete(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
    """השלמת פריקה חופשית"""
    user_id = update.effective_user.id
    
    # הודעת אישור
    await update.message.reply_text(
        "💝 תודה שחלקת איתי. זה דורש אומץ לפתוח את הלב.\n\nהאם לשמור את זה למעקב וניתוח עתידי?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 כן, שמור לניתוח", callback_data="save_venting_yes")],
            [InlineKeyboardButton("🗑️ לא, רק פריקה", callback_data="save_venting_no")]
        ])
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
    INSERT INTO free_venting (user_id, content, save_for_analysis, timestamp)
    VALUES (?, ?, ?, ?)
    ''', (user_id, content, save_for_analysis, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    
    if save_for_analysis:
        message = "✅ נשמר בהצלחה לניתוח!\n\n💡 הפריקה שלך תעזור לי להבין טוב יותר את הדפוסים שלך ולתת המלצות מותאמות."
    else:
        message = "✅ הפריקה הושלמה!\n\n🌟 אני מקווה שזה עזר לך להרגיש טוב יותר. לפעמים פשוט לכתוב את מה שמרגישים זה הרבה."
    
    # ניקוי מצב
    if user_id in user_states:
        del user_states[user_id]
    if user_id in temp_data:
        del temp_data[user_id]
    
    keyboard = [
        [InlineKeyboardButton("🎵 שיר מרגיע", callback_data="relaxing_music")],
        [InlineKeyboardButton("💡 עזרה כללית", callback_data="show_help")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

# פונקציות הגדרות חדשות
async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת תפריט הגדרות מלא"""
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("⚡ סוג דיווח מועדף", callback_data="settings_report_type")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")],
        [InlineKeyboardButton("🏠 חזור לתפריט", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(
        "⚙️ הגדרות\n\nבחר מה תרצה לשנות:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_settings_callback(query, context):
    """טיפול בהגדרות"""
    user_id = query.from_user.id
    data = query.data
    
    if data == "settings_reminders":
        await show_reminder_settings(query, context)
    elif data == "settings_report_type":
        await show_report_type_settings(query, context)
    elif data == "settings_export":
        await export_user_data(query, context)
    elif data == "settings_reset":
        await confirm_reset_data(query, context)
    elif data.startswith("reminder_"):
        await toggle_reminders(query, context)
    elif data.startswith("report_type_"):
        await set_report_type(query, context)
    elif data == "confirm_reset":
        await reset_user_data(query, context)

async def show_reminder_settings(query, context):
    """הגדרות תזכורות"""
    user_id = query.from_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_reminder, reminder_time FROM user_settings WHERE user_id = ?", (user_id,))
    settings = cursor.fetchone()
    conn.close()
    
    current_status = "מופעל" if settings[0] else "מופסק"
    reminder_time = settings[1] if settings[1] else "20:00"
    
    keyboard = [
        [InlineKeyboardButton(f"🔔 {'השבת' if settings[0] else 'הפעל'} תזכורות", 
                            callback_data=f"reminder_toggle")],
        [InlineKeyboardButton("⏰ שנה שעה", callback_data="reminder_time")],
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")]
    ]
    
    message = f"""
🔔 הגדרות תזכורות

סטטוס נוכחי: {current_status}
שעת תזכורת: {reminder_time}

תזכורות יומיות יכולות לעזור לך לזכור לעקוב אחר הרגשות שלך באופן קבוע.
"""
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_report_type_settings(query, context):
    """הגדרות סוג דיווח מועדף"""
    user_id = query.from_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT preferred_report_type FROM user_settings WHERE user_id = ?", (user_id,))
    current_type = cursor.fetchone()[0]
    conn.close()
    
    keyboard = [
        [InlineKeyboardButton(f"⚡ דיווח מהיר {'✓' if current_type == 'quick' else ''}", 
                            callback_data="report_type_quick")],
        [InlineKeyboardButton(f"🔍 דיווח מלא {'✓' if current_type == 'full' else ''}", 
                            callback_data="report_type_full")],
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")]
    ]
    
    message = f"""
⚡ סוג דיווח מועדף

הגדרה נוכחית: {'דיווח מהיר' if current_type == 'quick' else 'דיווח מלא'}

• דיווח מהיר: מהיר ופשוט, רק תיאור ורמת חרדה
• דיווח מלא: מפורט עם פרטים על מיקום, אנשים ומזג אוויר
"""
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def export_user_data(query, context):
    """ייצוא נתוני המשתמש"""
    user_id = query.from_user.id
    
    try:
        conn = sqlite3.connect('anxiety_data.db')
        cursor = conn.cursor()
        
        # שליפת דיווחי חרדה
        cursor.execute('''
        SELECT timestamp, anxiety_level, description, location, people_around, weather, report_type
        FROM anxiety_reports WHERE user_id = ? ORDER BY timestamp DESC
        ''', (user_id,))
        anxiety_reports = cursor.fetchall()
        
        # שליפת פריקות חופשיות
        cursor.execute('''
        SELECT timestamp, content FROM free_venting 
        WHERE user_id = ? AND save_for_analysis = 1 ORDER BY timestamp DESC
        ''', (user_id,))
        ventings = cursor.fetchall()
        
        conn.close()
        
        # יצירת קובץ JSON
        export_data = {
            "export_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "anxiety_reports": [
                {
                    "timestamp": report[0],
                    "anxiety_level": report[1],
                    "description": report[2],
                    "location": report[3],
                    "people_around": report[4],
                    "weather": report[5],
                    "report_type": report[6]
                }
                for report in anxiety_reports
            ],
            "free_ventings": [
                {
                    "timestamp": venting[0],
                    "content": venting[1]
                }
                for venting in ventings
            ],
            "statistics": {
                "total_reports": len(anxiety_reports),
                "total_ventings": len(ventings),
                "avg_anxiety_level": sum(r[1] for r in anxiety_reports) / len(anxiety_reports) if anxiety_reports else 0
            }
        }
        
        # שליחת הקובץ
        json_data = json.dumps(export_data, ensure_ascii=False, indent=2)
        
        message = f"""
✅ ייצוא נתונים הושלם!

📊 הנתונים שלך:
• {len(anxiety_reports)} דיווחי חרדה
• {len(ventings)} פריקות חופשיות
• ממוצע חרדה: {export_data['statistics']['avg_anxiety_level']:.1f}/10

📁 הנתונים מוכנים להורדה בפורמט JSON
"""
        
        keyboard = [
            [InlineKeyboardButton("📥 הורד קובץ", callback_data="download_data")],
            [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # שליחת הקובץ בהודעה נפרדת
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=json_data.encode('utf-8'),
            filename=f"anxiety_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            caption="📁 הנתונים שלך - שמור במקום בטוח!"
        )
        
    except Exception as e:
        await query.edit_message_text(
            "❌ שגיאה בייצוא הנתונים. נסה שוב מאוחר יותר.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזור", callback_data="settings_menu")]])
        )

async def confirm_reset_data(query, context):
    """אישור איפוס נתונים"""
    message = """
⚠️ איפוס נתונים

האם אתה בטוח שברצונך למחוק את כל הנתונים שלך?

פעולה זו תמחק:
• כל דיווחי החרדה
• כל הפריקות החופשיות  
• ההיסטוריה וההגדרות

⛔ פעולה זו בלתי הפיכה!
"""
    
    keyboard = [
        [InlineKeyboardButton("❌ ביטול", callback_data="settings_menu")],
        [InlineKeyboardButton("🗑️ כן, מחק הכל", callback_data="confirm_reset")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def reset_user_data(query, context):
    """איפוס נתוני המשתמש"""
    user_id = query.from_user.id
    
    try:
        conn = sqlite3.connect('anxiety_data.db')
        cursor = conn.cursor()
        
        # מחיקת כל הנתונים
        cursor.execute("DELETE FROM anxiety_reports WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM free_venting WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        
        # יצירת הגדרות חדשות
        cursor.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
        
        conn.commit()
        conn.close()
        
        message = """
✅ הנתונים נמחקו בהצלחה!

🆕 התחלתם מהתחלה עם חשבון נקי.
כל ההגדרות חזרו לברירות המחדל.

אני כאן לעזור לך להתחיל מחדש! 💙
"""
        
        keyboard = [[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        await query.edit_message_text(
            "❌ שגיאה במחיקת הנתונים. נסה שוב מאוחר יותר.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזור", callback_data="settings_menu")]])
        )

async def toggle_reminders(query, context):
    """הפעלה/השבתה של תזכורות"""
    user_id = query.from_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_reminder FROM user_settings WHERE user_id = ?", (user_id,))
    current_status = cursor.fetchone()[0]
    
    # החלפת הסטטוס
    new_status = not current_status
    cursor.execute("UPDATE user_settings SET daily_reminder = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    
    status_text = "הופעלו" if new_status else "הושבתו"
    
    message = f"""
✅ תזכורות {status_text} בהצלחה!

{'🔔 תקבל תזכורת יומית לדווח על הרגשות שלך' if new_status else '🔕 לא תקבל עוד תזכורות יומיות'}
"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 חזור להגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def set_report_type(query, context):
    """הגדרת סוג דיווח מועדף"""
    user_id = query.from_user.id
    report_type = query.data.split("_")[-1]  # quick או full
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE user_settings SET preferred_report_type = ? WHERE user_id = ?", (report_type, user_id))
    conn.commit()
    conn.close()
    
    type_text = "דיווח מהיר" if report_type == "quick" else "דיווח מלא"
    
    message = f"""
✅ סוג הדיווח המועדף הוגדר ל{type_text}!

🎯 בדיווחים הבאים המערכת תציע לך ראשית את סוג הדיווח שבחרת.
"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

def get_immediate_recommendation(anxiety_level):
    """המלצה מיידית על פי רמת חרדה"""
    if anxiety_level >= 8:
        return "🚨 רמת חרדה גבוהה! נסה טכניקת נשימה 4-4-6 עכשיו: שאף 4 שניות, עצור 4, נשוף 6. אם זה ממשיך, שקול לפנות לעזרה מקצועית."
    elif anxiety_level >= 6:
        return "⚠️ חרדה ברמה בינונית. נסה לזהות מה גורם לזה ולהשתמש בטכניקת 5-4-3-2-1: מצא 5 דברים שאתה רואה, 4 שאתה שומע, 3 שאתה מרגיש, 2 שאתה מריח, 1 שאתה טועם."
    elif anxiety_level >= 4:
        return "💛 חרדה קלה. זה הזמן הטוב לנשימה עמוקה ולהזכיר לעצמך שזה יעבור. נסה לשתות מים קרים או לצאת לאוויר צח."
    else:
        return "💚 רמת חרדה נמוכה. נהדר שאתה מודע לרגשות שלך! זה הזמן לחזק את הרגשה הטובה."

def analyze_user_patterns(user_id):
    """ניתוח דפוסים אישיים"""
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    
    # משיכת נתונים של השבועיים האחרונים
    two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('''
    SELECT anxiety_level, location, people_around, weather, timestamp 
    FROM anxiety_reports 
    WHERE user_id = ? AND timestamp > ?
    ORDER BY timestamp DESC
    ''', (user_id, two_weeks_ago))
    
    reports = cursor.fetchall()
    conn.close()
    
    if len(reports) < 3:
        return "🔍 עדיין אוסף נתונים לניתוח דפוסים. המשך לדווח כדי לקבל תובנות מותאמות!"
    
    # ניתוח פשוט
    avg_anxiety = sum(report[0] for report in reports) / len(reports)
    location_counter = Counter(report[1] for report in reports if report[1])
    people_counter = Counter(report[2] for report in reports if report[2])
    
    analysis = f"הממוצע שלך בשבועיים האחרונים: {avg_anxiety:.1f}/10"
    
    if location_counter:
        most_common_location = location_counter.most_common(1)[0]
        analysis += f"\nהמיקום הבעייתי ביותר: {most_common_location[0]} ({most_common_location[1]} פעמים)"
    
    if people_counter:
        most_common_people = people_counter.most_common(1)[0]
        analysis += f"\nמצבים עם: {most_common_people[0]} מופיעים הכי הרבה"
    
    return analysis

def get_personalized_recommendation(user_id, current_data):
    """המלצה מותאמת אישית"""
    base_recommendation = get_immediate_recommendation(current_data["anxiety_level"])
    
    if current_data.get("location") == "🏢 עבודה":
        base_recommendation += "\n\n💼 כיוון שזה בעבודה, נסה לקחת הפסקה קצרה, לצאת לאוויר צח או לדבר עם עמית שאתה סומך עליו."
    elif current_data.get("location") == "🏠 בית":
        base_recommendation += "\n\n🏠 אתה בבית - זה מקום בטוח. נסה לעשות משהו שמרגיע אותך: תה חם, מוזיקה, או קריאה."
    elif current_data.get("location") == "🚌 תחבורה ציבורית":
        base_recommendation += "\n\n🚌 תחבורה ציבורית יכולה להיות מלחיצה. נסה להתרכז בנשימה ולהקשיב למוזיקה מרגיעה."
    
    if current_data.get("people_around") == "👤 לבד":
        base_recommendation += "\n\n👤 אתה לבד עכשיו - זה בסדר. לפעמים קצת זמן לעצמנו זה בדיוק מה שאנחנו צריכים."
    
    return base_recommendation

async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת גרפים וניתוחים"""
    user_id = update.effective_user.id
    
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT anxiety_level, timestamp, location, people_around, report_type
    FROM anxiety_reports 
    WHERE user_id = ? 
    ORDER BY timestamp DESC LIMIT 30
    ''', (user_id,))
    
    reports = cursor.fetchall()
    conn.close()
    
    if not reports:
        await update.message.reply_text(
            "📊 עדיין אין נתונים לניתוח\n\nהתחל לדווח כדי לראות דפוסים מעניינים על עצמך! 🎯", 
            reply_markup=get_main_keyboard()
        )
        return
    
    # יצירת ניתוח טקסטואלי מפורט
    anxiety_levels = [report[0] for report in reports]
    avg_anxiety = sum(anxiety_levels) / len(anxiety_levels)
    max_anxiety = max(anxiety_levels)
    min_anxiety = min(anxiety_levels)
    
    # ניתוח מיקומים
    locations = [report[2] for report in reports if report[2]]
    location_counter = Counter(locations)
    
    # ניתוח אנשים
    people = [report[3] for report in reports if report[3]]
    people_counter = Counter(people)
    
    # ניתוח סוגי דיווח
    report_types = [report[4] for report in reports]
    quick_reports = sum(1 for rt in report_types if rt == 'quick')
    full_reports = sum(1 for rt in report_types if rt == 'full')
    
    analysis_text = f"""
📈 הניתוח שלך ({len(reports)} הדיווחים האחרונים):

📊 סטטיסטיקות כלליות:
• ממוצע חרדה: {avg_anxiety:.1f}/10
• חרדה מקסימלית: {max_anxiety}/10  
• חרדה מינימלית: {min_anxiety}/10
• דיווחים מהירים: {quick_reports}
• דיווחים מלאים: {full_reports}

📍 מיקומים שנמדדו:"""
    
    for location, count in location_counter.most_common(3):
        percentage = (count / len(locations)) * 100 if locations else 0
        avg_anxiety_location = sum(r[0] for r in reports if r[2] == location) / count
        analysis_text += f"\n• {location}: {count} פעמים ({percentage:.0f}%) - ממוצע חרדה: {avg_anxiety_location:.1f}"
    
    if people_counter:
        analysis_text += f"\n\n👥 מצבים חברתיים:"
        for people_type, count in people_counter.most_common(3):
            percentage = (count / len(people)) * 100 if people else 0
            avg_anxiety_people = sum(r[0] for r in reports if r[3] == people_type) / count
            analysis_text += f"\n• {people_type}: {count} פעמים ({percentage:.0f}%) - ממוצע חרדה: {avg_anxiety_people:.1f}"
    
    # הוספת מגמות
    if len(reports) >= 7:
        recent_week = anxiety_levels[:7]
        prev_week = anxiety_levels[7:14] if len(anxiety_levels) > 7 else []
        
        if prev_week:
            recent_avg = sum(recent_week) / len(recent_week)
            prev_avg = sum(prev_week) / len(prev_week)
            change = recent_avg - prev_avg
            
            if change > 0.5:
                trend = "📈 עלייה ברמת החרדה"
            elif change < -0.5:
                trend = "📉 ירידה ברמת החרדה"
            else:
                trend = "➡️ יציבות ברמת החרדה"
                
            analysis_text += f"\n\n🔄 מגמה: {trend} ({change:+.1f})"
    
    analysis_text += "\n\n💡 המשך לדווח באופן קבוע כדי לקבל תובנות מדויקות יותר!"
    
    await update.message.reply_text(analysis_text, reply_markup=get_main_keyboard())

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת עזרה כללית"""
    help_text = """
💡 עזרה כללית בהתמודדות עם חרדה:

🫁 טכניקות נשימה:
• נשימה 4-4-6: שאף 4 שניות, עצור 4, נשוף 6
• נשימה עמוקה מהבטן (לא מהחזה)
• נשימת קופסה: 4-4-4-4 (שאף, עצור, נשוף, עצור)

🧘‍♂️ טכניקות הרגעה מיידית:
• 5-4-3-2-1: מצא 5 דברים שאתה רואה, 4 שאתה שומע, 3 שאתה מרגיש, 2 שאתה מריח, 1 שאתה טועם
• הזכר לעצמך: "זה רגש, לא עובדה. זה יעבור"
• ספור לאחור מ-100 במקפצות של 7

💪 פעולות פיזיות מרגיעות:
• קום וזוז - תזוזה משחררת מתח
• שתה מים קרים לאט לאט
• שטוף פנים במים קרים
• לחץ על כף היד במקום בין האגודל והאצבע

🎯 טכניקות קוגניטיביות:
• שאל את עצמך: "האם זה באמת כל כך נורא?"
• חשוב על 3 דברים שאתה אסיר תודה עליהם
• דמיין מקום שקט ובטוח

📞 עזרה מקצועית 24/7:
• ער"ן - עזרה רגשית ונפשית: 1201
  💬 צ'אט: https://www.eran.org.il/online-emotional-help/
• סה"ר - סיוע והקשבה: 1800-120-140
  💬 צ'אט: https://sahar.org.il/help/
• נט"ל - קו חם לחירום נפשי: 1800-363-363

⚠️ חשוב לזכור: הבוט הזה לא מחליף טיפול מקצועי!
אם החרדה מפריעה לחיים הרגילים, מומלץ לפנות לעזרה מקצועית.
"""
    
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard())

async def show_relaxing_music_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת שירים מרגיעים מהתפריט הראשי"""
    music_text = """
🎵 שירים מרגיעים (מוכחים מחקרית לירידה בסטרס):

🎼 "Weightless" - Marconi Union
🎧 יוטיוב: https://youtu.be/UfcAVejslrU
🎶 ספוטיפיי: spotify:track:6j2P7MoSNEDE9BwT4CGBFA
⭐ השיר הכי מרגיע בעולם לפי מחקרים!

🎼 "Someone Like You" - Adele
🎧 יוטיוב: https://youtu.be/hLQl3WQQoQ0
🎶 ספוטיפיי: spotify:track:4gSMuI5TqvCKk0s0iY3I7I

🎼 "Watermark" - Enya
🎧 יוטיוב: https://youtu.be/0IKvdaXZP8Q
🎶 ספוטיפיי: spotify:track:4vOQ55pOMyE6bQJJzm3kei

🎼 "Strawberry Swing" - Coldplay
🎧 יוטיוב: https://youtu.be/h3pJZSTQqIg
🎶 ספוטיפיי: spotify:track:0zVYSaFo1b2v8YDmx0QYEh

🎼 "Claire de Lune" - Claude Debussy
🎧 יוטיוב: https://youtu.be/CvFH_6DNRCY
🎶 קלאסיקה מרגיעה במיוחד

🎼 "Aqueous Transmission" - Incubus
🎧 יוטיוב: https://youtu.be/_ndHqJ3RP5Y
🎶 מוזיקה אינסטרומנטלית ארוכה ומרגיעה

💡 טיפים להאזנה מרגיעה:
• האזן עם אוזניות בעוצמה נמוכה-בינונית
• נסה לנשום עמוק בזמן ההאזנה
• סגור עיניים ותן למוזיקה לשטוף אותך
• 8-10 דקות של האזנה יכולות להפחית סטרס משמעותית
"""
    
    await update.message.reply_text(music_text, reply_markup=get_main_keyboard())

async def show_relaxing_music(query, context):
    """הצגת רשימת שירים מרגיעים מכפתור"""
    music_text = """
🎵 שירים מרגיעים (מוכחים מחקרית לירידה בסטרס):

🎼 "Weightless" - Marconi Union
🎧 יוטיוב: https://youtu.be/UfcAVejslrU
⭐ השיר הכי מרגיע בעולם לפי מחקרים!

🎼 "Someone Like You" - Adele  
🎧 יוטיוב: https://youtu.be/hLQl3WQQoQ0

🎼 "Watermark" - Enya
🎧 יוטיוב: https://youtu.be/0IKvdaXZP8Q

🎼 "Strawberry Swing" - Coldplay
🎧 יוטיוב: https://youtu.be/h3pJZSTQqIg

🎼 "Claire de Lune" - Claude Debussy
🎧 יוטיוב: https://youtu.be/CvFH_6DNRCY

💡 מומלץ להאזין עם אוזניות בעוצמה נמוכה-בינונית
🧘‍♂️ נסה לנשום עמוק בזמן ההאזנה - זה יעזור להרגעה
"""
    
    keyboard = [
        [InlineKeyboardButton("💡 עזרה נוספת", callback_data="show_help")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(music_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """לוג שגיאות משופר"""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    # נסיון לשלוח הודעת שגיאה למשתמש אם אפשר
    if update and hasattr(update, 'effective_chat'):
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ אופס! קרתה שגיאה קטנה. נסה שוב או חזור לתפריט הראשי.",
                reply_markup=get_main_keyboard()
            )
        except:
            pass  # אם גם זה נכשל, לא נעשה כלום

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
        logger.info("🤖 הבוט החדש והמשופר מתחיל לרוץ...")
        print("✅ הבוט פעיל! לחץ Ctrl+C לעצירה")
        application.run_polling()
            
    except Exception as e:
        logger.error(f"שגיאה קריטית בהפעלת הבוט: {e}")
        print(f"❌ שגיאה קריטית: {e}")
        raise

if __name__ == '__main__':
    main()
