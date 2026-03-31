"""
db.py — MongoDB connection + collection accessors
"""

import os
from pymongo import MongoClient, ASCENDING, DESCENDING

_client = None
_db     = None

def get_db():
    global _client, _db
    if _db is not None:
        return _db
    uri  = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
    _client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    _client.admin.command("ping")
    _db = _client["nexus_learn"]
    _ensure_indexes(_db)
    return _db

def _ensure_indexes(db):
    db.users.create_index("email", unique=True)
    db.messages.create_index([("user_id", ASCENDING), ("session_id", ASCENDING), ("timestamp", DESCENDING)])
    db.chat_sessions.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.planner_tasks.create_index([("user_id", ASCENDING), ("day", ASCENDING)])
    db.usage_logs.create_index([("user_id", ASCENDING), ("date", ASCENDING)], unique=True)
    db.practice_sets.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    db.quiz_results.create_index([("user_id", ASCENDING), ("practice_set_id", ASCENDING)])
    db.motivations.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

def users():          return get_db()["users"]
def messages():       return get_db()["messages"]
def planner():        return get_db()["planner_tasks"]
def usage_logs():     return get_db()["usage_logs"]
def chat_sessions():  return get_db()["chat_sessions"]
def practice_sets():  return get_db()["practice_sets"]
def quiz_results():   return get_db()["quiz_results"]
def motivations():    return get_db()["motivations"]