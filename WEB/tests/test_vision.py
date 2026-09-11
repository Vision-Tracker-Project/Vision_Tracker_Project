import unittest
from unittest.mock import Mock, patch

import numpy as np

from rc_web.vision import VisionService
from rc_web.vision_api import ClientReport, StartRequest, TargetRequest


class VisionTest(unittest.TestCase):
    def setUp(self):
        self.service = VisionService()

    def test_stopped_status_and_frame(self):
        self.assertFalse(self.service.status()['running'])
        self.assertIsNone(self.service.status()['controller'])
        self.assertIsNone(self.service.frame())
        with self.assertRaisesRegex(RuntimeError, 'AI 모드'):
            self.service.track(True)

    def test_latest_frame_replaces_previous_frame(self):
        service = self.service
        service.worker = Mock()
        service.worker.is_alive.return_value = False
        service.publish(np.zeros((48, 64, 3), np.uint8))
        service.publish(np.full((48, 64, 3), 255, np.uint8))
        sequence, _, data = service.frame()
        self.assertEqual(sequence, 2)
        self.assertTrue(data.startswith(b'\xff\xd8'))
        import cv2
        decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        self.assertEqual(decoded.mean(), 255)

    def test_camera_baseline_does_not_encode(self):
        self.service.worker = Mock()
        self.service.state['mode'] = 'camera'
        with patch('cv2.imencode') as encode:
            self.service.publish(np.zeros((48, 64, 3), np.uint8))
        encode.assert_not_called()
        self.assertIsNone(self.service.latest)

    def test_request_models_validate_values(self):
        self.assertEqual(StartRequest(mode='ai').mode, 'ai')
        self.assertEqual(TargetRequest(x=0.5, y=0.5).x, 0.5)
        with self.assertRaises(ValueError):
            StartRequest(mode='bad')
        with self.assertRaises(ValueError):
            TargetRequest(x=1.5, y=0.5)
        with self.assertRaises(ValueError):
            ClientReport(session='x', seconds=0, displayed=0, skipped=0, fps=0, request_ms=0)

    def test_integrated_uart_and_controller_status(self):
        sender = Mock(port='/dev/serial/by-id/stm32', baud_rate=115200)
        sender.is_open = False
        control = Mock(sender=sender)
        control.status.return_value = {'connected': True, 'direction': '전진'}
        service = VisionService(control)
        self.assertEqual(service.status()['uart'], '재연결 대기 — /dev/serial/by-id/stm32')
        sender.is_open = True
        state = service.status()
        self.assertEqual(state['uart'], '연결됨 — /dev/serial/by-id/stm32 115200bps')
        self.assertEqual(state['controller']['direction'], '전진')


if __name__ == '__main__':
    unittest.main()
