"""
סוכן AI לניווט בשירותי בריאות הנפש בישראל
Israeli Mental Health Navigator Agent
מבוסס על: https://github.com/skills-il/health-services/tree/master/israeli-mental-health-navigator
"""

import os
import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler,
    filters, CommandHandler
)

logger = logging.getLogger(__name__)

# =================================================================
# מצב שיחה
# =================================================================
MH_ACTIVE = 200

# =================================================================
# הפרומפט של סוכן ה-AI - כל הידע מוזרק לכאן
# =================================================================

NAVIGATOR_SYSTEM_PROMPT = """אתה סוכן AI מומחה בניווט מערכת בריאות הנפש בישראל.
אתה פועל בתוך בוט טלגרם בשם "שלווה". תפקידך לעזור למשתמשים למצוא את השירות הנכון עבורם,
לענות על שאלות, ולהנגיש מידע מעשי על בריאות הנפש בישראל.

══════════════════════════════════
מאגר הידע שלך:
══════════════════════════════════

📌 רפורמת בריאות הנפש (2015):
- מאז 2015, טיפול נפשי בישראל מכוסה תחת חוק ביטוח בריאות ממלכתי
- הרפורמה העבירה שירותים פסיכיאטריים ופסיכולוגיים ממרכזים ממשלתיים לקופות החולים
- כל תושב ישראל הרשום בקופת חולים זכאי לטיפול נפשי מסובסד
- השירותים כוללים: ייעוץ פסיכיאטרי, פסיכותרפיה, אבחון פסיכולוגי, תרופות
- השתתפות עצמית: כ-34 ₪ לרבעון
- לא צריך הפניה מרופא משפחה

📌 גישה לטיפול דרך קופות החולים (כללית, מכבי, מאוחדת, לאומית):
- שלב 1: פנייה למחלקת בריאות הנפש של הקופה
- שלב 2: סינון ראשוני (בד"כ טלפוני) לקביעת דחיפות ומסלול
- שלב 3: התאמת מטפל/ת מקצועי/ת
- שלב 4: התחלת טיפול שוטף (בדרך כלל שבועי, 12-20 מפגשים)
- זמני המתנה: 2-8 שבועות בהתאם לאזור ולדחיפות
- טיפ: אם ההמתנה ארוכה, אפשר לבקש הפניה לביטוח המשלים
- אפשר לבקש החלפת מטפל אם לא מתאים
- אפשר לשלב טיפול תרופתי ופסיכותרפיה

📌 קווי חירום ותמיכה רגשית:
- ער"ן (1201): עזרה ראשונה נפשית, תמיכה רגשית 24/7, מעל 500,000 שיחות בשנה. שפות: עברית, ערבית, רוסית, אמהרית, אנגלית
- סה"ר (sahar.org.il): צ'אט מקוון 24/7 למי שמעדיפים לכתוב. אנונימי לחלוטין
- נט"ל (1-800-363-363): מרכז לנפגעי טראומה, תמיכה מקצועית לנפגעי אירועים ביטחוניים, ימים א'-ה' 9:00-21:00
- קו לחיים (*2784): מניעת התאבדות 24/7, שיחות אנונימיות וחסויות
- עמח"א (02-5427127): סיוע לניצולי שואה ובני דור שני, ימים א'-ה' 8:00-16:00
- קווים ייעודיים: קווים לנוער, נשים במצוקה, קהילה גאה, דוברי ערבית/רוסית/אמהרית
- מספרי חירום: מד"א 101, משטרה 100, כיבוי 102, חירום כללי 112
- כל השיחות אנונימיות וחינמיות. לא חייבים להיות במשבר כדי להתקשר

📌 סוגי טיפולים:
- CBT (קוגניטיבי-התנהגותי): הנפוץ ביותר במערכת הציבורית. מתמקד בשינוי דפוסי חשיבה והתנהגות. מתאים לחרדה, דיכאון, פוביות, OCD. בדרך כלל 12-20 מפגשים. זמין בכל קופות החולים
- EMDR (עיבוד טראומה): מעבד זיכרונות טראומטיים באמצעות תנועות עיניים מונחות. מתאים ל-PTSD, טראומה. 6-12 מפגשים. הורחב משמעותית לאחר 7 באוקטובר
- פסיכודינמי: חקירה של דפוסים לא-מודעים וקשרים מוקדמים. מתאים לקשיים חוזרים ביחסים, דפוסי התנהגות, דיכאון ממושך. טווח בינוני-ארוך
- DBT (דיאלקטי-התנהגותי): שילוב CBT עם מיינדפולנס. מתאים לוויסות רגשי, פגיעה עצמית, הפרעת אישיות גבולית. 6-12 חודשים
- טיפול קבוצתי: במסגרת קבוצה קטנה, שיתוף חוויות ותמיכה הדדית. מתאים לחרדה חברתית, אובדן, התמכרויות
- טיפול תרופתי: ניתן ע"י פסיכיאטר בלבד. נוגדי דיכאון, תרופות נגד חרדה וכו'. מתאים לדיכאון, חרדה, הפרעה דו-קוטבית, ADHD
- טיפול באמנות/משחק: מתאים במיוחד לילדים ולנפגעי טראומה שמתקשים בהבעה מילולית

📌 עלויות טיפול:
- קופת חולים (ציבורי): ~34 ₪ לרבעון, המתנה 2-8 שבועות
- פסיכולוג פרטי: 300-600 ₪ למפגש, אפשר החזר חלקי מביטוח משלים
- פסיכיאטר פרטי: 500-900 ₪ למפגש, רק פסיכיאטר יכול לרשום תרופות
- עו"ס קליני/ת: 200-450 ₪ למפגש, אפשרות טובה ומשתלמת
- מרפאת אוניברסיטה (הכשרה): 150-250 ₪ למפגש, מטפלים בהכשרה תחת פיקוח
- פלטפורמות טיפול מקוון: 200-400 ₪ למפגש, נגיש מכל מקום
- טיפ: בדוק ביטוח משלים - הרבה מציעים החזר חלקי על טיפולים פרטיים
- ניכוי מס: אפשר לנכות הוצאות רפואיות מעל תקרה מסוימת (סעיף 44 לפקודת מס הכנסה)

📌 זכויות בריאות הנפש בעבודה:
- כל עובד צובר 1.5 ימי מחלה לחודש (18 בשנה) - ניתן להשתמש גם למצב נפשי
- חוק שוויון זכויות לאנשים עם מוגבלות אוסר אפליה על בסיס מצב נפשי
- מעסיק לא יכול לדרוש פרטי אבחנה - אישור מחלה מציין רק ימי היעדרות
- תוכניות EAP (Employee Assistance Programs): מעסיקים רבים מציעים 3-6 מפגשי טיפול חינמיים וחסויים
- זכויות מיוחדות: היעדרות בגלל מצב נפשי מוגנת כמו כל מחלה אחרת

📌 PTSD ומשאבי טראומה:
- נט"ל (1-800-363-363): טיפול מתמחה בנפגעי טראומה ביטחונית, ליווי ארוך טווח
- ביטוח לאומי: PTSD מוכר כמוגבלות, אפשר להגיש תביעה לנכות, זכאות לטיפולים ושיקום
- קרן OneFamily: תמיכה בנפגעי טרור ומשפחותיהם
- תוכניות לאחר 7 באוקטובר: הרחבה משמעותית של טיפולי EMDR, מרכזי חוסן קהילתיים ברחבי הארץ, קבוצות תמיכה ייעודיות
- חיילים ומשרתי מילואים: זכאות לטיפול דרך אגף השיקום במשרד הביטחון

📌 טיפול בפתרון בעיות נפוצות:
- זמני המתנה ארוכים: לבקש הפניה לביטוח משלים, לפנות למרפאת אוניברסיטה, לשקול טיפול מקוון
- "רק מקרים חמורים מקבלים טיפול": לא נכון! כל תושב זכאי, גם בלי אבחנה חמורה
- מעסיק מבקש פרטי אבחנה: לא חוקי! אישור רפואי מציין רק ימי היעדרות

══════════════════════════════════
הנחיות התנהגות:
══════════════════════════════════
1. ענה תמיד בעברית, בשפה ברורה ונגישה
2. היה אמפתי, חם ומקצועי - אבל מעשי ותכליתי
3. תן מידע ספציפי עם מספרים, עלויות, ושלבים ברורים
4. אם מישהו מזכיר מצוקה חריפה, מחשבות אובדניות או סכנה - הפנה מיד לקו לחיים (*2784) או מד"א (101)
5. הבהר תמיד שאתה כלי מידע ולא מחליף ייעוץ מקצועי
6. היה רגיש לקונטקסט הישראלי: צבא, מילואים, מצב ביטחוני, שואה, 7 באוקטובר
7. כשמתאים, הצע כמה אפשרויות ותן למשתמש לבחור
8. אל תאבחן - רק תכוון לשירות המתאים
"""

