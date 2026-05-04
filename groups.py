"""
groups.py  —  Group Study Blueprint (Full Feature Upgrade)
===========================================================
Features:
  • Group CRUD (create / join / leave)
  • Real-time Socket.IO group chat
  • @AI trigger → LLaMA 3 reply injected into chat
  • Notice Board  (post / pin / AI summarise)
  • Shared Notes  (live socket sync)
  • Pomodoro Timer (socket-synced across members)
  • AI Quiz Generator (MCQ + short-answer)
  • Doubt Upvote system
  • Session Summary (AI key-points + weak areas)
"""

import re
import json
import os
import uuid
import threading
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, jsonify,
    request, session, redirect, url_for,
)
from flask_socketio import join_room, leave_room, emit
from bson import ObjectId

from db         import get_db
from utils      import serial as _serial, require_auth as _require_auth
from extensions import socketio
from llm        import ask_ollama

groups_bp = Blueprint("groups", __name__)


# ── DB helpers ────────────────────────────────────────────────

def _db():          return get_db()
def _groups():      return _db()["study_groups"]
def _gmessages():   return _db()["group_messages"]
def _notices():     return _db()["group_notices"]
def _notes():       return _db()["group_notes"]


def _ensure_indexes():
    _groups().create_index("name", unique=True)
    _groups().create_index("members")
    _gmessages().create_index([("group_id", 1), ("posted_at", -1)])
    _notices().create_index([("group_id", 1), ("posted_at", -1)])
    _notes().create_index([("group_id", 1)], unique=True)

try:
    _ensure_indexes()
except Exception:
    pass


# ══════════════════════════════════════════════════════════════
#  PAGE ROUTE
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/groups")
def groups_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("groups.html")


# ══════════════════════════════════════════════════════════════
#  API — LIST / CREATE
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups")
def api_list_groups():
    uid, err = _require_auth()
    if err: return err

    all_groups = list(_groups().find().sort("created_at", -1))
    result = []
    for g in all_groups:
        s = _serial(g)
        s["member_count"] = len(g.get("members", []))
        s["is_member"]    = uid in [str(m) for m in g.get("members", [])]
        result.append(s)

    my_group    = _groups().find_one({"members": uid})
    my_group_id = str(my_group["_id"]) if my_group else None

    return jsonify({
        "groups":      result,
        "my_group_id": my_group_id,
        "user_id":     uid,
        "user_name":   session.get("user_name", "Student"),
    })


@groups_bp.route("/api/groups", methods=["POST"])
def api_create_group():
    uid, err = _require_auth()
    if err: return err

    data  = request.get_json() or {}
    name  = data.get("name",  "").strip()
    topic = data.get("topic", "").strip()

    if not name:
        return jsonify({"error": "Group name is required."}), 400
    if not topic:
        return jsonify({"error": "Topic is required."}), 400
    if len(name) > 60:
        return jsonify({"error": "Group name too long (max 60 chars)."}), 400

    existing = _groups().find_one({"members": uid})
    if existing:
        return jsonify({"error": "You are already in a group. Leave it first."}), 409

    safe_name = re.escape(name)
    if _groups().find_one({"name": {"$regex": f"^{safe_name}$", "$options": "i"}}):
        return jsonify({"error": "A group with that name already exists."}), 409

    now = datetime.now(timezone.utc)
    doc = {
        "name":         name,
        "topic":        topic,
        "creator_id":   uid,
        "creator_name": session.get("user_name", "Student"),
        "members":      [uid],
        "member_names": {uid: session.get("user_name", "Student")},
        "created_at":   now,
    }
    result = _groups().insert_one(doc)
    doc["_id"] = result.inserted_id
    return jsonify({"group": _serial(doc), "message": "Group created!"}), 201


