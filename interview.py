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

interview_bp = Blueprint("interview", __name__)


# ── DB helpers ────────────────────────────────────────────────
def _db():         return get_db()
def _profiles():   return _db()["iv_profiles"]
def _sessions():   return _db()["iv_sessions"]
def _results():    return _db()["iv_results"]

def _require_auth():
    uid = session.get("user_id")
    if not uid:
        return None, (jsonify({"error": "Not authenticated"}), 401)
    return uid, None

def _serial(doc):
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):    out[k] = str(v)
        elif isinstance(v, datetime):  out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [_serial(i) if isinstance(i, dict)
                      else str(i) if isinstance(i, ObjectId) else i for i in v]
        elif isinstance(v, dict):      out[k] = _serial(v)
        else:                          out[k] = v
    return out

def _ex(raw, key):
    """Extract a block between KEY: and the next KEY: or end of string."""
    m = re.search(rf"{key}:\s*(.+?)(?=\n[A-Z_]{{2,}}:|$)", raw, re.DOTALL)
    return m.group(1).strip() if m else ""

def _ensure_indexes():
    _profiles().create_index("user_id", unique=True)
    _sessions().create_index([("user_id", 1), ("created_at", -1)])
    _results().create_index([("user_id",  1), ("created_at", -1)])

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
        "desc": "Best for opinion and 'tell me about yourself' questions",
        "steps": [
            {"letter": "P", "word": "Point",       "explain": "State your main point directly."},
            {"letter": "R", "word": "Reason",      "explain": "Give the reason or evidence."},
            {"letter": "E", "word": "Example",     "explain": "Provide a specific real-world example."},
            {"letter": "P", "word": "Point again", "explain": "Restate your point to close strongly."},
        ]
    }
}


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

    # GET — return saved roadmap if exists
    if request.method == "GET":
        p = _profiles().find_one({"user_id": uid})
        if p and p.get("roadmap"):
            return jsonify({"roadmap": p["roadmap"], "profile": _serial(p)})
        return jsonify({"roadmap": None, "profile": _serial(p) if p else None})

    # POST — generate new roadmap
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

        # Save roadmap to profile so it persists
        _profiles().update_one(
            {"user_id": uid},
            {"$set": {"roadmap": roadmap, "roadmap_role": role, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        )

        # Save 5-day plan to weekly planner
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

        return jsonify({
            "roadmap":        roadmap,
            "planner_saved":  planner_saved,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  LEARN — poor / average / excellent examples
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
            "framework":        framework,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  GUIDED PRACTICE
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/practice/question", methods=["POST"])
def api_practice_question():
    uid, err = _require_auth()
    if err: return err
    data    = request.get_json() or {}
    role    = data.get("role", "General / Any Role")
    q_type  = data.get("question_type", "Mixed")
    prev_qs = data.get("previous_questions", [])
    prev    = ("Avoid repeating: " + " | ".join(prev_qs[-5:])) if prev_qs else ""

    prompt = f"""Friendly interview coach. Generating a practice question for {role} ({q_type} type). {prev}
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

    if not answer:
        return jsonify({"error": "Answer cannot be empty"}), 400

    prompt = f"""Warm, encouraging study buddy helping a student prepare for {role} interviews. Attempt {attempt}.

Question: {question}
Answer: {answer}

Give coaching feedback. Format EXACTLY:

BUDDY_REACTION: [Warm genuine reaction — acknowledge something specific they did right. 1-2 sentences.]
WHAT_WORKED: [1-2 specific things they did well]
MAKE_IT_STRONGER: [2-3 specific practical suggestions — reference {framework} if relevant]
MISSING_PIECE: [The ONE most important thing missing]
TRY_THIS: [Rewrite their opening sentence to show a stronger start]
REFLECTION_Q: [One question to help them think deeper — e.g. can you think of a specific example?]
ENCOURAGEMENT: [One short motivating sentence]

Tone: warm, specific, constructive. Never harsh."""

    try:
        raw = ask_ollama([], prompt).strip()
        base  = min(40 + len(answer.split()) * 0.5, 75)
        score = min(int(base + (attempt-1)*5), 95)
        return jsonify({
            "buddy_reaction":    _ex(raw,"BUDDY_REACTION")   or "Good effort on this one!",
            "what_worked":       _ex(raw,"WHAT_WORKED")      or "You attempted the question directly.",
            "make_it_stronger":  _ex(raw,"MAKE_IT_STRONGER") or "Try to add a specific example.",
            "missing_piece":     _ex(raw,"MISSING_PIECE")    or "A concrete result or outcome.",
            "try_this":          _ex(raw,"TRY_THIS")         or "",
            "reflection_q":      _ex(raw,"REFLECTION_Q")    or "Can you think of a specific example?",
            "encouragement":     _ex(raw,"ENCOURAGEMENT")   or "Keep going — you are improving!",
            "attempt": attempt, "score": score,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  SIMULATION
# ══════════════════════════════════════════════════════════════

@interview_bp.route("/api/interview/simulation/start", methods=["POST"])
def api_sim_start():
    uid, err = _require_auth()
    if err: return err
    data   = request.get_json() or {}
    role   = data.get("role", "General / Any Role")
    q_type = data.get("question_type", "Mixed")
    total  = max(3, min(8, int(data.get("total_questions", 5))))
    now    = datetime.now(timezone.utc)
    first_q = _sim_question(role, q_type, 1, total, [])
    doc = {
        "user_id": uid, "role": role, "question_type": q_type,
        "total_questions": total, "current_q": 1,
        "current_question": first_q, "answers": [],
        "status": "active", "created_at": now,
    }
    res = _sessions().insert_one(doc)
    doc["_id"] = res.inserted_id
    return jsonify({"session": _serial(doc)}), 201


@interview_bp.route("/api/interview/simulation/<session_id>/answer", methods=["POST"])
def api_sim_answer(session_id):
    uid, err = _require_auth()
    if err: return err
    data   = request.get_json() or {}
    answer = data.get("answer","").strip()
    if not answer:
        return jsonify({"error": "Answer cannot be empty"}), 400
    try:
        sess = _sessions().find_one({"_id": ObjectId(session_id), "user_id": uid})
    except Exception:
        return jsonify({"error": "Invalid session"}), 400
    if not sess or sess["status"] != "active":
        return jsonify({"error": "Session not found or complete"}), 404

    cq = sess["current_q"]; tq = sess["total_questions"]
    q  = sess.get("current_question","")
    fb = _sim_fb(sess["role"], q, answer)
    rec = {"question_number": cq, "question": q, "answer": answer, "feedback": fb}
    is_last = cq >= tq
    upd = {"$push": {"answers": rec}, "$set": {"updated_at": datetime.now(timezone.utc)}}
    if is_last:
        upd["$set"]["status"] = "completed"
    else:
        nq = _sim_question(sess["role"], sess["question_type"], cq+1, tq,
                           [a["question"] for a in sess.get("answers",[])+[rec]])
        upd["$set"]["current_question"] = nq
        upd["$set"]["current_q"] = cq+1
    _sessions().update_one({"_id": ObjectId(session_id)}, upd)
    overall = None
    if is_last:
        overall = _sim_overall(sess.get("answers",[])+[rec], sess["role"])
        _results().insert_one({
            "user_id": uid, "session_id": session_id,
            "role": sess["role"], "question_type": sess["question_type"],
            "total_questions": tq, "overall_score": overall["score"],
            "overall_grade": overall["grade"], "overall_feedback": overall["summary"],
            "created_at": datetime.now(timezone.utc),
        })
    resp = {"feedback": fb, "is_last": is_last, "overall": overall}
    if not is_last:
        updated = _sessions().find_one({"_id": ObjectId(session_id)})
        resp["next_question"] = updated.get("current_question")
        resp["next_q_num"]    = cq+1
        resp["total_questions"] = tq
    return jsonify(resp)


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
    if not all_r:
        return jsonify({"total":0,"avg_score":0,"best_score":0,"grade":"N/A","roles":[]})
    scores = [r.get("overall_score",0) for r in all_r]
    avg    = round(sum(scores)/len(scores))
    grade  = "A" if avg>=90 else "B" if avg>=75 else "C" if avg>=60 else "D" if avg>=40 else "F"
    return jsonify({"total":len(all_r),"avg_score":avg,"best_score":max(scores),
                    "grade":grade,"roles":list(set(r.get("role","") for r in all_r))})


def _sim_question(role, q_type, q_num, total, prev):
    p = ("Avoid: "+" | ".join(prev[-3:])) if prev else ""
    try:
        q = ask_ollama([],
            f"Professional interviewer. {role}. {q_type}. Q{q_num}/{total}. {p} Output ONLY the question.").strip()
        return q or f"Tell me about yourself and your interest in {role}."
    except:
        return f"Describe a challenge relevant to the {role} role."

def _sim_fb(role, question, answer):
    prompt = f"""Evaluator. Role:{role}. Q:{question} A:{answer}
Format:
SCORE:[0-100]
GRADE:[A/B/C/D/F]
CLARITY:[1 sentence]
CONTENT:[1 sentence]
IMPROVEMENT:[1-2 suggestions]
BETTER_ANSWER:[2-3 sentence stronger version]
STRENGTH:[one strength]"""
    try:
        raw = ask_ollama([], prompt).strip()
        s_str = _ex(raw,"SCORE")
        try:    score = max(0,min(100,int("".join(filter(str.isdigit,s_str)))))
        except: score = 60
        grade = _ex(raw,"GRADE").upper()
        if grade not in ["A","B","C","D","F"]:
            grade = "A" if score>=90 else "B" if score>=75 else "C" if score>=60 else "D" if score>=40 else "F"
        return {"score":score,"grade":grade,"clarity":_ex(raw,"CLARITY"),
                "content":_ex(raw,"CONTENT"),"improvement":_ex(raw,"IMPROVEMENT"),
                "better_answer":_ex(raw,"BETTER_ANSWER"),"strength":_ex(raw,"STRENGTH")}
    except:
        return {"score":60,"grade":"C","clarity":"","content":"","improvement":"","better_answer":"","strength":""}

def _sim_overall(answers, role):
    scores = [a.get("feedback",{}).get("score",0) for a in answers]
    avg    = round(sum(scores)/len(scores)) if scores else 0
    grade  = "A" if avg>=90 else "B" if avg>=75 else "C" if avg>=60 else "D" if avg>=40 else "F"
    try:    summary = ask_ollama([], f"2-sentence encouraging summary. {role} interview. Score:{avg}/100. Mention strongest area and one thing to improve. Output summary only.").strip()
    except: summary = f"You scored {avg}/100. Keep practising to build confidence."
    return {"score":avg,"grade":grade,"summary":summary}
