"""
tests/test_routes.py — Flask route integration tests (Gap 5)

Covers: authentication guards, input validation, API contracts.
All MongoDB and Ollama calls are mocked so tests run without
any external services.

Run with:
    pytest tests/test_routes.py -v
"""

import pytest
import json
from unittest.mock import patch, MagicMock


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """Create Flask test app with DB and Ollama mocked out."""
    with patch("db.MongoClient"), \
         patch("db._ensure_indexes", return_value=None), \
         patch("groups._ensure_indexes", return_value=None), \
         patch("interview._ensure_indexes", return_value=None):
        import app as flask_app_module
        flask_app_module.app.config["TESTING"]   = True
        flask_app_module.app.config["SECRET_KEY"] = "test-secret"
        yield flask_app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def authed_client(client):
    """A client whose session contains a valid user_id."""
    with client.session_transaction() as sess:
        sess["user_id"]    = "507f1f77bcf86cd799439011"
        sess["user_name"]  = "Test Student"
        sess["user_email"] = "test@nexus.dev"
    return client


# ═════════════════════════════════════════════════════════════
#  PAGE ROUTES
# ═════════════════════════════════════════════════════════════

class TestPageRoutes:

    def test_index_returns_200(self, client):
        r = client.get("/")
        assert r.status_code == 200

    def test_login_page_returns_200(self, client):
        r = client.get("/login")
        assert r.status_code == 200

    def test_register_page_returns_200(self, client):
        r = client.get("/register")
        assert r.status_code == 200

    def test_dashboard_redirects_when_unauthenticated(self, client):
        r = client.get("/dashboard")
        assert r.status_code == 302
        assert "/login" in r.headers["Location"]

    def test_chat_page_redirects_when_unauthenticated(self, client):
        r = client.get("/chat")
        assert r.status_code == 302

    def test_planner_page_redirects_when_unauthenticated(self, client):
        r = client.get("/planner")
        assert r.status_code == 302

    def test_dashboard_accessible_when_authenticated(self, authed_client):
        r = authed_client.get("/dashboard")
        assert r.status_code == 200


# ═════════════════════════════════════════════════════════════
#  AUTH API
# ═════════════════════════════════════════════════════════════

class TestAuthAPI:

    def test_api_me_requires_auth(self, client):
        r = client.get("/api/me")
        assert r.status_code == 401
        assert b"Not authenticated" in r.data

    def test_api_me_returns_user_when_authed(self, authed_client):
        with patch("app.get_user_stats", return_value={"total_messages": 5, "active_days": 2, "task_count": 3}), \
             patch("app.quiz_results") as mock_qr:
            mock_qr.return_value.find.return_value.sort.return_value.limit.return_value = []
            r = authed_client.get("/api/me")
        assert r.status_code == 200
        data = r.get_json()
        assert data["name"] == "Test Student"
        assert "stats" in data

    def test_register_missing_fields_returns_400(self, client):
        r = client.post("/api/register",
                        data=json.dumps({"name": "Test"}),
                        content_type="application/json")
        assert r.status_code == 400
        assert b"required" in r.data

    def test_register_short_password_returns_400(self, client):
        r = client.post("/api/register",
                        data=json.dumps({"name": "T", "email": "t@t.com", "password": "short"}),
                        content_type="application/json")
        assert r.status_code == 400
        assert b"8 characters" in r.data

    def test_login_missing_email_returns_400(self, client):
        r = client.post("/api/login",
                        data=json.dumps({"password": "somepass"}),
                        content_type="application/json")
        assert r.status_code == 400

    def test_login_wrong_credentials_returns_401(self, client):
        with patch("app.login_user", return_value=None):
            r = client.post("/api/login",
                            data=json.dumps({"email": "bad@bad.com", "password": "wrongpass"}),
                            content_type="application/json")
        assert r.status_code == 401

    def test_logout_clears_session(self, authed_client):
        r = authed_client.post("/api/logout")
        assert r.status_code == 200
        assert r.get_json()["success"] is True


