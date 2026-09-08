import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from rc_web.app import create_app
import numpy as np


class VisionTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)
        self.addCleanup(self.client.close)
        self.service = self.app.state.vision

    def test_stopped_frame_and_tracking(self):
        self.assertEqual(self.client.get('/api/vision/frame').status_code, 204)
        self.assertEqual(self.client.post('/api/vision/tracking', json={'enabled':True}).status_code, 409)
        self.assertFalse(self.client.get('/api/vision/status').json()['running'])

    def test_invalid_mode_and_sequence(self):
        self.assertEqual(self.client.post('/api/vision/start', json={'mode':'bad'}).status_code, 422)
        self.assertEqual(self.client.get('/api/vision/frame?after=-1').status_code, 422)

    def test_latest_frame_replaces_previous_frame(self):
        service = self.service
        service.worker = Mock()
        service.worker.is_alive.return_value = False
        service.publish(np.zeros((48, 64, 3), np.uint8))
        service.publish(np.full((48, 64, 3), 255, np.uint8))
        response = self.client.get('/api/vision/frame')
        self.assertEqual(response.headers['x-sequence'], '2')
        self.assertTrue(response.content.startswith(b'\xff\xd8'))
        self.assertEqual(self.client.get('/api/vision/frame?after=2').status_code, 204)
        import cv2
        decoded = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.mean(), 255)
        self.assertEqual(service.status()['server_fps'], 0)
        self.assertEqual(service.worker.mark_frame_consumed.call_count, 2)

    def test_camera_baseline_does_not_encode(self):
        service = self.service
        service.worker = Mock()
        service.state['mode'] = 'camera'
        with patch('cv2.imencode') as encode:
            service.publish(np.zeros((48, 64, 3), np.uint8))
        encode.assert_not_called()
        self.assertIsNone(service.latest)
        self.assertEqual(service.sequence, 1)

    def test_client_report_validation_and_storage(self):
        record = dict(session='test', seconds=30, displayed=600, skipped=3, fps=20, request_ms=40)
        self.assertEqual(self.client.post('/api/vision/report', json=record).status_code, 200)
        self.assertEqual(self.service.status()['client_reports'][0]['client_ip'], 'testclient')
        record['seconds'] = 0
        self.assertEqual(self.client.post('/api/vision/report', json=record).status_code, 422)

    def test_duplicate_start_rejected(self):
        self.service.worker = Mock()
        self.service.worker.is_alive.return_value = True
        self.assertEqual(self.client.post('/api/vision/start', json={'mode':'raw'}).status_code, 409)

    def test_target_requires_running_ai(self):
        self.assertEqual(
            self.client.post('/api/vision/target', json={'x': 0.5, 'y': 0.5}).status_code,
            409,
        )

    def test_target_coordinates_are_validated(self):
        self.assertEqual(
            self.client.post('/api/vision/target', json={'x': 1.5, 'y': 0.5}).status_code,
            422,
        )

    def test_shutdown_stops_worker(self):
        worker = Mock()
        worker.is_alive.return_value = False
        self.service.worker = worker
        with self.client:
            pass
        worker.request_stop.assert_called_once()
        worker.set_tracking_enabled.assert_called_with(False)
