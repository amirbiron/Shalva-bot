"""
סוכן AI לניווט בשירותי בריאות הנפש בישראל
Israeli Mental Health Navigator Agent
מבוסס על: https://github.com/skills-il/health-services/tree/master/israeli-mental-health-navigator
"""

import logging
import google.generativeai as genai
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler, CallbackQueryHandler, MessageHandler,
    filters, CommandHandler
)

logger = logging.getLogger(__name__)

# =================================================================
# מצבי שיחה לנווט בריאות הנפש
# =================================================================
MH_ACTIVE = range(200, 201)[0]

# =================================================================
# מאגר ידע - בריאות הנפש בישראל
# =================================================================

CRISIS_HOTLINES = {
    "eran": {
        "name": "ער\"ן - עזרה ראשונה נפשית",
        "number": "1201",
        "hours": "24/7",
        "description": "תמיכה רגשית, סיוע במשבר, ייעוץ ראשוני. מעל 500,000 שיחות בשנה.",
        "languages": "עברית, ערבית, רוסית, אמהרית, אנגלית"
    },
    "sahar": {
        "name": "סה\"ר - סיוע והקשבה ברשת",
        "number": "sahar.org.il",
        "hours": "24/7",
        "description": "צ'אט מקוון למי שמעדיפים לכתוב. אנונימי לחלוטין."
    },
    "natal": {
        "name": "נט\"ל - מרכז לנפגעי טראומה",
        "number": "1-800-363-363",
        "hours": "ימים א'-ה' 9:00-21:00",
        "description": "תמיכה מקצועית לנפגעי אירועים ביטחוניים, טראומה ו-PTSD."
    },
    "kav_lahaim": {
        "name": "קו לחיים - מניעת התאבדות",
        "number": "*2784",
        "hours": "24/7",
        "description": "קו חירום למניעת התאבדות. שיחות אנונימיות וחסויות."
    },
    "amcha": {
        "name": "עמח\"א - סיוע לניצולי שואה",
        "number": "02-5427127",
        "hours": "ימים א'-ה' 8:00-16:00",
        "description": "תמיכה נפשית ופסיכולוגית לניצולי השואה ובני דור שני."
    },
    "emergency": {
        "name": "מספרי חירום",
        "number": "מד\"א: 101 | משטרה: 100 | כיבוי: 102 | חירום כללי: 112",
        "hours": "24/7",
        "description": "לסכנת חיים מיידית."
    }
}

# סוגי טיפולים
THERAPY_TYPES = {
    "cbt": {
        "name": "CBT - טיפול קוגניטיבי-התנהגותי",
        "description": "הטיפול הנפוץ ביותר במערכת הציבורית. מתמקד בשינוי דפוסי חשיבה והתנהגות שגורמים למצוקה.",
        "good_for": "חרדה, דיכאון, פוביות, OCD",
        "duration": "12-20 מפגשים בדרך כלל",
        "availability": "זמין בכל קופות החולים"
    },
    "emdr": {
        "name": "EMDR - עיבוד טראומה",
        "description": "טיפול שמעבד זיכרונות טראומטיים באמצעות תנועות עיניים מונחות. הורחב משמעותית לאחר אוקטובר 2023.",
        "good_for": "PTSD, טראומה, חרדה פוסט-טראומטית",
        "duration": "6-12 מפגשים",
        "availability": "זמין בקופות ובפרטי, הורחב לאחר 7 באוקטובר"
    },
    "psychodynamic": {
        "name": "טיפול פסיכודינמי",
        "description": "חקירה של דפוסים לא-מודעים, קשרים מוקדמים והשפעתם על ההווה.",
        "good_for": "קשיים חוזרים ביחסים, דפוסי התנהגות, דיכאון ממושך",
        "duration": "טווח בינוני-ארוך",
        "availability": "זמין בפרטי ובחלק מקופות החולים"
    },
    "dbt": {
        "name": "DBT - טיפול דיאלקטי-התנהגותי",
        "description": "שילוב של CBT עם מיינדפולנס. מתמקד בוויסות רגשי ומיומנויות בין-אישיות.",
        "good_for": "ויסות רגשי, פגיעה עצמית, הפרעת אישיות גבולית",
        "duration": "6-12 חודשים",
        "availability": "זמין בפרטי ובמרכזים מתמחים"
    },
    "group": {
        "name": "טיפול קבוצתי",
        "description": "טיפול במסגרת קבוצה קטנה, מאפשר שיתוף חוויות ותמיכה הדדית.",
        "good_for": "חרדה חברתית, אובדן, התמכרויות, PTSD",
        "duration": "משתנה",
        "availability": "זמין בקופות ובמרכזים פסיכולוגיים"
    },
    "medication": {
        "name": "טיפול תרופתי",
        "description": "תרופות פסיכיאטריות (נוגדי דיכאון, תרופות נגד חרדה וכו'). ניתנות ע\"י פסיכיאטר בלבד.",
        "good_for": "דיכאון, חרדה, הפרעה דו-קוטבית, ADHD",
        "duration": "משתנה",
        "availability": "דרך רופא משפחה או פסיכיאטר בקופה"
    }
}

