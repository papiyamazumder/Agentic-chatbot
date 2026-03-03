"""
KPI File Connector — fetches KPI data from localized files in data/KPI Data/
Prioritizes files (Excel, CSV, PDF, Docx) over mock data.
"""
import os
import logging
from pathlib import Path
from ingestion.pdf_loader import _load_pdf, _load_docx, _load_excel, _load_csv

logger = logging.getLogger(__name__)

KPI_DATA_DIR = Path("data/KPI Data")

# Mapping of metric keys to filenames
METRIC_FILE_MAP = {
    "delivery_risk_score": "Delivery_Risk_Score.xlsx",
    "resource_utilisation": "Resource_Utilisation.xlsx",
    "budget_burn_rate": "Budget_Burn_Rate.xlsx",
    "sprint_velocity": "Sprint_Velocity.csv",
    "milestone_completion": "Milestone_Completion.csv",
    "open_risk_items": "Open_Risk_Items.docx",
    "helpdesk_tickets": "Helpdesk_Tickets.csv",
    "stakeholder_satisfaction": "Stakeholder_Satisfaction.pdf",
    "project_summary": "Project_Summary.xlsx",
    "team_performance": "Team_Performance.docx",
    "budget_details": "Budget_Details.pdf",
    "jira_sprints": "Jira_Sprints.csv",
}

def get_kpi_from_file(metric_key: str) -> dict | None:
    """
    Fetch KPI data from a file if it exists.
    Returns a dict with 'data' (parsed text) and 'source' (filename).
    """
    filename = METRIC_FILE_MAP.get(metric_key)
    if not filename:
        return None

    filepath = KPI_DATA_DIR / filename
    if not filepath.exists():
        logger.warning(f"KPI file not found: {filepath}")
        return None

    ext = filename.lower().split(".")[-1]
    try:
        if ext == "pdf":
            text = _load_pdf(str(filepath))
        elif ext == "docx":
            text = _load_docx(str(filepath))
        elif ext in ("xlsx", "xls"):
            text = _load_excel(str(filepath))
        elif ext == "csv":
            text = _load_csv(str(filepath))
        else:
            logger.warning(f"Unsupported file extension for KPI: {ext}")
            return None

        if text.strip():
            logger.info(f"[KPI FILE] Successfully loaded {filename} for {metric_key}")
            return {
                "data": text,
                "source": filename
            }
    except Exception as e:
        logger.error(f"[KPI FILE] Error loading {filename}: {e}")
    
    return None
