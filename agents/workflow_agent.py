"""
Workflow Agent — executes actions: emails, approvals, RAID log updates, system logs
Pipeline: query → Groq extracts action JSON → execute via connector → confirmation

Handles: Email notifications (Outlook), approval routing (Teams), RAID log (SharePoint),
         system log queries (Azure App Insights)
LLM:     Groq (llama-3.1-8b-instant) — classifies intent + extracts parameters
Note:    Ticket creation moved to helpdesk_agent.py
"""
import os
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from utils.llm_client import get_llm_client, get_model_name

from connectors.outlook_connector import (send_email, get_sent_emails,
    initiate_onboarding, initiate_offboarding, tag_resource, get_onboarding_records,
    cancel_workflow_request)
from connectors.teams_connector import send_approval_card, send_notification, get_all_approvals
from connectors.sharepoint_connector import add_raid_entry, get_raid_logs
from connectors.azure_insights_connector import query_logs, get_performance_summary

load_dotenv()
logger = logging.getLogger(__name__)


def _get_workflow_client():
    return get_llm_client()


# ── Step 1: Extract action intent from query ─────────
def _classify_action(query: str, chat_history: list = None) -> dict:
    """
    Use Groq LLM to parse natural language into structured action JSON.
    """
    client = _get_workflow_client()
    model  = get_model_name()

    system = """You are a PMO workflow classifier for KPMG.
Extract the action from the user query and return ONLY valid JSON.
No explanation, no markdown, just raw JSON.

Actions available:
- send_email      → for notifications, updates, alerts to specific people
- approve         → for budget changes, scope changes, sign-offs
- update_raid     → for RAID log entries (Risk, Action, Issue, Decision)
- query_logs      → for checking system logs, errors, performance
- notify_team     → for posting a notification to a Teams channel
- onboard         → for onboarding a new team member / resource to a project
- offboard        → for offboarding / releasing a resource from a project
- tag_resource    → for tagging / re-tagging a resource between projects
- cancel_request  → for cancelling an onboarding, offboarding, or tagging request

JSON format:
{
  "action": "send_email|approve|update_raid|query_logs|notify_team|onboard|offboard|tag_resource|cancel_request",
  "title": "short title",
  "description": "body/details",
  "to_email": "who to notify",
  "approver": "who approves",
  "raid_type": "Risk|Action|Issue|Decision",
  "project": "project name",
  "severity": "Information|Warning|Error|Critical",
  "employee_name": "name of resource",
  "role": "role of resource",
  "department": "department of resource",
  "reason": "reason for offboarding",
  "from_project": "current project",
  "to_project": "new project",
  "request_type": "onboarding|offboarding|tagging",
  "emp_id": "EMP ID for cancellation",
  "timeframe": "today|yesterday|last 4 hours|last 24 hours"
}"""

    messages = [{"role": "system", "content": system}]
    if chat_history:
        messages.extend(chat_history[-10:])
    messages.append({"role": "user", "content": f"Query: {query}"})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        max_tokens=300,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(f"LLM returned unparseable JSON: {raw}")
        return {
            "action":      "send_email",
            "title":       "PMO Notification",
            "description": query,
            "to_email":    None,
            "approver":    "Delivery Lead",
            "raid_type":   None,
            "severity":    None,
            "project":     "General",
        }


# ── Action Handlers ───────────────────────────────────

def _handle_send_email(params: dict) -> str:
    to = params.get("to_email") or "pmo-team@kpmg.com"
    result = send_email(
        to=to,
        subject=params.get("title", "PMO Notification"),
        body=params.get("description", ""),
    )

    status = "sent" if result.get("status") == "sent" else "logged (mock mode)"
    return (
        f"📧 **Email {status}!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **To** | {to} |\n"
        f"| **Subject** | {params.get('title')} |\n"
        f"| **Status** | {status} |"
    )