# =================================================================
# כפתורי קיצור - כל אחד שולח שאלה מוגדרת מראש ל-AI
# =================================================================

TOPIC_SHORTCUTS = {
    "mh_topic_hotlines": "מה קווי החירום והתמיכה הרגשית הזמינים בישראל? תן לי את כל המספרים והפרטים.",
    "mh_topic_kupat": "איך מתחילים טיפול נפשי דרך קופת החולים? תסביר שלב אחר שלב.",
    "mh_topic_types": "מה סוגי הטיפולים הנפשיים שזמינים בישראל? תסביר כל אחד בקצרה ולמי הוא מתאים.",
    "mh_topic_costs": "כמה עולה טיפול נפשי בישראל? תן לי טווחי מחירים לכל סוג מטפל ומסלול.",
    "mh_topic_workplace": "מה הזכויות שלי בנושא בריאות הנפש במקום העבודה?",
    "mh_topic_ptsd": "מה המשאבים שזמינים בישראל לטיפול ב-PTSD וטראומה? כולל אחרי 7 באוקטובר.",
}


def get_topic_shortcuts_keyboard():
    """כפתורי קיצור לנושאים פופולריים"""
    keyboard = [
        [InlineKeyboardButton("📞 קווי חירום", callback_data="mh_topic_hotlines")],
        [InlineKeyboardButton("🏥 טיפול בקופה", callback_data="mh_topic_kupat"),
         InlineKeyboardButton("💊 סוגי טיפולים", callback_data="mh_topic_types")],
        [InlineKeyboardButton("💰 עלויות", callback_data="mh_topic_costs"),
         InlineKeyboardButton("🏢 זכויות בעבודה", callback_data="mh_topic_workplace")],
        [InlineKeyboardButton("🎗️ PTSD וטראומה", callback_data="mh_topic_ptsd")],
    ]
    return InlineKeyboardMarkup(keyboard)


