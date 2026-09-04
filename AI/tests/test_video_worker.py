import unittest

from src.workers.video_worker import VideoWorker


class VideoWorkerTrackingControlTest(unittest.TestCase):
    def setUp(self):
        self.worker = VideoWorker(
            camera=object(),
            detector=object(),
            extractor=object(),
            tracker=object(),
            uart_sender=object(),
        )

    def tearDown(self):
        self.worker.deleteLater()

    def test_tracking_is_disabled_by_default(self):
        self.assertFalse(self.worker.is_tracking_enabled)

    def test_tracking_can_be_enabled_and_disabled(self):
        self.worker.set_tracking_enabled(True)
        self.assertTrue(self.worker.is_tracking_enabled)

        self.worker.set_tracking_enabled(False)
        self.assertFalse(self.worker.is_tracking_enabled)


if __name__ == "__main__":
    unittest.main()
