"""Wan27 ComfyUI nodes. Credentials stay in the host environment, not workflows."""
import hashlib
import json
import math
import os
import re
from .wan27_client import Wan27


def _client():
    return Wan27(os.environ.get("WAN27_ACCESS_TOKEN", ""))


def _json(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _object(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > 32768:
        raise ValueError("Provide a JSON object no larger than 32 KiB.")
    try:
        value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Non-finite JSON")))
    except (ValueError, TypeError):
        raise ValueError("Provide a valid JSON object.") from None
    if not isinstance(value, dict):
        raise ValueError("Provide a JSON object.")
    return value


def _credits(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("The service must return a finite, nonnegative credit estimate.")
    return value


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()).hexdigest()


class Wan27Inspect:
    CATEGORY = "Wan27"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("account_json", "models_or_schema_json")
    FUNCTION = "inspect"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"model_id": ("STRING", {"default": ""})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def inspect(self, model_id):
        client = _client()
        return (_json(client.account()), _json(client.model(model_id) if model_id else client.models()))


class Wan27Estimate:
    CATEGORY = "Wan27"
    RETURN_TYPES = ("STRING", "FLOAT")
    RETURN_NAMES = ("review_json", "estimated_credits")
    FUNCTION = "estimate"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"generation_input_json": ("STRING", {"multiline": True, "default": '{"modelId":"wan2.7-image","prompt":"A paper crane on a desk","resolution":"2K"}'})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def estimate(self, generation_input_json):
        value = _object(generation_input_json)
        result = _client().estimate(value)
        credits = _credits(result.get("credits"))
        receipt = {"version": 1, "input": value, "inputDigest": _digest(value), "estimatedCredits": credits}
        return (_json(receipt), float(credits))


class Wan27Generate:
    CATEGORY = "Wan27"
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("task_id", "submission_json")
    FUNCTION = "generate"
    OUTPUT_NODE = True

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "review_json": ("STRING", {"multiline": True, "default": ""}),
            "approved_after_review": ("BOOLEAN", {"default": False}),
            "maximum_credits": ("FLOAT", {"default": 0.0, "min": 0.0}),
            "request_id": ("STRING", {"default": ""}),
        }}

    def generate(self, review_json, approved_after_review, maximum_credits, request_id):
        if approved_after_review is not True:
            raise ValueError("First display and review the estimate, then explicitly approve this generation.")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", request_id):
            raise ValueError("Supply a stable 16–128 character request ID. Reuse it when retrying the same generation.")
        receipt = _object(review_json)
        value = receipt.get("input")
        if receipt.get("version") != 1 or not isinstance(value, dict) or receipt.get("inputDigest") != _digest(value):
            raise ValueError("Invalid review receipt. Run Wan27 Estimate again.")
        reviewed = _credits(receipt.get("estimatedCredits"))
        ceiling = _credits(maximum_credits)
        if reviewed > ceiling:
            raise ValueError("Reviewed estimate exceeds your maximum credits.")
        client = _client()
        current = _credits(client.estimate(value).get("credits"))
        if current != reviewed or current > ceiling:
            raise ValueError("The estimate changed. Review a fresh estimate and confirm again.")
        # Exactly one attempt with the user's retained idempotency key. No retry/poll loop.
        result = client.generate(value, request_id=request_id)
        task = result.get("task")
        task_id = task.get("id") if isinstance(task, dict) else None
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("The service may have accepted the request. Inspect your tasks and reuse the same request ID; do not submit with a new ID.")
        return (task_id, _json(result))


class Wan27GetTask:
    CATEGORY = "Wan27"
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("status", "outputs_json", "task_json")
    FUNCTION = "get_task"

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"task_id": ("STRING", {"default": ""})}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float("nan")

    def get_task(self, task_id):
        response = _client().task(task_id)
        task = response
        if not isinstance(task, dict):
            raise ValueError("Unreadable task response.")
        status = task.get("status")
        if not isinstance(status, str):
            raise ValueError("Unreadable task status.")
        # Only succeeded is a completed generation. Never download/execute returned URLs.
        outputs = task.get("outputs", []) if status == "succeeded" else []
        return (status, _json(outputs), _json(response))


NODE_CLASS_MAPPINGS = {"Wan27Inspect": Wan27Inspect, "Wan27Estimate": Wan27Estimate, "Wan27Generate": Wan27Generate, "Wan27GetTask": Wan27GetTask}
NODE_DISPLAY_NAME_MAPPINGS = {"Wan27Inspect": "Wan27 Account and Models", "Wan27Estimate": "Wan27 Estimate Credits", "Wan27Generate": "Wan27 Submit Generation", "Wan27GetTask": "Wan27 Get Task"}
