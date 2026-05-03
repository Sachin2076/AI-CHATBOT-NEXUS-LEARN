import os
import re
import json
import traceback
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv()

from flask import (
    Flask, render_template, jsonify,
    request, session, redirect, url_for,
    Response, stream_with_context,
)
from bson import ObjectId
from datetime import datetime, timezone, date
import requests

from db        import get_db, messages, planner, usage_logs, chat_sessions, \
                      practice_sets, quiz_results, motivations, srs_records
from srs       import update_srs, get_due_topics
from utils     import serial, require_auth
from extensions import socketio
from groups    import groups_bp
from interview import interview_bp
from llm       import ask_ollama, stream_ollama, check_ollama_status, \
                      build_adaptive_context

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")
socketio.init_app(app, cors_allowed_origins="*")
app.register_blueprint(groups_bp)
app.register_blueprint(interview_bp)

# ═════════════════════════════════════════════════════════════
#  RATE LIMITER  (in-memory, per user, sliding window)
#  20 chat messages per minute per user.
#  Resets automatically as timestamps age out.
# ═════════════════════════════════════════════════════════════
import time as _time

_rate_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT      = 20    # max requests
RATE_WINDOW     = 60    # seconds

def _check_rate_limit(user_id: str) -> bool:
    """Return True (allowed) or False (limit exceeded)."""
    now = _time.time()
    timestamps = _rate_store[user_id]
    # Drop timestamps outside the window
    _rate_store[user_id] = [t for t in timestamps if now - t < RATE_WINDOW]
    if len(_rate_store[user_id]) >= RATE_LIMIT:
        return False
    _rate_store[user_id].append(now)
    return True


# ═════════════════════════════════════════════════════════════
#  INPUT SANITISER
#  Strips HTML tags and control characters from user text
#  before it is stored in MongoDB or sent to the LLM.
# ═════════════════════════════════════════════════════════════
_HTML_TAG_RE  = re.compile(r"<[^>]{0,200}>")
_CTRL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
MESSAGE_MAX_LEN = 4000  # characters

def sanitise_input(text: str) -> str:
    """Strip HTML tags and control characters; truncate to safe length."""
    text = _HTML_TAG_RE.sub("", text)
    text = _CTRL_CHAR_RE.sub("", text)
    return text[:MESSAGE_MAX_LEN].strip()

try:
    get_db()
    print("✅  MongoDB connected")
except Exception as e:
    print(f"⚠️  MongoDB connection failed: {e}")


# ═════════════════════════════════════════════════════════════
#  CONTENT SECURITY POLICY
#  Allows Socket.IO CDN + inline styles. Removes CSP block on
#  onclick handlers in groups.html and other templates.
# ═════════════════════════════════════════════════════════════

@app.after_request
def set_csp(response):
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.socket.io; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: https://i.ytimg.com; "
        "connect-src 'self' ws: wss:;"
    )
    return response


# ═════════════════════════════════════════════════════════════
#  HELPERS
# ═════════════════════════════════════════════════════════════

def current_user_id():
    return session.get("user_id")

def today_str():
    return date.today().isoformat()

def log_activity(user_id):
    usage_logs().update_one(
        {"user_id": user_id, "date": today_str()},
        {"$inc":  {"message_count": 1},
         "$set":  {"active_day": True},
         "$setOnInsert": {"login_time": datetime.now(timezone.utc)}},
        upsert=True,
    )

def get_user_stats(user_id):
    total_msgs  = messages().count_documents({"user_id": user_id, "role": "user"})
    active_days = usage_logs().count_documents({"user_id": user_id, "active_day": True})
    task_count  = planner().count_documents({"user_id": user_id})
    return {"total_messages": total_msgs, "active_days": active_days, "task_count": task_count}


