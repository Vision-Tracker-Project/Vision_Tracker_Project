import glob
import os
import unittest
from unittest.mock import Mock

from src.camera.camera_capture import CameraCapture, FrameReadError


class CameraCaptureUnitTest(unittest.TestCase):
    def test_default_state(self):
        camera = CameraCapture()
        self.assertEqual(camera.camera_index, 0)
        self.assertEqual((camera.width, camera.height), (640, 480))
        self.assertFalse(camera.is_opened)

    def test_read_before_open_has_clear_error(self):
        camera = CameraCapture()
        with self.assertRaisesRegex(FrameReadError, "열려 있지 않습니다"):
            camera.read()

    def test_release_is_idempotent(self):
        camera = CameraCapture()
        fake_capture = Mock()
        camera._capture = fake_capture

        camera.release()
        camera.release()

        fake_capture.release.assert_called_once_with()
        self.assertIsNone(camera._capture)


@unittest.skipUnless(
    os.environ.get("RUN_CAMERA_TESTS") == "1" and glob.glob("/dev/video*"),
    "RUN_CAMERA_TESTS=1이고 /dev/video*가 있을 때만 실행합니다.",
)
class CameraCaptureHardwareTest(unittest.TestCase):
    def test_open_read_and_release(self):
        camera = CameraCapture(width=640, height=480)
        try:
            info = camera.open()
            frame = camera.read()
            self.assertGreater(info.width, 0)
            self.assertGreater(info.height, 0)
            self.assertGreater(frame.size, 0)
        finally:
            camera.release()


if __name__ == "__main__":
    unittest.main()