# ══════════════════════════════════════════════════════════════
#  API — JOIN / LEAVE
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/join", methods=["POST"])
def api_join_group(group_id):
    uid, err = _require_auth()
    if err: return err

    existing = _groups().find_one({"members": uid})
    if existing:
        if str(existing["_id"]) == group_id:
            return jsonify({"error": "You are already in this group."}), 409
        return jsonify({"error": "You are already in another group. Leave it first."}), 409

    try:
        oid = ObjectId(group_id)
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400

    group = _groups().find_one({"_id": oid})
    if not group:
        return jsonify({"error": "Group not found."}), 404

    uname = session.get("user_name", "Student")
    _groups().update_one(
        {"_id": oid},
        {"$addToSet": {"members": uid}, "$set": {f"member_names.{uid}": uname}},
    )
    return jsonify({"message": f"Joined '{group['name']}' successfully!"})


@groups_bp.route("/api/groups/<group_id>/leave", methods=["POST"])
def api_leave_group(group_id):
    uid, err = _require_auth()
    if err: return err

    try:
        oid = ObjectId(group_id)
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400

    group = _groups().find_one({"_id": oid})
    if not group:
        return jsonify({"error": "Group not found."}), 404
    if uid not in group.get("members", []):
        return jsonify({"error": "You are not in this group."}), 400

    _groups().update_one(
        {"_id": oid},
        {"$pull": {"members": uid}, "$unset": {f"member_names.{uid}": ""}},
    )

    updated = _groups().find_one({"_id": oid})
    if updated and len(updated.get("members", [])) == 0:
        _groups().delete_one({"_id": oid})
        _gmessages().delete_many({"group_id": group_id})
        _notices().delete_many({"group_id": group_id})
        _notes().delete_one({"group_id": group_id})
        return jsonify({"message": "You left the group. Group was deleted (no members left)."})

    return jsonify({"message": "You left the group."})


# ══════════════════════════════════════════════════════════════
#  API — GROUP DETAIL
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>")
def api_get_group(group_id):
    uid, err = _require_auth()
    if err: return err

    try:
        oid = ObjectId(group_id)
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400

    group = _groups().find_one({"_id": oid})
    if not group:
        return jsonify({"error": "Group not found."}), 404

    s = _serial(group)
    s["is_member"]    = uid in group.get("members", [])
    s["member_count"] = len(group.get("members", []))
    mn = group.get("member_names", {})
    s["members_list"] = [{"id": k, "name": v} for k, v in mn.items()]
    return jsonify({"group": s})


# ══════════════════════════════════════════════════════════════
#  API — MESSAGES (REST)
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/messages")
def api_get_messages(group_id):
    uid, err = _require_auth()
    if err: return err

    group = _groups().find_one({"_id": ObjectId(group_id)})
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "You must be a member to view messages."}), 403

    msgs = list(
        _gmessages().find({"group_id": group_id}).sort("posted_at", 1).limit(100)
    )
    return jsonify({"messages": [_serial(m) for m in msgs]})


@groups_bp.route("/api/groups/<group_id>/messages", methods=["POST"])
def api_post_message(group_id):
    uid, err = _require_auth()
    if err: return err

    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400

    if not group or uid not in group.get("members", []):
        return jsonify({"error": "You must be a member to post messages."}), 403

    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Message cannot be empty."}), 400
    if len(text) > 500:
        return jsonify({"error": "Message too long (max 500 characters)."}), 400

    now = datetime.now(timezone.utc)
    doc = {
        "group_id":   group_id,
        "user_id":    uid,
        "user_name":  session.get("user_name", "Student"),
        "text":       text,
        "posted_at":  now,
        "upvotes":    0,
        "upvoted_by": [],
        "is_ai":      False,
    }
    _gmessages().insert_one(doc)
    return jsonify({"message": _serial(doc)}), 201