def get_performance_context(user_id: str) -> str:
    """
    Read the student's quiz_results and build an adaptive context string.
    Topics where avg score < 70% are flagged as weak areas; topics >= 80%
    are flagged as mastered. This string is injected into every LLM prompt
    so responses are personalised to each user's performance.
    """
    try:
        results = list(
            quiz_results().find({"user_id": user_id})
            .sort("submitted_at", -1)
            .limit(30)
        )
        if not results:
            return ""

        topic_scores: dict[str, list[int]] = {}
        for r in results:
            topic = r.get("topic", "").strip()
            score = r.get("score", 0)
            if topic:
                topic_scores.setdefault(topic, []).append(score)

        weak_topics = []
        topic_avgs  = {}
        for topic, scores in topic_scores.items():
            avg = round(sum(scores) / len(scores))
            topic_avgs[topic] = avg
            if avg < 70:
                weak_topics.append(f"{topic} ({avg}%)")

        ctx = build_adaptive_context(weak_topics, topic_avgs)

        due = get_due_topics(user_id, get_db())
        if due:
            ctx += f"\nTopics due for review today: {', '.join(due)}"
        return ctx
    except Exception:
        return ""


# ═════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ═════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if not current_user_id():
        return redirect(url_for("login_page"))
    return render_template("dashboard.html")

@app.route("/chat")
def chat_page():
    if not current_user_id():
        return redirect(url_for("login_page"))
    return render_template("chat.html")

@app.route("/planner")
def planner_page():
    if not current_user_id():
        return redirect(url_for("login_page"))
    return render_template("planner.html")

@app.route("/coding")
def coding_page():
    if not current_user_id():
        return redirect(url_for("login_page"))
    return render_template("practice.html")

@app.route("/motivation")
def motivation_page():
    if not current_user_id():
        return redirect(url_for("login_page"))
    return render_template("motivation.html")


# ═════════════════════════════════════════════════════════════
#  AUTH API
# ═════════════════════════════════════════════════════════════

from auth import register_user, login_user

@app.route("/api/register", methods=["POST"])
def api_register():
    data     = request.get_json() or {}
    name     = data.get("name",     "").strip()
    email    = data.get("email",    "").strip()
    password = data.get("password", "")

    if not name or not email or not password:
        return jsonify({"error": "All fields are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400

    try:
        user = register_user(name, email, password)
    except ValueError as e:
        return jsonify({"error": str(e)}), 409
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "Registration failed. Please try again."}), 500

    session["user_id"]    = str(user["_id"])
    session["user_name"]  = user["name"]
    session["user_email"] = user["email"]
    return jsonify({"success": True})


@app.route("/api/login", methods=["POST"])
def api_login():
    data     = request.get_json() or {}
    email    = data.get("email",    "").strip()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    user = login_user(email, password)
    if not user:
        return jsonify({"error": "Invalid email or password."}), 401

    session["user_id"]    = str(user["_id"])
    session["user_name"]  = user["name"]
    session["user_email"] = user["email"]

    usage_logs().update_one(
        {"user_id": str(user["_id"]), "date": today_str()},
        {"$set": {"active_day": True, "login_time": datetime.now(timezone.utc)},
         "$setOnInsert": {"message_count": 0}},
        upsert=True,
    )
    return jsonify({"success": True})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"success": True})


@app.route("/api/me")
def api_me():
    uid, err = require_auth()
    if err: return err
    try:
        stats = get_user_stats(uid)
    except Exception:
        stats = {"total_messages": 0, "active_days": 0, "task_count": 0}
    return jsonify({
        "user_id": uid,
        "name":    session.get("user_name",  "Student"),
        "email":   session.get("user_email", ""),
        "stats":   stats,
    })


# ═════════════════════════════════════════════════════════════
#  CHAT API
# ═════════════════════════════════════════════════════════════

HISTORY_WINDOW = 10


