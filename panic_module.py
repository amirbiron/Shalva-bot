 
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

# מצבי השיחה
ASK_BREATH, BREATHING, ASK_WASH, ASK_SCALE, OFFER_EXTRA, EXEC_EXTRA = range(6)

# טכניקות נוספות – מזהה: (טקסט תצוגה, הודעת התחלה)
EXTRA_TECHNIQUES = {
    "count": (
        "🔹 ספירה לאחור מ-100 בקפיצות של 7",
        "נתחיל: 100… 93… 86… בהצלחה!",
    ),
    "press": (
        "🔸 לחץ על כף היד בין האגודל לאצבע",
        "לחץ על הנקודה חצי דקה, ואז לחץ '✅ ביצעתי'",
    ),
    "move": (
        "🚶 קום וזוז קצת – תזוזה משחררת מתח",
        "קום לזוז דקה-שתיים ואז לחץ '✅ ביצעתי'",
    ),
    "drink": (
        "💧 שתה מים קרים לאט לאט",
        "שתה מים בלגימות קטנות ולחץ '✅ ביצעתי'",
    ),
}

# ──────────────────────────────────────────────────────────────────────
# 1. כניסה מיידית במצוקה
async def panic_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [
            InlineKeyboardButton("✅ כן", callback_data="yes_breath"),
            InlineKeyboardButton("⛔️ לא, תודה", callback_data="no_breath"),
        ]
    ]
    await update.message.reply_text(
        "אני איתך.\n"
        "האם תרצה שננשום יחד בקצב 4-4-6?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return ASK_BREATH


# 2. נשימה או דילוג אל שטיפת פנים
async def decide_breath(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "yes_breath":
        await query.edit_message_text("מתחילים לנשום יחד…")
        asyncio.create_task(breathing_cycle(query, context))
        return BREATHING
    # אם סירב – מציעים שטיפת פנים
    await query.edit_message_text(
        "אני מציע שתלך לשטוף פנים במים קרים.\n"
        "כשתסיים לחץ על '✅ שטפתי פנים'. אם לא מתאים – נמצא פתרון אחר 🙂",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅ שטפתי פנים", callback_data="face_done")]]
        ),
    )
    return ASK_WASH


# 2א. רצף נשימה – 3 מחזורים
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
    # לאחר הנשימה – שאל דירוג
    await ask_scale_generic(bot, chat_id)
    return


# פונקציית עזר – שליחת שאלת דירוג
async def ask_scale_generic(bot, chat_id):
    scale_kb = [
        [InlineKeyboardButton(str(i), callback_data=f"scale_{i}") for i in range(0, 11)]
    ]
    await bot.send_message(
        chat_id,
        "ואיך עכשיו, החרדה ירדה?\nבחר מספר:",
        reply_markup=InlineKeyboardMarkup(scale_kb),
    )


# 3. דירוג ראשון אחרי נשימה או שטיפה
async def got_first_scale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    new_level = int(update.callback_query.data.split("_")[1])
    context.user_data["level_start"] = new_level
    context.user_data["level_now"] = new_level
    context.user_data["attempts"] = 0
    context.user_data["history"] = [(datetime.utcnow(), new_level)]
    await update.callback_query.answer()

    if new_level <= 3:
        await update.callback_query.edit_message_text(
            "נפלא! אתה כבר ברמת חרדה נמוכה. אני כאן אם תצטרך."
        )
        return ConversationHandler.END

    await offer_extra(update.callback_query, context)
    return OFFER_EXTRA


# 4. הצעת טכניקה נוספת (4 אפשרויות)
async def offer_extra(query, context):
    buttons = [
        [InlineKeyboardButton(text, callback_data=f"extra_{key}")]
        for key, (text, _) in EXTRA_TECHNIQUES.items()
    ]
    await query.edit_message_text(
        "איזו מהאפשרויות הבאות תרצה לנסות עכשיו?",
        reply_markup=InlineKeyboardMarkup(buttons),
    )
    return


# 5. התחלת הטכניקה שנבחרה
async def start_extra(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_")[1]
    display, intro = EXTRA_TECHNIQUES[key]
    context.user_data["current_extra"] = key
    await query.edit_message_text(
        f"{intro}\n"
        "כשתסיים לחץ '✅ ביצעתי'",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("✅ ביצעתי", callback_data="done_extra")]]
        ),
    )
    return EXEC_EXTRA


