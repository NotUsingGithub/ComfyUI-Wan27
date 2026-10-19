import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError
import importlib.util
from pathlib import Path
import sys
if "comfy_wan27" not in sys.modules:
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("comfy_wan27", root / "__init__.py", submodule_search_locations=[str(root)])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
from comfy_wan27.wan27_client import Wan27, Wan27Error, _NoRedirect


class Response(io.BytesIO):
    def __init__(self, data=b'{"ok":true}', status=200):
        super().__init__(data)
        self.status = status

    def getcode(self):
        return self.status


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch("comfy_wan27.wan27_client.build_opener")
        self.opener = self.patch.start().return_value
        self.addCleanup(self.patch.stop)
        self.client = Wan27("fixture-token")
        self.opener.open.side_effect = lambda *a, **k: Response()

    def test_routes_headers_and_encoding(self):
        self.client.account()
        r = self.opener.open.call_args.args[0]
        self.assertEqual(r.full_url, "https://wan2-7.io/api/v1/account/")
        self.assertEqual(r.get_header("Authorization"), "Bearer fixture-token")
        self.client.model("wan2.7-image")
        self.assertEqual(self.opener.open.call_args.args[0].full_url, "https://wan2-7.io/api/v1/models/wan2.7-image")
        self.client.tasks(limit=5, cursor="a+b&c")
        self.assertEqual(self.opener.open.call_args.args[0].full_url, "https://wan2-7.io/api/v1/tasks/?limit=5&cursor=a%2Bb%26c")

    def test_generation_uses_retained_key_and_returns_task(self):
        self.opener.open.return_value = Response(b'{"task":{"id":"task-1","status":"queued"}}')
        self.opener.open.side_effect = None
        result = self.client.generate({"modelId":"wan2.7-image","prompt":"boat"}, request_id="12345678-1234-1234-1234-123456789abc")
        r = self.opener.open.call_args.args[0]
        self.assertEqual(r.get_header("Idempotency-key"), "12345678-1234-1234-1234-123456789abc")
        self.assertEqual(r.method, "POST")
        self.assertEqual(result["task"]["id"], "task-1")
        self.assertEqual(self.opener.open.call_count, 1)

    def test_validation_before_network(self):
        actions = [lambda: Wan27(""), lambda: Wan27("x\r\ny"), lambda: Wan27("x",timeout=0),
                   lambda: self.client.tasks(limit=51), lambda: self.client.tasks(limit=True),
                   lambda: self.client.model(".."), lambda: self.client.task(""),
                   lambda: self.client.generate({},request_id="short"),
                   lambda: self.client.estimate({"prompt":"é"*17000}),
                   lambda: self.client.estimate({"bad":float("nan")})]
        for action in actions:
            with self.subTest(action=action), self.assertRaises(Wan27Error): action()
        self.opener.open.assert_not_called()

    def test_estimate_only_sends_estimate(self):
        self.client.estimate({"modelId":"wan2.7-image","prompt":"crane"})
        r = self.opener.open.call_args.args[0]
        self.assertEqual(r.full_url, "https://wan2-7.io/api/v1/estimates/")
        self.assertEqual(json.loads(r.data)["prompt"], "crane")
        self.assertIsNone(r.get_header("Idempotency-key"))

    def test_api_error(self):
        self.opener.open.side_effect = lambda *a, **k: Response(b'{"error":{"code":"SUBSCRIPTION_REQUIRED","message":"Paid subscription required"}}',403)
        with self.assertRaises(Wan27Error) as ctx: self.client.account()
        self.assertEqual(ctx.exception.code,"SUBSCRIPTION_REQUIRED")
        self.assertEqual(ctx.exception.status,403)

    def test_no_retry_or_token_disclosure_on_network_error(self):
        self.opener.open.side_effect = URLError("fixture-token")
        with self.assertRaises(Wan27Error) as ctx:
            self.client.generate({},request_id="12345678-1234-1234-1234-123456789abc")
        self.assertEqual(ctx.exception.code,"SERVICE_UNAVAILABLE")
        self.assertNotIn("fixture-token",str(ctx.exception))
        self.assertEqual(self.opener.open.call_count,1)

    def test_bad_and_oversized_responses(self):
        for data in [b'<html>error</html>', b'[]', b'x'*2_097_153]:
            self.opener.open.side_effect = lambda *a, **k: Response(data)
            with self.assertRaises(Wan27Error) as ctx: self.client.account()
            self.assertEqual(ctx.exception.code,"INVALID_RESPONSE")

    def test_redirects_are_rejected(self):
        with self.assertRaises(Wan27Error) as ctx:
            _NoRedirect().redirect_request(None,None,302,"redirect",{},"https://elsewhere.example/")
        self.assertEqual(ctx.exception.code,"REDIRECT_REJECTED")


if __name__ == "__main__": unittest.main()
