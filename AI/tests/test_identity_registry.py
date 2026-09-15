import unittest

from src.detection.person_detector import PersonDetection
from src.tracking.identity_registry import IdentityRegistry


class IdentityRegistryTest(unittest.TestCase):
    def test_rebind_is_one_to_one_and_never_reuses_retired_id(self):
        registry = IdentityRegistry()
        original = PersonDetection(1, (0, 0, 10, 20), 0.9)
        replacement = PersonDetection(9, (20, 0, 10, 20), 0.9)
        registry.assign([original, replacement])
        self.assertEqual((original.track_id, replacement.track_id), (1, 9))

        registry.rebind(identity_id=1, tracker_id=9)
        replacement_next = PersonDetection(9, (20, 0, 10, 20), 0.9)
        stale_original = PersonDetection(1, (0, 0, 10, 20), 0.9)
        registry.assign([replacement_next, stale_original])

        ids = [replacement_next.track_id, stale_original.track_id]
        self.assertEqual(replacement_next.track_id, 1)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn(9, ids)


if __name__ == '__main__':
    unittest.main()
