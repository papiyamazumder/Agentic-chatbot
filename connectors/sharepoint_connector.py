"""
SharePoint Connector — read/write SharePoint files and lists via Graph API
Pattern: try real Microsoft Graph API → fall back to local files / in-memory

Covers TWO use cases:
  1. Document download (for ingestion — pull PDFs/docs from SharePoint)
  2. List write (for RAID logs — add items to a SharePoint List)

Production: set AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID, SHAREPOINT_SITE_ID in .env
Local dev:  reads from data/raw_docs/ and stores RAID logs in-memory
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
RAID_FILE = RAW_DOCS_DIR / "RAID_Log_KPMG.csv"


def _get_raid_df() -> pd.DataFrame:
    """Load RAID logs from CSV or create empty dataframe."""
    if RAID_FILE.exists():
        try:
            df = pd.read_csv(RAID_FILE)
            # Normalize column names for internal filtering logic
            df.columns = df.columns.str.lower()
            if 'raid_id' in df.columns:
                df = df.rename(columns={'raid_id': 'log_id'})
            if 'raised_date' in df.columns:
                df = df.rename(columns={'raised_date': 'created_at'})
            # Add project column if missing, since frontend needs it
            if 'project' not in df.columns:
                df['project'] = "General"
            return df
        except Exception as e:
            logger.error(f"Failed to read RAID CSV file: {e}")
            
    # Return empty schema if missing
    return pd.DataFrame(columns=[
        "log_id", "type", "title", "description",
        "owner", "status", "impact", "created_at", "project"
    ])

def _save_raid_df(df: pd.DataFrame):
    """Save RAID DataFrame to CSV."""
    try:
        df.to_csv(RAID_FILE, index=False)
    except Exception as e:
        logger.error(f"Failed to save RAID CSV file: {e}")

# ── Mock RAID log entries (pre-populated for demo) ───
# ── Legacy mock entries removed, now using RAID_Log_KPMG.csv ───


def _is_configured() -> bool:
    return bool(os.getenv("AZURE_CLIENT_ID") and os.getenv("SHAREPOINT_SITE_ID"))


def _get_access_token() -> str:
    """Get OAuth2 token from Azure AD."""
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


# ═══════════════════════════════════════════════════
# PART 1: Document Download (for ingestion pipeline)
# ═══════════════════════════════════════════════════

def list_documents(folder_path: str = "root") -> list[dict]:
    """List documents in a SharePoint document library."""
    if _is_configured():
        try:
            import requests
            token = _get_access_token()
            site_id = os.getenv("SHAREPOINT_SITE_ID")

            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/{folder_path}/children"
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            resp.raise_for_status()
            items = resp.json().get("value", [])
            return [
                {"name": i["name"], "size": i.get("size", 0),
                 "modified": i.get("lastModifiedDateTime", ""), "id": i["id"]}
                for i in items if not i.get("folder")  # files only
            ]
        except Exception as e:
            logger.warning(f"SharePoint list failed: {e} — using local files")

    # Mock: list local data/raw_docs/ directory
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "raw_docs")
    if os.path.exists(docs_dir):
        files = []
        for f in os.listdir(docs_dir):
            fpath = os.path.join(docs_dir, f)
            if os.path.isfile(fpath):
                files.append({
                    "name": f, "size": os.path.getsize(fpath),
                    "modified": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                    "id": f"local-{f}"
                })
        logger.info(f"[MOCK] Listed {len(files)} local documents")
        return files
    return []


def download_document(file_id: str, save_path: str) -> str:
    """Download a document from SharePoint to local path."""
    if _is_configured():
        try:
            import requests
            token = _get_access_token()
            site_id = os.getenv("SHAREPOINT_SITE_ID")

            url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{file_id}/content"
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}"},
                timeout=30
            )
            resp.raise_for_status()

            with open(save_path, 'wb') as f:
                f.write(resp.content)

            logger.info(f"Downloaded {file_id} → {save_path}")
            return save_path
        except Exception as e:
            logger.warning(f"SharePoint download failed: {e}")

    logger.info(f"[MOCK] No SharePoint download — use local files in data/raw_docs/")
    return ""


# ═══════════════════════════════════════════════════
# PART 2: RAID Log (SharePoint List operations)
# ═══════════════════════════════════════════════════

def add_raid_entry(entry_type: str, title: str, description: str,
                    owner: str = "PMO Team", impact: str = "Medium",
                    project: str = "General") -> dict:
    """
    Add a RAID (Risk/Action/Issue/Decision) log entry.
    Writes to SharePoint List if configured, else stores in-memory.
    """
    log_id = f"RAID-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    entry = {
        "log_id": log_id,
        "type": entry_type,  # Risk, Action, Issue, Decision
        "title": title,
        "description": description,
        "owner": owner,
        "status": "Open",
        "impact": impact,
        "created_at": datetime.now().isoformat(),
        "project": project,
    }

    if _is_configured() and os.getenv("SHAREPOINT_LIST_ID"):
        try:
            import requests
            token = _get_access_token()
            site_id = os.getenv("SHAREPOINT_SITE_ID")
            list_id = os.getenv("SHAREPOINT_LIST_ID")

            requests.post(
                f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"fields": entry},
                timeout=10
            )
            entry["source"] = "SharePoint"
            logger.info(f"RAID entry added to SharePoint: {log_id}")
        except Exception as e:
            logger.warning(f"SharePoint list write failed: {e} — storing locally")
            entry["source"] = "local_mock"
    else:
        entry["source"] = "local_csv"
        logger.info(f"[EXCEL MOCK] RAID entry stored locally: {log_id}")

    # Persist to CSV dataframe
    df = _get_raid_df()
    new_row_df = pd.DataFrame([entry])
    df = pd.concat([df, new_row_df], ignore_index=True)
    _save_raid_df(df)

    return entry


def get_raid_logs(entry_type: str = None, project: str = None) -> list[dict]:
    """Get RAID log entries, optionally filtered by type or project."""
    if _is_configured() and os.getenv("SHAREPOINT_LIST_ID"):
        try:
            import requests
            token = _get_access_token()
            site_id = os.getenv("SHAREPOINT_SITE_ID")
            list_id = os.getenv("SHAREPOINT_LIST_ID")

            resp = requests.get(
                f"https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{list_id}/items?$expand=fields",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            resp.raise_for_status()
            items = [i.get("fields", {}) for i in resp.json().get("value", [])]
            if items:
                return items
        except Exception as e:
            logger.warning(f"SharePoint list read failed: {e} — using local")

    # Mock fallback using CSV
    df = _get_raid_df()
    if len(df) == 0:
        return []
        
    if entry_type:
        mask = df['type'].str.lower() == entry_type.lower()
        df = df[mask]
        
    if project:
        mask = df['project'].str.lower() == project.lower()
        df = df[mask]

    # Convert to dict and clean NaNs
    results = df.to_dict('records')
    results = [{k: ("" if pd.isna(v) else v) for k, v in t.items()} for t in results]
    
    # Needs reversing so newest is first? Usually tail keeps lowest index at top
    results.reverse()

    logger.info(f"[EXCEL MOCK] Returning {len(results)} RAID entries")
    return results