def _get_or_create_session(uid: str, session_id: str, first_message: str) -> str:
    if not session_id:
        now   = datetime.now(timezone.utc)
        title = first_message[:40] + ("…" if len(first_message) > 40 else "")
        doc   = {"user_id": uid, "title": title, "created_at": now, "updated_at": now}
        result = chat_sessions().insert_one(doc)
        return str(result.inserted_id)
    else:
        chat_sessions().update_one(
            {"_id": ObjectId(session_id), "user_id": uid},
            {"$set": {"updated_at": datetime.now(timezone.utc)}},
        )
        return session_id


def _fetch_history(uid: str, session_id: str) -> list:
    raw = list(
        messages().find(
            {"user_id": uid, "session_id": session_id},
            {"role": 1, "content": 1, "_id": 0},
        ).sort("timestamp", -1).limit(HISTORY_WINDOW)
    )
    return list(reversed(raw))


@app.route("/api/chat/sessions")
def api_chat_sessions():
    uid, err = require_auth()
    if err: return err
    sess = list(
        chat_sessions().find({"user_id": uid}).sort("created_at", -1).limit(30)
    )
    return jsonify({"sessions": [serial(s) for s in sess]})


@app.route("/api/chat/sessions", methods=["POST"])
def api_create_session():
    uid, err = require_auth()
    if err: return err
    data  = request.get_json() or {}
    title = data.get("title", "New Chat")
    now   = datetime.now(timezone.utc)
    doc   = {"user_id": uid, "title": title, "created_at": now, "updated_at": now}
    result = chat_sessions().insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"session": serial(doc)}), 201


@app.route("/api/chat/sessions/<session_id>", methods=["DELETE"])
def api_delete_session(session_id):
    uid, err = require_auth()
    if err: return err
    try:
        oid = ObjectId(session_id)
    except Exception:
        return jsonify({"error": "Invalid session ID."}), 400
    chat_sessions().delete_one({"_id": oid, "user_id": uid})
    messages().delete_many({"session_id": session_id, "user_id": uid})
    return jsonify({"success": True})


@app.route("/api/chat/sessions/<session_id>/rename", methods=["POST"])
def api_rename_session(session_id):
    uid, err = require_auth()
    if err: return err
    data  = request.get_json() or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "Title required."}), 400
    chat_sessions().update_one(
        {"_id": ObjectId(session_id), "user_id": uid},
        {"$set": {"title": title}},
    )
    return jsonify({"success": True})


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """
    SSE streaming endpoint. Tokens stream to the client as they arrive
    from Ollama, eliminating the blank wait on long responses.

    SSE event format:
      data: {"token": "..."}   — streamed token
      data: {"error": "..."}   — on failure
      data: {"done": true, "session_id": "..."}  — after last token
    """
    uid, err = require_auth()
    if err: return err

    if not _check_rate_limit(uid):
        return jsonify({"error": "Too many messages. Please wait a moment."}), 429

    data         = request.get_json() or {}
    user_message = sanitise_input(data.get("message", "").strip())
    session_id   = data.get("session_id", "")

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    session_id = _get_or_create_session(uid, session_id, user_message)
    history    = _fetch_history(uid, session_id)
    perf_ctx   = get_performance_context(uid)

    def generate():
        full_reply = []
        try:
            for token in stream_ollama(history, user_message, perf_ctx):
                full_reply.append(token)
                yield f"data: {json.dumps({'token': token})}\n\n"
        except RuntimeError as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return
        except Exception:
            print(traceback.format_exc())
            yield f"data: {json.dumps({'error': 'The AI model encountered an error.'})}\n\n"
            return

        complete_reply = "".join(full_reply)
        now = datetime.now(timezone.utc)
        messages().insert_many([
            {"user_id": uid, "session_id": session_id, "role": "user",
             "content": user_message, "timestamp": now},
            {"user_id": uid, "session_id": session_id, "role": "bot",
             "content": complete_reply, "timestamp": now},
        ])
        log_activity(uid)
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/chat", methods=["POST"])
def api_chat():
    uid, err = require_auth()
    if err: return err

    if not _check_rate_limit(uid):
        return jsonify({"error": "Too many messages. Please wait a moment."}), 429

    data         = request.get_json() or {}
    user_message = sanitise_input(data.get("message", "").strip())
    session_id   = data.get("session_id", "")

    if not user_message:
        return jsonify({"error": "Message cannot be empty."}), 400

    session_id = _get_or_create_session(uid, session_id, user_message)
    history    = _fetch_history(uid, session_id)
    perf_ctx   = get_performance_context(uid)

    try:
        bot_reply = ask_ollama(history, user_message, perf_ctx)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 503
    except Exception:
        print(traceback.format_exc())
        return jsonify({"error": "The AI model encountered an error."}), 500

    now = datetime.now(timezone.utc)
    messages().insert_many([
        {"user_id": uid, "session_id": session_id, "role": "user",
         "content": user_message, "timestamp": now},
        {"user_id": uid, "session_id": session_id, "role": "bot",
         "content": bot_reply, "timestamp": now},
    ])
    log_activity(uid)
    return jsonify({"reply": bot_reply, "timestamp": now.isoformat(),
                    "session_id": session_id})


