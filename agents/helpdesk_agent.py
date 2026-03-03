"""
Helpdesk Agent — handles IT support ticket operations via ServiceNow
Pipeline: query → Groq extracts intent JSON → ServiceNow connector → confirmation

Handles: create ticket, check status, list tickets, escalate, update
LLM:     Groq (llama-3.1-8b-instant) — extracts action + parameters
Data:    ServiceNow (mock fallback for local dev)
"""
import os
import json
import logging
from dotenv import load_dotenv
from utils.llm_client import get_llm_client, get_model_name

from connectors.servicenow_connector import (
    create_ticket, get_ticket, list_tickets, update_ticket, escalate_ticket
)

load_dotenv()
logger = logging.getLogger(__name__)


def _get_helpdesk_client():
    return get_llm_client()


# ── Step 1: Extract helpdesk intent from query ──────
def _classify_helpdesk_action(query: str, chat_history: list = None) -> dict:
    """
    Use Groq LLM to parse natural language into structured helpdesk JSON.
    Returns dict with: action, short_description, description, urgency, category
    """
    client = _get_helpdesk_client()
    model  = get_model_name()

    system = """You are an IT helpdesk classifier for KPMG.
Extract the helpdesk action from the user query and return ONLY valid JSON.
No explanation, no markdown, just raw JSON.

Actions available:
- create_ticket   → user wants to report an explicitly stated IT problem or request specific help
- check_status    → user wants to check a ticket's status (needs ticket number)
- list_tickets    → user wants to see all/recent tickets
- escalate        → user wants to escalate an existing ticket
- update_ticket   → user wants to update/close a ticket
- clarification_needed → user is just saying hello, asking a vague "help me" without an IT problem, or just chatting.

JSON format:
{
  "action": "create_ticket|check_status|list_tickets|escalate|update_ticket|clarification_needed",
  "short_description": "brief title of the issue",
  "description": "full description from query",
  "urgency": "1|2|3",
  "category": "Network|Email|Access|Hardware|Software|General",
  "ticket_number": "INC number if mentioned, else null",
  "status_filter": "Open|In Progress|Resolved|null"
}
Note on urgency: ALWAYS map High to "1", Medium to "2", and Low to "3"."""

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
            "action": "create_ticket",
            "short_description": "General IT Request",
            "description": query,
            "urgency": "3",
            "category": "General",
            "ticket_number": None,
            "status_filter": None,
        }


# ── Action Handlers ──────────────────────────────────

def _handle_create_ticket(params: dict) -> str:
    ticket = create_ticket(
        short_description=params.get("short_description", "IT Request"),
        description=params.get("description", ""),
        urgency=params.get("urgency", "3"),
        category=params.get("category", "General"),
    )
    return (
        f"✅ **Ticket created successfully!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Ticket #** | {ticket['number']} |\n"
        f"| **Title** | {ticket['short_description']} |\n"
        f"| **Urgency** | {ticket['urgency']} |\n"
        f"| **Category** | {ticket['category']} |\n"
        f"| **Assigned to** | {ticket['assigned_to']} |\n"
        f"| **Status** | {ticket['state']} |"
    )


def _handle_check_status(params: dict) -> str:
    ticket_num = params.get("ticket_number")
    if not ticket_num:
        return "⚠️ Please provide a ticket number (e.g., INC0010001) to check its status."

    ticket = get_ticket(ticket_num)
    if not ticket:
        return f"❌ Ticket **{ticket_num}** not found. Please verify the ticket number."

    return (
        f"Ticket **{ticket['number']}** ('{ticket['short_description']}') is currently **{ticket['state']}**. "
        f"It is assigned to {ticket['assigned_to']} with a priority of {ticket.get('priority', 'N/A')}."
    )


def _handle_list_tickets(params: dict) -> str:
    state = params.get("status_filter")
    tickets = list_tickets(state=state, limit=5)

    if not tickets:
        return "📭 No tickets found matching your criteria."

    lines = ["📋 **Recent IT Helpdesk Tickets**\n"]
    lines.append("| Ticket # | Title | Status | Priority |")
    lines.append("|----------|-------|--------|----------|")
    for t in tickets:
        lines.append(
            f"| {t['number']} | {t['short_description']} | {t['state']} | {t.get('priority', 'N/A')} |"
        )
    return "\n".join(lines)