# =================================================================
# פונקציות שיחה
# =================================================================

async def _send_to_ai(context, user_message):
    """שליחת הודעה ל-AI וקבלת תשובה"""
    model = context.user_data.get('mh_navigator_model')
    if not model:
        return None

    chat = model.start_chat(history=context.user_data.get('mh_chat_history', []))
    response = await chat.send_message_async(user_message)
    bot_response = response.text

    context.user_data['mh_chat_history'].append({'role': 'user', 'parts': [user_message]})
    context.user_data['mh_chat_history'].append({'role': 'model', 'parts': [bot_response]})

    return bot_response


def _init_ai_session(context):
    """אתחול סשן AI חדש"""
    context.user_data['mh_navigator_model'] = genai.GenerativeModel('gemini-1.5-flash')
    opening = (
        "🧠 נווט בריאות הנפש - ישראל\n\n"
        "היי! אני סוכן AI שמתמחה בבריאות הנפש בישראל.\n"
        "אפשר לשאול אותי כל שאלה - על זכויות, טיפולים, עלויות, קופות חולים, "
        "קווי חירום, PTSD, זכויות בעבודה, ועוד.\n\n"
        "אפשר גם לבחור נושא מהכפתורים למטה, או פשוט לכתוב שאלה חופשית.\n\n"
        "לסיום: /end_navigator"
    )
    context.user_data['mh_chat_history'] = [
        {'role': 'user', 'parts': [NAVIGATOR_SYSTEM_PROMPT]},
        {'role': 'model', 'parts': [opening]}
    ]
    return opening


async def entry_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """נקודת כניסה: המשתמש לחץ על כפתור הנווט"""
    query = update.callback_query
    await query.answer()

    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        await query.edit_message_text("שירות ה-AI אינו זמין כרגע.")
        return ConversationHandler.END

    opening = _init_ai_session(context)
    await query.edit_message_text(text=opening, reply_markup=get_topic_shortcuts_keyboard())
    return MH_ACTIVE


