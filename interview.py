"""
interview.py — Interview Preparation Platform Blueprint
========================================================
Register in app.py with:
    from interview import interview_bp
    app.register_blueprint(interview_bp)
"""

from flask import Blueprint, render_template, jsonify, request, session
from bson  import ObjectId
from datetime import datetime, timezone
import re
from db  import get_db
from llm import ask_ollama
from utils import serial as _serial, require_auth as _require_auth, extract_field as _ex  # Gap 4

interview_bp = Blueprint("interview", __name__)


# ── DB helpers ────────────────────────────────────────────────
def _db():           return get_db()
def _profiles():     return _db()["iv_profiles"]
def _sessions():     return _db()["iv_sessions"]
def _results():      return _db()["iv_results"]
def _mock_sessions():return _db()["iv_mock_sessions"]


# ── Scoring functions (extracted to module level for testability — Gap 5) ──

def recalc_overall(intro: int, behaviour: int, technical: int) -> int:
    """
    Recalculate weighted overall score from round scores.
    Weights: intro 20 %, behaviour 40 %, technical 40 %.
    """
    return round(intro * 0.20 + behaviour * 0.40 + technical * 0.40)


def apply_verdict_rules(
    overall: int,
    intro: int,
    behaviour: int,
    technical: int,
    raw_verdict: str,
) -> str:
    """
    Apply pass/fail guardrail rules on top of the LLM's raw verdict.

    Rules:
    - FAIL if overall < 65 OR any round < 45  (hard floor)
    - Override FAIL → PASS if overall >= 75 AND all rounds >= 45
    """
    verdict = raw_verdict.upper().strip()
    if overall < 65 or min(intro, behaviour, technical) < 45:
        return "FAIL"
    if verdict == "FAIL" and overall >= 75 and min(intro, behaviour, technical) >= 45:
        return "PASS"
    return verdict if verdict in {"PASS", "FAIL"} else "FAIL"


def calc_grade(score: int) -> str:
    """Convert a numeric score to a letter grade."""
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 65: return "C"
    if score >= 50: return "D"
    return "F"

def _ensure_indexes():
    _profiles().create_index("user_id", unique=True)
    _sessions().create_index([("user_id", 1), ("created_at", -1)])
    _results().create_index([("user_id",  1), ("created_at", -1)])
    _mock_sessions().create_index([("user_id", 1), ("created_at", -1)])

try:
    _ensure_indexes()
except Exception:
    pass


# ── Static data ───────────────────────────────────────────────
ROLES = [
    "Software Engineer", "Frontend Developer", "Backend Developer",
    "Full Stack Developer", "Data Scientist", "Data Analyst",
    "DevOps Engineer", "Cybersecurity Analyst", "Product Manager",
    "Project Manager", "Business Analyst", "Marketing Manager",
    "Sales Executive", "HR Manager", "Financial Analyst",
    "Graphic Designer", "UX/UI Designer", "Content Writer",
    "Nurse / Healthcare", "Teacher / Educator", "General / Any Role",
]

NERVOUSNESS = [
    "Answering technical questions",
    "Behavioural / situational questions",
    "Talking about myself confidently",
    "Explaining my experience clearly",
    "Handling unexpected questions",
    "Communication and body language",
    "Everything — first interview ever",
]

EXPERIENCE = [
    "No experience (first interview ever)",
    "Some experience (1-2 interviews)",
    "Moderate experience (3-5 interviews)",
    "Experienced (5+ interviews)",
]

