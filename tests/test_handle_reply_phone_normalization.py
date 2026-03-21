from __future__ import annotations

import os
import shutil
import tempfile
import unittest

from fastapi.testclient import TestClient

from apartment_bot.api import create_app


class HandleReplyPhoneNormalizationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = os.environ.copy()
        self._state_dir = tempfile.mkdtemp(prefix="apartment-bot-state-")
        os.environ.update(
            {
                "STATE_STORE_DIR": self._state_dir,
                "USER_ONE_NAME": "Shane",
                "USER_ONE_PHONE": "9086426469",
                "USER_TWO_NAME": "Wife",
                "USER_TWO_PHONE": "4155551212",
            }
        )
        self.client = TestClient(create_app())

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_env)
        shutil.rmtree(self._state_dir, ignore_errors=True)

    def test_accepts_leading_us_country_code(self) -> None:
        response = self.client.post(
            "/handle-reply",
            json={"from_number": "+19086426469", "body": "3"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["reply_text"], "Unknown sender number.")

    def test_accepts_whatsapp_prefix(self) -> None:
        response = self.client.post(
            "/handle-reply",
            json={"from_number": "whatsapp:+19086426469", "body": "3"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.json()["reply_text"], "Unknown sender number.")


if __name__ == "__main__":
    unittest.main()
