import unittest

from src.network.discovery import DISCOVERY_MAGIC, _build_payload, _parse_payload


class DiscoveryProtocolTests(unittest.TestCase):
    def test_round_trip(self):
        result = _parse_payload(_build_payload(5000, 5001), "192.168.0.12")
        self.assertIsNotNone(result)
        self.assertEqual(result.host, "192.168.0.12")
        self.assertEqual(result.video_port, 5000)
        self.assertEqual(result.metadata_port, 5001)

    def test_invalid_payload_is_ignored(self):
        self.assertIsNone(_parse_payload(b"not-json", "192.168.0.12"))
        self.assertIsNone(
            _parse_payload(
                (f'{{"magic":"{DISCOVERY_MAGIC}-bad","video_port":5000,"metadata_port":5001}}').encode(),
                "192.168.0.12",
            )
        )


if __name__ == "__main__":
    unittest.main()
