"""
Shalva Bot — Web Application
Flask backend serving the SPA and providing API endpoints.
"""

import os
import json
import logging
from datetime import datetime, timedelta
from functools import wraps

import pymongo
import google.generativeai as genai
from flask import Flask, request, jsonify, send_from_directory, session
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MONGO_URI = os.getenv("MONGO_URI")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "shalva-webapp-secret-key-change-me")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.secret_key = SECRET_KEY

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
client = pymongo.MongoClient(MONGO_URI)
db = client.get_database("ShalvaBotDB")
reports_collection = db.get_collection("anxiety_reports")
venting_collection = db.get_collection("free_venting")
settings_collection = db.get_collection("user_settings")
users_collection = db.get_collection("users")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# In-memory chat sessions (keyed by session id)
chat_sessions = {}


def get_user_id():
    """Get or create a user identifier from the session."""
    if "user_id" not in session:
        # For web users, generate a unique numeric-ish ID based on session
        import hashlib
        sid = session.sid if hasattr(session, "sid") else str(id(session))
        session["user_id"] = int(hashlib.sha256(sid.encode()).hexdigest()[:12], 16)
    return session["user_id"]


def ensure_user_settings(user_id: int) -> dict:
    settings = settings_collection.find_one({"user_id": user_id})
    if not settings:
        default_settings = {
            "user_id": user_id,
            "daily_reminder": False,
            "reminder_time": "20:00",
            "preferred_report_type": "quick",
            "notifications_enabled": True,
            "language": "he",
        }
        settings_collection.insert_one(default_settings)
        return default_settings
    return settings


def get_immediate_recommendation(anxiety_level):
    if anxiety_level >= 8:
        return "🚨 רמת חרדה גבוהה! נסה טכניקת נשימה 4-4-6 עכשיו: שאף 4 שניות, עצור 4, נשוף 6."
    elif anxiety_level >= 6:
        return "⚠️ חרדה ברמה בינונית. נסה לזהות מה גורם לזה ולהשתמש בטכניקת 5-4-3-2-1."
    elif anxiety_level >= 4:
        return "💛 חרדה קלה. נשימה עמוקה והזכר לעצמך שזה יעבור."
    else:
        return "💚 רמת חרדה נמוכה. נהדר שאתה מודע לרגשות שלך!"


LOCATION_OPTIONS = ["🏠 בית", "🏢 עבודה", "🚗 רחוב", "🛒 קניון", "🚌 תחבורה ציבורית", "📍 אחר"]
PEOPLE_OPTIONS = ["👤 לבד", "👥 עם חברים", "👔 קולגות", "👨‍👩‍👧‍👦 משפחה", "👥 זרים", "👥 אחר"]
WEATHER_OPTIONS = ["☀️ שמש", "🌧️ גשם", "☁️ מעונן", "🔥 חם", "❄️ קר", "🌤️ אחר"]


# Crisis detection (from mental_health_navigator.py)
import re

CRISIS_KEYWORDS = [
    r"להתאבד", r"התאבדות", r"לגמור עם הכל", r"לסיים את החיים",
    r"לא רוצה לחיות", r"רוצה למות", r"אין טעם לחיות",
    r"לפגוע בעצמי", r"פוגע בעצמי", r"חותך את עצמי",
    r"אובדני", r"מחשבות אובדניות",
]
EMERGENCY_KEYWORDS = [
    r"לא נושם", r"לא מגיב", r"איבד הכרה",
    r"דימום חמור", r"מכה אותי", r"אלימות",
    r"התקף לב", r"כאבים בחזה",
]

CRISIS_PATTERN = re.compile("|".join(CRISIS_KEYWORDS), re.IGNORECASE)
EMERGENCY_PATTERN = re.compile("|".join(EMERGENCY_KEYWORDS), re.IGNORECASE)

CRISIS_RESPONSE = (
    "🚨 אני שומע אותך, ומה שאתה מרגיש עכשיו זה אמיתי וכבד.\n\n"
    "אתה לא לבד. יש אנשים מקצועיים שיכולים לעזור לך עכשיו:\n\n"
    "📞 קו לחיים (מניעת התאבדות): *2784 - זמין 24/7\n"
    "📞 ער\"ן (עזרה ראשונה נפשית): 1201 - זמין 24/7\n"
    "💬 סה\"ר (צ'אט מקוון): sahar.org.il - זמין 24/7\n"
    "🚑 מד\"א (סכנה מיידית): 101\n\n"
    "השיחות אנונימיות, חינמיות, ובלי שיפוט."
)

