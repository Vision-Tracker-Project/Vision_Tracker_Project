import unittest

from src.main import camera_autostart_enabled


class CameraAutostartTest(unittest.TestCase):
    def test_disabled_by_default(self):
        self.assertFalse(camera_autostart_enabled({}))

    def test_enabled_values(self):
        for value in ("1", "true", "TRUE", "yes", " on "):
            with self.subTest(value=value):
                self.assertTrue(
                    camera_autostart_enabled({"VISION_AUTOSTART_CAMERA": value})
                )

    def test_unrecognized_value_is_disabled(self):
        self.assertFalse(camera_autostart_enabled({"VISION_AUTOSTART_CAMERA": "0"}))


if __name__ == "__main__":
    unittest.main()
