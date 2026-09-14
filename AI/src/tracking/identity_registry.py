"""One-to-one mapping from volatile tracker IDs to stable public identities."""


class IdentityRegistry:
    """Keep public IDs unique while allowing a long-term ReID rebind."""

    def __init__(self):
        self._identity_by_tracker = {}
        self._tracker_by_identity = {}
        self._issued = set()
        self._next_identity = 1

    def assign(self, detections):
        for detection in detections:
            tracker_id = int(detection.tracker_id)
            identity_id = self._identity_by_tracker.get(tracker_id)
            if identity_id is None:
                identity_id = self._allocate(preferred=tracker_id)
                self._identity_by_tracker[tracker_id] = identity_id
                self._tracker_by_identity[identity_id] = tracker_id
            detection.track_id = identity_id

    def rebind(self, identity_id, tracker_id):
        """Move one identity to one tracker, retiring conflicting aliases."""
        identity_id, tracker_id = int(identity_id), int(tracker_id)
        previous_tracker = self._tracker_by_identity.get(identity_id)
        if previous_tracker is not None and previous_tracker != tracker_id:
            self._identity_by_tracker.pop(previous_tracker, None)

        previous_identity = self._identity_by_tracker.get(tracker_id)
        if previous_identity is not None and previous_identity != identity_id:
            self._tracker_by_identity.pop(previous_identity, None)

        self._issued.add(identity_id)
        self._identity_by_tracker[tracker_id] = identity_id
        self._tracker_by_identity[identity_id] = tracker_id
        self._next_identity = max(self._next_identity, identity_id + 1)

    def identity_for(self, tracker_id):
        return self._identity_by_tracker.get(int(tracker_id))

    def _allocate(self, preferred):
        preferred = int(preferred)
        if preferred >= 0 and preferred not in self._issued:
            identity_id = preferred
        else:
            while self._next_identity in self._issued:
                self._next_identity += 1
            identity_id = self._next_identity
        self._issued.add(identity_id)
        self._next_identity = max(self._next_identity, identity_id + 1)
        return identity_id