def _handle_approval(params: dict) -> str:
    result = send_approval_card(
        title=params.get("title", "Approval Request"),
        description=params.get("description", ""),
        approver=params.get("approver", "Delivery Lead"),
    )
    channel = result.get("channel", "local_mock")
    return (
        f"✅ **Approval request created!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Approval ID** | {result['approval_id']} |\n"
        f"| **Title** | {result['title']} |\n"
        f"| **Sent to** | {result['approver']} |\n"
        f"| **Channel** | {channel} |\n"
        f"| **Status** | ⏳ Pending |"
    )


def _handle_raid_update(params: dict) -> str:
    entry = add_raid_entry(
        entry_type=params.get("raid_type", "Risk"),
        title=params.get("title", "Log Entry"),
        description=params.get("description", ""),
        project=params.get("project", "General"),
    )
    return (
        f"✅ **RAID log updated!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Log ID** | {entry['log_id']} |\n"
        f"| **Type** | {entry['type']} |\n"
        f"| **Title** | {entry['title']} |\n"
        f"| **Project** | {entry['project']} |\n"
        f"| **Source** | {entry['source']} |"
    )


def _handle_query_logs(params: dict) -> str:
    severity = params.get("severity")
    timeframe = params.get("timeframe")
    logs = query_logs(severity=severity, timeframe=timeframe, limit=5)

    if not logs:
        return "📭 No system logs found matching your criteria."

    # Use LLM to summarize logs
    import json
    from groq import Groq
    import os
    
    perf = get_performance_summary()
    payload = {
        "recent_logs": logs,
        "performance_24h": perf
    }
    
    system_prompt = """You are an expert IT Systems Administrator.
You are given a JSON array of recent system logs and a 24-hour performance summary block.
Please provide a short, 2-3 sentence summary of the system health.
Highlight any critical errors or warnings. Do NOT return a table or raw JSON. Keep it human-readable."""

    try:
        client = _get_workflow_client()
        model = get_model_name()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload)}
            ],
            temperature=0,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"System logs retrieved, but failed to summarize via LLM: {str(e)}"


def _handle_notify_team(params: dict) -> str:
    result = send_notification(
        channel_name="PMO General",
        message=f"📢 {params.get('title', 'Notification')}: {params.get('description', '')}",
    )
    status = "sent" if result.get("status") == "sent" else "logged (mock mode)"
    return (
        f"📢 **Teams notification {status}!**\n\n"
        f"**Channel:** {result.get('channel', 'PMO General')}\n"
        f"**Message:** {params.get('description', '')[:200]}"
    )


def _handle_onboard(params: dict) -> str:
    """Handle onboarding workflow — PMO Admin only."""
    result = initiate_onboarding(
        employee_name=params.get("employee_name", params.get("title", "New Resource")),
        role=params.get("role", "Team Member"),
        project=params.get("project", "General"),
        department=params.get("department", "Engineering"),
    )
    checklist = result.get("checklist", {})
    checklist_items = "\n".join(f"| {k.replace('_', ' ').title()} | ⬜ Pending |" for k in checklist)
    return (
        f"👤 **Onboarding Initiated!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **EMP ID** | {result.get('emp_id', 'N/A')} |\n"
        f"| **Employee** | {result['employee']} |\n"
        f"| **Role** | {result['role']} |\n"
        f"| **Project** | {result['project']} |\n"
        f"| **Department** | {result['department']} |\n"
        f"| **Start Date** | {result['start_date']} |\n"
        f"| **Status** | ⏳ {result['status']} |\n\n"
        f"**Onboarding Checklist:**\n\n"
        f"| Task | Status |\n|------|--------|\n{checklist_items}\n\n"
        f"📧 **Approval email sent to manager** (Email ID: {result.get('approval_email_id', 'N/A')})"
    )


