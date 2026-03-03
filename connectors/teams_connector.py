"""
Teams Connector — post Adaptive Cards for approvals + notifications via Graph API
Pattern: try real Graph API / Webhook → fall back to in-memory mock

Production: set TEAMS_WEBHOOK_URL or AZURE_CLIENT_ID in .env
Local dev:  stores approval records in-memory
"""
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── In-memory approval store (local dev) ─────────────
_approvals = []


def _is_configured() -> bool:
    return bool(os.getenv("TEAMS_WEBHOOK_URL") or os.getenv("AZURE_CLIENT_ID"))


def send_approval_card(title: str, description: str,
                        approver: str = "Delivery Lead",
                        requested_by: str = "PMO AI") -> dict:
    """
    Send an approval request as an Adaptive Card to Teams.
    Falls back to in-memory storage if not configured.
    """
    approval_id = f"APR-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    approval_record = {
        "approval_id": approval_id,
        "title": title,
        "description": description,
        "approver": approver,
        "requested_by": requested_by,
        "status": "Pending",
        "created_at": datetime.now().isoformat(),
    }

    if _is_configured():
        try:
            _post_adaptive_card(approval_record)
            approval_record["channel"] = "Teams"
            logger.info(f"Approval card sent to Teams: {approval_id}")
        except Exception as e:
            logger.warning(f"Teams card failed: {e} — storing locally")
            approval_record["channel"] = "local_mock"
    else:
        approval_record["channel"] = "local_mock"
        logger.info(f"[MOCK] Approval logged locally: {approval_id}")

    _approvals.append(approval_record)
    return approval_record


def _post_adaptive_card(approval: dict):
    """Post an Adaptive Card to Teams via webhook or Graph API."""
    import requests

    webhook_url = os.getenv("TEAMS_WEBHOOK_URL")
    if webhook_url:
        # Incoming Webhook — simplest approach
        card = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "summary": f"Approval: {approval['title']}",
            "themeColor": "0076D7",
            "title": f"🔔 Approval Request: {approval['title']}",
            "sections": [{
                "activityTitle": f"Requested by: {approval['requested_by']}",
                "facts": [
                    {"name": "Approval ID", "value": approval["approval_id"]},
                    {"name": "Description", "value": approval["description"]},
                    {"name": "Approver",    "value": approval["approver"]},
                    {"name": "Status",      "value": "⏳ Pending"},
                ],
                "markdown": True
            }],
            "potentialAction": [
                {"@type": "ActionCard", "name": "Approve", "actions": [
                    {"@type": "HttpPOST", "name": "Approve", "target": "https://your-app/approve"}
                ]},
                {"@type": "ActionCard", "name": "Reject", "actions": [
                    {"@type": "HttpPOST", "name": "Reject", "target": "https://your-app/reject"}
                ]},
            ]
        }
        resp = requests.post(webhook_url, json=card, timeout=10)
        resp.raise_for_status()
        return

    # Fallback: Graph API (requires more setup)
    raise NotImplementedError("Graph API approval cards require additional setup")


def send_notification(channel_name: str, message: str) -> dict:
    """Send a simple text notification to a Teams channel."""
    if _is_configured() and os.getenv("TEAMS_WEBHOOK_URL"):
        try:
            import requests
            requests.post(
                os.getenv("TEAMS_WEBHOOK_URL"),
                json={"text": message},
                timeout=10
            )
            logger.info(f"Teams notification sent: {message[:50]}...")
            return {"channel": channel_name, "message": message, "status": "sent"}
        except Exception as e:
            logger.warning(f"Teams notification failed: {e}")

    logger.info(f"[MOCK] Teams notification: {message[:50]}...")
    return {"channel": channel_name, "message": message, "status": "mock_logged"}


def get_all_approvals() -> list[dict]:
    """Get all approval records."""
    return _approvals


def update_approval(approval_id: str, status: str) -> dict | None:
    """Update approval status (Approved/Rejected)."""
    for a in _approvals:
        if a["approval_id"] == approval_id:
            a["status"] = status
            a["resolved_at"] = datetime.now().isoformat()
            logger.info(f"Approval {approval_id} → {status}")
            return a
    return None