FRAMEWORKS = {
    "STAR": {
        "name": "STAR Method",
        "desc": "Best for behavioural and situational questions",
        "steps": [
            {"letter": "S", "word": "Situation",  "explain": "Describe the context. Set the scene briefly."},
            {"letter": "T", "word": "Task",        "explain": "Explain what your responsibility was."},
            {"letter": "A", "word": "Action",      "explain": "Describe exactly what YOU did — be specific."},
            {"letter": "R", "word": "Result",      "explain": "Share the outcome. Use numbers if possible."},
        ]
    },
    "CAR": {
        "name": "CAR Method",
        "desc": "Best for experience and achievement questions",
        "steps": [
            {"letter": "C", "word": "Challenge",  "explain": "What problem or challenge did you face?"},
            {"letter": "A", "word": "Action",     "explain": "What specific steps did you take to solve it?"},
            {"letter": "R", "word": "Result",     "explain": "What was the outcome and what did you learn?"},
        ]
    },
    "PREP": {
        "name": "PREP Method",
        "desc": "Best for opinion and open-ended questions",
        "steps": [
            {"letter": "P", "word": "Point",       "explain": "State your main point directly."},
            {"letter": "R", "word": "Reason",      "explain": "Give the reason or evidence behind it."},
            {"letter": "E", "word": "Example",     "explain": "Provide a specific real-world example."},
            {"letter": "P", "word": "Point again", "explain": "Restate your point to close strongly."},
        ]
    }
}

# Mock interview round config
MOCK_ROUNDS = [
    {"id": "intro",      "name": "Introduction",         "questions": 2, "weight": 0.20},
    {"id": "behaviour",  "name": "Behavioural",          "questions": 3, "weight": 0.40},
    {"id": "technical",  "name": "Technical",            "questions": 3, "weight": 0.40},
]


# ══════════════════════════════════════════════════════════════
#  PAGE ROUTE
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/interview")
def interview_page():
    if not session.get("user_id"):
        from flask import redirect, url_for
        return redirect(url_for("login_page"))
    return render_template("interview.html")


# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/config")
def api_config():
    uid, err = _require_auth()
    if err: return err
    return jsonify({
        "roles": ROLES, "nervousness": NERVOUSNESS,
        "experience": EXPERIENCE, "frameworks": FRAMEWORKS,
    })


# ══════════════════════════════════════════════════════════════
#  PROFILE
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/profile", methods=["GET","POST"])
def api_profile():
    uid, err = _require_auth()
    if err: return err
    if request.method == "POST":
        data = request.get_json() or {}
        now  = datetime.now(timezone.utc)
        doc  = {
            "user_id":     uid,
            "role":        data.get("role", "General / Any Role"),
            "experience":  data.get("experience", "No experience"),
            "nervousness": data.get("nervousness", []),
            "goals":       data.get("goals", ""),
            "updated_at":  now,
        }
        _profiles().update_one(
            {"user_id": uid},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True
        )
        return jsonify({"profile": doc})
    p = _profiles().find_one({"user_id": uid})
    return jsonify({"profile": _serial(p) if p else None})


