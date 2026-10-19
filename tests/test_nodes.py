import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("comfy_wan27", ROOT / "__init__.py", submodule_search_locations=[str(ROOT)])
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
nodes = sys.modules["comfy_wan27.nodes"]

class NodeTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.client.estimate.return_value = {"modelId": "wan2.7-image", "credits": 9}
        self.client.generate.return_value = {"task": {"id": "fixture-task", "status": "queued"}, "replayed": False}
        self.patcher = patch.object(nodes, "_client", return_value=self.client)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.input = {"modelId": "wan2.7-image", "prompt": "paper crane"}
        self.key = "fixture-generation-0001"

    def receipt(self):
        return nodes.Wan27Estimate().estimate(json.dumps(self.input))[0]

    def test_real_comfy_node_contracts(self):
        self.assertEqual(len(module.NODE_CLASS_MAPPINGS), 4)
        for cls in module.NODE_CLASS_MAPPINGS.values():
            self.assertTrue(cls.INPUT_TYPES()["required"])
            self.assertTrue(callable(getattr(cls(), cls.FUNCTION)))
        self.assertFalse(nodes.Wan27Generate.INPUT_TYPES()["required"]["approved_after_review"][1]["default"])

    def test_estimate_never_generates(self):
        receipt, cost = nodes.Wan27Estimate().estimate(json.dumps(self.input))
        self.assertEqual(cost, 9)
        self.assertEqual(json.loads(receipt)["input"], self.input)
        self.client.generate.assert_not_called()

    def test_no_approval_no_network_or_generation(self):
        with self.assertRaisesRegex(ValueError, "review"):
            nodes.Wan27Generate().generate("", False, 100, self.key)
        self.client.estimate.assert_not_called()
        self.client.generate.assert_not_called()

    def test_changed_estimate_requires_new_confirmation(self):
        receipt = self.receipt()
        self.client.estimate.return_value = {"credits": 10}
        with self.assertRaisesRegex(ValueError, "changed"):
            nodes.Wan27Generate().generate(receipt, True, 100, self.key)
        self.client.generate.assert_not_called()

    def test_budget_ceiling_stops_before_creation(self):
        with self.assertRaisesRegex(ValueError, "maximum"):
            nodes.Wan27Generate().generate(self.receipt(), True, 8, self.key)
        self.client.generate.assert_not_called()

    def test_input_tampering_stops_creation(self):
        receipt = json.loads(self.receipt())
        receipt["input"]["prompt"] = "changed"
        with self.assertRaisesRegex(ValueError, "receipt"):
            nodes.Wan27Generate().generate(json.dumps(receipt), True, 100, self.key)
        self.client.generate.assert_not_called()

    def test_exactly_one_submission_uses_retained_request_id(self):
        task_id, result = nodes.Wan27Generate().generate(self.receipt(), True, 9, self.key)
        self.assertEqual(task_id, "fixture-task")
        self.assertEqual(json.loads(result)["task"]["status"], "queued")
        self.client.generate.assert_called_once_with(self.input, request_id=self.key)

    def test_timeout_is_not_retried(self):
        receipt = self.receipt()
        self.client.generate.side_effect = TimeoutError("fixture timeout")
        with self.assertRaises(TimeoutError):
            nodes.Wan27Generate().generate(receipt, True, 9, self.key)
        self.client.generate.assert_called_once()

    def test_api_task_response_is_unwrapped_and_pending_has_no_outputs(self):
        # GET /api/v1/tasks/:id returns a task directly, unlike POST /generations.
        self.client.task.return_value = {"id": "fixture-task", "status": "processing", "outputs": ["https://example.test/unfinished.png"]}
        status, urls, raw = nodes.Wan27GetTask().get_task("fixture-task")
        self.assertEqual(status, "processing")
        self.assertEqual(json.loads(urls), [])
        self.client.task.return_value = {"id": "fixture-task", "status": "succeeded", "outputs": ["https://example.test/result.png"]}
        self.assertEqual(json.loads(nodes.Wan27GetTask().get_task("fixture-task")[1]), ["https://example.test/result.png"])

    def test_no_token_in_node_inputs_and_missing_env_is_safe(self):
        self.patcher.stop()
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(sys.modules["comfy_wan27.wan27_client"].Wan27Error) as ctx:
            nodes.Wan27Inspect().inspect("")
        self.assertEqual(ctx.exception.code, "AUTH_REQUIRED")
        self.patcher.start()
        for cls in module.NODE_CLASS_MAPPINGS.values():
            self.assertNotIn("token", cls.INPUT_TYPES()["required"])

    def test_malformed_json_and_nonfinite_cost_do_not_generate(self):
        for data in ["[]", '{"x":NaN}', "not json"]:
            with self.assertRaises(ValueError):nodes.Wan27Estimate().estimate(data)
        self.client.estimate.return_value = {"credits": float("nan")}
        with self.assertRaises(ValueError):self.receipt()
        self.client.generate.assert_not_called()

if __name__ == "__main__":
    unittest.main()
