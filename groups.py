"""
groups.py — Collaborative Study Groups Blueprint
Changes vs original:
  Gap 3 — /api/groups/<id>/stream  SSE endpoint (3-second polling, 30s timeout)
  Gap 4 — serial/_require_auth imported from utils (no local copies)
"""

import json
import time
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, jsonify,
    request, session, redirect, url_for,
    Response, stream_with_context,
)
from bson import ObjectId

from db    import get_db
from utils import serial as _serial, require_auth as _require_auth   # Gap 4

groups_bp = Blueprint("groups", __name__)


# ── DB helpers ────────────────────────────────────────────────

def _db():         return get_db()
def _groups():     return _db()["study_groups"]
def _gmessages():  return _db()["group_messages"]

def _ensure_indexes():
    _groups().create_index("name", unique=True)
    _groups().create_index("members")
    _gmessages().create_index([("group_id", 1), ("posted_at", -1)])

try:
    _ensure_indexes()
except Exception:
    pass


# ═════════════════════════════════════════════════════════════
#  PAGE ROUTE
# ═════════════════════════════════════════════════════════════

@groups_bp.route("/groups")
def groups_page():
    if not session.get("user_id"):
        return redirect(url_for("login_page"))
    return render_template("groups.html")


# ═════════════════════════════════════════════════════════════
#  API — LIST / CREATE
# ═════════════════════════════════════════════════════════════

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

    if _groups().find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}):
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


# ═════════════════════════════════════════════════════════════
#  API — JOIN / LEAVE
# ═════════════════════════════════════════════════════════════

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
        return jsonify({"message": "You left the group. Group was deleted (no members left)."})

    return jsonify({"message": "You left the group."})


# ═════════════════════════════════════════════════════════════
#  API — GROUP DETAIL
# ═════════════════════════════════════════════════════════════

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


# ═════════════════════════════════════════════════════════════
#  API — MESSAGES (REST)
# ═════════════════════════════════════════════════════════════

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
        "group_id":  group_id,
        "user_id":   uid,
        "user_name": session.get("user_name", "Student"),
        "text":      text,
        "posted_at": now,
    }
    _gmessages().insert_one(doc)
    return jsonify({"message": _serial(doc)}), 201


# ═════════════════════════════════════════════════════════════
#  API — SSE REAL-TIME STREAM (Gap 3)
# ═════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/stream")
def api_group_stream(group_id):
    """
    Server-Sent Events endpoint for real-time group chat.

    The client connects via EventSource; the server polls MongoDB every 3 s
    for new messages and pushes them as SSE events.  After 30 seconds the
    server sends a {timeout: true} event and the client auto-reconnects,
    keeping the connection fresh without tying up workers indefinitely.

    Query param:
      ?since=<ISO-timestamp>   — only return messages newer than this

    SSE event format (each new message):
      data: {<serialised message doc>}\n\n

    Heartbeat (no new messages):
      : heartbeat\n\n

    Timeout signal (client must reconnect):
      data: {"timeout": true}\n\n
    """
    uid, err = _require_auth()
    if err: return err

    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        return jsonify({"error": "Invalid group ID."}), 400

    if not group or uid not in group.get("members", []):
        return jsonify({"error": "Must be a member to stream messages."}), 403

    since_param = request.args.get("since", "")
    try:
        last_seen = datetime.fromisoformat(since_param.replace("Z", "+00:00")) \
                    if since_param else None
    except ValueError:
        last_seen = None

    def event_stream():
        nonlocal last_seen
        deadline = time.time() + 30   # 30-second connection lifetime

        while time.time() < deadline:
            query = {"group_id": group_id}
            if last_seen:
                query["posted_at"] = {"$gt": last_seen}

            new_msgs = list(
                _gmessages().find(query).sort("posted_at", 1).limit(20)
            )

            for msg in new_msgs:
                last_seen = msg["posted_at"]
                yield f"data: {json.dumps(_serial(msg))}\n\n"

            if not new_msgs:
                yield ": heartbeat\n\n"   # SSE comment — keeps connection alive

            time.sleep(3)

        yield f"data: {json.dumps({'timeout': True})}\n\n"

    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control":     "no-cache",
            "X-Accel-Buffering": "no",
        },
    )