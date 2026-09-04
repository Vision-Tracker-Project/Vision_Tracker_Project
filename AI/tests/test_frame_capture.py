import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.capture.frame_capture import CaptureError, FrameCapture


class FrameCaptureTest(unittest.TestCase):
    def test_saves_live_and_replay_frames_as_png(self):
        frame = np.full((48, 64, 3), 127, dtype=np.uint8)
        with tempfile.TemporaryDirectory() as directory:
            capture = FrameCapture(Path(directory))

            live_path = capture.save(frame, "live")
            replay_path = capture.save(frame, "replay")

            self.assertTrue(live_path.is_file())
            self.assertTrue(replay_path.is_file())
            self.assertTrue(live_path.name.endswith("_live.png"))
            self.assertTrue(replay_path.name.endswith("_replay.png"))
            self.assertEqual(cv2.imread(str(live_path)).shape, frame.shape)

    def test_rejects_empty_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = FrameCapture(Path(directory))
            with self.assertRaisesRegex(CaptureError, "캡처할 화면이 없습니다"):
                capture.save(np.empty((0, 0, 3), dtype=np.uint8), "live")

    def test_rejects_unknown_source(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = FrameCapture(Path(directory))
            frame = np.zeros((10, 10, 3), dtype=np.uint8)
            with self.assertRaisesRegex(CaptureError, "알 수 없는"):
                capture.save(frame, "unknown")

    def test_rejects_missing_selected_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = FrameCapture(Path(directory))
            with self.assertRaisesRegex(CaptureError, "찾을 수 없습니다"):
                capture.set_output_directory(Path(directory) / "missing")


if __name__ == "__main__":
    unittest.main()
