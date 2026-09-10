import unittest
from unittest.mock import Mock
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi.testclient import TestClient

from rc_web.app import create_app


class CommandApiTest(unittest.TestCase):
    def setUp(self):
        # 각 테스트가 독립된 메모리 기록으로 시작.
        self.client = TestClient(create_app(history_capacity=5))
        self.addCleanup(self.client.close)

    def send(self, command):
        return self.client.post("/api/command", json={"command": command})

    def test_four_valid_commands(self):
        actions = {"FORWARD": "전진", "BACKWARD": "후진", "LEFT": "좌회전", "RIGHT": "우회전"}
        for sequence, (command, action) in enumerate(actions.items(), start=1):
            with self.subTest(command=command):
                response = self.send(command)
                self.assertEqual(response.status_code, 200)
                receipt = response.json()
                self.assertTrue(receipt["success"])
                self.assertEqual(receipt["command"], command)
                self.assertEqual(receipt["action"], action)
                self.assertEqual(receipt["sequence"], sequence)
                self.assertFalse(receipt["hardware_sent"])
                self.assertEqual(receipt["client_ip"], "testclient")
                self.assertIsNotNone(datetime.fromisoformat(receipt["received_at"].replace("Z", "+00:00")).tzinfo)

    def test_invalid_commands_rejected_without_recording(self):
        for command in ("STOP", "forward", " FORWARD ", "임의 문자열", 1, True, [], {}):
            with self.subTest(command=command):
                self.assertEqual(self.send(command).status_code, 422)
        self.assertEqual(self.client.get("/api/status").json()["total_received"], 0)

    def test_empty_and_missing_commands_rejected(self):
        for payload in ({"command": ""}, {"command": " "}, {"command": None}, {}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/api/command", json=payload).status_code, 422)
        self.assertEqual(self.client.get("/api/history").json()["count"], 0)

    def test_extra_fields_rejected(self):
        response = self.client.post("/api/command", json={"command": "LEFT", "speed": 100})
        self.assertEqual(response.status_code, 422)

    def test_malformed_json_rejected(self):
        response = self.client.post("/api/command", content='{"command":', headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)

    def test_initial_status(self):
        state = self.client.get("/api/status").json()
        self.assertEqual(state["status"], "ok")
        self.assertEqual(state["mode"], "receive_only")
        self.assertFalse(state["hardware_enabled"])
        self.assertIsNone(state["latest_command"])
        self.assertEqual(state["history"], [])

    def test_latest_command_state(self):
        self.send("FORWARD")
        receipt = self.send("RIGHT").json()
        state = self.client.get("/api/status").json()
        self.assertEqual(state["latest_command"], receipt)
        self.assertEqual(state["total_received"], 2)
        self.assertEqual(state["history"][0], receipt)

    def test_history_is_newest_first_and_bounded(self):
        for _ in range(8):
            self.send("LEFT")
        response = self.client.get("/api/history")
        self.assertEqual(response.status_code, 200)
        history = response.json()
        self.assertEqual(history["total_received"], 8)
        self.assertEqual(history["count"], 5)
        self.assertEqual([item["sequence"] for item in history["history"]], [8, 7, 6, 5, 4])

    def test_invalid_command_preserves_latest(self):
        receipt = self.send("BACKWARD").json()
        self.send("STOP")
        self.assertEqual(self.client.get("/api/status").json()["latest_command"], receipt)

    def test_concurrent_commands_have_unique_sequence(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            responses = list(pool.map(lambda _: self.send("FORWARD"), range(24)))
        self.assertTrue(all(response.status_code == 200 for response in responses))
        self.assertEqual(sorted(response.json()["sequence"] for response in responses), list(range(1, 25)))
        self.assertEqual(self.client.get("/api/status").json()["total_received"], 24)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "mode": "receive_only", "hardware_enabled": False})

    def test_new_app_has_new_session_and_no_history(self):
        old_id = self.send("LEFT").json()["instance_id"]
        with TestClient(create_app()) as restarted:
            state = restarted.get("/api/status").json()
            self.assertNotEqual(state["instance_id"], old_id)
            self.assertIsNone(state["latest_command"])

    def test_client_ip_does_not_trust_forwarded_header(self):
        response = self.client.post("/api/command", json={"command": "RIGHT"}, headers={"X-Forwarded-For": "203.0.113.1"})
        self.assertEqual(response.json()["client_ip"], "testclient")

    def test_mobile_page_and_static_assets(self):
        page = self.client.get("/")
        self.assertEqual(page.status_code, 200)
        for command in ("FORWARD", "BACKWARD", "LEFT", "RIGHT"):
            self.assertIn(f'data-command="{command}"', page.text)
        self.assertIn('name="apple-mobile-web-app-capable" content="yes"', page.text)
        for path in ("app.js", "style.css", "icon.svg", "manifest.webmanifest"):
            self.assertEqual(self.client.get(f"/static/{path}").status_code, 200)
        self.assertEqual(self.client.get("/static/manifest.webmanifest").json()["display"], "standalone")

    def test_responses_not_cached(self):
        for path in ("/", "/api/status", "/api/history", "/health"):
            self.assertEqual(self.client.get(path).headers["cache-control"], "no-store")

    def test_command_requires_post(self):
        self.assertEqual(self.client.get("/api/command").status_code, 405)

    def test_shared_control_service_follows_server_lifespan(self):
        control = Mock()
        control.mailbox = Mock()
        with TestClient(create_app(control_service=control)) as client:
            self.assertEqual(client.get("/health").status_code, 200)
        control.start.assert_called_once_with()
        control.stop.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
