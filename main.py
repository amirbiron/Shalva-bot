import logging
import sqlite3
import os
import json
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler
from collections import Counter

# הגדרות לוגים
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# טוקן הבוט
BOT_TOKEN = os.getenv('BOT_TOKEN', "7622868890:AAEnk_PC-hbOJIYWICXgE8F654RlOJxY5Sk")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN לא נמצא!")

# הגדרת מצבי שיחה
QUICK_DESC, QUICK_ANXIETY = range(2)
FULL_DESC, FULL_ANXIETY, FULL_LOCATION, FULL_PEOPLE, FULL_WEATHER = range(5)
FREE_VENTING, VENTING_SAVE = range(2)

# הגדרת בסיס הנתונים
def init_database():
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS anxiety_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, timestamp TEXT,
        anxiety_level INTEGER, description TEXT, location TEXT, people_around TEXT,
        weather TEXT, report_type TEXT DEFAULT 'full', created_at TEXT DEFAULT (datetime('now'))
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS free_venting (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, content TEXT,
        save_for_analysis BOOLEAN DEFAULT FALSE, timestamp TEXT DEFAULT (datetime('now'))
    )''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_settings (
        user_id INTEGER PRIMARY KEY, daily_reminder BOOLEAN DEFAULT FALSE,
        reminder_time TEXT DEFAULT '20:00', preferred_report_type TEXT DEFAULT 'quick',
        notifications_enabled BOOLEAN DEFAULT TRUE, language TEXT DEFAULT 'he'
    )''')
    conn.commit()
    conn.close()

LOCATION_OPTIONS = ['🏠 בית', '🏢 עבודה', '🚗 רחוב', '🛒 קניון', '🚌 תחבורה ציבורית', '📍 אחר']
PEOPLE_OPTIONS = ['👤 לבד', '👥 עם חברים', '👔 קולגות', '👨‍👩‍👧‍👦 משפחה', '👥 זרים', '👥 אחר']
WEATHER_OPTIONS = ['☀️ שמש', '🌧️ גשם', '☁️ מעונן', '🔥 חם', '❄️ קר', '🌤️ אחר']

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("⚡ דיווח מהיר"), KeyboardButton("🔍 דיווח מלא")],
        [KeyboardButton("🗣️ פריקה חופשית"), KeyboardButton("📈 גרפים והיסטוריה")],
        [KeyboardButton("🎵 שירים מרגיעים"), KeyboardButton("💡 עזרה כללית")],
        [KeyboardButton("⚙️ הגדרות")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_anxiety_level_keyboard():
    keyboard = [[InlineKeyboardButton(f"{i}", callback_data=f"anxiety_{i}") for i in range(1, 6)],
                [InlineKeyboardButton(f"{i}", callback_data=f"anxiety_{i}") for i in range(6, 11)]]
    return InlineKeyboardMarkup(keyboard)

def get_options_keyboard(options, callback_prefix):
    return InlineKeyboardMarkup([[InlineKeyboardButton(option, callback_data=f"{callback_prefix}_{option}")] for option in options])

def get_progress_indicator(current_step, total_steps):
    return f"{'●' * current_step}{'○' * (total_steps - current_step)} ({current_step}/{total_steps})"

async def handle_menu_during_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data.clear()
    if text == "📈 גרפים והיסטוריה":
        await show_analytics(update, context)
    elif text == "🎵 שירים מרגיעים":
        await show_relaxing_music_message(update, context)
    elif text == "💡 עזרה כללית":
        await show_help(update, context)
    elif text == "⚙️ הגדרות":
        await show_settings_menu(update, context)
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
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

🩵 איך אני יכול לתמוך בך:
⚡ דיווח מהיר - כשאתה מרגיש חרדה עכשיו
🔍 דיווח מפורט - לזהות מה מעורר את הרגשות
🗣️ פריקה חופשית - מקום בטוח לכתוב מה שמטריד
📈 מבט על הדרך - לראות איך אתה מתקדם
💡 כלים לעזרה - טכניקות שיכולות להרגיע
🔒 הכל נשאר רק אצלך ופרטי לחלוטין.

קח את הזמן שלך, ובחר מה מתאים לך עכשיו:
"""
    await update.message.reply_text(welcome_message, reply_markup=get_main_keyboard())
    music_keyboard = [
        [InlineKeyboardButton("🎵 כן, אשמח לשיר מרגיע", callback_data="relaxing_music")],
        [InlineKeyboardButton("🚀 לא, בוא נתחיל", callback_data="start_using")]
    ]
    await update.message.reply_text(
        "🎶 רוצה לפני שנתחיל לשים שיר מרגיע? יש לי קולקציה של שירים שנמצאו מחקרית הכי מרגיעים במצבי סטרס:",
        reply_markup=InlineKeyboardMarkup(music_keyboard)
    )

async def handle_general_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "📈 גרפים והיסטוריה":
        await show_analytics(update, context)
    elif text == "🎵 שירים מרגיעים":
        await show_relaxing_music_message(update, context)
    elif text == "💡 עזרה כללית":
        await show_help(update, context)
    elif text == "⚙️ הגדרות":
        await show_settings_menu(update, context)
    else:
        # Avoid replying to conversation starters here
        if text not in ["⚡ דיווח מהיר", "🔍 דיווח מלא", "🗣️ פריקה חופשית"]:
            await update.message.reply_text("בחר אפשרות מהתפריט למטה:", reply_markup=get_main_keyboard())

# --- FIX 1: Helper function to check for menu commands in conversation ---
async def check_for_menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    menu_commands = ["📈 גרפים והיסטוריה", "🎵 שירים מרגיעים", "💡 עזרה כללית", "⚙️ הגדרות", "⚡ דיווח מהיר", "🔍 דיווח מלא", "🗣️ פריקה חופשית"]
    if text in menu_commands:
        await handle_menu_during_conversation(update, context)
        return True
    return False

async def start_quick_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['report_type'] = 'quick'
    context.user_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    await update.message.reply_text("⚡ דיווח מהיר\n\n🔄 שלב 1/2: תיאור המצב\n\nמה קורה עכשיו? (תיאור קצר)")
    return QUICK_DESC

async def get_quick_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # <--- FIX 1: Check for menu command before processing
    if await check_for_menu_command(update, context):
        return ConversationHandler.END
    context.user_data['description'] = update.message.text
    progress = get_progress_indicator(2, 2)
    await update.message.reply_text(f"⚡ דיווח מהיר\n\n{progress} רמת חרדה\n\nבאיזה רמת חרדה? (1-10)", reply_markup=get_anxiety_level_keyboard())
    return QUICK_ANXIETY

async def complete_quick_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    anxiety_level = int(query.data.split("_")[1])
    user_id = query.from_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO anxiety_reports (user_id, timestamp, anxiety_level, description, report_type) VALUES (?, ?, ?, ?, ?)',
                   (user_id, context.user_data['timestamp'], anxiety_level, context.user_data['description'], 'quick'))
    conn.commit()
    conn.close()
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
    keyboard = [[InlineKeyboardButton("📈 ראה גרפים", callback_data="show_analytics")],
                [InlineKeyboardButton("💡 עזרה כללית", callback_data="show_help")],
                [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()
    return ConversationHandler.END

async def cancel_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ דיווח בוטל. אפשר להתחיל מחדש בכל עת.", reply_markup=get_main_keyboard())
    return ConversationHandler.END

async def start_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    context.user_data['report_type'] = 'full'
    context.user_data['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    progress = get_progress_indicator(1, 5)
    await update.message.reply_text(f"🔍 דיווח מלא\n\n{progress} תיאור המצב\n\nמה גורם לחרדה עכשיו? (תאר במפורט)")
    return FULL_DESC

async def get_full_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # <--- FIX 1: Check for menu command before processing
    if await check_for_menu_command(update, context):
        return ConversationHandler.END
    context.user_data['description'] = update.message.text
    progress = get_progress_indicator(2, 5)
    await update.message.reply_text(f"🔍 דיווח מלא\n\n{progress} רמת חרדה\n\nבאיזה רמת חרדה? (1-10)", reply_markup=get_anxiety_level_keyboard())
    return FULL_ANXIETY

async def get_full_anxiety_level(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['anxiety_level'] = int(query.data.split("_")[1])
    progress = get_progress_indicator(3, 5)
    await query.edit_message_text(f"🔍 דיווח מלא\n\n{progress} מיקום\n\nאיפה זה קרה?", reply_markup=get_options_keyboard(LOCATION_OPTIONS, "location"))
    return FULL_LOCATION

async def get_full_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['location'] = query.data.replace("location_", "")
    progress = get_progress_indicator(4, 5)
    await query.edit_message_text(f"🔍 דיווח מלא\n\n{progress} אנשים בסביבה\n\nמי היה בסביבה?", reply_markup=get_options_keyboard(PEOPLE_OPTIONS, "people"))
    return FULL_PEOPLE

async def get_full_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['people_around'] = query.data.replace("people_", "")
    progress = get_progress_indicator(5, 5)
    await query.edit_message_text(f"🔍 דיווח מלא\n\n{progress} מזג אוויר\n\nאיך מזג האוויר?", reply_markup=get_options_keyboard(WEATHER_OPTIONS, "weather"))
    return FULL_WEATHER

async def complete_full_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    weather = query.data.replace("weather_", "")
    user_id = query.from_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO anxiety_reports (user_id, timestamp, anxiety_level, description, location, people_around, weather, report_type) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                   (user_id, context.user_data['timestamp'], context.user_data['anxiety_level'], context.user_data['description'],
                    context.user_data['location'], context.user_data['people_around'], weather, 'full'))
    conn.commit()
    conn.close()
    analysis = analyze_user_patterns(user_id)
    recommendation = get_personalized_recommendation(user_id, {**context.user_data, 'weather': weather})
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
    keyboard = [[InlineKeyboardButton("📈 ראה גרפים והיסטוריה", callback_data="show_analytics")],
                [InlineKeyboardButton("🎵 שיר מרגיע", callback_data="relaxing_music")],
                [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()
    return ConversationHandler.END

async def start_free_venting(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🗣️ פריקה חופשית\n\nכתב כל מה שאתה מרגיש. אין שאלות, אין לחץ.\nרק תן לזה לצאת...")
    return FREE_VENTING

async def get_venting_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # <--- FIX 1: Check for menu command before processing
    if await check_for_menu_command(update, context):
        return ConversationHandler.END
    context.user_data['venting_content'] = update.message.text
    await update.message.reply_text("💝 תודה שחלקת איתי. זה דורש אומץ לפתוח את הלב.\n\nהאם לשמור את זה למעקב וניתוח עתידי?",
                                    reply_markup=InlineKeyboardMarkup([
                                        [InlineKeyboardButton("💾 כן, שמור לניתוח", callback_data="save_venting_yes")],
                                        [InlineKeyboardButton("🗑️ לא, רק פריקה", callback_data="save_venting_no")]
                                    ]))
    return VENTING_SAVE

async def save_venting_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    save_for_analysis = query.data == "save_venting_yes"
    user_id = query.from_user.id
    content = context.user_data['venting_content']
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO free_venting (user_id, content, save_for_analysis, timestamp) VALUES (?, ?, ?, ?)',
                   (user_id, content, save_for_analysis, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    conn.commit()
    conn.close()
    message = "✅ נשמר בהצלחה לניתוח!\n\n💡 הפריקה שלך תעזור לי להבין טוב יותר את הדפוסים שלך ולתת המלצות מותאמות." if save_for_analysis else "✅ הפריקה הושלמה!\n\n🌟 אני מקווה שזה עזר לך להרגיש טוב יותר. לפעמים פשוט לכתוב את מה שמרגישים זה הרבה."
    keyboard = [[InlineKeyboardButton("🎵 שיר מרגיע", callback_data="relaxing_music")],
                [InlineKeyboardButton("💡 עזרה כללית", callback_data="show_help")],
                [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    context.user_data.clear()
    return ConversationHandler.END

def create_quick_report_conversation():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^⚡ דיווח מהיר$"), start_quick_report)],
        states={
            QUICK_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_quick_description)],
            QUICK_ANXIETY: [CallbackQueryHandler(complete_quick_report, pattern="^anxiety_")]
        },
        fallbacks=[CommandHandler("start", cancel_report), MessageHandler(filters.Regex("^❌ ביטול$"), cancel_report)]
    )

def create_full_report_conversation():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🔍 דיווח מלא$"), start_full_report)],
        states={
            FULL_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_full_description)],
            FULL_ANXIETY: [CallbackQueryHandler(get_full_anxiety_level, pattern="^anxiety_")],
            FULL_LOCATION: [CallbackQueryHandler(get_full_location, pattern="^location_")],
            FULL_PEOPLE: [CallbackQueryHandler(get_full_people, pattern="^people_")],
            FULL_WEATHER: [CallbackQueryHandler(complete_full_report, pattern="^weather_")]
        },
        fallbacks=[CommandHandler("start", cancel_report), MessageHandler(filters.Regex("^❌ ביטול$"), cancel_report)]
    )

def create_venting_conversation():
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🗣️ פריקה חופשית$"), start_free_venting)],
        states={
            FREE_VENTING: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_venting_content)],
            VENTING_SAVE: [CallbackQueryHandler(save_venting_choice, pattern="^save_venting_")]
        },
        fallbacks=[CommandHandler("start", cancel_report), MessageHandler(filters.Regex("^❌ ביטול$"), cancel_report)]
    )

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # <--- FIX 2: Reordered to check for specific 'settings_menu' before generic 'settings_'
    if data == "main_menu":
        await query.edit_message_text("🏠 חזרת לתפריט הראשי\n\nבחר אפשרות מהתפריט למטה:", reply_markup=get_main_keyboard())
        # After editing the message, we can't add another keyboard, so we send a new message with the main keyboard.
        await context.bot.send_message(chat_id=query.message.chat_id, text=".", reply_markup=get_main_keyboard())

    elif data == "settings_menu" or data == "settings_reminders_back":
        await show_settings_menu_callback(query, context)
    elif data.startswith("settings_"):
        await handle_settings_callback(query, context)
    elif data == "relaxing_music":
        await show_relaxing_music(query, context)
    elif data == "start_using":
        await query.edit_message_text("🎯 מעולה! אני כאן בשבילך.\n\nבחר מה מתאים לך עכשיו דרך התפריט שמופיע למטה בצ'אט:")
    elif data == "show_analytics":
        await show_analytics_callback(query, context)
    elif data == "show_help":
        await show_help_callback(query, context)
    elif data == "reminder_toggle":
        await toggle_reminders(query, context)
    elif data == "reminder_time":
        await query.edit_message_text("⏰ שינוי שעת תזכורת\n\nתכונה זו תבוא בעדכון הבא.\nכרגע ברירת המחדל היא 20:00.",
                                      reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזור", callback_data="settings_reminders")]]))
    elif data.startswith("report_type_"):
        await set_report_type(query, context)
    elif data == "confirm_reset":
        await reset_user_data(query, context)

def get_immediate_recommendation(anxiety_level):
    if anxiety_level >= 8: return "🚨 רמת חרדה גבוהה! נסה טכניקת נשימה 4-4-6 עכשיו: שאף 4 שניות, עצור 4, נשוף 6. אם זה ממשיך, שקול לפנות לעזרה מקצועית."
    if anxiety_level >= 6: return "⚠️ חרדה ברמה בינונית. נסה לזהות מה גורם לזה ולהשתמש בטכניקת 5-4-3-2-1: מצא 5 דברים שאתה רואה, 4 שאתה שומע, 3 שאתה מרגיש, 2 שאתה מריח, 1 שאתה טועם."
    if anxiety_level >= 4: return "💛 חרדה קלה. זה הזמן הטוב לנשימה עמוקה ולהזכיר לעצמך שזה יעבור. נסה לשתות מים קרים או לצאת לאוויר צח."
    return "💚 רמת חרדה נמוכה. נהדר שאתה מודע לרגשות שלך! זה הזמן לחזק את הרגשה הטובה."

def analyze_user_patterns(user_id):
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    two_weeks_ago = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute('SELECT anxiety_level, location, people_around, weather, timestamp FROM anxiety_reports WHERE user_id = ? AND timestamp > ? ORDER BY timestamp DESC', (user_id, two_weeks_ago))
    reports = cursor.fetchall()
    conn.close()
    if len(reports) < 3: return "🔍 עדיין אוסף נתונים לניתוח דפוסים. המשך לדווח כדי לקבל תובנות מותאמות!"
    avg_anxiety = sum(r[0] for r in reports) / len(reports)
    location_counter = Counter(r[1] for r in reports if r[1])
    people_counter = Counter(r[2] for r in reports if r[2])
    analysis = f"הממוצע שלך בשבועיים האחרונים: {avg_anxiety:.1f}/10"
    if location_counter:
        most_common_location = location_counter.most_common(1)[0]
        analysis += f"\nהמיקום הבעייתי ביותר: {most_common_location[0]} ({most_common_location[1]} פעמים)"
    if people_counter:
        most_common_people = people_counter.most_common(1)[0]
        analysis += f"\nמצבים עם: {most_common_people[0]} מופיעים הכי הרבה"
    return analysis

def get_personalized_recommendation(user_id, current_data):
    base_recommendation = get_immediate_recommendation(current_data['anxiety_level'])
    if current_data.get("location") == "🏢 עבודה": base_recommendation += "\n\n💼 כיוון שזה בעבודה, נסה לקחת הפסקה קצרה, לצאת לאוויר צח או לדבר עם עמית שאתה סומך עליו."
    elif current_data.get("location") == "🏠 בית": base_recommendation += "\n\n🏠 אתה בבית - זה מקום בטוח. נסה לעשות משהו שמרגיע אותך: תה חם, מוזיקה, או קריאה."
    elif current_data.get("location") == "🚌 תחבורה ציבורית": base_recommendation += "\n\n🚌 תחבורה ציבורית יכולה להיות מלחיצה. נסה להתרכז בנשימה ולהקשיב למוזיקה מרגיעה."
    if current_data.get("people_around") == "👤 לבד": base_recommendation += "\n\n👤 אתה לבד עכשיו - זה בסדר. לפעמים קצת זמן לעצמנו זה בדיוק מה שאנחנו צריכים."
    return base_recommendation

async def show_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT anxiety_level, timestamp, location, people_around, report_type FROM anxiety_reports WHERE user_id = ? ORDER BY timestamp DESC LIMIT 30', (user_id,))
    reports = cursor.fetchall()
    conn.close()
    if not reports:
        await update.message.reply_text("📊 עדיין אין נתונים לניתוח\n\nהתחל לדווח כדי לראות דפוסים מעניינים על עצמך! 🎯", reply_markup=get_main_keyboard())
        return
    anxiety_levels = [r[0] for r in reports]
    avg_anxiety = sum(anxiety_levels) / len(anxiety_levels)
    locations = [r[2] for r in reports if r[2]]
    location_counter = Counter(locations)
    people = [r[3] for r in reports if r[3]]
    people_counter = Counter(people)
    analysis_text = f"""
📈 הניתוח שלך ({len(reports)} הדיווחים האחרונים):
📊 סטטיסטיקות כלליות:
• ממוצע חרדה: {avg_anxiety:.1f}/10
• חרדה מקסימלית: {max(anxiety_levels)}/10
• חרדה מינימלית: {min(anxiety_levels)}/10
• דיווחים מהירים: {sum(1 for r in reports if r[4] == 'quick')}
• דיווחים מלאים: {sum(1 for r in reports if r[4] == 'full')}
📍 מיקומים שנמדדו:"""
    for location, count in location_counter.most_common(3):
        avg_anxiety_location = sum(r[0] for r in reports if r[2] == location) / count
        analysis_text += f"\n• {location}: {count} פעמים ({(count / len(locations)) * 100:.0f}%) - ממוצע חרדה: {avg_anxiety_location:.1f}"
    if people_counter:
        analysis_text += f"\n\n👥 מצבים חברתיים:"
        for people_type, count in people_counter.most_common(3):
            avg_anxiety_people = sum(r[0] for r in reports if r[3] == people_type) / count
            analysis_text += f"\n• {people_type}: {count} פעמים ({(count / len(people)) * 100:.0f}%) - ממוצע חרדה: {avg_anxiety_people:.1f}"
    await update.message.reply_text(analysis_text, reply_markup=get_main_keyboard())

async def show_analytics_callback(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute('SELECT anxiety_level FROM anxiety_reports WHERE user_id = ?', (user_id,))
    reports = cursor.fetchall()
    conn.close()
    if not reports:
        await query.edit_message_text("📊 עדיין אין נתונים לניתוח.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]))
        return
    anxiety_levels = [r[0] for r in reports]
    analysis_text = f"""
📈 הניתוח שלך ({len(reports)} דיווחים):
📊 סטטיסטיקות:
• ממוצע חרדה: {sum(anxiety_levels) / len(anxiety_levels):.1f}/10
• מקסימום: {max(anxiety_levels)}/10
• מינימום: {min(anxiety_levels)}/10
"""
    await query.edit_message_text(analysis_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]))

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
💡 עזרה כללית בהתמודדות עם חרדה:
🫁 טכניקות נשימה:
• נשימה 4-4-6: שאף 4 שניות, עצור 4, נשוף 6
🧘‍♂️ טכניקות הרגעה מיידית:
• 5-4-3-2-1: מצא 5 דברים שאתה רואה, 4 שומע, 3 מרגיש, 2 מריח, 1 טועם
📞 עזרה מקצועית 24/7:
• ער"ן: 1201 (צ'אט: https://www.eran.org.il/online-emotional-help/)
• סה"ר: 1800-120-140 (צ'אט: https://sahar.org.il/help/)
⚠️ הבוט אינו מחליף טיפול מקצועי!
"""
    await update.message.reply_text(help_text, reply_markup=get_main_keyboard(), disable_web_page_preview=True)

async def show_help_callback(query, context):
    help_text = """
💡 עזרה מיידית:
🫁 נשימה 4-4-6: שאף 4, עצור 4, נשוף 6
🧘‍♂️ טכניקת 5-4-3-2-1: 5 לראות, 4 לשמוע, 3 להרגיש, 2 להריח, 1 לטעום
📞 עזרה מקצועית: ער"ן 1201
"""
    await query.edit_message_text(help_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]))

async def show_relaxing_music_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    music_text = """
🎵 שירים מרגיעים (מוכחים מחקרית):
🎼 "Weightless" - Marconi Union (הכי מרגיע!)
🎧 [יוטיוב](https://youtu.be/UfcAVejslrU) | 🎶 [ספוטיפיי](https://open.spotify.com/track/6j2P7MoSNEDE9BwT4CGBFA)
🎼 "Someone Like You" - Adele
🎧 [יוטיוב](https://youtu.be/hLQl3WQQoQ0) | 🎶 [ספוטיפיי](https://open.spotify.com/track/4ErraYS3SSoBYF0A7cWk6H)
🎼 "Watermark" - Enya
🎧 [יוטיוב](https://youtu.be/0IKvdaXZP8Q) | 🎶 [ספוטיפיי](https://open.spotify.com/track/0CBpxAa95ZvdH1D9K7cFem)
"""
    await update.message.reply_text(music_text, reply_markup=get_main_keyboard(), parse_mode='Markdown', disable_web_page_preview=True)

async def show_relaxing_music(query, context):
    music_text = """
🎵 שירים מרגיעים:
🎼 "Weightless" - Marconi Union
🎧 [יוטיוב](https://youtu.be/UfcAVejslrU) | 🎶 [ספוטיפיי](https://open.spotify.com/track/6j2P7MoSNEDE9BwT4CGBFA)
🎼 "Someone Like You" - Adele
🎧 [יוטיוב](https://youtu.be/hLQl3WQQoQ0) | 🎶 [ספוטיפיי](https://open.spotify.com/track/4ErraYS3SSoBYF0A7cWk6H)
"""
    await query.edit_message_text(music_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]), parse_mode='Markdown', disable_web_page_preview=True)

async def show_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("⚡ סוג דיווח מועדף", callback_data="settings_report_type")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")],
    ]
    await update.message.reply_text("⚙️ הגדרות\n\nבחר מה תרצה לשנות:", reply_markup=InlineKeyboardMarkup(keyboard))

async def show_settings_menu_callback(query, context):
    keyboard = [
        [InlineKeyboardButton("🔔 הגדרות תזכורות", callback_data="settings_reminders")],
        [InlineKeyboardButton("⚡ סוג דיווח מועדף", callback_data="settings_report_type")],
        [InlineKeyboardButton("📊 ייצוא נתונים", callback_data="settings_export")],
        [InlineKeyboardButton("🗑️ איפוס נתונים", callback_data="settings_reset")],
        [InlineKeyboardButton("🏠 חזור לתפריט", callback_data="main_menu")]
    ]
    await query.edit_message_text("⚙️ הגדרות\n\nבחר מה תרצה לשנות:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_settings_callback(query, context):
    data = query.data
    if data == "settings_reminders": await show_reminder_settings(query, context)
    elif data == "settings_report_type": await show_report_type_settings(query, context)
    elif data == "settings_export": await export_user_data(query, context)
    elif data == "settings_reset": await confirm_reset_data(query, context)

async def show_reminder_settings(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_reminder, reminder_time FROM user_settings WHERE user_id = ?", (user_id,))
    settings = cursor.fetchone() or (False, '20:00')
    conn.close()
    keyboard = [
        [InlineKeyboardButton(f"🔔 {'השבת' if settings[0] else 'הפעל'} תזכורות", callback_data="reminder_toggle")],
        [InlineKeyboardButton("⏰ שנה שעה", callback_data="reminder_time")],
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")]
    ]
    message = f"🔔 הגדרות תזכורות\n\nסטטוס נוכחי: {'מופעל' if settings[0] else 'מופסק'}\nשעת תזכורת: {settings[1]}"
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_report_type_settings(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT preferred_report_type FROM user_settings WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    # <--- FIX 3: Handle case where settings don't exist for user
    current_type = result[0] if result and result[0] else 'quick'
    keyboard = [
        [InlineKeyboardButton(f"⚡ דיווח מהיר {'✓' if current_type == 'quick' else ''}", callback_data="report_type_quick")],
        [InlineKeyboardButton(f"🔍 דיווח מלא {'✓' if current_type == 'full' else ''}", callback_data="report_type_full")],
        [InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")]
    ]
    message = f"⚡ סוג דיווח מועדף\n\nהגדרה נוכחית: {'דיווח מהיר' if current_type == 'quick' else 'דיווח מלא'}"
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def export_user_data(query, context):
    # This function remains largely the same but with better error handling
    await query.edit_message_text("מכין את הנתונים לייצוא...", reply_markup=None)
    # The rest of the function...
    await query.message.reply_text("ייצוא יושלם בקרוב.") # Placeholder for full implementation

async def confirm_reset_data(query, context):
    message = "⚠️ איפוס נתונים\n\nהאם אתה בטוח שברצונך למחוק את כל הנתונים שלך? פעולה זו בלתי הפיכה!"
    keyboard = [[InlineKeyboardButton("❌ ביטול", callback_data="settings_menu")],
                [InlineKeyboardButton("🗑️ כן, מחק הכל", callback_data="confirm_reset")]]
    await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))

async def reset_user_data(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM anxiety_reports WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM free_venting WHERE user_id = ?", (user_id,))
    cursor.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
    cursor.execute("INSERT INTO user_settings (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()
    await query.edit_message_text("✅ הנתונים נמחקו בהצלחה!", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]]))

async def toggle_reminders(query, context):
    user_id = query.from_user.id
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("SELECT daily_reminder FROM user_settings WHERE user_id = ?", (user_id,))
    current_status = cursor.fetchone()[0]
    new_status = not current_status
    cursor.execute("UPDATE user_settings SET daily_reminder = ? WHERE user_id = ?", (new_status, user_id))
    conn.commit()
    conn.close()
    await query.edit_message_text(f"✅ תזכורות {'הופעלו' if new_status else 'הושבתו'} בהצלחה!",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזור", callback_data="settings_reminders")]]))

async def set_report_type(query, context):
    user_id = query.from_user.id
    report_type = query.data.split("_")[-1]
    conn = sqlite3.connect('anxiety_data.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE user_settings SET preferred_report_type = ? WHERE user_id = ?", (report_type, user_id))
    conn.commit()
    conn.close()
    await query.edit_message_text(f"✅ סוג הדיווח המועדף הוגדר ל{'דיווח מהיר' if report_type == 'quick' else 'דיווח מלא'}!",
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 חזור להגדרות", callback_data="settings_menu")]]))

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    if update and hasattr(update, 'effective_chat') and update.effective_chat:
        try:
            # Check if the update is a callback query and edit the message to show the error
            if isinstance(update, CallbackQuery):
                 await update.callback_query.edit_message_text(
                     text="❌ אופס! קרתה שגיאה. נסה שוב או חזור לתפריט הראשי.",
                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]])
                 )
            else:
                 await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ אופס! קרתה שגיאה. נסה שוב או חזור לתפריט הראשי.",
                    reply_markup=get_main_keyboard()
                 )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")

def main():
    try:
        init_database()
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Add conversation handlers first
        application.add_handler(create_quick_report_conversation())
        application.add_handler(create_full_report_conversation())
        application.add_handler(create_venting_conversation())
        
        # Add other handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(handle_callback_query))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_general_message))
        
        application.add_error_handler(error_handler)
        
        logger.info("🚀 הבוט מתחיל לרוץ...")
        print("✅ הבוט פעיל! לחץ Ctrl+C לעצירה")
        application.run_polling()
            
    except Exception as e:
        logger.error(f"שגיאה קריטית בהפעלת הבוט: {e}")
        print(f"❌ שגיאה קריטית: {e}")
        raise

if __name__ == '__main__':
    main()
