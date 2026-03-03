"""
Outlook Connector — send emails via Microsoft Graph API
Pattern: try real Graph API → fall back to mock (log only)

Production: set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID in .env
Local dev:  logs mock email — no real email sent
"""
import os
import logging
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from pathlib import Path
import ast

load_dotenv()
logger = logging.getLogger(__name__)

# ── In-memory email log (local dev) ──────────────────
_sent_emails = []


def _is_configured() -> bool:
    return bool(os.getenv("AZURE_CLIENT_ID") and os.getenv("AZURE_CLIENT_SECRET"))


def _get_access_token() -> str:
    """Get OAuth2 token from Azure AD using client credentials flow."""
    import requests
    tenant_id = os.getenv("AZURE_TENANT_ID")
    resp = requests.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
        data={
            "grant_type": "client_credentials",
            "client_id": os.getenv("AZURE_CLIENT_ID"),
            "client_secret": os.getenv("AZURE_CLIENT_SECRET"),
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def send_email(to: str, subject: str, body: str,
               cc: str = None, attachments: list = None) -> dict:
    """
    Send an email via Outlook (Microsoft Graph API).
    Falls back to mock logging if not configured.
    """
    if _is_configured():
        try:
            return _send_real_email(to, subject, body, cc, attachments)
        except Exception as e:
            logger.warning(f"Outlook send failed: {e} — using mock")

    # Mock fallback
    email_record = {
        "id": f"MAIL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "to": to,
        "cc": cc,
        "subject": subject,
        "body": body[:200],
        "sent_at": datetime.now().isoformat(),
        "status": "mock_logged",
    }
    _sent_emails.append(email_record)
    logger.info(f"[MOCK] Email logged: to={to}, subject={subject}")
    return email_record


def _send_real_email(to: str, subject: str, body: str,
                      cc: str = None, attachments: list = None) -> dict:
    """Send email via Microsoft Graph API."""
    import requests
    token = _get_access_token()

    message = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body},
            "toRecipients": [{"emailAddress": {"address": to}}],
        },
        "saveToSentItems": "true"
    }

    if cc:
        message["message"]["ccRecipients"] = [{"emailAddress": {"address": cc}}]

    sender = os.getenv("OUTLOOK_SENDER", "pmo-chatbot@kpmg.com")
    resp = requests.post(
        f"https://graph.microsoft.com/v1.0/users/{sender}/sendMail",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=message,
        timeout=10
    )
    resp.raise_for_status()
    logger.info(f"Email sent to {to}: {subject}")
    return {"to": to, "subject": subject, "status": "sent"}


def get_sent_emails() -> list[dict]:
    """Get all sent/logged emails (for admin view)."""
    return _sent_emails


# ── Onboarding / Offboarding records (Excel Persistent Storage) ──
RAW_DOCS_DIR = Path(__file__).parent.parent / "data" / "raw_docs"
RAW_DOCS_DIR.mkdir(parents=True, exist_ok=True)

def _append_to_excel(record: dict, filename: str):
    file_path = RAW_DOCS_DIR / filename
    df_new = pd.DataFrame([record])
    
    # Cast complex types to string for Excel compatibility
    for col in df_new.columns:
        if isinstance(df_new[col].iloc[0], (dict, list)):
            df_new[col] = df_new[col].astype(str)
            
    if file_path.exists():
        try:
            df_existing = pd.read_excel(file_path)
            df_combined = pd.concat([df_existing, df_new], ignore_index=True)
            df_combined.to_excel(file_path, index=False)
        except Exception as e:
            logger.error(f"Failed to append to {filename}: {e}")
            df_new.to_excel(file_path, index=False)
    else:
        df_new.to_excel(file_path, index=False)

def _read_excel(filename: str) -> list[dict]:
    file_path = RAW_DOCS_DIR / filename
    if not file_path.exists():
        return []
    try:
        # Fill NaN with empty string to avoid JSON serialization issues later
        df = pd.read_excel(file_path).fillna("")
        records = df.to_dict(orient="records")
        for r in records:
            if 'checklist' in r and isinstance(r['checklist'], str):
                try:
                    r['checklist'] = ast.literal_eval(r['checklist'])
                except (ValueError, SyntaxError):
                    pass
        return records
    except Exception as e:
        logger.error(f"Failed to read {filename}: {e}")
        return []