@app.route("/api/chat/history")
def api_chat_history():
    uid, err = require_auth()
    if err: return err
    session_id = request.args.get("session_id", "")
    query = {"user_id": uid}
    if session_id:
        query["session_id"] = session_id
    raw = list(messages().find(query).sort("timestamp", 1).limit(100))
    return jsonify({"messages": [serial(m) for m in raw]})


@app.route("/api/chat/history", methods=["DELETE"])
def api_clear_history():
    uid, err = require_auth()
    if err: return err
    session_id = request.args.get("session_id", "")
    query = {"user_id": uid}
    if session_id:
        query["session_id"] = session_id
    messages().delete_many(query)
    return jsonify({"success": True})


@app.route("/api/practice/weak-topics")
def api_weak_topics():
    """
    Returns the student's topic performance summary.
    Used by the frontend to surface personalised improvement suggestions.
    """
    uid, err = require_auth()
    if err: return err

    results = list(
        quiz_results().find({"user_id": uid}).sort("submitted_at", -1).limit(30)
    )
    topic_scores: dict[str, list[int]] = {}
    for r in results:
        topic = r.get("topic", "").strip()
        if topic:
            topic_scores.setdefault(topic, []).append(r.get("score", 0))

    summary = []
    for topic, scores in topic_scores.items():
        avg = round(sum(scores) / len(scores))
        summary.append({
            "topic":     topic,
            "avg_score": avg,
            "attempts":  len(scores),
            "status":    "weak" if avg < 70 else "strong" if avg >= 80 else "improving",
        })
    summary.sort(key=lambda x: x["avg_score"])
    return jsonify({"topics": summary})


# ═════════════════════════════════════════════════════════════
#  PLANNER API
# ═════════════════════════════════════════════════════════════

VALID_DAYS = {"Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"}

@app.route("/api/planner")
def api_planner_get():
    uid, err = require_auth()
    if err: return err
    tasks = list(planner().find({"user_id": uid}).sort("created_at", 1))
    return jsonify({"tasks": [serial(t) for t in tasks]})


@app.route("/api/planner", methods=["POST"])
def api_planner_add():
    uid, err = require_auth()
    if err: return err
    data      = request.get_json() or {}
    day       = data.get("day",       "").strip()
    task_text = data.get("task_text", "").strip()
    if not day or day not in VALID_DAYS:
        return jsonify({"error": "Invalid day."}), 400
    if not task_text:
        return jsonify({"error": "Task text is required."}), 400
    doc = {"user_id": uid, "day": day, "task_text": task_text,
           "created_at": datetime.now(timezone.utc)}
    result = planner().insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"task": serial(doc)}), 201


