import json
import unittest
import numpy as np
from src.streaming.gstreamer_sender import GStreamerSender, sender_pipeline
from src.streaming.metadata import MetadataError, MetadataOrder, StreamMetadata

def make_item(sequence=1, session_id="session"):
    return StreamMetadata(
        session_id=session_id, sequence=sequence, source_time=1.0,
        processing_fps=20.0, face_count=1, tracking=None,
        uart={"connected": True, "message": "OK"},
    )

class MetadataTest(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(StreamMetadata.from_bytes(make_item().to_bytes()), make_item())

    def test_invalid_and_non_finite_values_are_rejected(self):
        with self.assertRaises(MetadataError):
            StreamMetadata.from_bytes(b"not-json")
        value = json.loads(make_item().to_bytes())
        value["processing_fps"] = float("nan")
        with self.assertRaises(MetadataError):
            StreamMetadata.from_bytes(json.dumps(value).encode())

    def test_duplicate_and_old_sequence_are_dropped(self):
        order = MetadataOrder()
        self.assertTrue(order.accept(make_item(2)))
        self.assertFalse(order.accept(make_item(2)))
        self.assertFalse(order.accept(make_item(1)))
        self.assertTrue(order.accept(make_item(0, "new-session")))

class StreamingTest(unittest.TestCase):
    def test_sender_pipeline_uses_hardware_encoder(self):
        pipeline = sender_pipeline("10.0.0.2", 5000, 640, 480, 20, 3_000_000, 1200)
        self.assertIn("nvv4l2h264enc", pipeline)
        self.assertIn("framerate=20/1", pipeline)
        self.assertIn("mtu=1200", pipeline)

    def test_sender_keeps_only_latest_frame(self):
        sender = GStreamerSender("127.0.0.1", 5000, 2, 2, 20, 1_000_000)
        first = np.zeros((2, 2, 3), dtype=np.uint8)
        latest = np.ones((2, 2, 3), dtype=np.uint8)
        sender.publish(first)
        sender.publish(latest)
        queued = sender._queue.get_nowait()
        self.assertTrue(np.array_equal(queued, latest))
        self.assertEqual(sender.dropped, 1)

if __name__ == "__main__":
    unittest.main()