EMERGENCY_RESPONSE = (
    "🚨 זה נשמע כמו מצב שדורש עזרה מיידית.\n\n"
    "🚑 חירום רפואי: 101 מד\"א\n"
    "👮 אלימות / סכנה: 100 משטרה\n"
    "📱 לא בטוח/ה: 112\n\n"
    "📞 ער\"ן: 1201 (24/7)\n"
    "📞 קו לחיים: *2784 (24/7)"
)


EMPATHY_PROMPT = """אתה עוזר רגשי אישי, שפועל דרך אפליקציית ווב. משתמש פונה אליך כשהוא מרגיש לחץ, חרדה, או צורך באוזן קשבת. תפקידך: להגיב בחום, בטון רך, בגישה לא שיפוטית ומכילה. אתה לא מייעץ – אתה שם בשבילו. שמור על שפה אנושית, פשוטה ואכפתית. אם המשתמש שותק – עודד אותו בעדינות. המטרה שלך: להשרות רוגע, להקל על תחושת הבדידות, ולעזור לו להרגיש שמישהו איתו."""

NAVIGATOR_SYSTEM_PROMPT = """אתה סוכן AI מומחה בניווט מערכת בריאות הנפש בישראל.
תפקידך לעזור למשתמשים למצוא את השירות הנכון עבורם, לענות על שאלות, ולהנגיש מידע מעשי על בריאות הנפש בישראל.

מאגר הידע שלך כולל:
- רפורמת בריאות הנפש (2015) - טיפול מסובסד דרך קופות החולים
- גישה לטיפול דרך כללית, מכבי, מאוחדת, לאומית
- קווי חירום: ער"ן 1201, סה"ר sahar.org.il, נט"ל 1-800-363-363, קו לחיים *2784
- סוגי טיפולים: CBT, EMDR, פסיכודינמי, DBT, קבוצתי, תרופתי
- עלויות: קופה ~34₪/רבעון, פרטי 300-600₪, פסיכיאטר 500-900₪
- זכויות בעבודה: ימי מחלה, איסור אפליה, EAP
- PTSD ומשאבי טראומה כולל 7 באוקטובר

הנחיות: ענה בעברית, היה אמפתי ומעשי, תן מידע ספציפי, הפנה למשבר אם צריך, אל תאבחן."""


# ---------------------------------------------------------------------------
# SPA routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory("templates", "index.html")


# ---------------------------------------------------------------------------
# API: Auth / Session
# ---------------------------------------------------------------------------