def _handle_offboard(params: dict) -> str:
    """Handle offboarding workflow — PMO Admin only."""
    result = initiate_offboarding(
        employee_name=params.get("employee_name", params.get("title", "Resource")),
        role=params.get("role", "Team Member"),
        project=params.get("project", "General"),
        reason=params.get("reason", "Project completion"),
    )
    checklist = result.get("checklist", {})
    checklist_items = "\n".join(f"| {k.replace('_', ' ').title()} | ⬜ Pending |" for k in checklist)
    return (
        f"📤 **Offboarding Initiated!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **EMP ID** | {result.get('emp_id', 'N/A')} |\n"
        f"| **Employee** | {result['employee']} |\n"
        f"| **Role** | {result['role']} |\n"
        f"| **Project** | {result['project']} |\n"
        f"| **Reason** | {result['reason']} |\n"
        f"| **Last Date** | {result['last_date']} |\n"
        f"| **Status** | ⏳ {result['status']} |\n\n"
        f"**Offboarding Checklist:**\n\n"
        f"| Task | Status |\n|------|--------|\n{checklist_items}\n\n"
        f"📧 **Approval email sent to manager** (Email ID: {result.get('approval_email_id', 'N/A')})"
    )


def _handle_tag_resource(params: dict) -> str:
    """Handle resource tagging/re-tagging workflow — PMO Admin only."""
    result = tag_resource(
        emp_id=params.get("emp_id", params.get("id", "UNKNOWN")),
        employee_name=params.get("employee_name", params.get("title", "Resource")),
        role=params.get("role", "Team Member"),
        from_project=params.get("from_project", params.get("project", "Current Project")),
        to_project=params.get("to_project", params.get("project", "New Project")),
    )
    return (
        f"🏷️ **Resource Tagging Initiated!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **EMP ID** | {result.get('emp_id', 'N/A')} |\n"
        f"| **Employee** | {result['employee']} |\n"
        f"| **Role** | {result['role']} |\n"
        f"| **From Project** | {result['from_project']} |\n"
        f"| **To Project** | {result['to_project']} |\n"
        f"| **Status** | ⏳ {result['status']} |\n\n"
        f"📧 **Approval email sent to manager** (Email ID: {result.get('approval_email_id', 'N/A')})"
    )


def _handle_cancel(params: dict) -> str:
    """Handle cancellation of workflow requests — PMO Admin only."""
    # Attempt to extract the type of request and employee ID
    req_type = params.get("request_type", params.get("type", ""))
    emp_id = params.get("emp_id", params.get("id", ""))
    
    if not req_type or not emp_id:
        return "❌ Missing parameters. Please provide the Request Type (Onboarding/Offboarding/Tagging) and the EMP ID."
        
    result = cancel_workflow_request(req_type, emp_id)
    
    if result.get("success"):
        return f"❌ **Request Cancelled Successfully**\n\n{result.get('message')}"
    else:
        return f"⚠️ **Cancellation Failed**\n\n{result.get('error')}"


# ── Required Fields per Action ────────────────────────
REQUIRED_FIELDS = {
    "onboard": {
        "employee_name": "Employee Name (e.g., Priya Sharma)",
        "role":          "Role (e.g., Business Analyst, Developer)",
        "project":       "Project Name (e.g., EOSL, Alpha)",
        "department":    "Department (e.g., Engineering, Finance)",
    },
    "offboard": {
        "employee_name": "Employee Name",
        "role":          "Role",
        "project":       "Project Name",
        "reason":        "Reason for offboarding (e.g., Project completion, Resignation)",
    },
    "tag_resource": {
        "employee_name": "Employee Name",
        "role":          "Role",
        "from_project":  "Current Project",
        "to_project":    "New Project",
    },
    "send_email": {
        "to_email":      "Recipient Email (e.g., pmo-team@kpmg.com)",
        "title":         "Email Subject",
        "description":   "Email Body / Details",
    },
    "approve": {
        "title":         "Approval Title",
        "description":   "Approval Details",
        "approver":      "Approver Name (e.g., Delivery Lead)",
    },
}


