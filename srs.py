"""
srs.py — SM-2 spaced repetition algorithm
"""

from datetime import datetime, timezone, timedelta


def _default_record(user_id: str, topic: str) -> dict:
    return {
        "user_id":     user_id,
        "topic":       topic,
        "ease_factor": 2.5,
        "interval":    1,
        "repetitions": 0,
        "next_review": datetime.now(timezone.utc),
    }


def update_srs(current_record: dict, score_percent: int) -> dict:
    """
    Apply SM-2 update rules to current_record given a quiz score percentage.
    Returns a new dict with updated fields (does not mutate the input).
    """
    rec = dict(current_record)
    ef  = rec.get("ease_factor", 2.5)
    iv  = rec.get("interval", 1)
    reps = rec.get("repetitions", 0)

    if score_percent < 60:
        iv   = 1
        reps = 0
    elif score_percent < 80:
        # keep ease_factor and interval unchanged, just advance next_review
        pass
    else:
        # score >= 80%: increase interval and ease_factor
        if reps == 0:
            iv = 1
        elif reps == 1:
            iv = 6
        else:
            iv = round(iv * ef)
        ef   = round(ef + 0.1, 2)
        reps += 1

    rec["ease_factor"] = ef
    rec["interval"]    = iv
    rec["repetitions"] = reps
    rec["next_review"] = datetime.now(timezone.utc) + timedelta(days=iv)
    return rec


def get_due_topics(user_id: str, db) -> list[str]:
    """
    Returns topic names whose next_review is on or before the current UTC time.
    """
    now = datetime.now(timezone.utc)
    cursor = db["srs_records"].find(
        {"user_id": user_id, "next_review": {"$lte": now}},
        {"topic": 1, "_id": 0},
    )
    return [doc["topic"] for doc in cursor]
