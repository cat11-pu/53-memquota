import json
import threading
import unittest
import urllib.error
import urllib.request

from memquota import Quota
from server import serve

class TestQuota(unittest.TestCase):
    def test_put_counts(self):
        pool = Quota()
        self.assertEqual(pool.put("a", "k1", 10)["used"], 10)

    def test_get_touches(self):
        pool = Quota()
        pool.put("a", "k1", 10)
        self.assertTrue(pool.get("a", "k1")["found"])

    def test_get_missing(self):
        self.assertFalse(Quota().get("a", "nope")["found"])

    def test_stats_shape(self):
        self.assertIn("tenant_quota", Quota().stats())

    def test_http_put(self):
        server = serve(0)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:%d" % server.server_port
        with urllib.request.urlopen(base + "/put", data=b'{"tenant": "a", "key": "k1", "size": 10}',
                                    timeout=5) as response:
            self.assertEqual(json.loads(response.read())["used"], 10)
        server.shutdown()
