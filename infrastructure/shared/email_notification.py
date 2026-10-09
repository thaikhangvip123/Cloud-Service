"""SES email rendering and delivery."""

from html import escape
from typing import Any
from urllib.parse import urlencode

import boto3


class EmailNotifier:
    def __init__(self, sender: str, client=None):
        self.sender = sender
        self.client = client or boto3.client("ses")

    def _send(self, recipient: str, subject: str, html: str, text: str) -> None:
        self.client.send_email(
            Source=self.sender,
            Destination={"ToAddresses": [recipient]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Html": {"Data": html, "Charset": "UTF-8"},
                    "Text": {"Data": text, "Charset": "UTF-8"},
                },
            },
        )

    def send_access_granted_email(self, recipient: str, details: dict[str, Any]) -> None:
        request_id = escape(details["requestId"])
        portal = escape(details["identityCenterPortalUrl"])
        html = (
            f"<h2>Production access ready</h2><p>Request {request_id} is active until "
            f"{escape(details['expiresAt'])}.</p><p><a href=\"{portal}\">Open AWS portal</a></p>"
        )
        self._send(recipient, f"Access ready: {request_id}", html, f"Open AWS portal: {portal}")

    def send_access_expired_email(self, recipient: str, request_id: str) -> None:
        safe_id = escape(request_id)
        self._send(
            recipient,
            f"Access expired: {safe_id}",
            f"<h2>Production access expired</h2><p>Request {safe_id} has been revoked.</p>",
            f"Request {safe_id} has been revoked.",
        )

    def send_approval_email(
        self,
        recipient: str,
        request_id: str,
        base_url: str,
        approve_token: str,
        decline_token: str,
        details: dict[str, Any],
    ) -> None:
        approve_url = f"{base_url}?{urlencode({'token': approve_token, 'action': 'approve'})}"
        decline_url = f"{base_url}?{urlencode({'token': decline_token, 'action': 'decline'})}"
        safe_id = escape(request_id)
        html = (
            f"<h2>Approval required: {safe_id}</h2>"
            f"<p>{escape(details['requester'])} requests {escape(details['accessType'])} "
            f"access to {escape(details['awsAccount'])} for "
            f"{escape(str(details['durationHours']))} hours.</p>"
            f'<p><a href="{escape(approve_url)}">Approve</a>&nbsp;&nbsp;'
            f'<a href="{escape(decline_url)}">Decline</a></p>'
        )
        self._send(recipient, f"Approval required: {safe_id}", html, f"Review request {safe_id}")


def _default_notifier() -> EmailNotifier:
    from shared.config import settings

    return EmailNotifier(settings.ses_sender_email)


def send_access_granted_email(recipient: str, details: dict[str, Any]) -> None:
    _default_notifier().send_access_granted_email(recipient, details)


def send_access_expired_email(recipient: str, request_id: str) -> None:
    _default_notifier().send_access_expired_email(recipient, request_id)


def send_approval_email(
    recipient: str,
    request_id: str,
    base_url: str,
    approve_token: str,
    decline_token: str,
    details: dict[str, Any],
) -> None:
    _default_notifier().send_approval_email(
        recipient,
        request_id,
        base_url,
        approve_token,
        decline_token,
        details,
    )
