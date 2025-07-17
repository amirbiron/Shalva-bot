# panic_module.py
from telegram import (
    Update,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.ext import (
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
)
import asyncio
from datetime import datetime

# מצבי השיחה - נשאר אותו הדבר
ASK_BREATH, BREATHING, ASK_WASH, ASK_SCALE, OFFER_EXTRA, EXEC_EXTRA = range(6)

# טכניקות נוספות - נשאר אותו הדבר
EXTRA_TECHNIQUES = {
    "count": ("🔹 ספירה לאחור מ-100 בקפיצות של 7", "נתחיל: 100… 93… 86… בהצלחה!"),
    "press": ("🔸 לחץ על כף היד בין האגודל לאצבע", "לחץ על הנקודה חצי דקה, ואז לחץ '✅ ביצעתי'"),
    "move": ("🚶 קום וזוז קצת – תזוזה משחררת מתח", "קום לזוז דקה-שתיים ואז לחץ '✅ ביצעתי'"),
    "drink": ("💧 שתה מים קרים לאט לאט", "שתה מים בלגימות קטנות ולחץ '✅ ביצעתי'"),
}

# ──────────────────────────────────────────────────────────────────────
# 1. כניסה - ללא שינוי
async def panic_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [[
        InlineKeyboardButton("✅ כן", callback_data="yes_breath"),
        InlineKeyboardButton("⛔️ לא, תודה", callback_data="no_breath"),
    ]]
    # ⭐ שינוי קטן: הוספת הנחיה ליציאה
    await update.message.reply_text(
        "אני איתך.\n"
        "האם תרצה שננשום יחד בקצב 4-4-6?\n\n"
        "(בכל שלב, אפשר לחזור לתפריט הראשי עם /start)",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_BREATH

# 2. החלטה על נשימה
async def decide_breath(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "yes_breath":
        await query.edit_message_text("מתחילים לנשום יחד…")
        # ⭐ קריאה לפונקציית הנשימה, והפונקציה הזו אחראית על המעבר למצב הבא
        asyncio.create_task(breathing_cycle(query, context))
        return BREATHING # ⭐ מעבר למצב המתנה לתגובה אחרי הנשימה

    # אם סירב – מציעים שטיפת פנים
    await query.edit_message_text(
        "אני מציע שתלך לשטוף פנים במים קרים.\n"
        "כשתסיים לחץ על '✅ שטפתי פנים'.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ שטפתי פנים", callback_data="face_done")]]),
    )
    return ASK_WASH

# 2א. רצף נשימה - ללא שינוי
async def breathing_cycle(query, context):
    chat_id = query.message.chat_id
    bot = context.bot
    for _ in range(3):
        await bot.send_message(chat_id, "שאיפה… 4")
        await asyncio.sleep(4)
        await bot.send_message(chat_id, "החזק… 4")
        await asyncio.sleep(4)
        await bot.send_message(chat_id, "נשיפה… 6")
        await asyncio.sleep(6)
    await ask_scale_generic(bot, chat_id)

# ⭐ 2ב. פונקציה חדשה וברורה לטיפול בשטיפת פנים
async def face_washed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.delete_message() # מחיקת ההודעה הקודמת
    await ask_scale_generic(query.bot, query.message.chat_id)
    return ASK_SCALE # ⭐ מעבר למצב דירוג

# פונקציית עזר לדירוג - ללא שינוי
async def ask_scale_generic(bot, chat_id):
    scale_kb = [[InlineKeyboardButton(str(i), callback_data=f"scale_{i}") for i in range(0, 11)]]
    await bot.send_message(
        chat_id, "ואיך עכשיו, החרדה ירדה?\nבחר מספר:",
        reply_markup=InlineKeyboardMarkup(scale_kb)
    )

