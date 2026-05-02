"""
utils.py — Shared helpers for Nexus Learn
Replaces duplicated _serial / _require_auth / _ex across all blueprints.
"""

import re
from bson import ObjectId
from datetime import datetime
from flask import session, jsonify


# ── Serialisation ─────────────────────────────────────────────

def serial(doc):
    """
    Recursively convert a MongoDB document to a JSON-safe dict.
    Handles: ObjectId → str, datetime → ISO str, bytes → UTF-8 str,
             nested dicts, nested lists containing ObjectIds.
    """
    if isinstance(doc, list):
        return [serial(i) for i in doc]
    if not isinstance(doc, dict):
        return doc
    out = {}
    for k, v in doc.items():
        if isinstance(v, ObjectId):
            out[k] = str(v)
        elif isinstance(v, datetime):
            out[k] = v.isoformat()
        elif isinstance(v, bytes):
            out[k] = v.decode("utf-8", errors="replace")
        elif isinstance(v, list):
            out[k] = [
                serial(i)      if isinstance(i, dict)     else
                str(i)         if isinstance(i, ObjectId) else
                i
                for i in v
            ]
        elif isinstance(v, dict):
            out[k] = serial(v)
        else:
            out[k] = v
    return out


# ── Auth ──────────────────────────────────────────────────────

def require_auth():
    """
    Read user_id from Flask session.
    Returns (user_id: str, None) on success.
    Returns (None, (Response, 401)) when not authenticated.
    """
    uid = session.get("user_id")
    if not uid:
        return None, (jsonify({"error": "Not authenticated"}), 401)
    return uid, None


# ── LLM output parser ─────────────────────────────────────────

def extract_field(raw: str, key: str) -> str:
    """
    Extract a named field from structured LLM output.

    Matches lines of the form:
        KEY: value (possibly multi-line)
    Stops at the next ALL_CAPS field or end of string.

    Examples
    --------
    >>> extract_field("SCORE: 87\\nGRADE: B", "SCORE")
    '87'
    >>> extract_field("COMMENT: line one\\nline two\\nNAME: Bob", "COMMENT")
    'line one\\nline two'
    """
    m = re.search(
        rf"{re.escape(key)}:\s*(.+?)(?=\n[A-Z_]{{2,}}:|$)",
        raw,
        re.DOTALL,
    )
    return m.group(1).strip() if m else ""