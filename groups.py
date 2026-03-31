"""
groups.py — Collaborative Study Groups Blueprint
=================================================
Register in app.py with:
    from groups import groups_bp
    app.register_blueprint(groups_bp)
"""

from flask import Blueprint, render_template, jsonify, request, session
from bson import ObjectId
from datetime import datetime, timezone
from db import get_db

groups_bp = Blueprint("groups", __name__)


# ── Helpers ───────────────────────────────────────────────────

def _db():
    return get_db()

def _groups():
    return _db()["study_groups"]

def _gmessages():
    return _db()["group_messages"]

def _require_auth():
    uid = session.get("user_id")
    if not uid:
        return None, (jsonify({"error": "Not authenticated"}), 401)
    return uid, None

def _serial(doc):
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, list):
            out[k] = [_serial(i) if isinstance(i, dict) else
                      str(i) if isinstance(i, ObjectId) else i
                      for i in v]
        else:
            out[k] = v
    return out

def _ensure_indexes():
    """Call once on startup to create indexes."""
    _groups().create_index("name", unique=True)
    _groups().create_index("members")
    _gmessages().create_index([("group_id", 1), ("posted_at", -1)])

# Create indexes when module loads
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
        from flask import redirect, url_for
        return redirect(url_for("login_page"))
    return render_template("groups.html")


# ══════════════════════════════════════════════════════════════
#  API — LIST ALL GROUPS
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

    # Find which group current user is in
    my_group = _groups().find_one({"members": uid})
    my_group_id = str(my_group["_id"]) if my_group else None

    return jsonify({
        "groups":      result,
        "my_group_id": my_group_id,
        "user_id":     uid,
        "user_name":   session.get("user_name", "Student"),
    })


# ══════════════════════════════════════════════════════════════
#  API — CREATE GROUP
# ══════════════════════════════════════════════════════════════

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

    # Check user is not already in a group
    existing = _groups().find_one({"members": uid})
    if existing:
        return jsonify({"error": "You are already in a group. Leave it first."}), 409

    # Check name not taken
    if _groups().find_one({"name": {"$regex": f"^{name}$", "$options": "i"}}):
        return jsonify({"error": "A group with that name already exists."}), 409

    now = datetime.now(timezone.utc)
    doc = {
        "name":       name,
        "topic":      topic,
        "creator_id": uid,
        "creator_name": session.get("user_name", "Student"),
        "members":    [uid],
        "member_names": {uid: session.get("user_name", "Student")},
        "created_at": now,
    }
    result = _groups().insert_one(doc)
    doc["_id"] = result.inserted_id

    return jsonify({"group": _serial(doc), "message": "Group created!"}), 201


# ══════════════════════════════════════════════════════════════
#  API — JOIN GROUP
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/join", methods=["POST"])
def api_join_group(group_id):
    uid, err = _require_auth()
    if err: return err

    # Check user not already in a group
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
        {
            "$addToSet": {"members": uid},
            "$set":      {f"member_names.{uid}": uname}
        }
    )
    return jsonify({"message": f"Joined '{group['name']}' successfully!"})


# ══════════════════════════════════════════════════════════════
#  API — LEAVE GROUP
# ══════════════════════════════════════════════════════════════

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
        {
            "$pull": {"members": uid},
            "$unset": {f"member_names.{uid}": ""}
        }
    )

    # If group is now empty, delete it
    updated = _groups().find_one({"_id": oid})
    if updated and len(updated.get("members", [])) == 0:
        _groups().delete_one({"_id": oid})
        _gmessages().delete_many({"group_id": group_id})
        return jsonify({"message": "You left the group. Group was deleted (no members left)."})

    return jsonify({"message": "You left the group."})


# ══════════════════════════════════════════════════════════════
#  API — GET GROUP DETAIL
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

    # Get member names as list
    mn = group.get("member_names", {})
    s["members_list"] = [{"id": k, "name": v} for k, v in mn.items()]

    return jsonify({"group": s})


# ══════════════════════════════════════════════════════════════
#  API — GET MESSAGES
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/messages")
def api_get_messages(group_id):
    uid, err = _require_auth()
    if err: return err

    # Verify user is in this group
    group = _groups().find_one({"_id": ObjectId(group_id)})
    if not group or uid not in group.get("members", []):
        return jsonify({"error": "You must be a member to view messages."}), 403

    msgs = list(
        _gmessages()
        .find({"group_id": group_id})
        .sort("posted_at", 1)
        .limit(100)
    )
    return jsonify({"messages": [_serial(m) for m in msgs]})


# ══════════════════════════════════════════════════════════════
#  API — POST MESSAGE
# ══════════════════════════════════════════════════════════════

@groups_bp.route("/api/groups/<group_id>/messages", methods=["POST"])
def api_post_message(group_id):
    uid, err = _require_auth()
    if err: return err

    # Verify user is in this group
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
    }
    _gmessages().insert_one(doc)
    return jsonify({"message": _serial(doc)}), 201
