import unittest
import os
import re
from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.auth import clear_login_failures, clear_demo_login_limits
from backend.scripts.seed_demo_accounts import seed_demo_accounts

class TestDemoAuthentication(unittest.TestCase):
    """Verifies Milestone 6B demonstration authentication, Argon2id security,
    session lifecycle, rate limiting, and administrative privilege isolation.
    """

    @classmethod
    def setUpClass(cls):
        # Ensure demo accounts and local credentials exist
        cls.credentials_map = seed_demo_accounts()
        cls.client = TestClient(app)

    def setUp(self):
        # Clear rate-limit state between tests to isolate behaviors
        clear_login_failures("testclient")
        clear_demo_login_limits("testclient")
        for username in self.credentials_map.keys():
            clear_login_failures(username)
            clear_demo_login_limits(username)

    def test_demo_personas_endpoint_returns_five_personas(self):
        """Verifies GET /api/v1/auth/demo-personas lists all 5 distinct personas."""
        res = self.client.get("/api/v1/auth/demo-personas")
        self.assertEqual(res.status_code, 200)
        personas = res.json()
        self.assertEqual(len(personas), 5)
        usernames = {p["username"] for p in personas}
        expected = {"demo_gamer", "demo_student", "demo_creator", "demo_traveler", "demo_office"}
        self.assertEqual(usernames, expected)
        for p in personas:
            self.assertTrue(p["display_name"])
            self.assertTrue(p["persona_description"])

    def test_demo_personas_endpoint_never_exposes_credentials_or_secrets(self):
        """Verifies GET /api/v1/auth/demo-personas never returns passwords, hashes, tokens, or secrets."""
        res = self.client.get("/api/v1/auth/demo-personas")
        self.assertEqual(res.status_code, 200)
        personas = res.json()
        for p in personas:
            self.assertNotIn("demo_password", p)
            self.assertNotIn("password", p)
            self.assertNotIn("password_hash", p)
            self.assertNotIn("session_token", p)
            self.assertNotIn("token", p)
            self.assertNotIn("secret", p)

    def test_all_five_personas_authenticate_successfully(self):
        """Verifies each of the 5 demo accounts can authenticate with its generated high-entropy credential."""
        for username, password in self.credentials_map.items():
            client = TestClient(app)
            res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
            self.assertEqual(res.status_code, 200, f"Login failed for {username}")
            data = res.json()
            self.assertIn("session_token", data)
            self.assertEqual(data["user"]["username"], username)
            self.assertTrue(data["session_token"])

            # Verify /me returns the authenticated user
            token = data["session_token"]
            me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(me_res.status_code, 200)
            self.assertEqual(me_res.json()["username"], username)

    def test_invalid_password_returns_401_unauthorized(self):
        """Verifies incorrect passwords are rejected with HTTP 401 without timing/leakage clues."""
        res = self.client.post("/api/v1/auth/login", json={"username": "demo_gamer", "password": "WrongPassword!999"})
        self.assertEqual(res.status_code, 401)
        self.assertIn("Invalid username or password", res.json()["detail"])

    def test_nonexistent_user_returns_401_unauthorized(self):
        """Verifies nonexistent usernames are rejected uniformly with HTTP 401."""
        res = self.client.post("/api/v1/auth/login", json={"username": "nonexistent_hacker", "password": "AnyPassword#123"})
        self.assertEqual(res.status_code, 401)

    def test_logout_invalidates_session(self):
        """Verifies session termination prevents subsequent authenticated access."""
        gamer_pw = self.credentials_map["demo_gamer"]
        client = TestClient(app)
        login_res = client.post("/api/v1/auth/login", json={"username": "demo_gamer", "password": gamer_pw})
        token = login_res.json()["session_token"]

        # Confirm session is active
        me_res1 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res1.status_code, 200)

        # Logout
        logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(logout_res.status_code, 200)

        # Verify token is now invalid
        me_res2 = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_res2.status_code, 401)

    def test_failed_login_rate_limiting_triggers_429(self):
        """Verifies brute-force protection locks out an identifier after 5 consecutive failures."""
        target_user = "demo_office"
        for i in range(5):
            res = self.client.post("/api/v1/auth/login", json={"username": target_user, "password": f"BadAttempt_{i}"})
            self.assertEqual(res.status_code, 401)

        # 6th attempt should be blocked by rate limiter with HTTP 429
        blocked_res = self.client.post("/api/v1/auth/login", json={"username": target_user, "password": "AnyAttempt"})
        self.assertEqual(blocked_res.status_code, 429)
        self.assertIn("Too many failed login attempts", blocked_res.json()["detail"])

    def test_customer_token_cannot_access_merchant_settings(self):
        """Verifies customer session token has zero merchant administrative privileges."""
        from backend.app.config import settings
        orig_token = settings.ADMIN_TOKEN
        try:
            settings.ADMIN_TOKEN = "test_merchant_admin_secret_999"
            gamer_pw = self.credentials_map["demo_gamer"]
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/login", json={"username": "demo_gamer", "password": gamer_pw})
            token = login_res.json()["session_token"]

            # Attempt to modify merchant settings using customer session token
            res = client.post(
                "/api/v1/settings",
                json={"margin_floor": 0.05, "discount_cap": 0.50},
                headers={"Authorization": f"Bearer {token}", "X-Session-Token": token},
            )
            # Must return 403 Forbidden because customer session is not merchant ADMIN_TOKEN
            self.assertEqual(res.status_code, 403)
        finally:
            settings.ADMIN_TOKEN = orig_token

    def test_demo_login_whitelisted_personas_succeed(self):
        """Verifies all 5 whitelisted demo personas authenticate successfully via POST /api/v1/auth/demo-login."""
        whitelisted = ["demo_gamer", "demo_student", "demo_creator", "demo_traveler", "demo_office"]
        for persona in whitelisted:
            clear_demo_login_limits("testclient")
            client = TestClient(app)
            res = client.post("/api/v1/auth/demo-login", json={"persona": persona})
            self.assertEqual(res.status_code, 200, f"Demo login failed for {persona}")
            data = res.json()
            self.assertIn("session_token", data)
            self.assertEqual(data["user"]["username"], persona)
            self.assertIn("faircart_session", res.cookies)

            # Verify session is valid via /me
            token = data["session_token"]
            me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
            self.assertEqual(me_res.status_code, 200)
            self.assertEqual(me_res.json()["username"], persona)

    def test_demo_login_rejects_non_whitelisted_personas(self):
        """Verifies POST /api/v1/auth/demo-login rejects any arbitrary username with HTTP 400."""
        invalid_personas = ["admin", "root", "guest", "demo_hacker", "user123"]
        for bad_p in invalid_personas:
            res = self.client.post("/api/v1/auth/demo-login", json={"persona": bad_p})
            self.assertEqual(res.status_code, 400)
            self.assertIn("Invalid demo persona", res.json()["detail"])

    def test_demo_login_rate_limiting_triggers_429(self):
        """Verifies demo login enforces rate limiting after 15 requests in 60s."""
        clear_demo_login_limits("testclient")
        for i in range(15):
            res = self.client.post("/api/v1/auth/demo-login", json={"persona": "demo_gamer"})
            self.assertEqual(res.status_code, 200)

        # 16th request must be rate limited
        blocked_res = self.client.post("/api/v1/auth/demo-login", json={"persona": "demo_gamer"})
        self.assertEqual(blocked_res.status_code, 429)
        self.assertIn("Demo login rate limit reached", blocked_res.json()["detail"])

    def test_demo_login_session_cannot_access_merchant_settings(self):
        """Verifies sessions created via demo-login have zero merchant administrative privileges."""
        from backend.app.config import settings
        orig_token = settings.ADMIN_TOKEN
        try:
            settings.ADMIN_TOKEN = "test_merchant_admin_secret_999"
            clear_demo_login_limits("testclient")
            client = TestClient(app)
            login_res = client.post("/api/v1/auth/demo-login", json={"persona": "demo_traveler"})
            token = login_res.json()["session_token"]

            # Attempt to modify settings with demo-login session
            res = client.post(
                "/api/v1/settings",
                json={"margin_floor": 0.05, "discount_cap": 0.50},
                headers={"Authorization": f"Bearer {token}"},
            )
            self.assertEqual(res.status_code, 403)
        finally:
            settings.ADMIN_TOKEN = orig_token


if __name__ == "__main__":
    unittest.main()
