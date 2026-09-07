"""Run with the PC Python; uses local GStreamer RTP test video, no camera."""

import os
import shutil
import socket
import subprocess
import time
import unittest
from unittest.mock import patch

from src.streaming.stream_receiver import VideoReceiver


@unittest.skipUnless(shutil.which("gst-launch-1.0"), "GStreamer required")
class ExternalReceiverTest(unittest.TestCase):
    def setUp(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        self.receiver = VideoReceiver(self.port)

    def tearDown(self):
        self.receiver.stop()
        self.assertTrue(self.receiver.wait(3000), "receiver did not stop")
        self.assertIsNone(self.receiver._process)

    def test_receives_rtp_without_opencv_gstreamer(self):
        command = [
            shutil.which("gst-launch-1.0"), "-q", "videotestsrc", "is-live=true",
            "!", "video/x-raw,width=320,height=240,framerate=10/1",
            "!", "videoconvert", "!", "x264enc", "tune=zerolatency", "key-int-max=10",
            "!", "rtph264pay", "pt=96", "config-interval=1",
            "!", "udpsink", "host=127.0.0.1", f"port={self.port}",
        ]
        with patch("cv2.videoio_registry.hasBackend", return_value=False):
            self.receiver.start()
            sender = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            try:
                deadline = time.monotonic() + 12
                frame = None
                while time.monotonic() < deadline:
                    frame = self.receiver.take_latest()
                    if frame is not None:
                        break
                    time.sleep(0.05)
                self.assertIsNotNone(frame, "no decoded RTP frame")
                self.assertEqual(frame.shape, (480, 640, 3))
                self.assertGreater(float(frame.std()), 10)
            finally:
                sender.terminate()
                sender.wait(timeout=3)

    def test_stop_while_waiting_for_first_packet(self):
        with patch("cv2.videoio_registry.hasBackend", return_value=False):
            self.receiver.start()
            deadline = time.monotonic() + 3
            while self.receiver._process is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertIsNotNone(self.receiver._process)
            self.receiver.stop()
            self.assertTrue(self.receiver.wait(3000))


if __name__ == "__main__":
    unittest.main()
