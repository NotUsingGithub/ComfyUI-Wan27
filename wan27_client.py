"""Dependency-free HTTPS client; no automatic paid retries or credential storage."""

import json
import math
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class Wan27Error(Exception):
    """API/client failure exposing a stable code and optional HTTP status."""

    def __init__(self, code: str, message: str, status: int = 0):
        super().__init__(message)
        self.code = code
        self.status = status


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise Wan27Error("REDIRECT_REJECTED", "API redirects are not followed.", code)


def _segment(value: str) -> str:
    if not isinstance(value, str) or not value or value in (".", "..") or re.search(r"[\x00-\x1f]", value):
        raise Wan27Error("INVALID_INPUT", "Provide a nonempty model or task ID.")
    return quote(value, safe="")


class Wan27:
    """Client for https://wan2-7.io/api/v1.

    Supply an existing access token from a server-side secret store. API access
    requires an active paid subscription and generation consumes credits.
    No token is read from the CLI vault or written to disk by this package.
    """

    def __init__(self, token: str, *, timeout: float = 120):
        if not isinstance(token, str) or not token.strip() or "\r" in token or "\n" in token:
            raise Wan27Error("AUTH_REQUIRED", "Provide an existing Wan27 access token.")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise Wan27Error("INVALID_INPUT", "timeout must be greater than 0 and at most 120 seconds.")
        self._token = token
        self._timeout = timeout
        self._opener = build_opener(_NoRedirect())

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None, request_id: str | None = None) -> dict[str, Any]:
        payload = None
        if body is not None:
            if not isinstance(body, dict):
                raise Wan27Error("INVALID_INPUT", "Input must be a JSON object.")
            try:
                payload = json.dumps(body, allow_nan=False, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            except (ValueError, TypeError):
                raise Wan27Error("INVALID_INPUT", "Input must contain valid JSON values.") from None
            if len(payload) > 32_768:
                raise Wan27Error("INVALID_INPUT", "Request exceeds 32 KiB.")
        route, marker, query = path.partition("?")
        if not route.endswith("/") and "." not in route.rsplit("/", 1)[-1]:
            route += "/"
        url = "https://wan2-7.io/api/v1/" + route + ("?" + query if marker else "")
        headers = {"Authorization": "Bearer " + self._token, "Accept": "application/json", "X-Wan27-Client-Mode": "cli"}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        if request_id is not None:
            headers["Idempotency-Key"] = request_id
        request = Request(url, data=payload, headers=headers, method=method)
        try:
            try:
                response = self._opener.open(request, timeout=self._timeout)
            except HTTPError as error:
                response = error
            with response:
                status = response.getcode()
                raw = response.read(2_097_153)
        except Wan27Error:
            raise
        except (URLError, OSError, TimeoutError):
            raise Wan27Error("SERVICE_UNAVAILABLE", "Could not reach Wan27. A generation may still be accepted; inspect tasks and reuse the same request ID before retrying.") from None
        try:
            if len(raw) > 2_097_152:
                raise ValueError("Response too large")
            data = {} if status == 204 else json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("Expected object")
        except (ValueError, UnicodeError):
            raise Wan27Error("INVALID_RESPONSE", "Unreadable or oversized API response.", status) from None
        if not 200 <= status < 300:
            error = data.get("error")
            error = error if isinstance(error, dict) else {}
            code = error.get("code")
            message = error.get("message")
            raise Wan27Error(code if isinstance(code, str) else "API_ERROR", message if isinstance(message, str) else f"Wan27 returned HTTP {status}.", status)
        return data

    def account(self) -> dict[str, Any]:
        """Read access eligibility and credit balance."""
        return self._call("GET", "account")

    def models(self) -> dict[str, Any]:
        """List currently supported models."""
        return self._call("GET", "models")

    def model(self, model_id: str) -> dict[str, Any]:
        """Read the current model input schema."""
        return self._call("GET", "models/" + _segment(model_id))

    def estimate(self, input: dict[str, Any]) -> dict[str, Any]:
        """Estimate credits without creating a paid task."""
        return self._call("POST", "estimates", input)

    def generate(self, input: dict[str, Any], *, request_id: str) -> dict[str, Any]:
        """Create an authorized paid generation. Retain the ID; retries reuse it.

        Never use a new request ID solely because a network request timed out.
        This method does not retry or poll automatically.
        """
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{16,128}", request_id):
            raise Wan27Error("INVALID_INPUT", "request_id must be 16–128 letters, digits, underscores or hyphens.")
        return self._call("POST", "generations", input, request_id)

    def tasks(self, *, limit: int = 20, cursor: str | None = None) -> dict[str, Any]:
        """List tasks; cursor comes from a previous service response."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise Wan27Error("INVALID_INPUT", "limit must be between 1 and 50.")
        query = {"limit": str(limit)}
        if cursor:
            query["cursor"] = cursor
        return self._call("GET", "tasks?" + urlencode(query))

    def task(self, task_id: str) -> dict[str, Any]:
        """Read task state and outputs; only succeeded means completion."""
        return self._call("GET", "tasks/" + _segment(task_id))