# ══════════════════════════════════════════════════════════════
#  API — UPVOTE (Doubt System)
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/messages/<msg_id>/upvote", methods=["POST"])
def api_upvote_message(group_id, msg_id):
    """Toggle upvote on a group message. Each user can upvote once."""
    uid, err = _require_auth()
    if err: return err

    try:
        oid = ObjectId(msg_id)
    except Exception:
        return jsonify({"error": "Invalid message ID."}), 400

    msg = _gmessages().find_one({"_id": oid, "group_id": group_id})
    if not msg:
        return jsonify({"error": "Message not found."}), 404

    upvoted_by = msg.get("upvoted_by", [])
    if uid in upvoted_by:
        _gmessages().update_one(
            {"_id": oid},
            {"$pull": {"upvoted_by": uid}, "$inc": {"upvotes": -1}},
        )
        upvoted = False
    else:
        _gmessages().update_one(
            {"_id": oid},
            {"$addToSet": {"upvoted_by": uid}, "$inc": {"upvotes": 1}},
        )
        upvoted = True

    updated = _gmessages().find_one({"_id": oid})
    count   = updated.get("upvotes", 0)

    socketio.emit("upvote_update", {
        "msg_id":  msg_id,
        "upvotes": count,
        "upvoted": upvoted,
        "user_id": uid,
    }, to=group_id)

    return jsonify({"upvotes": count, "upvoted": upvoted})


# ══════════════════════════════════════════════════════════════
#  API — NOTICE BOARD
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/notices")
def api_get_notices(group_id):
    uid, err = _require_auth()
    if err: return err
    group = _groups().find_one({"_id": ObjectId(group_id)})
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403
    notices = list(
        _notices().find({"group_id": group_id})
        .sort([("pinned", -1), ("posted_at", -1)])
        .limit(50)
    )
    return jsonify({"notices": [_serial(n) for n in notices]})


@groups_bp.route("/api/groups/<group_id>/notices", methods=["POST"])
def api_post_notice(group_id):
    uid, err = _require_auth()
    if err: return err
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403
    data = request.get_json() or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Notice cannot be empty."}), 400
    if len(text) > 800:
        return jsonify({"error": "Notice too long (max 800 chars)."}), 400
    now = datetime.now(timezone.utc)
    doc = {
        "group_id":  group_id,
        "user_id":   uid,
        "user_name": session.get("user_name", "Student"),
        "text":      text,
        "posted_at": now,
        "pinned":    False,
    }
    result = _notices().insert_one(doc)
    doc["_id"] = result.inserted_id
    s = _serial(doc)
    socketio.emit("new_notice", s, to=group_id)
    return jsonify({"notice": s}), 201


@groups_bp.route("/api/groups/<group_id>/notices/<notice_id>/pin", methods=["POST"])
def api_pin_notice(group_id, notice_id):
    uid, err = _require_auth()
    if err: return err
    try:
        oid   = ObjectId(notice_id)
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid ID."}), 400
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403
    notice = _notices().find_one({"_id": oid, "group_id": group_id})
    if not notice:
        return jsonify({"error": "Notice not found."}), 404
    new_pin = not notice.get("pinned", False)
    _notices().update_one({"_id": oid}, {"$set": {"pinned": new_pin}})
    socketio.emit("notice_pinned", {"notice_id": notice_id, "pinned": new_pin}, to=group_id)
    return jsonify({"pinned": new_pin})


@groups_bp.route("/api/groups/<group_id>/notices/ai-summarise", methods=["POST"])
def api_summarise_notices(group_id):
    uid, err = _require_auth()
    if err: return err
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403
    notices = list(_notices().find({"group_id": group_id}).sort("posted_at", -1).limit(20))
    if not notices:
        return jsonify({"summary": "No notices to summarise yet."})
    notice_text = "\n".join([
        f"[{'PINNED' if n.get('pinned') else 'Notice'}] {n['user_name']}: {n['text']}"
        for n in notices
    ])
    prompt = (
        f"Study group notice board (Topic: {group.get('topic', 'General')}):\n\n"
        f"{notice_text}\n\n"
        "Summarise in 3-4 bullet points. Highlight urgent/pinned items. Be concise."
    )
    try:
        summary = ask_ollama(history=[], user_message=prompt)
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  API — SHARED NOTES
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/notes")
def api_get_notes(group_id):
    uid, err = _require_auth()
    if err: return err
    group = _groups().find_one({"_id": ObjectId(group_id)})
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403
    note = _notes().find_one({"group_id": group_id})
    if not note:
        return jsonify({"content": "", "last_editor": "", "last_updated": None})
    return jsonify({
        "content":      note.get("content", ""),
        "last_editor":  note.get("last_editor", ""),
        "last_updated": note.get("last_updated", "").isoformat() if note.get("last_updated") else None,
    })