def _handle_escalate(params: dict) -> str:
    ticket_num = params.get("ticket_number")
    if not ticket_num:
        return "⚠️ Please provide a ticket number to escalate (e.g., INC0010001)."

    result = escalate_ticket(ticket_num)
    if not result:
        return f"❌ Could not escalate ticket **{ticket_num}** — ticket not found."

    return (
        f"🚨 **Ticket {ticket_num} escalated!**\n\n"
        f"| Field | Value |\n"
        f"|-------|-------|\n"
        f"| **Urgency** | 1 - Critical |\n"
        f"| **Priority** | 1 - Critical |\n"
        f"| **Status** | In Progress |\n"
        f"| **Reassigned to** | Senior IT Support |"
    )


def _handle_update(params: dict) -> str:
    ticket_num = params.get("ticket_number")
    if not ticket_num:
        return "⚠️ Please provide a ticket number to update."

    updates = {}
    if params.get("status_filter"):
        updates["state"] = params["status_filter"]
    if params.get("description"):
        updates["comments"] = params["description"]

    result = update_ticket(ticket_num, updates)
    if not result:
        return f"❌ Ticket **{ticket_num}** not found."

    return f"✅ Ticket **{ticket_num}** updated successfully."


# ── Required Fields per Helpdesk Action ───────────────
HELPDESK_REQUIRED_FIELDS = {
    "create_ticket": {
        "short_description": "Issue Title (e.g., Laptop not connecting to WiFi)",
        "category":          "Category (Network / Email / Access / Hardware / Software / General)",
    },
}


def _check_helpdesk_missing(action: str, params: dict) -> list:
    """Check which required fields are missing or have placeholder values."""
    required = HELPDESK_REQUIRED_FIELDS.get(action, {})
    missing = []
    placeholders = {None, "", "null", "N/A", "General IT Request", "IT Request"}
    
    for field_key, field_label in required.items():
        val = params.get(field_key)
        if val is None or str(val).strip() in placeholders:
            missing.append(field_label)
    return missing


# ── Main agent function ──────────────────────────────
def run_helpdesk_agent(query: str, chat_history: list = None) -> dict:
    """
    Full helpdesk pipeline:
    1. Groq LLM classifies helpdesk action + extracts parameters
    2. Validate required fields — if missing, ask the user
    3. Execute ServiceNow operation via connector
    4. Return formatted confirmation
    """
    params = _classify_helpdesk_action(query, chat_history=chat_history)
    action = params.get("action", "create_ticket")

    # Field validation for ticket creation
    if action in HELPDESK_REQUIRED_FIELDS:
        missing = _check_helpdesk_missing(action, params)
        if missing:
            missing_str = "\n".join(f"  ⬜ {m}" for m in missing)
            provided = []
            for k, v in params.items():
                if v and str(v).strip() not in {None, "", "null", "N/A"}:
                    provided.append(f"  ✓ **{k.replace('_', ' ').title()}**: {v}")
            provided_str = "\n".join(provided) if provided else "  _(none yet)_"
            
            prompt = (
                f"🎫 **Create Ticket — Missing Details**\n\n"
                f"I need a few more details to raise a ticket:\n\n"
                f"**Already captured:**\n{provided_str}\n\n"
                f"**Please provide:**\n{missing_str}\n\n"
                f"💡 _Reply with the details (e.g., \"My laptop won't connect to WiFi, Category: Network\")_"
            )
            return {
                "answer":  prompt,
                "sources": [f"ServiceNow: {action} (awaiting details)"],
                "agent":   "helpdesk"
            }

    if action == "clarification_needed":
        return {
            "answer": "Hello! 🐾 How can I help you today? Please describe your IT issue or let me know what you need assistance with.",
            "sources": ["ServiceNow: Awaiting details"],
            "agent": "helpdesk"
        }

    action_map = {
        "create_ticket": _handle_create_ticket,
        "check_status":  _handle_check_status,
        "list_tickets":  _handle_list_tickets,
        "escalate":      _handle_escalate,
        "update_ticket": _handle_update,
    }

    handler = action_map.get(action, _handle_create_ticket)
    result  = handler(params)

    return {
        "answer":  result,
        "sources": [f"ServiceNow: {action}"],
        "agent":   "helpdesk"
    }
