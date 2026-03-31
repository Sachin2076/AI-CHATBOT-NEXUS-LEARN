"""
auth.py — User registration, login, and session helpers
"""

import bcrypt
from bson import ObjectId
from datetime import datetime, timezone
from db import users


def register_user(name: str, email: str, password: str) -> dict:
    """
    Create a new user. Returns the inserted user dict.
    Raises ValueError if email already exists.
    """
    email = email.lower().strip()
    if users().find_one({"email": email}):
        raise ValueError("An account with that email already exists.")

    pw_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    doc = {
        "name":         name.strip(),
        "email":        email,
        "password_hash": pw_hash,
        "created_at":   datetime.now(timezone.utc),
    }
    result = users().insert_one(doc)
    doc["_id"] = result.inserted_id
    return doc


def login_user(email: str, password: str) -> dict | None:
    """
    Verify credentials. Returns user dict on success, None on failure.
    """
    email = email.lower().strip()
    user  = users().find_one({"email": email})
    if not user:
        return None
    if not bcrypt.checkpw(password.encode("utf-8"), user["password_hash"]):
        return None
    return user


def get_user_by_id(user_id: str) -> dict | None:
    """Look up a user by their string ObjectId."""
    try:
        return users().find_one({"_id": ObjectId(user_id)})
    except Exception:
        return None