@groups_bp.route("/api/groups/<group_id>/notes", methods=["POST"])
def api_save_notes(group_id):
    uid, err = _require_auth()
    if err: return err
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403
    data    = request.get_json() or {}
    content = data.get("content", "")
    if len(content) > 20000:
        return jsonify({"error": "Notes too long (max 20000 chars)."}), 400
    now  = datetime.now(timezone.utc)
    name = session.get("user_name", "Student")
    _notes().update_one(
        {"group_id": group_id},
        {"$set": {"content": content, "last_editor": name, "last_updated": now, "group_id": group_id}},
        upsert=True,
    )
    socketio.emit("notes_updated", {
        "content":     content,
        "last_editor": name,
        "updated_at":  now.isoformat(),
    }, to=group_id)
    return jsonify({"status": "saved", "last_editor": name})


# ══════════════════════════════════════════════════════════════
#  API — AI QUIZ GENERATOR
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/quiz", methods=["POST"])
def api_generate_quiz(group_id):
    uid, err = _require_auth()
    if err: return err
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403
    data   = request.get_json() or {}
    source = data.get("source", "topic")
    count  = min(int(data.get("count", 5)), 10)
    topic  = group.get("topic", "General Knowledge")

    if source == "chat":
        recent = list(
            _gmessages().find({"group_id": group_id, "is_ai": {"$ne": True}})
            .sort("posted_at", -1).limit(20)
        )
        recent.reverse()
        context = "\n".join([f"{m['user_name']}: {m['text']}" for m in recent])
        prompt_source = f"the following group study discussion:\n\n{context}"
    else:
        prompt_source = f"the topic: {topic}"

    prompt = (
        f"Generate a quiz with {count} questions based on {prompt_source}.\n\n"
        "Return ONLY valid JSON (no markdown, no extra text):\n"
        '{"topic":"...","questions":[{"id":1,"type":"mcq","question":"...",'
        '"options":["A) ...","B) ...","C) ...","D) ..."],"answer":"A","explanation":"..."},'
        '{"id":2,"type":"short","question":"...","answer":"...","explanation":"..."}]}\n\n'
        "Mix MCQ and short-answer. Make questions clear and educational."
    )

    try:
        raw   = ask_ollama(history=[], user_message=prompt)
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return jsonify({"error": "AI returned invalid format. Try again."}), 500
        quiz  = json.loads(match.group())
        return jsonify({"quiz": quiz})
    except json.JSONDecodeError:
        return jsonify({"error": "Failed to parse quiz. Try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  API — SESSION SUMMARY
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/summary", methods=["POST"])
def api_session_summary(group_id):
    uid, err = _require_auth()
    if err: return err
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Members only."}), 403

    msgs = list(_gmessages().find({"group_id": group_id}).sort("posted_at", -1).limit(50))
    msgs.reverse()
    if len(msgs) < 3:
        return jsonify({"error": "Need at least 3 messages to summarise."}), 400

    top_doubts = sorted(
        [m for m in msgs if m.get("upvotes", 0) > 0],
        key=lambda x: x.get("upvotes", 0), reverse=True
    )[:5]

    chat_text  = "\n".join([f"{m['user_name']}: {m['text']}" for m in msgs])
    doubt_text = "\n".join([
        f"- ({m.get('upvotes',0)} upvotes) {m['user_name']}: {m['text']}"
        for m in top_doubts
    ]) if top_doubts else "None"

    prompt = (
        f"Group: {group.get('name','Group')} | Topic: {group.get('topic','General')}\n\n"
        f"Chat:\n{chat_text}\n\nTop doubts:\n{doubt_text}\n\n"
        "Write a concise session summary with these EXACT sections:\n"
        "**KEY POINTS:**\n- (3-5 bullets)\n\n"
        "**IMPORTANT QUESTIONS:**\n- (2-3 bullets)\n\n"
        "**WEAK AREAS TO REVIEW:**\n- (2-3 bullets)\n\n"
        "**NEXT STEPS:**\n- (1-2 bullets)"
    )

    try:
        summary = ask_ollama(history=[], user_message=prompt)
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════
#  SOCKETIO EVENTS
# ══════════════════════════════════════════════════════════════

@socketio.on("connect")
def handle_connect():
    if not session.get("user_id"):
        return False


@socketio.on("join_group")
def handle_join_group(data):
    uid      = session.get("user_id")
    group_id = (data or {}).get("group_id", "")
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        emit("error", {"message": "Invalid group ID."})
        return
    if not group or uid not in group.get("members", []):
        emit("error", {"message": "You must be a member to join this room."})
        return
    join_room(group_id)
    emit("joined", {"group_id": group_id, "name": group["name"]})


@socketio.on("send_message")
def handle_send_message(data):
    """Handle real-time message. @AI prefix triggers LLaMA 3."""
    uid = session.get("user_id")
    if not uid:
        emit("error", {"message": "Unauthorized."})
        return
    data     = data or {}
    group_id = data.get("group_id", "")
    text     = data.get("text", "").strip()
    if not text:
        emit("error", {"message": "Message cannot be empty."})
        return
    if len(text) > 500:
        emit("error", {"message": "Message too long."})
        return
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        emit("error", {"message": "Invalid group ID."})
        return
    if not group or uid not in group.get("members", []):
        emit("error", {"message": "You must be a member."})
        return

    now  = datetime.now(timezone.utc)
    name = session.get("user_name", "Student")
    doc  = {
        "group_id":   group_id,
        "user_id":    uid,
        "user_name":  name,
        "text":       text,
        "posted_at":  now,
        "upvotes":    0,
        "upvoted_by": [],
        "is_ai":      False,
    }
    _gmessages().insert_one(doc)
    emit("new_message", _serial(doc), to=group_id)

    # ── @AI trigger ──────────────────────────────────────────
    ai_match = re.match(r"@AI\s+(.+)", text, re.IGNORECASE | re.DOTALL)
    if ai_match:
        question    = ai_match.group(1).strip()
        group_topic = group.get("topic", "General")
        emit("ai_typing", {"typing": True}, to=group_id)

        def _bg_ai():
            try:
                recent = list(
                    _gmessages().find({"group_id": group_id})
                    .sort("posted_at", -1).limit(9)
                )
                recent.reverse()
                context = "\n".join([
                    f"{m['user_name']}: {m['text']}"
                    for m in recent if m.get("text") != text
                ])[-1000:]

                # ── RAG: retrieve relevant file context ──────────
                rag_context = ""
                try:
                    from rag import retrieve_context
                    rag_context = retrieve_context(question, topic=f"group_{group_id}", n=3)
                except Exception:
                    pass

                history = []
                if rag_context:
                    history.append({"role": "user", "content":
                        f"[Relevant document context for this group]\n{rag_context[:1200]}"})
                    history.append({"role": "assistant", "content":
                        "Understood — I have this document context available."})
                if context:
                    history.append({"role": "user", "content":
                        f"[Group Study Chat — Topic: {group_topic}]\n{context}"})

                GROUP_SYSTEM = (
                    "You are Nexus AI, a helpful study assistant inside a group chat. "
                    "Answer questions clearly and concisely. "
                    "Do NOT generate learning packages, weekly plans, MCQs, or structured study formats. "
                    "Just answer the question directly like a knowledgeable study buddy. "
                    "Use markdown (bold, bullet points, code blocks) where helpful. "
                    "Keep answers focused and reasonably short unless depth is needed."
                )

                import requests as _req, os as _os
                OLLAMA_URL   = _os.environ.get("OLLAMA_URL",   "http://localhost:11434")
                OLLAMA_MODEL = _os.environ.get("OLLAMA_MODEL", "llama3")

                prompt_parts = [f"[SYSTEM]\n{GROUP_SYSTEM}\n"]
                if rag_context:
                    prompt_parts.append(f"[Document context from uploaded group files]\n{rag_context[:1200]}\n")
                if context:
                    prompt_parts.append(f"[Recent group chat]\n{context}\n")
                prompt_parts.append(f"[Question from {name}]\n{question}\nNexus AI:")

                _payload = {
                    "model":  OLLAMA_MODEL,
                    "prompt": "\n".join(prompt_parts),
                    "stream": False,
                    "options": {"temperature": 0.6, "top_p": 0.9, "num_predict": 512},
                }
                _resp  = _req.post(f"{OLLAMA_URL}/api/generate", json=_payload, timeout=120)
                _resp.raise_for_status()
                reply  = _resp.json().get("response", "").strip() or "Sorry, I couldn't generate a reply."
                ai_now = datetime.now(timezone.utc)
                ai_doc = {
                    "group_id":   group_id,
                    "user_id":    "ai",
                    "user_name":  "🤖 Nexus AI",
                    "text":       reply,
                    "posted_at":  ai_now,
                    "is_ai":      True,
                    "upvotes":    0,
                    "upvoted_by": [],
                }
                _gmessages().insert_one(ai_doc)
                socketio.emit("ai_typing",   {"typing": False}, to=group_id)
                socketio.emit("new_message", _serial(ai_doc), to=group_id)
            except Exception as e:
                socketio.emit("ai_typing", {"typing": False}, to=group_id)
                socketio.emit("ai_error",  {"message": str(e)}, to=group_id)

        threading.Thread(target=_bg_ai, daemon=True).start()


@socketio.on("leave_group")
def handle_leave_group(data):
    group_id = (data or {}).get("group_id", "")
    if group_id:
        leave_room(group_id)


@socketio.on("disconnect")
def handle_disconnect():
    pass


@socketio.on("timer_action")
def handle_timer_action(data):
    """Sync Pomodoro timer (start/pause/reset) across all members."""
    uid = session.get("user_id")
    if not uid:
        return
    data      = data or {}
    group_id  = data.get("group_id", "")
    action    = data.get("action", "")
    time_left = data.get("time_left", 1500)
    mode      = data.get("mode", "study")
    if group_id and action in ("start", "pause", "reset", "sync"):
        emit("timer_sync", {
            "action":    action,
            "time_left": time_left,
            "mode":      mode,
            "by":        session.get("user_name", "Someone"),
        }, to=group_id)


@socketio.on("notes_typing")
def handle_notes_typing(data):
    """Broadcast notes editing indicator to other members."""
    uid = session.get("user_id")
    if not uid:
        return
    data     = data or {}
    group_id = data.get("group_id", "")
    if group_id:
        emit("notes_editor", {
            "editor": session.get("user_name", "Someone"),
            "typing": data.get("typing", False),
        }, to=group_id, include_self=False)


# ──────────────────────────────────────────────────────────
#  FILE UPLOAD + RAG  (PDF / TXT ingestion for group context)
# ──────────────────────────────────────────────────────────
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXT = {".pdf", ".txt", ".md"}
MAX_BYTES   = 5 * 1024 * 1024   # 5 MB


def _extract_text(path: str) -> str:
    """Extract plain text from PDF or text files (lightweight)."""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(path)
            return "\n".join(p.extract_text() or "" for p in reader.pages)
        except ImportError:
            pass
        try:
            import pdfminer.high_level as pdfminer
            return pdfminer.extract_text(path)
        except Exception:
            return ""
    # .txt / .md
    with open(path, "r", errors="ignore") as f:
        return f.read()


def _chunk_text(text: str, size: int = 400, overlap: int = 60) -> list[str]:
    """Split text into overlapping chunks."""
    words  = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunks.append(" ".join(words[i: i + size]))
        i += size - overlap
    return [c for c in chunks if c.strip()]


def _ingest_file_background(file_path: str, group_id: str, file_name: str, doc_id: str):
    """Background: extract text → chunk → embed into ChromaDB under group topic."""
    try:
        from rag import embed_documents
        text   = _extract_text(file_path)
        if not text.strip():
            return
        chunks = _chunk_text(text)
        docs   = [
            {"id": f"{doc_id}_{i}", "text": c, "topic": f"group_{group_id}"}
            for i, c in enumerate(chunks)
        ]
        embed_documents(docs)
        # Record in MongoDB
        db = get_db()
        db.group_files.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "ready", "chunks": len(chunks)}}
        )
    except Exception as e:
        db = get_db()
        db.group_files.update_one(
            {"_id": ObjectId(doc_id)},
            {"$set": {"status": "error", "error": str(e)}}
        )