# עלויות טיפול
THERAPY_COSTS = {
    "kupat_cholim": {
        "name": "קופת חולים (ציבורי)",
        "cost": "~34 ₪ לרבעון",
        "wait_time": "2-8 שבועות",
        "notes": "מאז 2015, טיפול נפשי הוא חלק מחוק ביטוח בריאות ממלכתי. כל תושב רשום בקופה זכאי."
    },
    "private_psychologist": {
        "name": "פסיכולוג פרטי",
        "cost": "300-600 ₪ למפגש",
        "wait_time": "שבוע-שבועיים",
        "notes": "אפשר לקבל החזר חלקי מביטוח משלים."
    },
    "private_psychiatrist": {
        "name": "פסיכיאטר פרטי",
        "cost": "500-900 ₪ למפגש",
        "wait_time": "שבוע-שלושה שבועות",
        "notes": "רק פסיכיאטר יכול לרשום תרופות."
    },
    "social_worker": {
        "name": "עובד/ת סוציאלי/ת קליני/ת",
        "cost": "200-450 ₪ למפגש",
        "wait_time": "שבוע-שבועיים",
        "notes": "אפשרות טובה ומשתלמת לטיפול רגשי."
    },
    "university_clinic": {
        "name": "מרפאת אוניברסיטה (הכשרה)",
        "cost": "150-250 ₪ למפגש",
        "wait_time": "2-4 שבועות",
        "notes": "מטפלים בהכשרה תחת פיקוח. אפשרות מצוינת במחיר מופחת."
    },
    "online": {
        "name": "פלטפורמות טיפול מקוון",
        "cost": "200-400 ₪ למפגש",
        "wait_time": "ימים ספורים",
        "notes": "נגיש מכל מקום. מתאים למי שמעדיף טיפול מהבית."
    }
}

# זכויות בעבודה
WORKPLACE_RIGHTS = """
🏢 *זכויות בריאות הנפש במקום העבודה*

📌 *ימי מחלה:*
• כל עובד צובר 1.5 ימי מחלה לחודש (18 בשנה)
• ניתן להשתמש בהם גם עבור מצב נפשי
• אישור מחלה לא צריך לכלול אבחנה מפורטת

📌 *איסור אפליה:*
• חוק שוויון זכויות לאנשים עם מוגבלות אוסר אפליה על בסיס מצב נפשי
• מעסיק לא יכול לדרוש פרטי אבחנה

📌 *תוכניות EAP:*
• מעסיקים רבים מציעים 3-6 מפגשי טיפול חינמיים וחסויים
• שאל את משאבי אנוש אם קיימת תוכנית כזו

📌 *שמירת סודיות:*
• המעסיק לא זכאי לדעת את סיבת המחלה
• אישור רפואי מציין רק ימי היעדרות
"""