def _update_onboarding_status(employee_name: str) -> str:
    """Find the employee in Onboarding_Records and set status to Inactive. Returns their EMP ID."""
    file_path = RAW_DOCS_DIR / "Onboarding_Records.xlsx"
    if not file_path.exists():
        return "UNKNOWN-EMP"
    
    try:
        df = pd.read_excel(file_path)
        # Find exactly the rows matching the employee name
        mask = df['employee'].str.lower() == employee_name.lower()
        if not mask.any():
            return "UNKNOWN-EMP"
        
        # Get the ID of the latest entry
        emp_id = df.loc[mask, 'emp_id'].iloc[-1]
        
        # Update the status to Inactive for all matching active rows
        df.loc[mask, 'status'] = "Inactive (Offboarded)"
        df.to_excel(file_path, index=False)
        return emp_id
    except Exception as e:
        logger.error(f"Failed to update onboarding status: {e}")
        return "ERROR-EMP"

def _get_record_by_emp_id(emp_id: str) -> dict:
    """Fetch an onboarding record by its EMP ID."""
    file_path = RAW_DOCS_DIR / "Onboarding_Records.xlsx"
    if not file_path.exists():
        return None
    try:
        df = pd.read_excel(file_path)
        mask = df['emp_id'].str.lower() == emp_id.lower()
        if not mask.any():
            return None
        # Return the latest record matching this ID
        record = df[mask].iloc[-1].to_dict()
        if 'checklist' in record and isinstance(record['checklist'], str):
            try:
                record['checklist'] = ast.literal_eval(record['checklist'])
            except (ValueError, SyntaxError):
                pass
        # Clean NaNs
        return {k: ("" if pd.isna(v) else v) for k, v in record.items()}
    except Exception as e:
        logger.error(f"Failed to retrieve record by EMP ID: {e}")
        return None

def cancel_workflow_request(request_type: str, emp_id: str) -> dict:
    """
    Cancel a workflow request if it was created within the last 3 business days.
    request_type must be one of: 'onboarding', 'offboarding', 'tagging'
    """
    tracker_map = {
        "onboarding": "Onboarding_Records.xlsx",
        "offboarding": "Offboarding_Records.xlsx",
        "tagging": "Resource_Tagging_Records.xlsx"
    }
    
    filename = tracker_map.get(request_type.lower())
    if not filename:
        return {"success": False, "error": f"Invalid request type '{request_type}'"}
        
    file_path = RAW_DOCS_DIR / filename
    if not file_path.exists():
        return {"success": False, "error": f"No active records found for {request_type}"}
        
    try:
        df = pd.read_excel(file_path)
        mask = df['emp_id'].str.lower() == emp_id.lower()
        
        if not mask.any():
            return {"success": False, "error": f"No {request_type} request found for EMP ID {emp_id}"}
            
        # Get the index of the latest entry
        latest_idx = df[mask].index[-1]
        record = df.loc[latest_idx]
        
        if record['status'] == 'Cancelled':
            return {"success": False, "error": f"This request is already cancelled."}
            
        # Check 3 business day rule
        created_at_str = record.get('created_at', '')
        if created_at_str:
            created_date = pd.to_datetime(created_at_str).tz_localize(None)
            today = pd.Timestamp.now().tz_localize(None)
            
            # Calculate business days
            b_days = len(pd.bdate_range(start=created_date.date(), end=today.date())) - 1
            if b_days > 3:
                return {"success": False, "error": f"Cancellation rejected. Request was raised {b_days} business days ago (limit is 3)."}
        
        # Update status
        df.loc[latest_idx, 'status'] = "Cancelled"
        df.to_excel(file_path, index=False)
        return {"success": True, "message": f"Successfully cancelled {request_type} request for {emp_id}."}
        
    except Exception as e:
        logger.error(f"Cancel failed: {e}")
        return {"success": False, "error": f"Database error during cancellation: {str(e)}"}

def send_approval_notification(action_type: str, employee_name: str, role: str,
                                project: str, requested_by: str,
                                manager_email: str = None) -> dict:
    """
    Send approval notification email to managers via Outlook / Graph API.
    Used for onboarding, offboarding, tagging workflows.
    """
    manager_email = manager_email or os.getenv("MANAGER_EMAIL", "manager@kpmg.com")
    subject = f"[Approval Required] {action_type}: {employee_name} — {project}"
    body = (
        f"Dear Manager,\n\n"
        f"A {action_type.lower()} request requires your approval:\n\n"
        f"  Employee: {employee_name}\n"
        f"  Role: {role}\n"
        f"  Project: {project}\n"
        f"  Requested by: {requested_by}\n"
        f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Please review and approve this request in the PMO chatbot "
        f"or reply to this email with your decision.\n\n"
        f"— KPMG PMO AI Assistant"
    )
    return send_email(to=manager_email, subject=subject, body=body)


