import logging
import sqlite3
import os
import json
from datetime import datetime, timedelta
import pymongo
import google.generativeai as genai
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from collections import Counter
import asyncio
from datetime import datetime


# -----------------------------

# הגדרות לוגים
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# טוקן הבוט
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONGO_URI = os.getenv('MONGO_URI')
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not BOT_TOKEN or not MONGO_URI:
    raise ValueError("FATAL: BOT_TOKEN or MONGO_URI not found in environment variables!")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# הגדרת מצבי שיחה
# דיווח מהיר
QUICK_DESC, QUICK_ANXIETY = range(2)

# דיווח מלא  
FULL_DESC, FULL_ANXIETY, FULL_LOCATION, FULL_PEOPLE, FULL_WEATHER = range(5)

# פריקה חופשית
FREE_VENTING, VENTING_SAVE = range(2)

# שיחת תמיכה
SUPPORT_CHAT = range(17)

# -----------------------------------------------------------------
# Panic feature global definitions (states and techniques)
# -----------------------------------------------------------------
(ASK_BREATH, BREATHING, ASK_WASH, ASK_SCALE, OFFER_EXTRA, EXEC_EXTRA) = range(100, 106)

EXTRA_TECHNIQUES = {
    "count": ("🔹 ספירה לאחור מ-100 בקפיצות של 7", "נתחיל: 100… 93… 86… בהצלחה!"),
    "press": ("🔸 לחץ על כף היד בין האגודל לאצבע", "לחץ על הנקודה חצי דקה, ואז לחץ '✅ ביצעתי'"),
    "move": ("🚶 קום וזוז קצת – תזוזה משחררת מתח", "קום לזוז דקה-שתיים ואז לחץ '✅ ביצעתי'"),
    "drink": ("💧 שתה מים קרים לאט לאט", "שתה מים בלגימות קטנות ולחץ '✅ ביצעתי'"),
}

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
    
    # טבלת הגדרות משתמש
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

# --- הגדרת MongoDB למעקב משתמשים ---
try:
    client = pymongo.MongoClient(MONGO_URI)
    db = client.get_database("ShalvaBotDB")
    users_collection = db.get_collection("users")
    logger.info("Successfully connected to MongoDB.")
except Exception as e:
    logger.error(f"Could not connect to MongoDB: {e}")
    exit()