@groups_bp.route("/api/groups/<group_id>/files", methods=["GET"])
def list_group_files(group_id):
    """List uploaded files for a group."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "auth"}), 401
    db    = get_db()
    files = list(db.group_files.find({"group_id": group_id}, {"file_path": 0}))
    return jsonify({"files": _serial(files)})


@groups_bp.route("/api/groups/<group_id>/files", methods=["POST"])
def upload_group_file(group_id):
    """Upload a PDF/TXT file, extract text, and embed into group RAG context."""
    uid   = session.get("user_id")
    uname = session.get("user_name", "Unknown")
    if not uid:
        return jsonify({"error": "auth"}), 401

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    f    = request.files["file"]
    name = f.filename or "upload"
    ext  = os.path.splitext(name)[1].lower()

    if ext not in ALLOWED_EXT:
        return jsonify({"error": "Only PDF, TXT, and MD files are allowed"}), 400

    # Save file
    safe_name = f"{uuid.uuid4().hex}{ext}"
    path      = os.path.join(UPLOAD_DIR, safe_name)
    f.save(path)

    if os.path.getsize(path) > MAX_BYTES:
        os.remove(path)
        return jsonify({"error": "File too large (max 5 MB)"}), 400

    db  = get_db()
    doc = {
        "group_id":   group_id,
        "file_name":  name,
        "file_path":  path,
        "uploaded_by": uid,
        "uploader_name": uname,
        "status":     "processing",
        "chunks":     0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    result = db.group_files.insert_one(doc)
    doc_id = str(result.inserted_id)

    # Process in background thread
    threading.Thread(
        target=_ingest_file_background,
        args=(path, group_id, name, doc_id),
        daemon=True
    ).start()

    return jsonify({"ok": True, "file_id": doc_id, "file_name": name, "status": "processing"})


@groups_bp.route("/api/groups/<group_id>/files/<file_id>", methods=["DELETE"])
def delete_group_file(group_id, file_id):
    """Delete a file and its embeddings from the group context."""
    uid = session.get("user_id")
    if not uid:
        return jsonify({"error": "auth"}), 401
    db  = get_db()
    doc = db.group_files.find_one({"_id": ObjectId(file_id), "group_id": group_id})
    if not doc:
        return jsonify({"error": "not found"}), 404
    # Remove file from disk
    try:
        if os.path.exists(doc["file_path"]):
            os.remove(doc["file_path"])
    except Exception:
        pass
    # Remove embeddings from ChromaDB
    try:
        from rag import _collection
        ids_to_del = [r["id"] for r in _collection.get(where={"topic": f"group_{group_id}"}).get("ids", [])]
        prefix = file_id + "_"
        ids_to_del = [i for i in ids_to_del if i.startswith(prefix)]
        if ids_to_del:
            _collection.delete(ids=ids_to_del)
    except Exception:
        pass
    db.group_files.delete_one({"_id": ObjectId(file_id)})
    return jsonify({"ok": True})