# משאבי PTSD
PTSD_RESOURCES = """
🎗️ *משאבי PTSD וטראומה*

📌 *נט\"ל (1-800-363-363):*
• טיפול מתמחה בנפגעי טראומה ביטחונית
• ליווי ארוך טווח

📌 *ביטוח לאומי:*
• PTSD מוכר כמוגבלות
• אפשר להגיש תביעה לנכות
• זכאות לטיפולים ושיקום

📌 *קרן OneFamily:*
• תמיכה בנפגעי טרור ומשפחותיהם

📌 *תוכניות לאחר 7 באוקטובר:*
• הרחבה משמעותית של טיפולי EMDR
• מרכזי חוסן קהילתיים ברחבי הארץ
• קבוצות תמיכה ייעודיות
"""

# =================================================================
# הפרומפט של סוכן ה-AI
# =================================================================

NAVIGATOR_SYSTEM_PROMPT = """אתה סוכן AI מומחה בניווט מערכת בריאות הנפש בישראל.
תפקידך לעזור למשתמשים למצוא את השירות הנכון עבורם.

הנה הידע שלך:

🔹 זכויות:
- מאז 2015, טיפול נפשי מכוסה בחוק ביטוח בריאות ממלכתי
- כל תושב רשום בקופת חולים זכאי לטיפול מסובסד (~34 ₪ לרבעון)
- השירותים כוללים: ייעוץ פסיכיאטרי, פסיכותרפיה, אבחון פסיכולוגי, תרופות

🔹 קופות חולים (כללית, מכבי, מאוחדת, לאומית):
- סינון ראשוני → התאמת מטפל → טיפול שוטף (בדרך כלל שבועי)
- זמני המתנה: 2-8 שבועות בהתאם לאזור
- השתתפות עצמית: ~34 ₪ לרבעון

🔹 קווי חירום:
- ער"ן (1201): תמיכה רגשית 24/7
- סה"ר (sahar.org.il): צ'אט מקוון
- נט"ל (1-800-363-363): טראומה ו-PTSD
- קו לחיים (*2784): מניעת התאבדות 24/7
- עמח"א (02-5427127): ניצולי שואה
- מד"א (101), משטרה (100) לסכנת חיים מיידית

🔹 סוגי טיפול:
- CBT: הנפוץ ביותר, לחרדה ודיכאון
- EMDR: לטראומה ו-PTSD (הורחב לאחר 7.10)
- פסיכודינמי: לדפוסים חוזרים
- DBT: לוויסות רגשי
- טיפול קבוצתי, טיפול תרופתי, טיפול באמנות

🔹 עלויות פרטי:
- פסיכולוג: 300-600 ₪ | פסיכיאטר: 500-900 ₪
- עו"ס קליני: 200-450 ₪ | מרפאת אוניברסיטה: 150-250 ₪
- אונליין: 200-400 ₪

🔹 זכויות בעבודה:
- 1.5 ימי מחלה בחודש (18 בשנה) - גם למצב נפשי
- איסור אפליה על בסיס מצב נפשי
- מעסיק לא יכול לדרוש פרטי אבחנה
- תוכניות EAP: 3-6 מפגשים חינמיים

🔹 PTSD:
- ביטוח לאומי מכיר ב-PTSD כמוגבלות
- נט"ל, קרן OneFamily, מרכזי חוסן

הנחיות:
1. ענה תמיד בעברית
2. היה אמפתי, חם ומקצועי
3. הפנה לקווי חירום כשיש צורך דחוף
4. תן מידע מעשי וספציפי
5. הבהר שאתה לא מחליף טיפול מקצועי
6. אם מישהו בסכנה - הפנה מיד ל-101 או *2784
7. היה רגיש לקונטקסט הישראלי (צבא, מילואים, מצב ביטחוני, שואה)
"""

# =================================================================
# פונקציות הנווט
# =================================================================

