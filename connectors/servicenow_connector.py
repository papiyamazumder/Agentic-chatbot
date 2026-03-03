"""
ServiceNow Connector — IT helpdesk ticket CRUD via ServiceNow Table API
Pattern: try real ServiceNow REST API → fall back to in-memory mock

Production: set SNOW_INSTANCE, SNOW_USER, SNOW_PASSWORD in .env
Local dev:  uses in-memory dict — no ServiceNow instance needed
"""
import os
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

RAW_DOCS_DIR = Path("data/raw_docs")
RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)
TICKETS_FILE = RAW_DOCS_DIR / "IT_Helpdesk_Tickets.xlsx"

def _get_tickets_df() -> pd.DataFrame:
    """Load tickets from Excel or create empty dataframe."""
    if TICKETS_FILE.exists():
        try:
            return pd.read_excel(TICKETS_FILE)
        except Exception as e:
            logger.error(f"Failed to read tickets file: {e}")
    
    # Return empty schema
    return pd.DataFrame(columns=[
        "number", "short_description", "description", "state",
        "urgency", "priority", "category", "assigned_to",
        "opened_at", "caller"
    ])

def _save_tickets_df(df: pd.DataFrame):
    """Save tickets DataFrame to Excel."""
    try:
        df.to_excel(TICKETS_FILE, index=False)
    except Exception as e:
        logger.error(f"Failed to save tickets file: {e}")


def _is_configured() -> bool:
    return bool(os.getenv("SNOW_INSTANCE") and os.getenv("SNOW_USER"))


def _snow_request(method: str, endpoint: str, data: dict = None) -> dict:
    """Make authenticated request to ServiceNow Table API."""
    import requests
    instance = os.getenv("SNOW_INSTANCE")
    url = f"https://{instance}/api/now/table/{endpoint}"

    resp = requests.request(
        method, url,
        auth=(os.getenv("SNOW_USER"), os.getenv("SNOW_PASSWORD")),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        json=data,
        timeout=10
    )
    resp.raise_for_status()
    return resp.json().get("result", {})


def create_ticket(short_description: str, description: str = "",
                   urgency: str = "3", category: str = "General",
                   assigned_to: str = "IT Support", caller: str = "PMO User") -> dict:
    """Create a new incident ticket."""
    if _is_configured():
        try:
            result = _snow_request("POST", "incident", {
                "short_description": short_description,
                "description": description,
                "urgency": urgency,
                "category": category,
                "assignment_group": assigned_to,
                "caller_id": caller,
            })
            logger.info(f"ServiceNow ticket created: {result.get('number')}")
            return {
                "number": result.get("number"),
                "short_description": short_description,
                "state": "Open",
                "urgency": urgency,
                "assigned_to": assigned_to,
            }
        except Exception as e:
            logger.warning(f"ServiceNow create failed: {e} — using mock")

    # Mock fallback using Excel
    df = _get_tickets_df()
    
    # Generate next INC number based on Excel length
    if len(df) > 0:
        last_inc = df['number'].iloc[-1]
        try:
            next_num = int(last_inc.replace("INC", "")) + 1
        except ValueError:
            next_num = 10000 + len(df) + 1
    else:
        next_num = 10000
        
    ticket_num = f"INC{next_num:07d}"

    ticket = {
        "number": ticket_num,
        "short_description": short_description,
        "description": description,
        "state": "Open",
        "urgency": f"{urgency} - {'High' if urgency == '1' else 'Moderate' if urgency == '2' else 'Low'}",
        "priority": f"{urgency} - {'High' if urgency == '1' else 'Moderate' if urgency == '2' else 'Low'}",
        "category": category,
        "assigned_to": assigned_to,
        "opened_at": datetime.now().isoformat(),
        "caller": caller,
    }
    
    # Append to df and save
    new_row_df = pd.DataFrame([ticket])
    df = pd.concat([df, new_row_df], ignore_index=True)
    _save_tickets_df(df)
    
    logger.info(f"[EXCEL MOCK] Ticket created: {ticket_num}")
    return ticket


def get_ticket(ticket_number: str) -> dict | None:
    """Get a single ticket by number."""
    if _is_configured():
        try:
            result = _snow_request("GET", f"incident?sysparm_query=number={ticket_number}&sysparm_limit=1")
            if isinstance(result, list) and result:
                return result[0]
        except Exception as e:
            logger.warning(f"ServiceNow get failed: {e} — using mock")
    df = _get_tickets_df()
    if len(df) == 0:
        return None
        
    mask = df['number'].str.upper() == ticket_number.upper()
    if mask.any():
        record = df[mask].iloc[-1].to_dict()
        # Clean NaNs
        return {k: ("" if pd.isna(v) else v) for k, v in record.items()}
    return None


def list_tickets(state: str = None, limit: int = 10) -> list[dict]:
    """List recent tickets, optionally filtered by state."""
    if _is_configured():
        try:
            query = f"incident?sysparm_limit={limit}&sysparm_orderby=opened_at"
            if state:
                query += f"&sysparm_query=state={state}"
            result = _snow_request("GET", query)
            return result if isinstance(result, list) else [result]
        except Exception as e:
            logger.warning(f"ServiceNow list failed: {e} — using mock")

    # Mock fallback
    df = _get_tickets_df()
    if len(df) == 0:
        return []
        
    if state:
        mask = df['state'].str.lower().str.contains(state.lower(), na=False)
        tickets = df[mask].tail(limit).to_dict('records')
    else:
        tickets = df.tail(limit).to_dict('records')
        
    # Clean NaNs
    tickets = [{k: ("" if pd.isna(v) else v) for k, v in t.items()} for t in tickets]
    
    # Needs reversing so newest is first? Usually tail keeps lowest index at top, so reversing puts newest at index 0
    tickets.reverse()

    logger.info(f"[EXCEL MOCK] Returning {len(tickets)} tickets")
    return tickets


def update_ticket(ticket_number: str, updates: dict) -> dict | None:
    """Update an existing ticket's fields."""
    if _is_configured():
        try:
            result = _snow_request("PATCH", f"incident?sysparm_query=number={ticket_number}", updates)
            return result
        except Exception as e:
            logger.warning(f"ServiceNow update failed: {e} — using mock")

    # Mock fallback
    df = _get_tickets_df()
    mask = df['number'].str.upper() == ticket_number.upper()
    
    if mask.any():
        idx = df[mask].index[-1]
        for k, v in updates.items():
            if k in df.columns:
                df.at[idx, k] = v
        _save_tickets_df(df)
        
        logger.info(f"[EXCEL MOCK] Ticket {ticket_number} updated")
        record = df.loc[idx].to_dict()
        return {k: ("" if pd.isna(v) else v) for k, v in record.items()}
    return None


def escalate_ticket(ticket_number: str) -> dict | None:
    """Escalate a ticket — sets urgency to High and reassigns."""
    return update_ticket(ticket_number, {
        "urgency": "1 - High",
        "priority": "1 - Critical",
        "state": "In Progress",
        "assigned_to": "Senior IT Support",
    })