# 6. לאחר ביצוע הטכניקה – שאל דירוג מחדש
async def extra_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await ask_scale_generic(update.callback_query.bot, update.callback_query.message.chat_id)
    return ASK_SCALE


# 7. טיפול בדירוגים חוזרים ולאחר ניסיונות נוספים
async def handle_scale_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    new_level = int(query.data.split("_")[1])
    old_level = context.user_data.get("level_now", new_level)
    context.user_data["level_now"] = new_level
    context.user_data["history"].append((datetime.utcnow(), new_level))
    await query.answer()

    if new_level <= 3 or old_level - new_level >= 2:
        await query.edit_message_text(
            "כל הכבוד! רואים ירידה יפה בחרדה.\n"
            "מרגיש מספיק רגוע או שתרצה עוד תרגיל?",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ מספיק לי", callback_data="enough"),
                        InlineKeyboardButton("🔄 עוד תרגיל", callback_data="more_extra"),
                    ]
                ]
            ),
        )
        return OFFER_EXTRA

    # לא השתפר מספיק
    context.user_data["attempts"] += 1
    if context.user_data["attempts"] >= 2:
        await query.edit_message_text(
            "נגמרו לי ההצעות במאגר, אבל אני מציע ללחוץ על כפתור "
            "'זקוק לאוזן קשבת?' ולשוחח עם סוכן AI אדיב ואמפתי, זה עשוי לעזור.\n"
            "בהצלחה 🩵"
        )
        return ConversationHandler.END

    # להציע טכניקה נוספת
    await offer_extra(query, context)
    return OFFER_EXTRA


# 8. ממשיך או מסיים בהתאם לבחירת המשתמש
async def extra_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "enough":
        await query.edit_message_text("שמחתי לעזור. אני כאן תמיד כשתצטרך 💙")
        return ConversationHandler.END
    # עוד תרגיל
    await offer_extra(query, context)
    return OFFER_EXTRA


# ──────────────────────────────────────────────────────────────────────
# יצירת ה־ConversationHandler
panic_conv = ConversationHandler(
    entry_points=[CommandHandler("panic", panic_entry)],
    states={
        ASK_BREATH: [
            CallbackQueryHandler(decide_breath, pattern="^(yes_breath|no_breath)$")
        ],
        BREATHING: [
            CallbackQueryHandler(got_first_scale, pattern="^scale_\\d+$")
        ],
        ASK_WASH: [
            CallbackQueryHandler(
                lambda u, c: ask_scale_generic(
                    u.callback_query.bot, u.callback_query.message.chat_id
                )
                or setattr(c.user_data, "washed", True)
                or ConversationHandler.END,
                pattern="^face_done$",
            ),
            CallbackQueryHandler(got_first_scale, pattern="^scale_\\d+$"),
        ],
        ASK_SCALE: [
            CallbackQueryHandler(handle_scale_again, pattern="^scale_\\d+$")
        ],
        OFFER_EXTRA: [
            CallbackQueryHandler(start_extra, pattern="^extra_"),
            CallbackQueryHandler(extra_choice, pattern="^(enough|more_extra)$"),
        ],
        EXEC_EXTRA: [
            CallbackQueryHandler(extra_done, pattern="^done_extra$"),
            CallbackQueryHandler(got_first_scale, pattern="^scale_\\d+$"),
        ],
    },
    fallbacks=[],
    name="panic_conv",
)