def get_navigator_main_menu():
    """תפריט ראשי של הנווט"""
    keyboard = [
        [InlineKeyboardButton("📞 קווי חירום ותמיכה", callback_data="mh_hotlines")],
        [InlineKeyboardButton("🏥 איך מתחילים טיפול בקופה?", callback_data="mh_kupat_cholim")],
        [InlineKeyboardButton("💊 סוגי טיפולים", callback_data="mh_therapy_types")],
        [InlineKeyboardButton("💰 עלויות טיפול", callback_data="mh_costs")],
        [InlineKeyboardButton("🏢 זכויות בעבודה", callback_data="mh_workplace")],
        [InlineKeyboardButton("🎗️ PTSD וטראומה", callback_data="mh_ptsd")],
        [InlineKeyboardButton("🤖 שאל אותי שאלה חופשית", callback_data="mh_ask_ai")],
        [InlineKeyboardButton("🏠 חזרה לתפריט הראשי", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(keyboard)


def format_hotlines_message():
    """עיצוב הודעת קווי חירום"""
    lines = ["📞 *קווי חירום ותמיכה רגשית בישראל*\n"]
    for key, info in CRISIS_HOTLINES.items():
        lines.append(f"🔹 *{info['name']}*")
        lines.append(f"   📱 {info['number']}")
        lines.append(f"   🕐 {info['hours']}")
        lines.append(f"   {info['description']}")
        if 'languages' in info:
            lines.append(f"   🌐 {info['languages']}")
        lines.append("")
    lines.append("💙 השיחות אנונימיות וחינמיות. לא חייבים להיות במשבר כדי להתקשר.")
    return "\n".join(lines)


def format_kupat_cholim_message():
    """עיצוב הודעת מידע על קופות חולים"""
    return """
🏥 *איך מתחילים טיפול נפשי דרך קופת החולים?*

📌 *שלב 1: פנייה*
התקשר/י למחלקת בריאות הנפש של הקופה שלך:
• כללית | מכבי | מאוחדת | לאומית

📌 *שלב 2: סינון ראשוני*
שיחת הערכה קצרה (בד"כ טלפונית) לקביעת דחיפות ומסלול

📌 *שלב 3: התאמת מטפל*
הקופה תתאים לך מטפל/ת בהתאם לצורך

📌 *שלב 4: התחלת טיפול*
מפגשים שבועיים, בדרך כלל 12-20 מפגשים

💰 *עלות:* ~34 ₪ לרבעון (השתתפות עצמית מסובסדת)
⏰ *זמני המתנה:* 2-8 שבועות בהתאם לאזור

💡 *טיפים:*
• אם ההמתנה ארוכה, בקש/י הפניה לביטוח המשלים
• אפשר לבקש החלפת מטפל אם לא מתאים
• אפשר לשלב טיפול תרופתי ופסיכותרפיה
• לא צריך הפניה מרופא המשפחה (מאז הרפורמה)
"""


def format_therapy_types_menu():
    """תפריט סוגי טיפולים"""
    keyboard = []
    for key, info in THERAPY_TYPES.items():
        keyboard.append([InlineKeyboardButton(info['name'], callback_data=f"mh_therapy_{key}")])
    keyboard.append([InlineKeyboardButton("🔙 חזור", callback_data="mh_main")])
    return InlineKeyboardMarkup(keyboard)


def format_therapy_detail(therapy_key):
    """עיצוב פרטי סוג טיפול"""
    info = THERAPY_TYPES.get(therapy_key)
    if not info:
        return "סוג טיפול לא נמצא."
    return f"""
💊 *{info['name']}*

📝 {info['description']}

✅ *מתאים ל:* {info['good_for']}
⏱️ *משך:* {info['duration']}
🏥 *זמינות:* {info['availability']}
"""


def format_costs_message():
    """עיצוב הודעת עלויות"""
    lines = ["💰 *עלויות טיפול נפשי בישראל*\n"]
    for key, info in THERAPY_COSTS.items():
        lines.append(f"🔹 *{info['name']}*")
        lines.append(f"   💰 {info['cost']}")
        lines.append(f"   ⏰ המתנה: {info['wait_time']}")
        lines.append(f"   📝 {info['notes']}")
        lines.append("")
    lines.append("💡 *טיפ:* בדוק/בדקי אם יש לך ביטוח משלים - הרבה ביטוחים מציעים החזר חלקי על טיפולים פרטיים.")
    return "\n".join(lines)


def format_cost_estimate(therapy_type, sessions_per_month):
    """חישוב הערכת עלות"""
    cost_data = THERAPY_COSTS.get(therapy_type)
    if not cost_data:
        return None

    cost_str = cost_data['cost']
    # ניסיון לחלץ טווח מחירים
    import re
    numbers = re.findall(r'\d+', cost_str.replace(',', ''))
    if len(numbers) >= 2:
        low = int(numbers[0])
        high = int(numbers[1])
        monthly_low = low * sessions_per_month
        monthly_high = high * sessions_per_month
        annual_low = monthly_low * 12
        annual_high = monthly_high * 12
        return f"""
💰 *הערכת עלות: {cost_data['name']}*

📊 *{sessions_per_month} מפגשים בחודש:*
• חודשי: {monthly_low:,}-{monthly_high:,} ₪
• שנתי: {annual_low:,}-{annual_high:,} ₪

📝 {cost_data['notes']}
"""
    elif len(numbers) == 1:
        cost = int(numbers[0])
        monthly = cost * sessions_per_month
        annual = monthly * 12
        return f"""
💰 *הערכת עלות: {cost_data['name']}*

📊 *{sessions_per_month} מפגשים בחודש:*
• חודשי: ~{monthly:,} ₪
• שנתי: ~{annual:,} ₪

📝 {cost_data['notes']}
"""
    return None


# =================================================================
# Handler Functions
# =================================================================

async def start_navigator(query, context):
    """התחלת הנווט מהתפריט הראשי"""
    message = """
🧠 *נווט בריאות הנפש - ישראל*

ברוכים הבאים! כאן תמצאו מידע מקיף על שירותי בריאות הנפש בישראל.

אני יכול לעזור לכם עם:
• מציאת קווי חירום ותמיכה
• הבנת הזכויות שלכם לטיפול נפשי
• מידע על סוגי טיפולים
• הערכת עלויות
• זכויות בעבודה
• משאבי PTSD וטראומה

⚠️ *שימו לב:* אני כלי מידע בלבד ולא מחליף ייעוץ מקצועי.
במצב חירום התקשרו ל-1201 (ער\"ן) או *2784 (קו לחיים).

בחרו נושא:
"""
    await query.edit_message_text(
        text=message,
        reply_markup=get_navigator_main_menu(),
        parse_mode='Markdown'
    )


async def handle_navigator_callback(query, context, data, gemini_api_key):
    """טיפול בלחיצות כפתור של הנווט"""
    back_to_nav = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 חזור לנווט", callback_data="mh_main")],
        [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
    ])

    if data == "mh_main":
        await start_navigator(query, context)

    elif data == "mh_hotlines":
        await query.edit_message_text(
            text=format_hotlines_message(),
            reply_markup=back_to_nav,
            parse_mode='Markdown'
        )

    elif data == "mh_kupat_cholim":
        await query.edit_message_text(
            text=format_kupat_cholim_message(),
            reply_markup=back_to_nav,
            parse_mode='Markdown'
        )

    elif data == "mh_therapy_types":
        await query.edit_message_text(
            text="💊 *סוגי טיפולים נפשיים בישראל*\n\nבחר/י סוג טיפול לפרטים נוספים:",
            reply_markup=format_therapy_types_menu(),
            parse_mode='Markdown'
        )

    elif data.startswith("mh_therapy_"):
        therapy_key = data.replace("mh_therapy_", "")
        detail = format_therapy_detail(therapy_key)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 חזור לסוגי טיפולים", callback_data="mh_therapy_types")],
            [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
        ])
        await query.edit_message_text(
            text=detail,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    elif data == "mh_costs":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 חזור לנווט", callback_data="mh_main")],
            [InlineKeyboardButton("🏠 תפריט ראשי", callback_data="main_menu")]
        ])
        await query.edit_message_text(
            text=format_costs_message(),
            reply_markup=keyboard,
            parse_mode='Markdown'
        )

    elif data == "mh_workplace":
        await query.edit_message_text(
            text=WORKPLACE_RIGHTS,
            reply_markup=back_to_nav,
            parse_mode='Markdown'
        )

    elif data == "mh_ptsd":
        await query.edit_message_text(
            text=PTSD_RESOURCES,
            reply_markup=back_to_nav,
            parse_mode='Markdown'
        )

    elif data == "mh_ask_ai":
        if not gemini_api_key:
            await query.edit_message_text(
                text="שירות ה-AI אינו זמין כרגע. נסה שוב מאוחר יותר.",
                reply_markup=back_to_nav
            )
            return False

        # אתחול מודל Gemini לשיחת ניווט
        context.user_data['mh_navigator_model'] = genai.GenerativeModel('gemini-1.5-flash')
        opening = (
            "🤖 *סוכן ניווט בריאות הנפש*\n\n"
            "שאל/י אותי כל שאלה על בריאות הנפש בישראל:\n"
            "• זכויות, טיפולים, עלויות\n"
            "• קופות חולים, ביטוח משלים\n"
            "• קווי חירום ומשאבים\n"
            "• PTSD, חרדה, דיכאון\n\n"
            "לסיום השיחה שלח/י /end_navigator"
        )
        context.user_data['mh_chat_history'] = [
            {'role': 'user', 'parts': [NAVIGATOR_SYSTEM_PROMPT]},
            {'role': 'model', 'parts': [opening]}
        ]
        await query.edit_message_text(text=opening, parse_mode='Markdown')
        return True  # signals ConversationHandler to enter MH_ACTIVE state

    return False