@app.route("/api/session", methods=["POST"])
def create_session():
    """Create or resume a web session. Accepts optional display name."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "אורח")

    if "user_id" not in session:
        import hashlib, time
        raw = f"{name}-{time.time()}-{os.urandom(8).hex()}"
        session["user_id"] = int(hashlib.sha256(raw.encode()).hexdigest()[:12], 16)
        session["name"] = name

    user_id = session["user_id"]
    ensure_user_settings(user_id)

    return jsonify({"ok": True, "user_id": user_id, "name": session.get("name", name)})


# ---------------------------------------------------------------------------
# API: Reports
# ---------------------------------------------------------------------------

@app.route("/api/reports/quick", methods=["POST"])
def quick_report():
    data = request.get_json()
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    description = data.get("description", "")
    anxiety_level = int(data.get("anxiety_level", 5))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    reports_collection.insert_one({
        "user_id": user_id,
        "timestamp": timestamp,
        "anxiety_level": anxiety_level,
        "description": description,
        "report_type": "quick",
        "created_at": timestamp,
    })

    recommendation = get_immediate_recommendation(anxiety_level)
    return jsonify({"ok": True, "recommendation": recommendation, "anxiety_level": anxiety_level})


@app.route("/api/reports/full", methods=["POST"])
def full_report():
    data = request.get_json()
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    anxiety_level = int(data.get("anxiety_level", 5))

    reports_collection.insert_one({
        "user_id": user_id,
        "timestamp": timestamp,
        "anxiety_level": anxiety_level,
        "description": data.get("description", ""),
        "location": data.get("location", ""),
        "people_around": data.get("people_around", ""),
        "weather": data.get("weather", ""),
        "report_type": "full",
        "created_at": timestamp,
    })

    recommendation = get_immediate_recommendation(anxiety_level)
    return jsonify({"ok": True, "recommendation": recommendation, "anxiety_level": anxiety_level})


@app.route("/api/reports/options", methods=["GET"])
def report_options():
    return jsonify({
        "locations": LOCATION_OPTIONS,
        "people": PEOPLE_OPTIONS,
        "weather": WEATHER_OPTIONS,
    })


# ---------------------------------------------------------------------------
# API: Analytics
# ---------------------------------------------------------------------------

@app.route("/api/analytics", methods=["GET"])
def analytics():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    reports_raw = list(reports_collection.find(
        {"user_id": user_id},
        {"_id": 0, "anxiety_level": 1, "timestamp": 1, "location": 1,
         "people_around": 1, "weather": 1, "report_type": 1, "description": 1}
    ).sort("timestamp", -1).limit(30))

    if not reports_raw:
        return jsonify({"has_data": False})

    anxiety_levels = [r["anxiety_level"] for r in reports_raw]
    avg_anxiety = sum(anxiety_levels) / len(anxiety_levels)

    # Location breakdown
    from collections import Counter
    locations = [r.get("location") for r in reports_raw if r.get("location")]
    location_counter = Counter(locations)
    location_stats = []
    for loc, count in location_counter.most_common(5):
        loc_avg = sum(r["anxiety_level"] for r in reports_raw if r.get("location") == loc) / count
        location_stats.append({"location": loc, "count": count, "avg_anxiety": round(loc_avg, 1)})

    # People breakdown
    people = [r.get("people_around") for r in reports_raw if r.get("people_around")]
    people_counter = Counter(people)
    people_stats = []
    for p, count in people_counter.most_common(5):
        p_avg = sum(r["anxiety_level"] for r in reports_raw if r.get("people_around") == p) / count
        people_stats.append({"people": p, "count": count, "avg_anxiety": round(p_avg, 1)})

    # Report types
    quick_count = sum(1 for r in reports_raw if r.get("report_type") == "quick")
    full_count = sum(1 for r in reports_raw if r.get("report_type") == "full")

    # Trend
    trend = None
    if len(anxiety_levels) >= 7:
        recent_week = anxiety_levels[:7]
        prev_week = anxiety_levels[7:14] if len(anxiety_levels) > 7 else []
        if prev_week:
            change = sum(recent_week) / len(recent_week) - sum(prev_week) / len(prev_week)
            if change > 0.5:
                trend = {"direction": "up", "change": round(change, 1)}
            elif change < -0.5:
                trend = {"direction": "down", "change": round(change, 1)}
            else:
                trend = {"direction": "stable", "change": round(change, 1)}

    # Recent reports for chart
    chart_data = [{"timestamp": r["timestamp"], "level": r["anxiety_level"]} for r in reversed(reports_raw)]

    return jsonify({
        "has_data": True,
        "total_reports": len(reports_raw),
        "avg_anxiety": round(avg_anxiety, 1),
        "max_anxiety": max(anxiety_levels),
        "min_anxiety": min(anxiety_levels),
        "quick_reports": quick_count,
        "full_reports": full_count,
        "location_stats": location_stats,
        "people_stats": people_stats,
        "trend": trend,
        "chart_data": chart_data,
    })


# ---------------------------------------------------------------------------
# API: Venting
# ---------------------------------------------------------------------------

@app.route("/api/venting", methods=["POST"])
def venting():
    data = request.get_json()
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    content = data.get("content", "")
    save_for_analysis = data.get("save_for_analysis", False)

    venting_collection.insert_one({
        "user_id": user_id,
        "content": content,
        "save_for_analysis": save_for_analysis,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })

    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: AI Chat (Empathetic)
# ---------------------------------------------------------------------------

@app.route("/api/chat/start", methods=["POST"])
def chat_start():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401
    if not GEMINI_API_KEY:
        return jsonify({"error": "AI not available"}), 503

    model = genai.GenerativeModel("gemini-2.5-flash")
    opening = "אני כאן, איתך. מה יושב לך על הלב?"
    history = [
        {"role": "user", "parts": [EMPATHY_PROMPT]},
        {"role": "model", "parts": [opening]},
    ]
    chat_sessions[user_id] = {"model": model, "history": history, "type": "support"}
    return jsonify({"ok": True, "message": opening})


@app.route("/api/chat/message", methods=["POST"])
def chat_message():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    data = request.get_json()
    user_message = data.get("message", "")

    sess = chat_sessions.get(user_id)
    if not sess:
        return jsonify({"error": "no active chat"}), 400

    model = sess["model"]
    history = sess["history"]

    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(user_message)
        bot_response = response.text
        history.append({"role": "user", "parts": [user_message]})
        history.append({"role": "model", "parts": [bot_response]})
        return jsonify({"ok": True, "message": bot_response})
    except Exception as e:
        logger.error(f"Chat error: {e}")
        return jsonify({"error": "AI error"}), 500


@app.route("/api/chat/end", methods=["POST"])
def chat_end():
    user_id = session.get("user_id")
    if user_id and user_id in chat_sessions:
        del chat_sessions[user_id]
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: Mental Health Navigator
# ---------------------------------------------------------------------------

@app.route("/api/navigator/start", methods=["POST"])
def navigator_start():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401
    if not GEMINI_API_KEY:
        return jsonify({"error": "AI not available"}), 503

    model = genai.GenerativeModel("gemini-2.5-flash", system_instruction=NAVIGATOR_SYSTEM_PROMPT)
    opening = (
        "🧠 נווט בריאות הנפש - ישראל\n\n"
        "היי! אני סוכן AI שמתמחה בבריאות הנפש בישראל.\n"
        "אפשר לשאול אותי על זכויות, טיפולים, עלויות, קופות חולים, קווי חירום ועוד."
    )
    chat_sessions[f"nav_{user_id}"] = {"model": model, "history": [], "type": "navigator"}
    return jsonify({"ok": True, "message": opening})


@app.route("/api/navigator/message", methods=["POST"])
def navigator_message():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    data = request.get_json()
    user_message = data.get("message", "")

    # Crisis detection
    if CRISIS_PATTERN.search(user_message):
        return jsonify({"ok": True, "message": CRISIS_RESPONSE, "crisis": True})
    if EMERGENCY_PATTERN.search(user_message):
        return jsonify({"ok": True, "message": EMERGENCY_RESPONSE, "crisis": True})

    key = f"nav_{user_id}"
    sess = chat_sessions.get(key)
    if not sess:
        return jsonify({"error": "no active navigator session"}), 400

    model = sess["model"]
    history = sess["history"]

    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(user_message)
        bot_response = response.text
        history.append({"role": "user", "parts": [user_message]})
        history.append({"role": "model", "parts": [bot_response]})
        return jsonify({"ok": True, "message": bot_response})
    except Exception as e:
        logger.error(f"Navigator error: {e}")
        return jsonify({"error": "AI error"}), 500


@app.route("/api/navigator/end", methods=["POST"])
def navigator_end():
    user_id = session.get("user_id")
    key = f"nav_{user_id}"
    if key in chat_sessions:
        del chat_sessions[key]
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# API: Settings
# ---------------------------------------------------------------------------

@app.route("/api/settings", methods=["GET"])
def get_settings():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401
    settings = ensure_user_settings(user_id)
    settings.pop("_id", None)
    return jsonify(settings)


@app.route("/api/settings", methods=["POST"])
def update_settings():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401
    data = request.get_json()
    allowed = {"daily_reminder", "reminder_time", "preferred_report_type", "notifications_enabled"}
    update = {k: v for k, v in data.items() if k in allowed}
    if update:
        settings_collection.update_one({"user_id": user_id}, {"$set": update})
    return jsonify({"ok": True})


@app.route("/api/settings/export", methods=["GET"])
def export_data():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    reports = list(reports_collection.find(
        {"user_id": user_id},
        {"_id": 0, "timestamp": 1, "anxiety_level": 1, "description": 1,
         "location": 1, "people_around": 1, "weather": 1, "report_type": 1}
    ).sort("timestamp", -1))

    ventings = list(venting_collection.find(
        {"user_id": user_id, "save_for_analysis": True},
        {"_id": 0, "timestamp": 1, "content": 1}
    ).sort("timestamp", -1))

    export = {
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "anxiety_reports": reports,
        "free_ventings": ventings,
        "statistics": {
            "total_reports": len(reports),
            "total_ventings": len(ventings),
            "avg_anxiety": round(sum(r.get("anxiety_level", 0) for r in reports) / len(reports), 1) if reports else 0
        }
    }
    return jsonify(export)


@app.route("/api/settings/reset", methods=["POST"])
def reset_data():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "no session"}), 401

    reports_collection.delete_many({"user_id": user_id})
    venting_collection.delete_many({"user_id": user_id})
    settings_collection.delete_one({"user_id": user_id})
    ensure_user_settings(user_id)
    return jsonify({"ok": True})


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("WEBAPP_PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
