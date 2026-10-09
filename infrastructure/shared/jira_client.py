"""Minimal Jira Service Management REST client."""

import time
from typing import Any

import requests  # type: ignore[import-untyped]  # Pinned requests has no bundled stubs.


class JiraClient:
    def __init__(
        self,
        credentials: dict[str, Any],
        session=None,
        timeout: int = 10,
        sleeper=time.sleep,
    ):
        self.base_url = credentials["base_url"].rstrip("/")
        self.auth = (credentials["email"], credentials["api_token"])
        self.session = session or requests.Session()
        self.timeout = timeout
        self.transitions = credentials.get("transitions", {})
        self.sleeper = sleeper

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        last_error = None
        for attempt in range(3):
            try:
                response = self.session.request(
                    method,
                    f"{self.base_url}{path}",
                    auth=self.auth,
                    timeout=self.timeout,
                    headers={
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    **kwargs,
                )
                if response.status_code not in {429, 500, 502, 503, 504}:
                    response.raise_for_status()
                    return response.json() if response.content else {}
                last_error = requests.HTTPError(
                    f"Jira returned retryable status {response.status_code}",
                    response=response,
                )
            except requests.RequestException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                if status_code and status_code not in {429, 500, 502, 503, 504}:
                    raise
                last_error = exc
            if attempt < 2:
                self.sleeper(2**attempt)
        raise RuntimeError("Jira API request failed after retries") from last_error

    def _transition_id(self, request_id: str, status: str) -> str:
        configured = self.transitions.get(status)
        if configured:
            return str(configured)
        result = self._request("GET", f"/rest/api/3/issue/{request_id}/transitions")
        expected = status.casefold()
        for transition in result.get("transitions", []):
            destination = transition.get("to", {}).get("name", "")
            if (
                transition.get("name", "").casefold() == expected
                or destination.casefold() == expected
            ):
                return str(transition["id"])
        raise RuntimeError(f"Jira transition not available: {status}")

    def _pending_approval_id(self, request_id: str) -> str:
        result = self._request("GET", f"/rest/servicedeskapi/request/{request_id}/approval")
        for approval in result.get("values", []):
            if approval.get("canAnswerApproval"):
                return str(approval["id"])
        raise RuntimeError(f"No answerable Jira approval found for {request_id}")

    def update_request_status(
        self, request_id: str, status: str, comment: str | None = None
    ) -> None:
        transition_id = self._transition_id(request_id, status)
        self._request(
            "POST",
            f"/rest/api/3/issue/{request_id}/transitions",
            json={"transition": {"id": transition_id}},
        )
        if comment:
            self.add_comment(request_id, comment)

    def approve_request(self, request_id: str) -> None:
        approval_id = self._pending_approval_id(request_id)
        self._request(
            "POST",
            f"/rest/servicedeskapi/request/{request_id}/approval/{approval_id}",
            json={"decision": "approve"},
        )

    def decline_request(self, request_id: str, reason: str | None = None) -> None:
        approval_id = self._pending_approval_id(request_id)
        self._request(
            "POST",
            f"/rest/servicedeskapi/request/{request_id}/approval/{approval_id}",
            json={"decision": "decline"},
        )
        if reason:
            self.add_comment(request_id, reason)

    def add_comment(self, request_id: str, comment: str) -> None:
        self._request(
            "POST",
            f"/rest/api/3/issue/{request_id}/comment",
            json={
                "body": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [{"type": "text", "text": comment}],
                        }
                    ],
                }
            },
        )
