import time
import unittest

import numpy as np

from src.buffer.frame_buffer import FrameBuffer
from src.buffer.frame_buffer_worker import FrameBufferWorker


class FrameBufferTest(unittest.TestCase):
    def test_append_reports_bounds_and_stats(self):
        buffer = FrameBuffer(max_duration_seconds=60.0)
        buffer.append(10.0, b"first")
        buffer.append(12.5, b"second")

        self.assertEqual(buffer.bounds(), (10.0, 12.5))
        self.assertEqual(buffer.stats(), (2, 2.5, 11))

    def test_removes_frames_older_than_duration(self):
        buffer = FrameBuffer(max_duration_seconds=2.0)
        buffer.append(1.0, b"old")
        buffer.append(2.0, b"middle")
        buffer.append(3.1, b"latest")

        self.assertEqual(buffer.bounds(), (2.0, 3.1))
        self.assertEqual(buffer.stats()[0], 2)

    def test_returns_frame_closest_to_requested_time(self):
        buffer = FrameBuffer(max_duration_seconds=60.0)
        buffer.append(1.0, b"one")
        buffer.append(2.0, b"two")
        buffer.append(3.0, b"three")

        self.assertEqual(buffer.closest(2.2).jpeg_data, b"two")
        self.assertEqual(buffer.closest(2.8).jpeg_data, b"three")

    def test_clear_removes_all_frames(self):
        buffer = FrameBuffer()
        buffer.append(1.0, b"frame")
        buffer.clear()

        self.assertIsNone(buffer.bounds())
        self.assertIsNone(buffer.closest(1.0))
        self.assertEqual(buffer.stats(), (0, 0.0, 0))


class FrameBufferWorkerTest(unittest.TestCase):
    def test_rejects_invalid_jpeg_quality(self):
        with self.assertRaisesRegex(ValueError, "1~100"):
            FrameBufferWorker(jpeg_quality=0)

    def test_compresses_and_restores_latest_frame(self):
        worker = FrameBufferWorker(max_duration_seconds=60.0, jpeg_quality=80)
        frame = np.full((48, 64, 3), 127, dtype=np.uint8)
        worker.start()
        try:
            worker.submit(frame, timestamp=1.0)
            deadline = time.monotonic() + 2.0
            while worker.buffer.stats()[0] == 0 and time.monotonic() < deadline:
                time.sleep(0.01)

            restored = worker.frame_seconds_ago(0.0)
            self.assertIsNotNone(restored)
            self.assertEqual(restored.shape, frame.shape)
        finally:
            worker.request_stop()
            self.assertTrue(worker.wait(2000))


if __name__ == "__main__":
    unittest.main()