def _check_missing_fields(action: str, params: dict) -> list:
    """Check which required fields are missing or have placeholder/default values."""
    required = REQUIRED_FIELDS.get(action, {})
    missing = []
    # Values that are considered "not provided"
    placeholders = {None, "", "null", "N/A", "UNKNOWN", "New Resource", "Resource",
                    "Team Member", "General", "Current Project", "New Project",
                    "Engineering", "Project completion", "PMO Notification",
                    "Delivery Lead", "pmo-team@kpmg.com"}
    
    for field_key, field_label in required.items():
        val = params.get(field_key)
        # Also check alternate keys (like "title" for "employee_name")
        if val is None and field_key == "employee_name":
            val = params.get("title")
        if val is None or str(val).strip() in placeholders:
            missing.append(field_label)
    return missing


def _format_missing_fields_prompt(action: str, params: dict, missing: list) -> str:
    """Format a user-friendly prompt listing the missing fields."""
    action_labels = {
        "onboard": "🚀 Onboarding", "offboard": "📤 Offboarding",
        "tag_resource": "🏷️ Resource Tagging", "send_email": "📧 Email",
        "approve": "✅ Approval",
    }
    action_name = action_labels.get(action, action.replace("_", " ").title())
    
    # Show what we already have
    provided = []
    for k, v in params.items():
        if v and str(v).strip() not in {None, "", "null", "N/A"}:
            provided.append(f"  ✓ **{k.replace('_', ' ').title()}**: {v}")
    
    provided_str = "\n".join(provided) if provided else "  _(none yet)_"
    missing_str = "\n".join(f"  ⬜ {m}" for m in missing)
    
    return (
        f"📋 **{action_name} — Missing Details**\n\n"
        f"I need a few more details to proceed:\n\n"
        f"**Already captured:**\n{provided_str}\n\n"
        f"**Please provide:**\n{missing_str}\n\n"
        f"💡 _Reply with the missing details (e.g., \"Role: BA, Project: EOSL, Department: Engineering\")_"
    )


# ── Main agent function ───────────────────────────────
def run_workflow_agent(query: str, chat_history: list = None) -> dict:
    """
    Full workflow pipeline:
    1. Groq LLM classifies action + extracts parameters as JSON
    2. Validate required fields — if missing, ask the user
    3. Execute via appropriate connector
    4. Return confirmation with details
    """
    params = _classify_action(query, chat_history=chat_history)
    action = params.get("action", "send_email")

    # Field validation — only for actions that have required fields
    if action in REQUIRED_FIELDS:
        missing = _check_missing_fields(action, params)
        if missing:
            prompt = _format_missing_fields_prompt(action, params, missing)
            return {
                "answer":  prompt,
                "sources": [f"Workflow: {action} (awaiting details)"],
                "agent":   "workflow"
            }

    action_map = {
        "send_email":    _handle_send_email,
        "approve":       _handle_approval,
        "update_raid":   _handle_raid_update,
        "query_logs":    _handle_query_logs,
        "notify_team":   _handle_notify_team,
        "onboard":       _handle_onboard,
        "offboard":      _handle_offboard,
        "tag_resource":  _handle_tag_resource,
        "cancel_request": _handle_cancel,
    }

    handler = action_map.get(action, _handle_send_email)
    result  = handler(params)

    return {
        "answer":  result,
        "sources": [f"Workflow: {action}"],
        "agent":   "workflow"
    }


# ── Utility: get all records (for admin view) ────────
def get_all_tickets() -> list:
    """Legacy compatibility — tickets now in helpdesk_agent."""
    from connectors.servicenow_connector import list_tickets
    return list_tickets(limit=20)

def get_all_logs() -> list:
    return get_raid_logs()

def get_all_approval_records() -> list:
    return get_all_approvals()
