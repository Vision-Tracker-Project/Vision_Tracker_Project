import unittest
from unittest.mock import Mock

from rc_web.app import STATIC_DIR, create_app


class WebApiTest(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def routes(app):
        routes = []
        for route in app.routes:
            nested = getattr(route, 'original_router', None)
            routes.extend(nested.routes if nested is not None else (route,))
        return {route.path: route for route in routes if hasattr(route, 'path')}

    def test_routes_and_health(self):
        app = create_app()
        routes = self.routes(app)
        self.assertIn('/', routes)
        self.assertIn('/health', routes)
        self.assertIn('/api/vision/status', routes)
        self.assertNotIn('/api/command', routes)
        self.assertNotIn('/api/history', routes)
        self.assertEqual(
            routes['/health'].endpoint(),
            {'status': 'ok', 'control_enabled': False},
        )

    def test_camera_is_above_controller_and_manual_buttons_are_gone(self):
        page = (STATIC_DIR / 'index.html').read_text(encoding='utf-8')
        self.assertLess(page.index('id="video"'), page.index('id="controller-panel"'))
        self.assertNotIn('data-command=', page)
        self.assertNotIn('app.js', page)
        self.assertIn('id="controller-stick"', page)
        for name in ('vision.js', 'style.css', 'icon.svg', 'manifest.webmanifest'):
            self.assertTrue((STATIC_DIR / name).is_file())

    async def test_shared_control_service_follows_lifespan(self):
        control = Mock()
        control.mailbox = Mock()
        app = create_app(control_service=control)
        async with app.router.lifespan_context(app):
            self.assertEqual(self.routes(app)['/health'].endpoint()['control_enabled'], True)
        control.start.assert_called_once_with()
        control.stop.assert_called_once_with()


if __name__ == '__main__':
    unittest.main()