async def handle_topic_shortcut(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """טיפול בלחיצה על כפתור קיצור - שולח שאלה מוגדרת ל-AI"""
    query = update.callback_query
    await query.answer()
    data = query.data

    shortcut_question = TOPIC_SHORTCUTS.get(data)
    if not shortcut_question:
        return MH_ACTIVE

    # הצגת אינדיקציה שהבוט מעבד
    await query.edit_message_text("⏳ מחפש מידע...")

    try:
        bot_response = await _send_to_ai(context, shortcut_question)
        if bot_response:
            await query.edit_message_text(
                text=bot_response,
                reply_markup=get_topic_shortcuts_keyboard()
            )
        else:
            await query.edit_message_text(
                "מצטער, קרתה שגיאה. נסה שוב.",
                reply_markup=get_topic_shortcuts_keyboard()
            )
    except Exception as e:
        logger.error(f"Navigator AI shortcut error: {e}")
        await query.edit_message_text(
            "מצטער, קרתה שגיאה. נסה שוב או כתוב שאלה חופשית.",
            reply_markup=get_topic_shortcuts_keyboard()
        )

    return MH_ACTIVE


async def handle_navigator_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """טיפול בהודעת טקסט חופשית - שליחה ל-AI"""
    user_message = update.message.text
    model = context.user_data.get('mh_navigator_model')

    if not model:
        from main import get_main_keyboard
        await update.message.reply_text(
            "אופס, נראה שהשיחה התאפסה. נסה להתחיל מחדש מהתפריט.",
            reply_markup=get_main_keyboard()
        )
        return ConversationHandler.END

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')

    try:
        bot_response = await _send_to_ai(context, user_message)
        if bot_response:
            await update.message.reply_text(
                bot_response,
                reply_markup=get_topic_shortcuts_keyboard()
            )
        else:
            await update.message.reply_text(
                "מצטער, קרתה שגיאה. נסה שוב.",
                reply_markup=get_topic_shortcuts_keyboard()
            )
    except Exception as e:
        logger.error(f"Navigator AI error: {e}")
        await update.message.reply_text(
            "מצטער, קרתה שגיאה. נסה שוב או חזור לתפריט עם /end_navigator"
        )

    return MH_ACTIVE


async def end_navigator_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """סיום שיחת הנווט"""
    from main import get_main_keyboard
    context.user_data.pop('mh_navigator_model', None)
    context.user_data.pop('mh_chat_history', None)
    await update.message.reply_text(
        "🧠 תודה שהשתמשת בנווט בריאות הנפש!\n\n"
        "זכור/זכרי: לפנות לעזרה מקצועית זה סימן של חוזק. 💙\n"
        "במצב חירום: ער\"ן 1201 | קו לחיים *2784",
        reply_markup=get_main_keyboard()
    )
    return ConversationHandler.END


# =================================================================
# ConversationHandler
# =================================================================

def create_navigator_conversation(main_menu_regex):
    """יצירת ConversationHandler לנווט בריאות הנפש"""

    async def ask_to_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        keyboard = [[
            InlineKeyboardButton("✅ כן, סיים שיחה", callback_data="cancel_mh_conversation"),
            InlineKeyboardButton("❌ לא, אמשיך", callback_data="continue_mh_conversation")
        ]]
        await update.message.reply_text(
            "🤔 נראה שניסית להתחיל פעולה חדשה. האם לסיים את שיחת הנווט?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return MH_ACTIVE

    async def perform_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        context.user_data.pop('mh_navigator_model', None)
        context.user_data.pop('mh_chat_history', None)
        await query.edit_message_text("שיחת הנווט הסתיימה. בחר/י פעולה חדשה מהתפריט.")
        return ConversationHandler.END

    async def perform_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("ממשיכים. מה השאלה שלך?")
        return MH_ACTIVE

    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(entry_from_callback, pattern="^mh_start_navigator$"),
        ],
        states={
            MH_ACTIVE: [
                CommandHandler("end_navigator", end_navigator_chat),
                CallbackQueryHandler(perform_cancel, pattern="^cancel_mh_conversation$"),
                CallbackQueryHandler(perform_continue, pattern="^continue_mh_conversation$"),
                CallbackQueryHandler(handle_topic_shortcut, pattern="^mh_topic_"),
                MessageHandler(filters.Regex(main_menu_regex), ask_to_cancel),
                MessageHandler(filters.TEXT & ~filters.COMMAND & ~filters.Regex(main_menu_regex), handle_navigator_message),
            ],
        },
        fallbacks=[
            CommandHandler("end_navigator", end_navigator_chat),
            CommandHandler("start", end_navigator_chat),
        ],
        name="navigator_conversation",
        persistent=False,
    )
