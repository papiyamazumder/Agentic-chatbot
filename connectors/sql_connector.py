"""
SQL Connector — connects to SQL Server for KPI and project data
Pattern: try real pyodbc connection → fall back to mock data

Production: set SQL_SERVER, SQL_DATABASE, SQL_USER, SQL_PASSWORD in .env
Local dev:  uses MOCK_SQL_DATA — no database needed
"""
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Mock SQL data (local dev) ────────────────────────
# Simulates what a real SQL query would return
MOCK_SQL_DATA = {
    "project_summary": [
        {"project": "Alpha", "status": "In Progress", "health": "Amber", "completion": 67, "budget_used": 91},
        {"project": "Beta",  "status": "On Track",    "health": "Green", "completion": 82, "budget_used": 74},
        {"project": "Gamma", "status": "At Risk",     "health": "Red",   "completion": 34, "budget_used": 55},
    ],
    "kpi_metrics": [
        {"metric": "delivery_risk_score",  "value": 72,  "unit": "%",     "period": "Q4 2024", "status": "Medium Risk"},
        {"metric": "resource_utilisation", "value": 84,  "unit": "%",     "period": "Q4 2024", "status": "On Track"},
        {"metric": "budget_burn_rate",     "value": 91,  "unit": "%",     "period": "Q4 2024", "status": "High — Review"},
        {"metric": "sprint_velocity",      "value": 38,  "unit": "pts",   "period": "Sprint 14", "status": "Good"},
        {"metric": "milestone_completion", "value": 67,  "unit": "%",     "period": "Q4 2024", "status": "Slightly Behind"},
        {"metric": "open_risk_items",      "value": 14,  "unit": "items", "period": "Current", "status": "Needs Attention"},
        {"metric": "helpdesk_tickets",     "value": 23,  "unit": "tickets","period": "This Week", "status": "Normal"},
        {"metric": "stakeholder_satisfaction", "value": 4.2, "unit": "/5","period": "Q4 2024", "status": "Good"},
    ],
    "team_performance": [
        {"team": "Team A", "velocity": 42, "sprint": "Sprint 14", "capacity": "90%"},
        {"team": "Team B", "velocity": 38, "sprint": "Sprint 14", "capacity": "85%"},
        {"team": "Team C", "velocity": 29, "sprint": "Sprint 14", "capacity": "70%"},
    ],
    "budget_details": [
        {"project": "Alpha", "total_budget": 500000, "spent": 455000, "remaining": 45000, "burn_rate": "91%"},
        {"project": "Beta",  "total_budget": 300000, "spent": 222000, "remaining": 78000, "burn_rate": "74%"},
        {"project": "Gamma", "total_budget": 750000, "spent": 412500, "remaining": 337500, "burn_rate": "55%"},
    ],
}


def _is_configured() -> bool:
    """Check if SQL Server connection is configured."""
    return bool(os.getenv("SQL_SERVER") and os.getenv("SQL_DATABASE"))


def execute_query(query_text: str) -> list[dict]:
    """
    Execute a SQL query against the configured database.
    Falls back to mock data if not configured.

    Args:
        query_text: Raw SQL or a natural-language table reference
    Returns:
        List of row dicts
    """
    if _is_configured():
        try:
            return _execute_real_query(query_text)
        except Exception as e:
            logger.warning(f"SQL query failed: {e} — using mock data")

    return _execute_mock_query(query_text)


def _execute_real_query(query_text: str) -> list[dict]:
    """Execute query against real SQL Server using pyodbc."""
    try:
        import pyodbc
    except ImportError:
        logger.error("pyodbc not installed — run: pip install pyodbc")
        raise

    server   = os.getenv("SQL_SERVER")
    database = os.getenv("SQL_DATABASE")
    user     = os.getenv("SQL_USER")
    password = os.getenv("SQL_PASSWORD")

    conn_str = (
        f"DRIVER={{ODBC Driver 18 for SQL Server}};"
        f"SERVER={server};DATABASE={database};"
        f"UID={user};PWD={password};"
        f"TrustServerCertificate=yes;Connection Timeout=5;"
    )

    conn = pyodbc.connect(conn_str, timeout=5)
    cursor = conn.cursor()
    cursor.execute(query_text)

    columns = [col[0] for col in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    logger.info(f"SQL query returned {len(rows)} rows")
    return rows


def _execute_mock_query(query_text: str) -> list[dict]:
    """
    Match query text to mock data tables.
    Simple keyword matching against table names.
    """
    q = query_text.lower()

    if any(kw in q for kw in ["budget", "burn", "spend", "cost", "financ"]):
        logger.info("[MOCK] Returning budget_details")
        return MOCK_SQL_DATA["budget_details"]

    if any(kw in q for kw in ["team", "capacity", "velocity", "sprint"]):
        logger.info("[MOCK] Returning team_performance")
        return MOCK_SQL_DATA["team_performance"]

    if any(kw in q for kw in ["project", "summary", "status", "health"]):
        logger.info("[MOCK] Returning project_summary")
        return MOCK_SQL_DATA["project_summary"]

    # Default: KPI metrics
    logger.info("[MOCK] Returning kpi_metrics")
    return MOCK_SQL_DATA["kpi_metrics"]


def get_metric(metric_key: str) -> dict | None:
    """
    Get a specific KPI metric by key name.
    Used by api_agent to fetch individual metrics.
    """
    if _is_configured():
        try:
            rows = _execute_real_query(
                f"SELECT * FROM kpi_metrics WHERE metric_name = '{metric_key}' ORDER BY period DESC LIMIT 1"
            )
            return rows[0] if rows else None
        except Exception as e:
            logger.warning(f"SQL metric fetch failed: {e} — using mock")

    # Mock fallback
    for m in MOCK_SQL_DATA["kpi_metrics"]:
        if m["metric"] == metric_key:
            return m
    return None


def get_all_tables() -> list[str]:
    """List available data tables."""
    if _is_configured():
        try:
            rows = _execute_real_query(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE='BASE TABLE'"
            )
            return [r["TABLE_NAME"] for r in rows]
        except Exception:
            pass

    return list(MOCK_SQL_DATA.keys())