# ═════════════════════════════════════════════════════════════
#  CHAT API
# ═════════════════════════════════════════════════════════════

class TestChatAPI:

    def test_chat_requires_auth(self, client):
        r = client.post("/api/chat",
                        data=json.dumps({"message": "hello"}),
                        content_type="application/json")
        assert r.status_code == 401

    def test_chat_empty_message_returns_400(self, authed_client):
        r = authed_client.post("/api/chat",
                               data=json.dumps({"message": ""}),
                               content_type="application/json")
        assert r.status_code == 400
        assert b"empty" in r.data

    def test_chat_stream_requires_auth(self, client):
        r = client.post("/api/chat/stream",
                        data=json.dumps({"message": "hello"}),
                        content_type="application/json")
        assert r.status_code == 401

    def test_chat_sessions_requires_auth(self, client):
        r = client.get("/api/chat/sessions")
        assert r.status_code == 401

    def test_chat_history_requires_auth(self, client):
        r = client.get("/api/chat/history")
        assert r.status_code == 401


# ═════════════════════════════════════════════════════════════
#  PLANNER API
# ═════════════════════════════════════════════════════════════

class TestPlannerAPI:

    def test_planner_get_requires_auth(self, client):
        r = client.get("/api/planner")
        assert r.status_code == 401

    def test_planner_add_requires_auth(self, client):
        r = client.post("/api/planner",
                        data=json.dumps({"day": "Monday", "task_text": "Study"}),
                        content_type="application/json")
        assert r.status_code == 401

    def test_planner_add_invalid_day_returns_400(self, authed_client):
        with patch("app.planner") as mock_p:
            mock_p.return_value.find.return_value.sort.return_value = []
            r = authed_client.post("/api/planner",
                                   data=json.dumps({"day": "Funday", "task_text": "Study"}),
                                   content_type="application/json")
        assert r.status_code == 400
        assert b"Invalid day" in r.data

    def test_planner_add_missing_task_returns_400(self, authed_client):
        r = authed_client.post("/api/planner",
                               data=json.dumps({"day": "Monday", "task_text": ""}),
                               content_type="application/json")
        assert r.status_code == 400


# ═════════════════════════════════════════════════════════════
#  PRACTICE API
# ═════════════════════════════════════════════════════════════

class TestPracticeAPI:

    def test_practice_requires_auth(self, client):
        r = client.get("/api/practice")
        assert r.status_code == 401

    def test_practice_stats_requires_auth(self, client):
        r = client.get("/api/practice/stats")
        assert r.status_code == 401

    def test_weak_topics_requires_auth(self, client):
        r = client.get("/api/practice/weak-topics")
        assert r.status_code == 401

    def test_weak_topics_returns_sorted_list(self, authed_client):
        mock_results = [
            {"topic": "Python",     "score": 45, "submitted_at": "2026-01-01"},
            {"topic": "Python",     "score": 55, "submitted_at": "2026-01-02"},
            {"topic": "JavaScript", "score": 90, "submitted_at": "2026-01-03"},
        ]
        with patch("app.quiz_results") as mock_qr:
            mock_qr.return_value.find.return_value.sort.return_value.limit.return_value = mock_results
            r = authed_client.get("/api/practice/weak-topics")
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["topics"]) == 2
        # Weakest topic should come first (sorted ascending by avg_score)
        assert data["topics"][0]["topic"] == "Python"
        assert data["topics"][0]["status"] == "weak"
        assert data["topics"][1]["status"] == "strong"


# ═════════════════════════════════════════════════════════════
#  STATUS
# ═════════════════════════════════════════════════════════════

class TestStatus:

    def test_status_endpoint_returns_json(self, client):
        with patch("app.check_ollama_status", return_value={"ok": False, "error": "offline"}), \
             patch("app.get_db") as mock_db:
            mock_db.return_value.command.side_effect = Exception("no mongo")
            r = client.get("/api/status")
        assert r.status_code == 200
        data = r.get_json()
        assert "ollama" in data
        assert "mongo" in data
        assert data["mongo"] is False