# 3. דירוג ראשון - ללא שינוי מהותי
async def got_first_scale(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    new_level = int(query.data.split("_")[1])
    context.user_data["level_start"] = new_level
    context.user_data["level_now"] = new_level
    context.user_data["attempts"] = 0
    context.user_data["history"] = [(datetime.utcnow(), new_level)]
    await query.answer()

    if new_level <= 3:
        await query.edit_message_text("נפלא! אתה כבר ברמת חרדה נמוכה. אני כאן אם תצטרך.")
        return ConversationHandler.END

    await offer_extra(query, context)
    return OFFER_EXTRA

# 4. הצעת טכניקה נוספת - ללא שינוי
async def offer_extra(query, context) -> None:
    buttons = [[InlineKeyboardButton(text, callback_data=f"extra_{key}")] for key, (text, _) in EXTRA_TECHNIQUES.items()]
    await query.edit_message_text(
        "אני מציע שננסה עוד טכניקה קצרה. איזו מהאפשרויות הבאות תעדיף?",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

# 5. התחלת טכניקה - ללא שינוי
async def start_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    key = query.data.split("_")[1]
    _, intro = EXTRA_TECHNIQUES[key]
    await query.edit_message_text(
        f"{intro}\nכשתסיים לחץ '✅ ביצעתי'",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ ביצעתי", callback_data="done_extra")]])
    )
    return EXEC_EXTRA

# 6. לאחר ביצוע טכניקה - ללא שינוי
async def extra_done(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.callback_query.answer()
    await update.callback_query.delete_message()
    await ask_scale_generic(update.callback_query.bot, update.callback_query.message.chat_id)
    return ASK_SCALE

# 7. טיפול בדירוגים חוזרים - ללא שינוי מהותי
async def handle_scale_again(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    new_level = int(query.data.split("_")[1])
    old_level = context.user_data.get("level_now", new_level)
    context.user_data["level_now"] = new_level
    context.user_data["history"].append((datetime.utcnow(), new_level))
    await query.answer()

    if new_level <= 3 or old_level - new_level >= 2:
        await query.edit_message_text(
            "כל הכבוד! רואים ירידה יפה בחרדה.\nמרגיש מספיק רגוע או שתרצה עוד תרגיל?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ מספיק לי", callback_data="enough"),
                InlineKeyboardButton("🔄 עוד תרגיל", callback_data="more_extra"),
            ]])
        )
        return OFFER_EXTRA

    context.user_data["attempts"] += 1
    if context.user_data["attempts"] >= 2:
        await query.edit_message_text(
            "נגמרו לי ההצעות במאגר, אבל אני מציע ללחוץ על 'זקוק לאוזן קשבת?' ולשוחח עם סוכן AI. בהצלחה 🩵"
        )
        return ConversationHandler.END

    await offer_extra(query, context)
    return OFFER_EXTRA

# 8. בחירה אחרונה - ללא שינוי
async def extra_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "enough":
        await query.edit_message_text("שמחתי לעזור. אני כאן תמיד כשתצטרך 💙")
        return ConversationHandler.END
    await offer_extra(query, context)
    return OFFER_EXTRA

# ──────────────────────────────────────────────────────────────────────
# ⭐ יצירת ה־ConversationHandler - גרסה משופרת
def create_panic_conversation_handler(start_command_func):
    return ConversationHandler(
        entry_points=[CommandHandler("panic", panic_entry)],
        states={
            ASK_BREATH: [CallbackQueryHandler(decide_breath, pattern="^(yes_breath|no_breath)$")],
            BREATHING: [CallbackQueryHandler(got_first_scale, pattern="^scale_\\d+$")],
            ASK_WASH: [CallbackQueryHandler(face_washed, pattern="^face_done$")],
            ASK_SCALE: [CallbackQueryHandler(handle_scale_again, pattern="^scale_\\d+$")],
            OFFER_EXTRA: [
                CallbackQueryHandler(start_extra, pattern="^extra_"),
                CallbackQueryHandler(extra_choice, pattern="^(enough|more_extra)$"),
            ],
            EXEC_EXTRA: [CallbackQueryHandler(extra_done, pattern="^done_extra$")],
        },
        fallbacks=[CommandHandler("start", start_command_func)], # ⭐ שימוש בפונקציית ה-start מהקובץ הראשי
        name="panic_conv",
        per_user=True,  # ⭐ הוספה
        per_chat=True,  # ⭐ הוספה
    )
