import unittest
from unittest.mock import Mock
import numpy as np

from src.workers.video_worker import VideoWorker


class VideoWorkerTrackingControlTest(unittest.TestCase):
    def setUp(self):
        self.worker = VideoWorker(
            camera=object(),
            detector=object(),
            tracker=object(),
            uart_sender=object(),
        )

    def test_tracking_is_disabled_by_default(self):
        self.assertFalse(self.worker.is_tracking_enabled)

    def test_tracking_can_be_enabled_and_disabled(self):
        self.worker.set_tracking_enabled(True)
        self.assertTrue(self.worker.is_tracking_enabled)

        self.worker.set_tracking_enabled(False)
        self.assertFalse(self.worker.is_tracking_enabled)

    def test_processed_frame_is_emitted_with_capture_time(self):
        camera, detector, tracker, uart = Mock(), Mock(), Mock(), Mock()
        camera.read.return_value = np.zeros((8, 8, 3), dtype=np.uint8)
        detector.detect.return_value = []
        detector.draw.side_effect = lambda frame, detections, selected_id: frame.fill(255)
        detector.elapsed_ms = 1.0
        tracker.update.return_value = None
        tracker.selected_id = None
        tracker.status.return_value = {'state': '선택 대기'}
        worker = VideoWorker(camera, detector, tracker, uart)
        worker.uart_enabled = False
        annotated, timestamps = [], []

        def consume(frame, timestamp):
            annotated.append(frame)
            timestamps.append(timestamp)
            worker.request_stop()

        worker.frame_ready.connect(consume)
        worker.run()
        self.assertEqual(annotated[0].mean(), 255)
        self.assertGreater(timestamps[0], 0)
        camera.release.assert_called_once()

    def test_latest_frame_replaces_stale_frames(self):
        worker = self.worker
        frame = np.zeros((8, 8, 3), dtype=np.uint8)
        with worker._latest_condition:
            worker._capture_sequence = 7
            worker._latest_frame = (7, 10.0, frame)
        sequence, captured_at, copied = worker._next_latest(processed_sequence=2)
        self.assertEqual(sequence, 7)
        self.assertEqual(captured_at, 10.0)
        self.assertIsNot(copied, frame)
        self.assertEqual(sequence - 2 - 1, 4)


if __name__ == "__main__":
    unittest.main()