async def handle_navigator_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """טיפול בהודעות חופשיות בשיחת AI של הנווט"""
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
        chat = model.start_chat(history=context.user_data.get('mh_chat_history', []))
        response = await chat.send_message_async(user_message)
        bot_response = response.text

        context.user_data['mh_chat_history'].append({'role': 'user', 'parts': [user_message]})
        context.user_data['mh_chat_history'].append({'role': 'model', 'parts': [bot_response]})

        await update.message.reply_text(bot_response)
    except Exception as e:
        logger.error(f"Navigator AI error: {e}")
        await update.message.reply_text(
            "מצטער, קרתה שגיאה. נסה שוב או חזור לתפריט עם /end_navigator"
        )

    return MH_ACTIVE


async def end_navigator_chat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """סיום שיחת AI של הנווט"""
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


def create_navigator_conversation(main_menu_regex):
    """יצירת ConversationHandler לשיחת AI של הנווט"""

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

    async def entry_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
        """Entry point: user clicked 'start_mh_ai' callback"""
        query = update.callback_query
        await query.answer()

        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            await query.edit_message_text("שירות ה-AI אינו זמין כרגע.")
            return ConversationHandler.END

        context.user_data['mh_navigator_model'] = genai.GenerativeModel('gemini-1.5-flash')
        opening = (
            "🤖 סוכן ניווט בריאות הנפש\n\n"
            "שאל/י אותי כל שאלה על בריאות הנפש בישראל:\n"
            "• זכויות, טיפולים, עלויות\n"
            "• קופות חולים, ביטוח משלים\n"
            "• קווי חירום ומשאבים\n"
            "• PTSD, חרדה, דיכאון\n\n"
            "לסיום השיחה שלח/י /end_navigator"
        )
        context.user_data['mh_chat_history'] = [
            {'role': 'user', 'parts': [NAVIGATOR_SYSTEM_PROMPT]},
            {'role': 'model', 'parts': [opening]}
        ]
        await query.edit_message_text(text=opening)
        return MH_ACTIVE

    import os

    return ConversationHandler(
        entry_points=[CallbackQueryHandler(entry_from_callback, pattern="^mh_ask_ai$")],
        states={
            MH_ACTIVE: [
                CommandHandler("end_navigator", end_navigator_chat),
                CallbackQueryHandler(perform_cancel, pattern="^cancel_mh_conversation$"),
                CallbackQueryHandler(perform_continue, pattern="^continue_mh_conversation$"),
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
