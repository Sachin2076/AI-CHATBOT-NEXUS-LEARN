"""
tests/test_integration.py — Flask integration tests using test client

Tests POST /api/register, POST /api/login, GET+POST /api/groups,
GET /api/srs/due, and GET /api/status with MongoDB calls mocked.

Run with:
    pytest tests/test_integration.py -v
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from bson import ObjectId


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    """Flask test app with all external services mocked out."""
    with patch("db.MongoClient"), \
         patch("db._ensure_indexes", return_value=None), \
         patch("groups._ensure_indexes", return_value=None), \
         patch("interview._ensure_indexes", return_value=None):
        import app as flask_app_module
        flask_app_module.app.config["TESTING"]    = True
        flask_app_module.app.config["SECRET_KEY"] = "integration-test-secret"
        yield flask_app_module.app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def authed_client(client):
    """Client with a pre-seeded authenticated session."""
    with client.session_transaction() as sess:
        sess["user_id"]    = "507f1f77bcf86cd799439011"
        sess["user_name"]  = "Integration Tester"
        sess["user_email"] = "integration@nexus.test"
    return client


# ════════════════════════════════════════════════════════════════
#  POST /api/register
# ════════════════════════════════════════════════════════════════

class TestRegister:

    def test_register_creates_user_and_returns_200(self, client):
        fake_user = {
            "_id":   ObjectId("507f1f77bcf86cd799439022"),
            "name":  "Alice",
            "email": "alice@nexus.test",
        }
        with patch("app.register_user", return_value=fake_user), \
             patch("app.usage_logs") as mock_logs:
            mock_logs.return_value.update_one.return_value = None
            r = client.post(
                "/api/register",
                data=json.dumps({
                    "name":     "Alice",
                    "email":    "alice@nexus.test",
                    "password": "securepassword1",
                }),
                content_type="application/json",
            )
        assert r.status_code == 200
        assert r.get_json()["success"] is True

    def test_register_missing_fields_returns_400(self, client):
        r = client.post(
            "/api/register",
            data=json.dumps({"name": "Bob"}),
            content_type="application/json",
        )
        assert r.status_code == 400
        assert b"required" in r.data

    def test_register_short_password_returns_400(self, client):
        r = client.post(
            "/api/register",
            data=json.dumps({"name": "Bob", "email": "b@b.com", "password": "short"}),
            content_type="application/json",
        )
        assert r.status_code == 400

    def test_register_duplicate_email_returns_409(self, client):
        with patch("app.register_user", side_effect=ValueError("Email already registered.")):
            r = client.post(
                "/api/register",
                data=json.dumps({
                    "name":     "Dup",
                    "email":    "dup@nexus.test",
                    "password": "validpassword1",
                }),
                content_type="application/json",
            )
        assert r.status_code == 409


# ════════════════════════════════════════════════════════════════
#  POST /api/login
# ════════════════════════════════════════════════════════════════

class TestLogin:

    def test_login_valid_credentials_returns_200_and_sets_session(self, client):
        fake_user = {
            "_id":   ObjectId("507f1f77bcf86cd799439033"),
            "name":  "Carol",
            "email": "carol@nexus.test",
        }
        with patch("app.login_user", return_value=fake_user), \
             patch("app.usage_logs") as mock_logs:
            mock_logs.return_value.update_one.return_value = None
            r = client.post(
                "/api/login",
                data=json.dumps({"email": "carol@nexus.test", "password": "correctpass"}),
                content_type="application/json",
            )
        assert r.status_code == 200
        assert r.get_json()["success"] is True

    def test_login_wrong_credentials_returns_401(self, client):
        with patch("app.login_user", return_value=None):
            r = client.post(
                "/api/login",
                data=json.dumps({"email": "nobody@nexus.test", "password": "wrongpass"}),
                content_type="application/json",
            )
        assert r.status_code == 401

    def test_login_missing_fields_returns_400(self, client):
        r = client.post(
            "/api/login",
            data=json.dumps({"email": "only@nexus.test"}),
            content_type="application/json",
        )
        assert r.status_code == 400


# ════════════════════════════════════════════════════════════════
#  GET /api/groups  (authenticated)
# ════════════════════════════════════════════════════════════════

class TestGetGroups:

    def test_get_groups_unauthenticated_returns_401(self, client):
        r = client.get("/api/groups")
        assert r.status_code == 401

    def test_get_groups_authenticated_returns_200_with_list(self, authed_client):
        fake_group = {
            "_id":          ObjectId("507f1f77bcf86cd799439044"),
            "name":         "CS Study Squad",
            "topic":        "Data Structures",
            "creator_id":   "507f1f77bcf86cd799439011",
            "creator_name": "Integration Tester",
            "members":      ["507f1f77bcf86cd799439011"],
            "member_names": {"507f1f77bcf86cd799439011": "Integration Tester"},
            "created_at":   "2026-01-01T00:00:00",
        }
        mock_cursor = MagicMock()
        mock_cursor.sort.return_value = [fake_group]

        with patch("groups._groups") as mock_col:
            mock_col.return_value.find.return_value = mock_cursor
            mock_col.return_value.find_one.return_value = None
            r = authed_client.get("/api/groups")

        assert r.status_code == 200
        data = r.get_json()
        assert "groups" in data
        assert isinstance(data["groups"], list)


# ════════════════════════════════════════════════════════════════
#  POST /api/groups  (authenticated)
# ════════════════════════════════════════════════════════════════

class TestCreateGroup:

    def test_create_group_unauthenticated_returns_401(self, client):
        r = client.post(
            "/api/groups",
            data=json.dumps({"name": "My Group", "topic": "Python"}),
            content_type="application/json",
        )
        assert r.status_code == 401

    def test_create_group_authenticated_returns_201(self, authed_client):
        inserted_id = ObjectId("507f1f77bcf86cd799439055")
        mock_result = MagicMock()
        mock_result.inserted_id = inserted_id

        with patch("groups._groups") as mock_col:
            mock_col.return_value.find_one.return_value = None   # not already in a group / no dupe name
            mock_col.return_value.insert_one.return_value = mock_result
            r = authed_client.post(
                "/api/groups",
                data=json.dumps({"name": "Integration Group", "topic": "Algorithms"}),
                content_type="application/json",
            )

        assert r.status_code == 201
        data = r.get_json()
        assert "group" in data
        assert data["message"] == "Group created!"

    def test_create_group_missing_name_returns_400(self, authed_client):
        with patch("groups._groups") as mock_col:
            mock_col.return_value.find_one.return_value = None
            r = authed_client.post(
                "/api/groups",
                data=json.dumps({"topic": "Python"}),
                content_type="application/json",
            )
        assert r.status_code == 400

    def test_create_group_already_in_group_returns_409(self, authed_client):
        existing = {"_id": ObjectId(), "name": "Old Group", "members": ["507f1f77bcf86cd799439011"]}
        with patch("groups._groups") as mock_col:
            mock_col.return_value.find_one.return_value = existing
            r = authed_client.post(
                "/api/groups",
                data=json.dumps({"name": "New Group", "topic": "Python"}),
                content_type="application/json",
            )
        assert r.status_code == 409


# ════════════════════════════════════════════════════════════════
#  GET /api/srs/due  (authenticated)
# ════════════════════════════════════════════════════════════════

class TestSrsDue:

    def test_srs_due_unauthenticated_returns_401(self, client):
        r = client.get("/api/srs/due")
        assert r.status_code == 401

    def test_srs_due_authenticated_returns_200_with_list(self, authed_client):
        with patch("app.get_due_topics", return_value=["Python", "SQL"]), \
             patch("app.get_db", return_value=MagicMock()):
            r = authed_client.get("/api/srs/due")
        assert r.status_code == 200
        data = r.get_json()
        assert "due_topics" in data
        assert isinstance(data["due_topics"], list)

    def test_srs_due_returns_empty_list_when_nothing_due(self, authed_client):
        with patch("app.get_due_topics", return_value=[]), \
             patch("app.get_db", return_value=MagicMock()):
            r = authed_client.get("/api/srs/due")
        assert r.status_code == 200
        assert r.get_json()["due_topics"] == []


# ════════════════════════════════════════════════════════════════
#  GET /api/status
# ════════════════════════════════════════════════════════════════

class TestStatus:

    def test_status_returns_200(self, client):
        with patch("app.check_ollama_status", return_value={"ok": True, "model": "llama3"}), \
             patch("app.get_db") as mock_db:
            mock_db.return_value.command.return_value = {"ok": 1}
            r = client.get("/api/status")
        assert r.status_code == 200

    def test_status_contains_ollama_and_mongo_keys(self, client):
        with patch("app.check_ollama_status", return_value={"ok": False, "error": "offline"}), \
             patch("app.get_db") as mock_db:
            mock_db.return_value.command.side_effect = Exception("no connection")
            r = client.get("/api/status")
        assert r.status_code == 200
        data = r.get_json()
        assert "ollama" in data
        assert "mongo" in data

    def test_status_mongo_false_when_db_unreachable(self, client):
        with patch("app.check_ollama_status", return_value={"ok": False, "error": "offline"}), \
             patch("app.get_db") as mock_db:
            mock_db.return_value.command.side_effect = Exception("no connection")
            r = client.get("/api/status")
        assert r.get_json()["mongo"] is False