@app.route("/api/planner", methods=["DELETE"])
def api_planner_delete():
    uid, err = require_auth()
    if err: return err
    data    = request.get_json() or {}
    task_id = data.get("task_id", "")
    try:
        oid = ObjectId(task_id)
    except Exception:
        return jsonify({"error": "Invalid task ID."}), 400
    result = planner().delete_one({"_id": oid, "user_id": uid})
    if result.deleted_count == 0:
        return jsonify({"error": "Task not found."}), 404
    return jsonify({"success": True})


# ═════════════════════════════════════════════════════════════
#  PRACTICE API
# ═════════════════════════════════════════════════════════════

@app.route("/api/practice")
def api_get_practice():
    uid, err = require_auth()
    if err: return err
    sets = list(practice_sets().find({"user_id": uid}).sort("created_at", -1).limit(10))
    return jsonify({"practice_sets": [serial(s) for s in sets]})


@app.route("/api/practice", methods=["POST"])
def api_save_practice():
    uid, err = require_auth()
    if err: return err
    data   = request.get_json() or {}
    now    = datetime.now(timezone.utc)
    doc    = {
        "user_id":    uid,
        "topic":      data.get("topic",  ""),
        "mcq":        data.get("mcq",    []),
        "coding":     data.get("coding", []),
        "created_at": now,
    }
    result = practice_sets().insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"practice_set": serial(doc)}), 201


@app.route("/api/practice/<set_id>/submit", methods=["POST"])
def api_submit_quiz(set_id):
    uid, err = require_auth()
    if err: return err
    data    = request.get_json() or {}
    day     = data.get("day", 1)
    answers = data.get("answers", {})

    try:
        pset = practice_sets().find_one({"_id": ObjectId(set_id), "user_id": uid})
    except Exception:
        return jsonify({"error": "Invalid practice set ID"}), 400

    if not pset:
        return jsonify({"error": "Practice set not found"}), 404

    day_mcq = [q for q in pset.get("mcq", []) if q.get("day") == day]
    if not day_mcq:
        return jsonify({"error": "No questions found for this day"}), 404

    correct = 0
    total   = len(day_mcq)
    results = []
    for i, q in enumerate(day_mcq):
        user_ans   = answers.get(str(i), "")
        is_correct = user_ans.upper() == q.get("answer", "").upper()
        if is_correct:
            correct += 1
        results.append({
            "question":       q.get("question"),
            "user_answer":    user_ans,
            "correct_answer": q.get("answer"),
            "is_correct":     is_correct,
        })

    score = round((correct / total) * 100) if total > 0 else 0
    grade = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"

    now = datetime.now(timezone.utc)
    result_doc = {
        "user_id":         uid,
        "practice_set_id": set_id,
        "topic":           pset.get("topic", ""),
        "day":             day,
        "score":           score,
        "grade":           grade,
        "correct":         correct,
        "total":           total,
        "results":         results,
        "submitted_at":    now,
    }
    quiz_results().insert_one(result_doc)

    topic = pset.get("topic", "").strip()
    if topic:
        existing = srs_records().find_one({"user_id": uid, "topic": topic})
        if not existing:
            existing = {"user_id": uid, "topic": topic,
                        "ease_factor": 2.5, "interval": 1,
                        "repetitions": 0, "next_review": datetime.now(timezone.utc)}
        updated = update_srs(existing, score)
        srs_records().update_one(
            {"user_id": uid, "topic": topic},
            {"$set": updated},
            upsert=True,
        )

    return jsonify({"score": score, "grade": grade,
                    "correct": correct, "total": total, "results": results})