def initiate_onboarding(employee_name: str, role: str, project: str,
                         department: str = "Engineering", start_date: str = None,
                         requested_by: str = "PMO Admin") -> dict:
    """
    Initiate employee onboarding workflow.
    1. Create onboarding record
    2. Send approval email to manager via Graph API
    3. Return confirmation
    """
    emp_id = f"EMP-{datetime.now().strftime('%y%m%d%H%M')}"
    record = {
        "emp_id": emp_id,
        "type": "Onboarding",
        "employee": employee_name,
        "role": role,
        "project": project,
        "department": department,
        "start_date": start_date or datetime.now().strftime("%Y-%m-%d"),
        "requested_by": requested_by,
        "status": "Pending Approval",
        "created_at": datetime.now().isoformat(),
        "checklist": {
            "system_access": False, "email_setup": False, "teams_added": False,
            "tools_provisioned": False, "orientation_scheduled": False,
        }
    }
    _append_to_excel(record, "Onboarding_Records.xlsx")

    # Send approval notification to manager
    approval = send_approval_notification(
        "Onboarding", employee_name, role, project, requested_by
    )
    record["approval_email_id"] = approval.get("id", "N/A")

    logger.info(f"[ONBOARDING] {employee_name} → {project} ({role}) — pending approval")
    return record


def initiate_offboarding(emp_id: str, employee_name: str, role: str, project: str,
                          last_date: str = None, reason: str = "Project completion",
                          requested_by: str = "PMO Admin") -> dict:
    """
    Initiate employee offboarding workflow using EMP ID.
    1. Update Onboarding status to Inactive
    2. Create offboarding record
    3. Send approval email to manager via Graph API
    4. Return confirmation with checklist
    """
    # Force the status to update by finding their name (we could also update the internal status updater to use emp_id)
    _update_onboarding_status(employee_name)
    
    record = {
        "emp_id": emp_id,
        "type": "Offboarding",
        "employee": employee_name,
        "role": role,
        "project": project,
        "last_date": last_date or "TBD",
        "reason": reason,
        "requested_by": requested_by,
        "status": "Pending Approval",
        "created_at": datetime.now().isoformat(),
        "checklist": {
            "access_revoked": False, "assets_returned": False,
            "knowledge_transfer": False, "exit_interview": False,
        }
    }
    _append_to_excel(record, "Offboarding_Records.xlsx")

    approval = send_approval_notification(
        "Offboarding", employee_name, role, project, requested_by
    )
    record["approval_email_id"] = approval.get("id", "N/A")

    logger.info(f"[OFFBOARDING] {employee_name} from {project} — pending approval")
    return record


def tag_resource(emp_id: str, employee_name: str, role: str, from_project: str,
                  to_project: str, requested_by: str = "PMO Admin") -> dict:
    """
    Tag/re-tag a resource from one project to another using EMP ID.
    1. Create tagging record
    2. Send approval email to manager via Graph API
    3. Return confirmation
    """
    record = {
        "emp_id": emp_id,
        "type": "Resource Tagging",
        "employee": employee_name,
        "role": role,
        "from_project": from_project,
        "to_project": to_project,
        "requested_by": requested_by,
        "status": "Pending Approval",
        "created_at": datetime.now().isoformat(),
    }
    _append_to_excel(record, "Resource_Tagging_Records.xlsx")

    approval = send_approval_notification(
        "Resource Tagging", employee_name, role, to_project, requested_by
    )
    record["approval_email_id"] = approval.get("id", "N/A")

    logger.info(f"[TAGGING] {employee_name}: {from_project} → {to_project} — pending approval")
    return record


def get_onboarding_records() -> list[dict]:
    """Get all onboarding, offboarding, and tagging records from Excel files."""
    records = []
    records.extend(_read_excel("Onboarding_Records.xlsx"))
    records.extend(_read_excel("Offboarding_Records.xlsx"))
    records.extend(_read_excel("Resource_Tagging_Records.xlsx"))
    
    # Sort by created_at descending
    records.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return records