# --- פונקציית עזר לשמירת משתמש ---
async def ensure_user_in_db(update: Update):
    try:
        user = update.effective_user
        if not user:
            return
        user_info = {
            "chat_id": user.id,
            "first_name": user.first_name,
            "username": user.username,
        }
        users_collection.update_one(
            {"chat_id": user.id},
            {"$set": user_info, "$setOnInsert": {"first_seen": datetime.now()}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Could not log user to MongoDB: {e}")

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
        [KeyboardButton("💬 זקוק/ה לאוזן קשבת"), KeyboardButton("🔴 אני במצוקה"), KeyboardButton("⚙️ הגדרות")]
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

# =================================================================
# טיפול בתפריט במהלך שיחות
# =================================================================

async def handle_menu_during_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בלחיצות על תפריט במהלך שיחה פעילה"""
    await ensure_user_in_db(update)
    text = update.message.text
    
    # ניקוי הנתונים הזמניים
    context.user_data.clear()
    
    # הפניה לפונקציה המתאימה
    if text == "📈 גרפים והיסטוריה":
        await show_analytics(update, context)
    elif text == "🎵 שירים מרגיעים":
        await show_relaxing_music_message(update, context)
    elif text == "💡 עזרה כללית":
        await show_help(update, context)
    elif text == "⚙️ הגדרות":
        await show_settings_menu(update, context)
    elif text == "💬 זקוק/ה לאוזן קשבת":
        keyboard = [[InlineKeyboardButton("לחץ כאן כדי להתחיל בשיחה אישית", callback_data='support_chat')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('כדי להגן על פרטיותך ולהיכנס למצב שיחה, אנא לחץ על הכפתור:', reply_markup=reply_markup)
    
    # יציאה מהשיחה
    return ConversationHandler.END

# =================================================================
# START וההודעות הכלליות
# =================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """פונקציית התחלה"""
    await ensure_user_in_db(update)
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

async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בהודעות כלליות שלא במסגרת שיחה"""
    await ensure_user_in_db(update)
    text = update.message.text
    
    # טיפול בכפתורי התפריט הראשי - תמיד פעילים
    if text == "📈 גרפים והיסטוריה":
        await show_analytics(update, context)
    elif text == "🎵 שירים מרגיעים":
        await show_relaxing_music_message(update, context)
    elif text == "💡 עזרה כללית":
        await show_help(update, context)
    elif text == "⚙️ הגדרות":
        await show_settings_menu(update, context)
    elif text == "💬 זקוק/ה לאוזן קשבת":
        keyboard = [[InlineKeyboardButton("לחץ כאן כדי להתחיל בשיחה אישית", callback_data='support_chat')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('כדי להגן על פרטיותך ולהיכנס למצב שיחה, אנא לחץ על הכפתור:', reply_markup=reply_markup)
    elif text == "⚡ דיווח מהיר":
        await update.message.reply_text(
            "🤔 נראה שאתה כבר באמצע פעולה אחרת.\n\nאם אתה רוצה להתחיל דיווח חדש, לחץ על /start ואז בחר דיווח מהיר.",
            reply_markup=get_main_keyboard()
        )
    elif text == "🔍 דיווח מלא":
        await update.message.reply_text(
            "🤔 נראה שאתה כבר באמצע פעולה אחרת.\n\nאם אתה רוצה להתחיל דיווח חדש, לחץ על /start ואז בחר דיווח מלא.",
            reply_markup=get_main_keyboard()
        )
    elif text == "🗣️ פריקה חופשית":
        await update.message.reply_text(
            "🤔 נראה שאתה כבר באמצע פעולה אחרת.\n\nאם אתה רוצה להתחיל פריקה חופשית, לחץ על /start ואז בחר פריקה חופשית.",
            reply_markup=get_main_keyboard()
        )
    elif text == "🔴 אני במצוקה":
        keyboard = [[InlineKeyboardButton("לחץ כאן להתחלת תרגול", callback_data='start_panic_flow')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('כדי להתחיל, אנא לחץ על הכפתור:', reply_markup=reply_markup)
    else:
        await update.message.reply_text(
            "בחר אפשרות מהתפריט למטה:",
            reply_markup=get_main_keyboard()
        )

# =================================================================
# דיווח מהיר - ConversationHandler
# =================================================================

async def start_quick_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת דיווח מהיר"""
    await ensure_user_in_db(update)
    context.user_data.clear()  # ניקוי נתונים קודמים
    context.user_data['report_type'] = 'quick'
    context.user_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    await update.message.reply_text(
        "⚡ דיווח מהיר\n\n🔄 שלב 1/2: תיאור המצב\n\nמה קורה עכשיו? (תיאור קצר)",
        reply_markup=None
    )
    return QUICK_DESC

async def get_quick_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """קבלת תיאור בדיווח מהיר"""
    context.user_data['description'] = update.message.text
    
    progress = get_progress_indicator(2, 2)
    await update.message.reply_text(
        f"⚡ דיווח מהיר\n\n{progress} רמת חרדה\n\nבאיזה רמת חרדה? (1-10)",
        reply_markup=get_anxiety_level_keyboard()
    )
    return QUICK_ANXIETY

async def complete_quick_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """השלמת דיווח מהיר"""
    query = update.callback_query
    await query.answer()
    
    anxiety_level = int(query.data.split("_")[1])
    user_id = query.from_user.id
    
    # שמירה בבסיס נתונים
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO anxiety_reports (user_id, timestamp, anxiety_level, description, report_type)
    VALUES (?, ?, ?, ?, ?)
    ''', (user_id, context.user_data['timestamp'], anxiety_level, 
          context.user_data['description'], 'quick'))
    conn.commit()
    conn.close()
    
    # מתן המלצה מיידית
    recommendation = get_immediate_recommendation(anxiety_level)
    
    message = f"""
✅ דיווח נשמר בהצלחה!

📊 הדיווח שלך:
• רמת חרדה: {anxiety_level}/10
• זמן: {datetime.strptime(context.user_data['timestamp'], '%Y-%m-%d %H:%M:%S').strftime("%H:%M")}
• תיאור: {context.user_data['description'][:50]}{'...' if len(context.user_data['description']) > 50 else ''}

💡 המלצה מיידית:
{recommendation}

🎯 המערכת למדה משהו חדש עליך!
"""
    
    keyboard = [
        [InlineKeyboardButton("📈 ראה גרפים", callback_data="show_analytics")],
        [InlineKeyboardButton("💡 עזרה כללית", callback_data="show_help")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ניקוי נתונים
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_quick_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ביטול דיווח מהיר"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ דיווח בוטל. אפשר להתחיל מחדש בכל עת.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# =================================================================
# דיווח מלא - ConversationHandler  
# =================================================================

async def start_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת דיווח מלא"""
    await ensure_user_in_db(update)
    context.user_data.clear()
    context.user_data['report_type'] = 'full'
    context.user_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    progress = get_progress_indicator(1, 5)
    await update.message.reply_text(
        f"🔍 דיווח מלא\n\n{progress} תיאור המצב\n\nמה גורם לחרדה עכשיו? (תאר במפורט)",
        reply_markup=None
    )
    return FULL_DESC

async def get_full_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """קבלת תיאור בדיווח מלא"""
    context.user_data['description'] = update.message.text
    
    progress = get_progress_indicator(2, 5)
    await update.message.reply_text(
        f"🔍 דיווח מלא\n\n{progress} רמת חרדה\n\nבאיזה רמת חרדה? (1-10)",
        reply_markup=get_anxiety_level_keyboard()
    )
    return FULL_ANXIETY

async def get_full_anxiety_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """קבלת רמת חרדה בדיווח מלא"""
    query = update.callback_query
    await query.answer()
    
    anxiety_level = int(query.data.split("_")[1])
    context.user_data['anxiety_level'] = anxiety_level
    
    progress = get_progress_indicator(3, 5)
    await query.edit_message_text(
        f"🔍 דיווח מלא\n\n{progress} מיקום\n\nאיפה זה קרה?",
        reply_markup=get_options_keyboard(LOCATION_OPTIONS, "location")
    )
    return FULL_LOCATION

async def get_full_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """קבלת מיקום בדיווח מלא"""
    query = update.callback_query
    await query.answer()
    
    location = query.data.replace("location_", "")
    context.user_data['location'] = location
    
    progress = get_progress_indicator(4, 5)
    await query.edit_message_text(
        f"🔍 דיווח מלא\n\n{progress} אנשים בסביבה\n\nמי היה בסביבה?",
        reply_markup=get_options_keyboard(PEOPLE_OPTIONS, "people")
    )
    return FULL_PEOPLE

async def get_full_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """קבלת מידע על אנשים בדיווח מלא"""
    query = update.callback_query
    await query.answer()
    
    people = query.data.replace("people_", "")
    context.user_data['people_around'] = people
    
    progress = get_progress_indicator(5, 5)
    await query.edit_message_text(
        f"🔍 דיווח מלא\n\n{progress} מזג אוויר\n\nאיך מזג האוויר?",
        reply_markup=get_options_keyboard(WEATHER_OPTIONS, "weather")
    )
    return FULL_WEATHER

async def complete_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """השלמת דיווח מלא"""
    query = update.callback_query
    await query.answer()
    
    weather = query.data.replace("weather_", "")
    context.user_data['weather'] = weather
    user_id = query.from_user.id
    
    # שמירה בבסיס נתונים
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO anxiety_reports (user_id, timestamp, anxiety_level, description, location, people_around, weather, report_type)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, context.user_data['timestamp'], context.user_data['anxiety_level'], 
          context.user_data['description'], context.user_data['location'], 
          context.user_data['people_around'], weather, 'full'))
    conn.commit()
    conn.close()
    
    # ניתוח ומתן המלצות
    analysis = analyze_user_patterns(user_id)
    recommendation = get_personalized_recommendation(user_id, context.user_data)
    
    message = f"""
🎉 דיווח מלא נשמר בהצלחה!

📊 הדיווח שלך:
• רמת חרדה: {context.user_data['anxiety_level']}/10
• מיקום: {context.user_data['location']}
• אנשים: {context.user_data['people_around']}
• מזג אוויר: {weather}
• זמן: {datetime.strptime(context.user_data['timestamp'], '%Y-%m-%d %H:%M:%S').strftime("%H:%M")}

🧠 תובנה אישית:
{analysis}

💡 המלצה מותאמת:
{recommendation}

✨ כל הכבוד על השלמת הדיווח המלא!
"""
    
    keyboard = [
        [InlineKeyboardButton("📈 ראה גרפים והיסטוריה", callback_data="show_analytics")],
        [InlineKeyboardButton("🎵 שיר מרגיע", callback_data="relaxing_music")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ניקוי נתונים
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ביטול דיווח מלא"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ דיווח בוטל. אפשר להתחיל מחדש בכל עת.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# =================================================================
# פריקה חופשית - ConversationHandler
# =================================================================

async def start_free_venting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """התחלת פריקה חופשית"""
    await ensure_user_in_db(update)
    context.user_data.clear()
    
    await update.message.reply_text(
        "🗣️ פריקה חופשית\n\nכתב כל מה שאתה מרגיש. אין שאלות, אין לחץ.\nרק תן לזה לצאת...",
        reply_markup=None
    )
    return FREE_VENTING

async def get_venting_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """קבלת תוכן הפריקה"""
    context.user_data['venting_content'] = update.message.text
    
    await update.message.reply_text(
        "💝 תודה שחלקת איתי. זה דורש אומץ לפתוח את הלב.\n\nהאם לשמור את זה למעקב וניתוח עתידי?",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 כן, שמור לניתוח", callback_data="save_venting_yes")],
            [InlineKeyboardButton("🗑️ לא, רק פריקה", callback_data="save_venting_no")]
        ])
    )
    return VENTING_SAVE

async def save_venting_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """שמירת בחירה לגבי פריקה"""
    query = update.callback_query
    await query.answer()
    
    save_for_analysis = query.data == "save_venting_yes"
    user_id = query.from_user.id
    content = context.user_data['venting_content']
    
    # שמירה בבסיס נתונים
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
    
    keyboard = [
        [InlineKeyboardButton("🎵 שיר מרגיע", callback_data="relaxing_music")],
        [InlineKeyboardButton("💡 עזרה כללית", callback_data="show_help")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    
    # ניקוי נתונים
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_venting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ביטול פריקה חופשית"""
    context.user_data.clear()
    await update.message.reply_text(
        "❌ פריקה בוטלה. אפשר להתחיל מחדש בכל עת.",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END

# =================================================================
# שיחת תמיכה מבוססת Gemini
# =================================================================

EMPATHY_PROMPT = """אתה עוזר רגשי אישי, שפועל דרך בוט טלגרם. משתמש פונה אליך כשהוא מרגיש לחץ, חרדה, או צורך באוזן קשבת. תפקידך: להגיב בחום, בטון רך, בגישה לא שיפוטית ומכילה. אתה לא מייעץ – אתה שם בשבילו. שמור על שפה אנושית, פשוטה ואכפתית. אם המשתמש שותק – עודד אותו בעדינות. המטרה שלך: להשרות רוגע, להקל על תחושת הבדידות, ולעזור לו להרגיש שמישהו איתו."""

async def start_support_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if not GEMINI_API_KEY:
        await query.edit_message_text("שירות השיחה אינו זמין כרגע.")
        return ConversationHandler.END

    context.user_data['gemini_model'] = genai.GenerativeModel('gemini-1.5-flash')
    opening_message = "אני כאן, איתך. מה יושב לך על הלב?\nכדי לסיים, שלח /end_chat. כדי לחזור לתפריט הראשי בכל שלב, שלח /start."
    context.user_data['chat_history'] = [{'role': 'user', 'parts': [EMPATHY_PROMPT]}, {'role': 'model', 'parts': [opening_message]}]
    await query.edit_message_text(text=opening_message)
    return SUPPORT_CHAT

async def handle_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_message = update.message.text
    model = context.user_data.get('gemini_model')
    if not model:
        await update.message.reply_text("אני מתנצל, נתקלתי בבעיה. נסה להתחיל מחדש עם /start.")
        return ConversationHandler.END

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    chat = model.start_chat(history=context.user_data.get('chat_history', []))
    response = await chat.send_message_async(user_message)
    bot_response = response.text
    context.user_data['chat_history'].append({'role': 'user', 'parts': [user_message]})
    context.user_data['chat_history'].append({'role': 'model', 'parts': [bot_response]})
    await update.message.reply_text(bot_response)
    return SUPPORT_CHAT

async def end_support_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("שמחתי להיות כאן בשבילך. אני תמיד כאן אם תצטרך אותי שוב. ❤️\nכדי לחזור לתפריט הראשי, הקלד /start.")
    if 'chat_history' in context.user_data: del context.user_data['chat_history']
    if 'gemini_model' in context.user_data: del context.user_data['gemini_model']
    return ConversationHandler.END

# =================================================================
# יצירת ConversationHandlers
# =================================================================

def create_quick_report_conversation():
    """יצירת שיחת דיווח מהיר"""
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚡ דיווח מהיר$"), start_quick_report)],
        states={
            QUICK_DESC: [
                MessageHandler(filters.Regex("^📈 גרפים והיסטוריה$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^🎵 שירים מרגיעים$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^💡 עזרה כללית$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^⚙️ הגדרות$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^💬 זקוק/ה לאוזן קשבת$"), handle_menu_during_conversation),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(📈 גרפים והיסטוריה|🎵 שירים מרגיעים|💡 עזרה כללית|⚙️ הגדרות|💬 זקוק/ה לאוזן קשבת)$"), get_quick_description)
            ],
            QUICK_ANXIETY: [CallbackQueryHandler(complete_quick_report, pattern="^anxiety_")]
        },
        fallbacks=[
            CommandHandler("start", cancel_quick_report),
            MessageHandler(filters.Regex("^❌ ביטול$"), cancel_quick_report)
        ]
    )

def create_full_report_conversation():
    """יצירת שיחת דיווח מלא"""
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 דיווח מלא$"), start_full_report)],
        states={
            FULL_DESC: [
                MessageHandler(filters.Regex("^📈 גרפים והיסטוריה$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^🎵 שירים מרגיעים$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^💡 עזרה כללית$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^⚙️ הגדרות$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^💬 זקוק/ה לאוזן קשבת$"), handle_menu_during_conversation),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(📈 גרפים והיסטוריה|🎵 שירים מרגיעים|💡 עזרה כללית|⚙️ הגדרות|💬 זקוק/ה לאוזן קשבת)$"), get_full_description)
            ],
            FULL_ANXIETY: [CallbackQueryHandler(get_full_anxiety_level, pattern="^anxiety_")],
            FULL_LOCATION: [CallbackQueryHandler(get_full_location, pattern="^location_")],
            FULL_PEOPLE: [CallbackQueryHandler(get_full_people, pattern="^people_")],
            FULL_WEATHER: [CallbackQueryHandler(complete_full_report, pattern="^weather_")]
        },
        fallbacks=[
            CommandHandler("start", cancel_full_report),
            MessageHandler(filters.Regex("^❌ ביטול$"), cancel_full_report),
        ]
    )

def create_venting_conversation():
    """יצירת שיחת פריקה חופשית"""
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗣️ פריקה חופשית$"), start_free_venting)],
        states={
            FREE_VENTING: [
                MessageHandler(filters.Regex("^📈 גרפים והיסטוריה$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^🎵 שירים מרגיעים$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^💡 עזרה כללית$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^⚙️ הגדרות$"), handle_menu_during_conversation),
                MessageHandler(filters.Regex("^💬 זקוק/ה לאוזן קשבת$"), handle_menu_during_conversation),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex("^(📈 גרפים והיסטוריה|🎵 שירים מרגיעים|💡 עזרה כללית|⚙️ הגדרות|💬 זקוק/ה לאוזן קשבת)$"), get_venting_content)
            ],
            VENTING_SAVE: [CallbackQueryHandler(save_venting_choice, pattern="^save_venting_")]
        },
        fallbacks=[
            CommandHandler("start", cancel_venting),
            MessageHandler(filters.Regex("^❌ ביטול$"), cancel_venting)
        ]
    )

def create_support_conversation():
    """יצירת שיחת תמיכה"""
    return ConversationHandler(
        entry_points=[CallbackQueryHandler(start_support_chat, pattern='^support_chat$')],
        states={SUPPORT_CHAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_support_message)]},
        fallbacks=[CommandHandler('end_chat', end_support_chat), CommandHandler('start', start)],
        per_user=True,
        per_chat=True,
    )

# =================================================================
# Callback handlers כלליים
# =================================================================

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """טיפול בלחיצות על כפתורים כלליים"""
    await ensure_user_in_db(update)
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "main_menu":
        await query.edit_message_text(
            "🏠 חזרת לתפריט הראשי\n\nבחר אפשרות מהתפריט למטה:",
        )
    elif data == "relaxing_music":
        await show_relaxing_music(query, context)
    elif data == "start_using":
        await query.edit_message_text(
            "🎯 מעולה! אני כאן בשבילך.\n\nבחר מה מתאים לך עכשיו דרך התפריט שמופיע למטה בצ'אט:"
        )
    elif data == "show_analytics":
        await show_analytics_callback(query, context)
    elif data == "show_help":
        await show_help_callback(query, context)
    # הגדרות
    elif data.startswith("settings_"):
        await handle_settings_callback(query, context)
    elif data == "reminder_toggle":
        await toggle_reminders(query, context)
    elif data == "reminder_time":
        await query.edit_message_text(
            "⏰ שינוי שעת תזכורת\n\nתכונה זו תבוא בעדכון הבא.\nכרגע ברירת המחדל היא 20:00.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזור", callback_data="settings_reminders")]])
        )
    elif data == "show_settings_menu":
        await show_settings_menu_callback(query, context)
    elif data == "settings_reminders":
        await show_reminder_settings(query, context)
    elif data == "confirm_reset":
        await reset_user_data(query, context)

# =================================================================
# פונקציות עזר ותצוגה
# =================================================================

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
    base_recommendation = get_immediate_recommendation(current_data['anxiety_level'])
    
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

async def show_analytics_callback(query, context):
    """הצגת אנליטיקה מכפתור callback"""
    user_id = query.from_user.id
    
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
        await query.edit_message_text(
            "📊 עדיין אין נתונים לניתוח\n\nהתחל לדווח כדי לראות דפוסים מעניינים על עצמך! 🎯",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]])
        )
        return
    
    # ניתוח מקוצר לcallback
    anxiety_levels = [report[0] for report in reports]
    avg_anxiety = sum(anxiety_levels) / len(anxiety_levels)
    max_anxiety = max(anxiety_levels)
    min_anxiety = min(anxiety_levels)
    
    analysis_text = f"""
📈 הניתוח שלך ({len(reports)} דיווחים):

📊 סטטיסטיקות:
• ממוצע חרדה: {avg_anxiety:.1f}/10
• מקסימום: {max_anxiety}/10
• מינימום: {min_anxiety}/10

💡 לניתוח מפורט יותר, השתמש בכפתור "גרפים והיסטוריה" מהתפריט הראשי.
"""
    
    keyboard = [[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]
    
    await query.edit_message_text(analysis_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת עזרה כללית"""
    help_text = """
💡 עזרה כללית בהתמודדות עם חרדה:

🫁 **טכניקות נשימה:**
• נשימה 4-4-6: שאף 4 שניות, עצור 4, נשוף 6
• נשימה עמוקה מהבטן (לא מהחזה)
• נשימת קופסא: 4-4-4-4 (שאף, עצור, נשוף, עצור)

🧘‍♂️ **טכניקות הרגעה מיידית:**
• 5-4-3-2-1: מצא 5 דברים שאתה רואה, 4 שאתה שומע, 3 שאתה מרגיש, 2 שאתה מריח, 1 שאתה טועם
• הזכר לעצמך: "זה רגש, לא עובדה. זה יעבור"
• ספור לאחור מ-100 במקפצות של 7

💪 **פעולות פיזיות מרגיעות:**
• קום וזוז - תזוזה משחררת מתח
• שתה מים קרים לאט לאט
• שטוף פנים במים קרים
• לחץ על כף היד במקום בין האגודל והאצבע

🎯 **טכניקות קוגניטיביות:**
• שאל את עצמך: "האם זה באמת כל כך נורא?"
• חשוב על 3 דברים שאתה אסיר תודה עליהם
• דמיין מקום שקט ובטוח

📞 **עזרה מקצועית 24/7:**
• **ער"ן** - עזרה רגשית ונפשית: 1201
  💬 [צ'אט ער"ן](https://www.eran.org.il/online-emotional-help/)
• **סה"ר** - סיוע והקשבה: 1800-120-140
  💬 [צ'אט סה"ר](https://sahar.org.il/help/)
• **נט"ל** - קו חם לחירום נפשי: 1800-363-363

⚠️ **חשוב לזכור:** הבוט הזה לא מחליף טיפול מקצועי!
אם החרדה מפריעה לחיים הרגילים, מומלץ לפנות לעזרה מקצועית.
"""
    
    await update.message.reply_text(
        help_text, 
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def show_help_callback(query, context):
    """הצגת עזרה מכפתור callback"""
    help_text = """
💡 **עזרה מיידית בהתמודדות עם חרדה:**

🫁 **נשימה 4-4-6:**
שאף 4 שניות, עצור 4, נשוף 6

🧘‍♂️ **טכניקת 5-4-3-2-1:**
5 דברים שאתה רואה
4 דברים שאתה שומע  
3 דברים שאתה מרגיש
2 דברים שאתה מריח
1 דבר שאתה טועם

📞 **עזרה מקצועית:**
• **ער"ן:** 1201 | [צ'אט](https://www.eran.org.il/online-emotional-help/)
• **סה"ר:** 1800-120-140 | [צ'אט](https://sahar.org.il/help/)

💡 לרשימה מלאה, השתמש בכפתור "עזרה כללית" מהתפריט הראשי.
"""
    
    keyboard = [[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]
    
    await query.edit_message_text(
        help_text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def show_relaxing_music_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת שירים מרגיעים מהתפריט הראשי"""
    music_text = """
🎵 שירים מרגיעים (מוכחים מחקרית לירידה בסטרס):

🎼 **"Weightless" - Marconi Union**
🎧 [יוטיוב](https://youtu.be/UfcAVejslrU) | 🎶 [ספוטיפיי](https://open.spotify.com/track/6kkwzB6hXLIONkEk9JciA6)
⭐ מחקר של המכון הבריטי לטכנולוגיית קול קבע שזה השיר הכי מרגיע!

🎼 **"Someone Like You" - Adele**
🎧 [יוטיוב](https://youtu.be/hLQl3WQQoQ0) | 🎶 [ספוטיפיי](https://open.spotify.com/track/1zwMYTA5nlNjZxYrvBB2pV)

🎼 **"Watermark" - Enya**
🎧 [יוטיוב](https://youtu.be/0IKvdaXZP8Q) | 🎶 [ספוטיפיי](https://open.spotify.com/track/2m8MwTvNHBYIqieOoQeyuY)

🎼 **"Strawberry Swing" - Coldplay**
🎧 [יוטיוב](https://youtu.be/h3pJZSTQqIg) | 🎶 [ספוטיפיי](https://open.spotify.com/track/0zVYSaFo1b2v8YDmx0QYEh)

🎼 **"Claire de Lune" - Claude Debussy**
🎧 [יוטיוב](https://youtu.be/CvFH_6DNRCY) | 🎶 [ספוטיפיי](https://open.spotify.com/track/5u5aVJKjSMJr4zesMPz7bL)

🎼 **"Aqueous Transmission" - Incubus**
🎧 [יוטיוב](https://youtu.be/_ndHqJ3RP5Y) | 🎶 [ספוטיפיי](https://open.spotify.com/track/5M67k54BVUDADZPryaqV1y)

💡 **טיפים להאזנה מרגיעה:**
• האזן עם אוזניות בעוצמה נמוכה-בינונית
• נסה לנשום עמוק בזמן ההאזנה
• סגור עיניים ותן למוזיקה לשטוף אותך
• 8-10 דקות של האזנה יכולות להפחית סטרס משמעותית
"""
    
    await update.message.reply_text(
        music_text, 
        reply_markup=get_main_keyboard(),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

async def show_relaxing_music(query, context):
    """הצגת רשימת שירים מרגיעים מכפתור"""
    music_text = """
🎵 שירים מרגיעים (מוכחים מחקרית לירידה בסטרס):

🎼 **"Weightless" - Marconi Union**
🎧 [יוטיוב](https://www.youtube.com/watch?v=UfcAVejslrU) | 🎶 [ספוטיפיי](https://open.spotify.com/track/6kkwzB6hXLIONkEk9JciA6)
⭐ מחקר של המכון הבריטי לטכנולוגיית קול קבע שזה השיר הכי מרגיע!

🎼 **"Someone Like You" - Adele**  
🎧 [יוטיוב](https://www.youtube.com/watch?v=hLQl3WQQoQ0) | 🎶 [ספוטיפיי](https://open.spotify.com/track/1zwMYTA5nlNjZxYrvBB2pV)

🎼 **"Watermark" - Enya**
🎧 [יוטיוב](https://www.youtube.com/watch?v=bPCdsa7hS7M) | 🎶 [ספוטיפיי](https://open.spotify.com/track/2m8MwTvNHBYIqieOoQeyuY)

🎼 **"Strawberry Swing" - Coldplay**
🎧 [יוטיוב](https://www.youtube.com/watch?v=h3pJZSTQqIg) | 🎶 [ספוטיפיי](https://open.spotify.com/track/0zVYSaFo1b2v8YDmx0QYEh)

🎼 **"Claire de Lune" - Claude Debussy**
🎧 [יוטיוב](https://www.youtube.com/watch?v=WNcsUNKlAKw) | 🎶 [ספוטיפיי](https://open.spotify.com/track/5u5aVJKjSMJr4zesMPz7bL)

🎼 **"Aqueous Transmission" - Incubus**
🎧 [יוטיוב](https://www.youtube.com/watch?v=EAVop3YSebQ) | 🎶 [ספוטיפיי](https://open.spotify.com/track/5M67k54BVUDADZPryaqV1y)

💡 מומלץ להאזין עם אוזניות בעוצמה נמוכה-בינונית
🧘‍♂️ נסה לנשום עמוק בזמן ההאזנה - זה יעזור להרגעה
"""
    
    keyboard = [
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        music_text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown',
        disable_web_page_preview=True
    )

# =================================================================
# הגדרות
# =================================================================

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """הצגת תפריט הגדרות מלא"""
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")],
        [InlineKeyboardButton("🏠 חזור לתפריט", callback_data="main_menu")]
    ]
    
    await update.message.reply_text(
        "⚙️ הגדרות\n\nבחר מה תרצה לשנות:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_settings_menu_callback(query, context):
    """הצגת תפריט הגדרות מכפתור callback"""
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")],
        [InlineKeyboardButton("🏠 חזור לתפריט", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(
        "⚙️ הגדרות\n\nבחר מה תרצה לשנות:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_settings_callback(query, context):
    """טיפול בהגדרות"""
    user_id = query.from_user.id
    data = query.data
    
    if data == "settings_reminders":
        await show_reminder_settings(query, context)
    elif data == "settings_export":
        await export_user_data(query, context)
    elif data == "settings_reset":
        await confirm_reset_data(query, context)

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
                            callback_data="reminder_toggle")],
        [InlineKeyboardButton("⏰ שנה שעה", callback_data="reminder_time")],
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="show_settings_menu")]
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
    
    try:
        conn = sqlite3.connect('anxiety_data.db')
        cursor = conn.cursor()
        cursor.execute("SELECT preferred_report_type FROM user_settings WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_type = result[0] if result else 'quick'
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton(f"⚡ דיווח מהיר {'✓' if current_type == 'quick' else ''}", 
                                callback_data="report_type_quick")],
            [InlineKeyboardButton(f"🔍 דיווח מלא {'✓' if current_type == 'full' else ''}", 
                                callback_data="report_type_full")],
            [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="show_settings_menu")]
        ]
        
        message = f"""
⚡ סוג דיווח מועדף

הגדרה נוכחית: {'דיווח מהיר' if current_type == 'quick' else 'דיווח מלא'}

• דיווח מהיר: מהיר ופשוט, רק תיאור ורמת חרדה
• דיווח מלא: מפורט עם פרטים על מיקום, אנשים ומזג אוויר
"""
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        await query.edit_message_text(
            "❌ שגיאה בטעינת ההגדרות. נסה שוב מאוחר יותר.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזור", callback_data="show_settings_menu")]])
        )

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

📁 הקובץ נשלח למטה!
"""
        
        keyboard = [
            [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")]
        ]
        
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
        
        # שליחת הקובץ בהודעה נפרדת
        import io
        file_buffer = io.BytesIO(json_data.encode('utf-8'))
        file_buffer.name = f"anxiety_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        await context.bot.send_document(
            chat_id=query.message.chat_id,
            document=file_buffer,
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

🎯 ההגדרה נשמרה בהצלחה. תוכל לשנות את זה בכל עת דרך הגדרות.
"""
    
    keyboard = [
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="show_settings_menu")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ]
    
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

# =================================================================
# Error Handler
# =================================================================

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

# =================================================================
# --- Panic Feature Functions (גרסה 7 - שיפורי UI ויציבות) ---
# =================================================================

async def panic_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    for key in ['breathing_task', 'scale_asked', 'offered_techniques', 'level_start', 'level_now', 'attempts']:
        context.user_data.pop(key, None)

    keyboard = [
        [
            InlineKeyboardButton("✅ כן, ננשום יחד", callback_data="panic_yes_breath"),
            InlineKeyboardButton("⛔️ לא, תודה", callback_data="panic_no_breath"),
        ],
        [InlineKeyboardButton("🔙 חזרה לתפריט הראשי", callback_data="panic_exit")]
    ]
    
    await query.edit_message_text(
        text="אני איתך. ❤️\nהאם תרצה שננשום יחד בקצב של 4-4-6?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_BREATH

async def decide_breath(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "panic_yes_breath":
        stop_button = InlineKeyboardMarkup([[InlineKeyboardButton("⏹️ הפסק והמשך הלאה", callback_data="panic_stop_breath")]])
        await query.edit_message_text("מתחילים לנשום יחד…\nתוכל להפסיק את התרגיל בכל שלב.", reply_markup=stop_button)
        
        breathing_task = asyncio.create_task(breathing_cycle(update.effective_chat.id, context))
        context.user_data['breathing_task'] = breathing_task
        
        return BREATHING

    # **>>> כאן בוצע השינוי שביקשת <<<**
    keyboard = [
        [InlineKeyboardButton("✅ ביצעתי", callback_data="panic_face_done")],
        [InlineKeyboardButton("🔄 הצע טכניקות נוספות", callback_data="panic_more_extra")],
        [InlineKeyboardButton("🔙 חזרה לתפריט הראשי", callback_data="panic_exit")]
    ]
    await query.edit_message_text(
        "לפעמים קשה להתרכז בנשימות, יש לי עוד הצעה, מה דעתך לשטוף פנים במים קרים? וכשתחזור - לחץ על \"ביצעתי\".",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_WASH

async def breathing_cycle(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    try:
        for i in range(3):
            if not context.user_data.get('breathing_task'): break
            await context.bot.send_message(chat_id, f"מחזור {i+1}/3:\n\n🌬️ שאיפה… (4 שניות)")
            await asyncio.sleep(4)
            if not context.user_data.get('breathing_task'): break
            await context.bot.send_message(chat_id, "🧘 החזק… (4 שניות)")
            await asyncio.sleep(4)
            if not context.user_data.get('breathing_task'): break
            await context.bot.send_message(chat_id, "😮‍💨 נשיפה… (6 שניות)")
            await asyncio.sleep(6)
        
        if context.user_data.get('breathing_task'):
             await context.bot.send_message(chat_id, "תרגיל הנשימה הסתיים.")
    except asyncio.CancelledError:
        logger.info(f"Breathing cycle for chat {chat_id} was cancelled.")
        raise
    except Exception as e:
        logger.error(f"Error in breathing_cycle for chat {chat_id}: {e}", exc_info=True)
    finally:
        if context.user_data.pop('breathing_task', None):
            await ask_scale_if_needed(chat_id, context)

async def stop_breathing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    task = context.user_data.get('breathing_task')
    if task:
        task.cancel()
    
    try:
        await query.delete_message()
    except Exception as e:
        logger.warning(f"Could not delete message on stop_breathing: {e}")

    await ask_scale_if_needed(update.effective_chat.id, context)
    return ASK_SCALE

async def face_washed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    try:
        await query.delete_message()
    except Exception as e:
        logger.warning(f"Could not delete message on face_washed: {e}")

    await ask_scale_if_needed(update.effective_chat.id, context)
    return ASK_SCALE

async def ask_scale_if_needed(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('scale_asked', False):
        context.user_data['scale_asked'] = True
        question = "איך אתה מרגיש עכשיו, זה עזר?"
        scale_kb = [[InlineKeyboardButton(str(i), callback_data=f"panic_scale_{i}") for i in range(0, 11)]]
        
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"{question}\nדרג מ-0 (רגוע לחלוטין) עד 10 (הכי חרד שאפשר):",
            reply_markup=InlineKeyboardMarkup(scale_kb)
        )

async def handle_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['scale_asked'] = False
    new_level = int(query.data.split("_")[2])

    if "level_start" not in context.user_data:
        context.user_data["level_start"] = new_level
        context.user_data["attempts"] = 0
    
    old_level = context.user_data.get("level_now", new_level)
    context.user_data["level_now"] = new_level

    if new_level <= 3 or old_level - new_level >= 2:
        keyboard = [[
            InlineKeyboardButton("✅ כן, מספיק לי", callback_data="panic_enough"),
            InlineKeyboardButton("🔄 עוד תרגיל בבקשה", callback_data="panic_more_extra"),
        ]]
        await query.edit_message_text(
            "כל הכבוד! רואים ירידה יפה בחרדה. 😊\nתרצה להמשיך לעוד תרגיל או שאתה מרגיש שזה מספיק?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return OFFER_EXTRA

    context.user_data["attempts"] += 1
    if context.user_data["attempts"] >= 2:
        await query.edit_message_text(
            "נגמרו לי ההצעות במאגר, תמיד תוכל ללחוץ על לחצן המצוקה כדי להתחיל סבב נוסף.\n"
            "ממליץ לך בחום לעבור ללחצן \"זקוק/ה לאוזן קשבת?\", תוכל לנהל שיחה עם סוכן בינה מלאכותית אדיב, מכיל ואמפתי 🩵"
        )
        return ConversationHandler.END

    return await offer_extra(update, context)

async def offer_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    all_keys = list(EXTRA_TECHNIQUES.keys())
    offered_keys = context.user_data.get('offered_techniques', [])
    remaining_keys = [key for key in all_keys if key not in offered_keys]
    
    if not remaining_keys:
        offered_keys = []
        remaining_keys = all_keys
    
    keys_to_show = remaining_keys[:2]
    buttons = [[InlineKeyboardButton(EXTRA_TECHNIQUES[key][0], callback_data=f"panic_extra_{key}")] for key in keys_to_show]
    context.user_data['offered_techniques'] = offered_keys + keys_to_show
    
    if len(remaining_keys) > 2:
        buttons.append([InlineKeyboardButton("🔄 הצע טכניקות נוספות", callback_data="panic_more_extra")])
        
    message_text = "בוא ננסה טכניקה נוספת. איזו מהבאות תרצה לנסות?"

    try:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(message_text, reply_markup=InlineKeyboardMarkup(buttons))
        else:
            await update.message.reply_text(message_text, reply_markup=InlineKeyboardMarkup(buttons))
    except Exception as e:
        logger.error(f"Error in offer_extra: {e}")

    return OFFER_EXTRA

async def start_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split("_")[2]
    _, intro = EXTRA_TECHNIQUES[key]
    
    try:
        await query.edit_message_text(
            f"{intro}\nכשתסיים, לחץ על הכפתור.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ ביצעתי", callback_data="panic_done_extra")]])
        )
    except Exception as e:
        logger.error(f"Error in start_extra: {e}")

    return EXEC_EXTRA

async def extra_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    try:
        await query.delete_message()
    except Exception as e:
        logger.warning(f"Could not delete message in extra_done (this is often OK): {e}")
    
    await ask_scale_if_needed(update.effective_chat.id, context)
    return ASK_SCALE

async def extra_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "panic_enough":
        await query.edit_message_text("שמחתי לעזור. אני כאן תמיד כשתצטרך. 💙")
        return ConversationHandler.END
    
    # אם לחץ על "עוד תרגיל", קוראים ל-offer_extra
    # חשוב לערוך את ההודעה הנוכחית ולא לשלוח חדשה
    try:
        await offer_extra(update.callback_query, context)
    except Exception:
        # במקרה שהקריאה נכשלת (כי offer_extra מצפה ל-update ולא ל-query), ננסה עם update
        await offer_extra(update, context)
    return OFFER_EXTRA

async def fallback_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    for key in ['breathing_task', 'scale_asked', 'offered_techniques', 'level_start', 'level_now', 'attempts']:
        context.user_data.pop(key, None)
    await start(update, context)
    return ConversationHandler.END

async def exit_panic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    try:
        await query.edit_message_text("מובן. חוזרים לתפריט הראשי.", reply_markup=None)
    except Exception as e:
        logger.warning(f"Could not edit message on exit_panic: {e}")
    
    for key in ['breathing_task', 'scale_asked', 'offered_techniques', 'level_start', 'level_now', 'attempts']:
        context.user_data.pop(key, None)
    return ConversationHandler.END


panic_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(panic_entry, pattern='^start_panic_flow$')],
    states={
        ASK_BREATH: [CallbackQueryHandler(decide_breath, pattern="^panic_(yes|no)_breath$")],
        BREATHING: [
            CallbackQueryHandler(stop_breathing, pattern="^panic_stop_breath$"),
            CallbackQueryHandler(handle_scale, pattern="^panic_scale_")
        ],
        # **>>> כאן בוצע השינוי למצב ASK_WASH <<<**
        ASK_WASH: [
            CallbackQueryHandler(face_washed, pattern="^panic_face_done$"),
            CallbackQueryHandler(extra_choice, pattern="^panic_more_extra$"), # מטפל בכפתור "הצע עוד"
        ],
        ASK_SCALE: [CallbackQueryHandler(handle_scale, pattern="^panic_scale_\\d+$")],
        OFFER_EXTRA: [
            CallbackQueryHandler(start_extra, pattern="^panic_extra_"),
            CallbackQueryHandler(extra_choice, pattern="^panic_(enough|more_extra)$"),
        ],
        EXEC_EXTRA: [CallbackQueryHandler(extra_done, pattern="^panic_done_extra$")],
    },
    fallbacks=[
        CommandHandler("start", fallback_start),
        CallbackQueryHandler(exit_panic, pattern='^panic_exit$')
    ],
    name="panic_conv",
    per_user=True,
    per_chat=True,
)

# =================================================================
# Main Function
# =================================================================

def main():
    """פונקציה ראשית - ConversationHandler Version"""
    try:
        # יצירת בסיס נתונים
        init_database()
        
        # יצירת האפליקציה
        application = Application.builder().token(BOT_TOKEN).build()
        
        # הוספת ConversationHandlers - סדר חשוב!
        application.add_handler(panic_conv_handler)  # רישום panic_conv_handler קודם
        application.add_handler(create_quick_report_conversation())
        application.add_handler(create_full_report_conversation())
        application.add_handler(create_venting_conversation())
        application.add_handler(create_support_conversation())
        
        # הוספת handlers כלליים
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_general_message))
        
        # הוספת error handler
        application.add_error_handler(error_handler)
        
        # הרצת הבוט
        logger.info("🚀 הבוט החדש עם ConversationHandler מתחיל לרוץ...")
        print("✅ הבוט פעיל עם ConversationHandler! לחץ Ctrl+C לעצירה")
        application.run_polling()
            
    except Exception as e:
        logger.error(f"שגיאה קריטית בהפעלת הבוט: {e}")
        print(f"❌ שגיאה קריטית: {e}")
        raise

if __name__ == '__main__':
    main()
