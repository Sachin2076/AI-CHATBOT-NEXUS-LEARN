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
        "groups":       result,
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
#  SOCKETIO — REAL-TIME GROUP CHAT
# ═════════════════════════════════════════════════════════════

@socketio.on("connect")
def handle_connect():
    if not session.get("user_id"):
        return False  # reject unauthenticated connections


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
        emit("error", {"message": "Message too long (max 500 characters)."})
        return
    try:
        group = _groups().find_one({"_id": ObjectId(group_id)})
    except Exception:
        emit("error", {"message": "Invalid group ID."})
        return
    if not group or uid not in group.get("members", []):
        emit("error", {"message": "You must be a member to post messages."})
        return
    now = datetime.now(timezone.utc)
    doc = {
        "group_id":  group_id,
        "user_id":   uid,
        "user_name": session.get("user_name", "Student"),
        "text":      text,
        "posted_at": now,
    }
    _gmessages().insert_one(doc)
    emit("new_message", _serial(doc), to=group_id)


@socketio.on("leave_group")
def handle_leave_group(data):
    group_id = (data or {}).get("group_id", "")
    if group_id:
        leave_room(group_id)


@socketio.on("disconnect")
def handle_disconnect():
    pass