# ══════════════════════════════════════════════════════════════
#  ROADMAP
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/roadmap", methods=["GET","POST"])
def api_roadmap():
    uid, err = _require_auth()
    if err: return err

    if request.method == "GET":
        p = _profiles().find_one({"user_id": uid})
        if p and p.get("roadmap"):
            return jsonify({"roadmap": p["roadmap"], "profile": _serial(p)})
        return jsonify({"roadmap": None, "profile": _serial(p) if p else None})

    data        = request.get_json() or {}
    role        = data.get("role", "General / Any Role")
    experience  = data.get("experience", "")
    nervousness = data.get("nervousness", [])
    goals       = data.get("goals", "")
    save_to_planner = data.get("save_to_planner", True)

    prompt = f"""You are a warm, encouraging interview coach helping a student prepare for a {role} interview.

Student: experience={experience}, nervous about={', '.join(nervousness) if nervousness else 'general prep'}, goal={goals or 'get the job'}

Write a personalised preparation roadmap. Format EXACTLY:

GREETING: [Warm encouraging sentence for their specific situation]
STRENGTHS: [What they likely already have going for them]
FOCUS_AREAS:
1. [Most important thing to work on]
2. [Second priority]
3. [Third priority]
DAILY_PLAN:
Day 1: [specific task]
Day 2: [specific task]
Day 3: [specific task]
Day 4: [specific task]
Day 5: [specific task]
ENCOURAGEMENT: [One powerful motivating closing sentence]"""

    try:
        raw = ask_ollama([], prompt).strip()
        focus = []
        for line in _ex(raw, "FOCUS_AREAS").split('\n'):
            c = re.sub(r'^[\d\-\.\)]+\s*', '', line.strip()).strip()
            if c: focus.append(c)
        plan = {}
        for line in _ex(raw, "DAILY_PLAN").split('\n'):
            m = re.match(r'Day\s*(\d+):\s*(.+)', line.strip(), re.IGNORECASE)
            if m: plan[f"Day {m.group(1)}"] = m.group(2).strip()

        roadmap = {
            "greeting":      _ex(raw,"GREETING")      or f"Let's get you ready for your {role} interview!",
            "strengths":     _ex(raw,"STRENGTHS")     or "You have taken the first step by starting preparation.",
            "focus_areas":   focus or ["Practice answering out loud","Learn the STAR method","Research the role"],
            "daily_plan":    plan,
            "encouragement": _ex(raw,"ENCOURAGEMENT") or "With consistent practice you will walk in with confidence.",
            "role":          role,
            "generated_at":  datetime.now(timezone.utc).isoformat(),
        }

        _profiles().update_one(
            {"user_id": uid},
            {"$set": {"roadmap": roadmap, "roadmap_role": role, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )

        planner_saved = 0
        if save_to_planner and plan:
            day_map = {
                "Day 1": "Monday", "Day 2": "Tuesday", "Day 3": "Wednesday",
                "Day 4": "Thursday", "Day 5": "Friday"
            }
            plan_name = f"Interview Prep — {role}"
            for day_key, task_text in plan.items():
                planner_day = day_map.get(day_key)
                if planner_day and task_text:
                    try:
                        _db()["planner_tasks"].insert_one({
                            "user_id":    uid,
                            "day":        planner_day,
                            "task_text":  task_text,
                            "source":     "interview",
                            "plan_name":  plan_name,
                            "created_at": datetime.now(timezone.utc),
                        })
                        planner_saved += 1
                    except Exception:
                        pass

        return jsonify({"roadmap": roadmap, "planner_saved": planner_saved})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  LEARN — generate example questions (poor/avg/excellent)
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/learn", methods=["POST"])
def api_learn():
    uid, err = _require_auth()
    if err: return err
    data      = request.get_json() or {}
    role      = data.get("role", "General / Any Role")
    q_type    = data.get("question_type", "Behavioural")
    framework = data.get("framework", "STAR")

    prompt = f"""Expert interview coach. Teaching a student preparing for {role} interviews.

Generate ONE {q_type} question and three answer levels. Format EXACTLY:

QUESTION: [One realistic {q_type} interview question for {role}]
POOR_ANSWER: [Weak, vague, unprepared — 2-3 sentences]
POOR_WHY: [Why it is weak — 1-2 sentences]
AVERAGE_ANSWER: [Decent but incomplete — 3-4 sentences]
AVERAGE_WHY: [What is missing — 1-2 sentences]
EXCELLENT_ANSWER: [Strong, structured using {framework} — 5-6 sentences]
EXCELLENT_WHY: [Why it works — 1-2 sentences]
KEY_TIP: [One powerful tip for this question type]"""

    try:
        raw = ask_ollama([], prompt).strip()
        return jsonify({
            "question":         _ex(raw,"QUESTION"),
            "poor_answer":      _ex(raw,"POOR_ANSWER"),
            "poor_why":         _ex(raw,"POOR_WHY"),
            "average_answer":   _ex(raw,"AVERAGE_ANSWER"),
            "average_why":      _ex(raw,"AVERAGE_WHY"),
            "excellent_answer": _ex(raw,"EXCELLENT_ANSWER"),
            "excellent_why":    _ex(raw,"EXCELLENT_WHY"),
            "key_tip":          _ex(raw,"KEY_TIP"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  PRACTICE — question + feedback
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/practice/question", methods=["POST"])
def api_practice_question():
    uid, err = _require_auth()
    if err: return err
    data    = request.get_json() or {}
    role    = data.get("role", "General / Any Role")
    q_type  = data.get("question_type", "Behavioural")
    level   = data.get("level", "Beginner")
    prev_qs = data.get("previous_questions", [])
    prev    = ("Avoid repeating: " + " | ".join(prev_qs[-5:])) if prev_qs else ""

    prompt = f"""Friendly interview coach. Generate ONE {level} level {q_type} practice question for {role} role. {prev}
Output ONLY the question text. No numbering. No explanation."""
    try:
        q = ask_ollama([], prompt).strip()
        for p in ["Question:","Q:","Q1:","1.","1)"]:
            if q.startswith(p): q = q[len(p):].strip()
        return jsonify({"question": q or f"Tell me about yourself and your interest in {role}."})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@interview_bp.route("/api/interview/practice/feedback", methods=["POST"])
def api_practice_feedback():
    uid, err = _require_auth()
    if err: return err
    data      = request.get_json() or {}
    role      = data.get("role", "General / Any Role")
    question  = data.get("question", "")
    answer    = data.get("answer", "").strip()
    attempt   = int(data.get("attempt", 1))
    framework = data.get("framework", "STAR")
    q_type    = data.get("question_type", "Behavioural")

    if not answer:
        return jsonify({"error": "Answer cannot be empty"}), 400

    prompt = f"""Warm, encouraging study buddy helping a student prepare for {role} {q_type} interviews. Attempt {attempt}.

Question: {question}
Answer: {answer}
Framework hint used: {framework}

Give coaching feedback. Format EXACTLY:

BUDDY_REACTION: [Warm genuine reaction — acknowledge something specific they did right. 1-2 sentences.]
WHAT_WORKED: [1-2 specific things they did well]
MAKE_IT_STRONGER: [2-3 specific practical suggestions — reference {framework} method if relevant]
MISSING_PIECE: [The ONE most important thing missing]
TRY_THIS: [Rewrite their opening sentence to show a stronger start]
REFLECTION_Q: [One question to help them think deeper]
ENCOURAGEMENT: [One short motivating sentence]

Tone: warm, specific, constructive. Never harsh. Never just "good job"."""

    try:
        raw = ask_ollama([], prompt).strip()
        base  = min(40 + len(answer.split()) * 0.5, 75)
        score = min(int(base + (attempt-1)*5), 95)
        return jsonify({
            "buddy_reaction":   _ex(raw,"BUDDY_REACTION")   or "Good effort on this one!",
            "what_worked":      _ex(raw,"WHAT_WORKED")      or "You attempted the question directly.",
            "make_it_stronger": _ex(raw,"MAKE_IT_STRONGER") or "Try to add a specific example.",
            "missing_piece":    _ex(raw,"MISSING_PIECE")    or "A concrete result or outcome.",
            "try_this":         _ex(raw,"TRY_THIS")         or "",
            "reflection_q":     _ex(raw,"REFLECTION_Q")    or "Can you think of a specific example?",
            "encouragement":    _ex(raw,"ENCOURAGEMENT")   or "Keep going — you are improving!",
            "attempt": attempt, "score": score,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  MOCK INTERVIEW — Start
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/mock/start", methods=["POST"])
def api_mock_start():
    uid, err = _require_auth()
    if err: return err
    data       = request.get_json() or {}
    role       = data.get("role", "General / Any Role")
    difficulty = data.get("difficulty", "Intermediate")
    now        = datetime.now(timezone.utc)

    # Generate first question — intro round
    first_q = _mock_gen_question(role, "intro", difficulty, [], 1, 2)

    doc = {
        "user_id":     uid,
        "user_name":   session.get("user_name", "Candidate"),
        "role":        role,
        "difficulty":  difficulty,
        "current_round":    "intro",
        "current_q_in_round": 1,
        "current_question":   first_q,
        "rounds": {
            "intro":     {"answers": [], "complete": False, "total": 2},
            "behaviour": {"answers": [], "complete": False, "total": 3},
            "technical": {"answers": [], "complete": False, "total": 3},
        },
        "status":      "active",
        "verdict":     None,
        "created_at":  now,
    }
    res = _mock_sessions().insert_one(doc)
    doc["_id"] = res.inserted_id
    return jsonify({
        "session_id":       str(res.inserted_id),
        "question":         first_q,
        "round":            "intro",
        "round_name":       "Introduction Round",
        "q_in_round":       1,
        "total_in_round":   2,
        "round_number":     1,
        "total_rounds":     3,
    }), 201


# ══════════════════════════════════════════════════════════════
#  MOCK INTERVIEW — Submit Answer
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/mock/<session_id>/answer", methods=["POST"])
def api_mock_answer(session_id):
    uid, err = _require_auth()
    if err: return err
    data   = request.get_json() or {}
    answer = data.get("answer", "").strip()
    if not answer:
        return jsonify({"error": "Answer cannot be empty"}), 400

    try:
        sess = _mock_sessions().find_one({"_id": ObjectId(session_id), "user_id": uid})
    except Exception:
        return jsonify({"error": "Invalid session"}), 400
    if not sess or sess["status"] != "active":
        return jsonify({"error": "Session not found or already complete"}), 404

    current_round   = sess["current_round"]
    q_in_round      = sess["current_q_in_round"]
    total_in_round  = sess["rounds"][current_round]["total"]
    question        = sess.get("current_question", "")
    role            = sess["role"]
    difficulty      = sess["difficulty"]

    # Save answer to current round
    answer_record = {
        "q_num":    q_in_round,
        "question": question,
        "answer":   answer,
    }
    update_path = f"rounds.{current_round}.answers"

    # Determine next state
    round_order  = ["intro", "behaviour", "technical"]
    round_idx    = round_order.index(current_round)
    is_last_q_in_round = (q_in_round >= total_in_round)
    is_last_round      = (round_idx == len(round_order) - 1)
    is_complete        = is_last_q_in_round and is_last_round

    upd = {
        "$push": {update_path: answer_record},
        "$set":  {"updated_at": datetime.now(timezone.utc)}
    }

    if is_last_q_in_round:
        upd["$set"][f"rounds.{current_round}.complete"] = True

    if is_complete:
        # Mark done — verdict generated below
        upd["$set"]["status"] = "completed"
    elif is_last_q_in_round:
        # Move to next round
        next_round = round_order[round_idx + 1]
        next_total = sess["rounds"][next_round]["total"]
        next_q     = _mock_gen_question(role, next_round, difficulty, [], 1, next_total)
        upd["$set"]["current_round"]       = next_round
        upd["$set"]["current_q_in_round"]  = 1
        upd["$set"]["current_question"]    = next_q
    else:
        # Next question in same round
        prev_qs = [a["question"] for a in sess["rounds"][current_round]["answers"]] + [question]
        next_q  = _mock_gen_question(role, current_round, difficulty, prev_qs, q_in_round+1, total_in_round)
        upd["$set"]["current_q_in_round"]  = q_in_round + 1
        upd["$set"]["current_question"]    = next_q

    _mock_sessions().update_one({"_id": ObjectId(session_id)}, upd)

    # If complete, generate verdict
    if is_complete:
        updated = _mock_sessions().find_one({"_id": ObjectId(session_id)})
        verdict = _mock_verdict(updated)
        _mock_sessions().update_one(
            {"_id": ObjectId(session_id)},
            {"$set": {"verdict": verdict}}
        )
        return jsonify({"complete": True, "verdict": verdict})

    # Return next question info
    if is_last_q_in_round:
        next_round_name = {"intro":"Introduction","behaviour":"Behavioural","technical":"Technical"}[round_order[round_idx+1]]
        return jsonify({
            "complete":       False,
            "round_change":   True,
            "question":       upd["$set"]["current_question"],
            "round":          round_order[round_idx+1],
            "round_name":     next_round_name + " Round",
            "round_number":   round_idx + 2,
            "total_rounds":   3,
            "q_in_round":     1,
            "total_in_round": sess["rounds"][round_order[round_idx+1]]["total"],
        })
    else:
        return jsonify({
            "complete":       False,
            "round_change":   False,
            "question":       upd["$set"]["current_question"],
            "round":          current_round,
            "round_name":     {"intro":"Introduction","behaviour":"Behavioural","technical":"Technical"}[current_round] + " Round",
            "round_number":   round_idx + 1,
            "total_rounds":   3,
            "q_in_round":     q_in_round + 1,
            "total_in_round": total_in_round,
        })


# ══════════════════════════════════════════════════════════════
#  MOCK INTERVIEW — History
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/mock/history")
def api_mock_history():
    uid, err = _require_auth()
    if err: return err
    results = list(_mock_sessions().find(
        {"user_id": uid, "status": "completed"}
    ).sort("created_at", -1).limit(5))
    return jsonify({"history": [_serial(r) for r in results]})


# ══════════════════════════════════════════════════════════════
#  EXISTING HISTORY / STATS
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/history")
def api_history():
    uid, err = _require_auth()
    if err: return err
    r = list(_results().find({"user_id": uid}).sort("created_at",-1).limit(10))
    return jsonify({"history": [_serial(x) for x in r]})


@interview_bp.route("/api/interview/stats")
def api_stats():
    uid, err = _require_auth()
    if err: return err
    all_r = list(_results().find({"user_id": uid}))
    mocks = list(_mock_sessions().find({"user_id": uid, "status": "completed"}))
    mock_scores = [m["verdict"]["overall_score"] for m in mocks if m.get("verdict")]
    if not all_r and not mock_scores:
        return jsonify({"total":0,"avg_score":0,"best_score":0,"grade":"N/A","roles":[]})
    all_scores = [r.get("overall_score",0) for r in all_r] + mock_scores
    avg    = round(sum(all_scores)/len(all_scores))
    grade  = "A" if avg>=90 else "B" if avg>=75 else "C" if avg>=60 else "D" if avg>=40 else "F"
    return jsonify({
        "total":len(all_r)+len(mocks),"avg_score":avg,
        "best_score":max(all_scores),"grade":grade,
        "roles":list(set(r.get("role","") for r in all_r)),
        "mock_sessions": len(mocks),
    })


# ══════════════════════════════════════════════════════════════
#  MOCK INTERVIEW — Internal helpers
# ══════════════════════════════════════════════════════════════

ROUND_PROMPTS = {
    "intro": "a warm professional introduction / get to know you",
    "behaviour": "a behavioural / situational (use STAR method)",
    "technical": "a technical / knowledge-based",
}

def _mock_gen_question(role, round_id, difficulty, prev_qs, q_num, total_in_round):
    round_type = ROUND_PROMPTS.get(round_id, "general")
    prev = ("Do NOT repeat: " + " | ".join(prev_qs[-3:])) if prev_qs else ""

    prompt = f"""You are a professional interviewer conducting a {difficulty} level interview for {role}.
This is the {round_id.upper()} ROUND. Generate question {q_num} of {total_in_round}.
Question type: {round_type} question.
{prev}

Rules:
- Output ONLY the question text
- Make it realistic and appropriate for {role}
- Match difficulty: {difficulty}
- No numbering, no preamble

Question:"""

    try:
        q = ask_ollama([], prompt).strip()
        for p in ["Question:","Q:","Q1:","1.","1)"]:
            if q.startswith(p): q = q[len(p):].strip()
        return q or _fallback_question(role, round_id, q_num)
    except Exception:
        return _fallback_question(role, round_id, q_num)

def _fallback_question(role, round_id, q_num):
    fallbacks = {
        "intro":     ["Tell me about yourself and your background.", "Why are you interested in this role?"],
        "behaviour": ["Tell me about a time you faced a challenge at work.", "Describe a situation where you showed leadership.", "Tell me about a time you had to work under pressure."],
        "technical": [f"What key skills do you bring to the {role} role?", "Explain your approach to problem solving.", "What are your strongest technical competencies?"],
    }
    opts = fallbacks.get(round_id, ["Tell me more about yourself."])
    return opts[min(q_num-1, len(opts)-1)]


def _mock_verdict(sess):
    """Generate PASS/FAIL verdict from all round answers."""
    role       = sess.get("role", "General")
    difficulty = sess.get("difficulty", "Intermediate")
    rounds     = sess.get("rounds", {})

    # Build Q&A text for each round
    def qa_text(round_id):
        answers = rounds.get(round_id, {}).get("answers", [])
        if not answers:
            return "No answers provided."
        lines = []
        for a in answers:
            lines.append(f"Q: {a.get('question','')}")
            lines.append(f"A: {a.get('answer','[No answer]')}")
            lines.append("")
        return "\n".join(lines)

    intro_text     = qa_text("intro")
    behaviour_text = qa_text("behaviour")
    technical_text = qa_text("technical")

    prompt = f"""You are a senior hiring manager who just completed a full mock interview for the role of {role} at {difficulty} level.

Review the candidate's complete interview below and provide your official verdict.

═══ ROUND 1 — INTRODUCTION ═══
{intro_text}

═══ ROUND 2 — BEHAVIOURAL ═══
{behaviour_text}

═══ ROUND 3 — TECHNICAL ═══
{technical_text}

Based on realistic {difficulty} level hiring standards for {role}, provide your verdict in EXACTLY this format:

INTRO_SCORE: [number 0-100]
INTRO_SUMMARY: [2 honest sentences on their introduction performance]
BEHAVIOUR_SCORE: [number 0-100]
BEHAVIOUR_SUMMARY: [2 honest sentences on their behavioural answers]
TECHNICAL_SCORE: [number 0-100]
TECHNICAL_SUMMARY: [2 honest sentences on their technical answers]
OVERALL_SCORE: [number 0-100, calculated: intro x0.20 + behaviour x0.40 + technical x0.40]
VERDICT: [write exactly the word PASS or the word FAIL — nothing else]
VERDICT_REASON: [2-3 honest sentences clearly explaining why they passed or failed]
TOP_STRENGTHS: [exactly 3 specific strengths shown, separated by the | character]
MUST_IMPROVE: [exactly 3 specific things they must work on, separated by the | character]
FINAL_MESSAGE: [One professional, respectful closing statement to the candidate]

Scoring rules you MUST follow:
- PASS = overall score 65 or above AND no single round below 45
- FAIL = overall score below 65 OR any single round below 45
- Be honest — do not inflate scores to be kind
- A real interview would assess these answers the same way"""

    try:
        raw = ask_ollama([], prompt).strip()

        def score_int(key):
            val = _ex(raw, key)
            try:    return max(0, min(100, int("".join(filter(str.isdigit, val)))))
            except: return 50

        intro_score     = score_int("INTRO_SCORE")
        behaviour_score = score_int("BEHAVIOUR_SCORE")
        technical_score = score_int("TECHNICAL_SCORE")
        overall_score   = score_int("OVERALL_SCORE")

        # Recalculate overall if model's arithmetic is off by more than 10 pts
        recalc = recalc_overall(intro_score, behaviour_score, technical_score)
        if abs(recalc - overall_score) > 10:
            overall_score = recalc

        verdict_raw = _ex(raw, "VERDICT")
        verdict     = apply_verdict_rules(
            overall_score, intro_score, behaviour_score, technical_score, verdict_raw
        )

        strengths = [s.strip() for s in _ex(raw,"TOP_STRENGTHS").split("|") if s.strip()][:3]
        improvements = [s.strip() for s in _ex(raw,"MUST_IMPROVE").split("|") if s.strip()][:3]

        return {
            "intro_score":       intro_score,
            "intro_summary":     _ex(raw,"INTRO_SUMMARY"),
            "behaviour_score":   behaviour_score,
            "behaviour_summary": _ex(raw,"BEHAVIOUR_SUMMARY"),
            "technical_score":   technical_score,
            "technical_summary": _ex(raw,"TECHNICAL_SUMMARY"),
            "overall_score":     overall_score,
            "verdict":           verdict,
            "verdict_reason":    _ex(raw,"VERDICT_REASON"),
            "top_strengths":     strengths or ["Attempted all questions","Showed willingness to engage","Provided relevant answers"],
            "must_improve":      improvements or ["Add specific examples","Structure answers more clearly","Deepen technical knowledge"],
            "final_message":     _ex(raw,"FINAL_MESSAGE") or "Thank you for your time. Keep practising and you will improve.",
            "grade":             "A" if overall_score>=90 else "B" if overall_score>=75 else "C" if overall_score>=65 else "D" if overall_score>=50 else "F",
        }

    except Exception as e:
        return {
            "intro_score": 50, "intro_summary": "Could not evaluate.",
            "behaviour_score": 50, "behaviour_summary": "Could not evaluate.",
            "technical_score": 50, "technical_summary": "Could not evaluate.",
            "overall_score": 50, "verdict": "FAIL",
            "verdict_reason": "Unable to generate verdict. Please ensure Ollama is running.",
            "top_strengths": [], "must_improve": [],
            "final_message": "Please try again.", "grade": "D",
        }