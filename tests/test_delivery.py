import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from guanlan.delivery import create_server
from test_core import example


class DeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = create_server({"velocity": example()}, 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def get(self, path):
        return urlopen(self.base + path, timeout=5)

    def test_envelope_and_snapshot_match(self):
        with self.get("/api/preview?view=velocity") as response:
            envelope = json.load(response)
        self.assertEqual(envelope["source_kind"], "synthetic")
        with self.get(envelope["image_url"]) as response:
            image = response.read()
        with self.get(f"/snapshot?view=velocity&frame={envelope['frame_id']}") as response:
            self.assertIn("attachment", response.headers["Content-Disposition"])
            self.assertEqual(response.read(), image)

    def test_invalid_routes_and_frames(self):
        for path, status in (("/../../config/scnet.local.json", 404),
                             ("/api/preview?view=missing", 404),
                             ("/image?view=velocity&frame=-1", 400),
                             ("/snapshot?view=velocity", 400)):
            with self.subTest(path=path), self.assertRaises(HTTPError) as result:
                self.get(path)
            self.assertEqual(result.exception.code, status)

    def test_browser_assets_are_served(self):
        for path in ("/", "/app.js", "/style.css", "/api/views"):
            with self.get(path) as response:
                self.assertEqual(response.status, 200)
                self.assertTrue(response.read())


if __name__ == "__main__":
    unittest.main()