@app.route("/api/practice/stats")
def api_practice_stats():
    uid, err = require_auth()
    if err: return err
    all_results = list(quiz_results().find({"user_id": uid}))
    if not all_results:
        return jsonify({"avg_score": 0, "total_quizzes": 0, "grade": "N/A", "best_score": 0})
    scores = [r["score"] for r in all_results]
    avg    = round(sum(scores) / len(scores))
    best   = max(scores)
    grade  = "A" if avg >= 90 else "B" if avg >= 75 else "C" if avg >= 60 else "D" if avg >= 40 else "F"
    return jsonify({"avg_score": avg, "best_score": best,
                    "total_quizzes": len(all_results), "grade": grade})


# ═════════════════════════════════════════════════════════════
#  SRS API
# ═════════════════════════════════════════════════════════════

@app.route("/api/srs/due")
def api_srs_due():
    uid, err = require_auth()
    if err: return err
    due = get_due_topics(uid, get_db())
    return jsonify({"due_topics": due})


# ═════════════════════════════════════════════════════════════
#  MOTIVATION API
# ═════════════════════════════════════════════════════════════

@app.route("/api/motivation")
def api_get_motivation():
    uid, err = require_auth()
    if err: return err
    mot = motivations().find_one({"user_id": uid}, sort=[("created_at", -1)])
    if not mot:
        return jsonify({"motivation": None})
    return jsonify({"motivation": serial(mot)})


@app.route("/api/motivation", methods=["POST"])
def api_save_motivation():
    uid, err = require_auth()
    if err: return err
    data = request.get_json() or {}
    doc  = {
        "user_id":    uid,
        "topic":      data.get("topic",     ""),
        "story":      data.get("story",     ""),
        "daily_tip":  data.get("daily_tip", ""),
        "created_at": datetime.now(timezone.utc),
    }
    motivations().insert_one(doc)
    return jsonify({"success": True}), 201


# ═════════════════════════════════════════════════════════════
#  YOUTUBE API
# ═════════════════════════════════════════════════════════════

YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")

@app.route("/api/youtube")
def api_youtube():
    uid, err = require_auth()
    if err: return err

    if not YOUTUBE_API_KEY:
        return jsonify({"error": "YOUTUBE_API_KEY not set", "videos": [], "topic": ""}), 200

    mot   = motivations().find_one({"user_id": uid}, sort=[("created_at", -1)])
    topic = mot.get("topic", "").strip() if mot else ""
    query = f"{topic} tutorial programming learn" if topic else "evidence based study techniques learning"

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={"part": "snippet", "q": query, "type": "video",
                    "maxResults": 4, "relevanceLanguage": "en",
                    "safeSearch": "strict", "key": YOUTUBE_API_KEY},
            timeout=10,
        )
        resp.raise_for_status()
        items  = resp.json().get("items", [])
        videos = []
        for item in items:
            vid_id  = item["id"]["videoId"]
            snippet = item["snippet"]
            thumb   = snippet["thumbnails"].get("high", snippet["thumbnails"].get("medium", {}))
            videos.append({
                "id":          vid_id,
                "title":       snippet["title"],
                "description": snippet["description"][:120],
                "thumbnail":   thumb.get("url", f"https://i.ytimg.com/vi/{vid_id}/hqdefault.jpg"),
                "channel":     snippet["channelTitle"],
            })
        return jsonify({"videos": videos, "topic": topic})
    except requests.exceptions.HTTPError as e:
        return jsonify({"error": f"YouTube API error: {e}", "videos": [], "topic": topic}), 200
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e), "videos": [], "topic": topic}), 200


# ═════════════════════════════════════════════════════════════
#  STATUS
# ═════════════════════════════════════════════════════════════

@app.route("/api/status")
def api_status():
    ollama = check_ollama_status()
    try:
        get_db().command("ping")
        mongo_ok = True
    except Exception:
        mongo_ok = False
    return jsonify({"ollama": ollama, "mongo": mongo_ok})


# ═════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port  = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    print(f"🚀  Starting Nexus Learn on http://localhost:{port}")
    socketio.run(app, debug=debug, host="0.0.0.0", port=port)