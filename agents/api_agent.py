"""
API Agent — fetches structured KPI and project metrics
Pipeline: query → LLM extracts metric intent → SQL/Jira connector → LLM formats response

Handles: KPI queries, dashboard data, performance metrics, project scores
LLM:     Groq (llama-3.1-8b-instant) — extracts intent + formats output
Data:    SQL Server + Jira (mock fallback for local dev)
"""
import os
import json
import logging
from dotenv import load_dotenv
from utils.llm_client import get_llm_client, get_model_name

from connectors.sql_connector import get_metric, execute_query, get_all_tables, MOCK_SQL_DATA
from connectors.jira_connector import get_sprints, get_issues, get_velocity, get_projects
from connectors.kpi_file_connector import get_kpi_from_file

load_dotenv()
logger = logging.getLogger(__name__)

# ── Combined metric keys (for LLM intent extraction) ─
AVAILABLE_METRICS = [
    "delivery_risk_score", "resource_utilisation", "budget_burn_rate",
    "sprint_velocity", "milestone_completion", "open_risk_items",
    "helpdesk_tickets", "stakeholder_satisfaction",
    "project_summary", "team_performance", "budget_details",
    "jira_sprints", "jira_issues", "jira_velocity", "jira_projects",
]


def _get_api_client():
    return get_llm_client()


def _extract_metric_intent(query: str) -> str:
    """Use LLM to extract which KPI/data the user is asking about."""
    client = _get_api_client()
    model  = get_model_name()

    prompt = f"""You are a KPI extraction assistant.
Given a user query, identify which metric or data they want from this list:
{AVAILABLE_METRICS}

Return ONLY the metric key from the list above (snake_case, no explanation).
If no match, return 'unknown'.

Query: {query}
Metric key:"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=30,
    )
    return response.choices[0].message.content.strip().lower()


def _fetch_data(metric_key: str) -> dict | list | None:
    """
    Fetch data from the appropriate connector based on metric key.
    SQL for KPI/project data, Jira for sprint/issue data.
    """
    # Jira data sources
    if metric_key == "jira_sprints":
        return get_sprints()
    if metric_key == "jira_issues":
        return get_issues()
    if metric_key == "jira_velocity":
        return get_velocity()
    if metric_key == "jira_projects":
        return get_projects()

    # SQL table-level queries
    if metric_key in ("project_summary", "team_performance", "budget_details"):
        return execute_query(metric_key)

    # Individual KPI metric (SQL)
    metric = get_metric(metric_key)
    if metric:
        return metric

    return None


def _format_response(query: str, metric_key: str, data) -> str:
    """Use LLM to format raw data into an executive-ready summary."""
    client = _get_api_client()
    model  = get_model_name()

    # Pre-process data to limit to top 3 if it's a list of records
    display_data = data
    if isinstance(data, list) and len(data) > 3:
        display_data = data[:3]
    elif isinstance(data, str) and "\n" in data:
        # If it's a string (from Excel/CSV loader), we'll let the LLM handle the "top 3" instruction
        pass

    prompt = f"""You are a PMO reporting assistant for KPMG.
Format this data into a BRIEF, on-point executive response.

Strict Rules:
1. If there are multiple records, show ONLY the TOP 3 most relevant results in a markdown table.
2. Provide a 1-2 sentence high-level summary/analysis.
3. Be professional and concise. No fluff.

Metric: {metric_key}
Raw context/data: {json.dumps(display_data, indent=2, default=str)}
User asked: {query}

Write the brief report:"""

    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


# ── Main agent function ──────────────────────────────
def run_api_agent(query: str) -> dict:
    """
    Full KPI retrieval pipeline:
    1. LLM extracts which metric/data user wants
    2. Try fetching from local KPI files first (Prioritized)
    3. Fallback to SQL/Jira connectors
    4. LLM formats raw data into readable summary
    """

    # Step 1 — Extract metric intent
    metric_key = _extract_metric_intent(query)
    logger.info(f"[API Agent] Extracted metric: {metric_key}")

    if metric_key == "unknown":
        return {
            "answer": (
                "I couldn't identify a specific KPI from your query. "
                f"Available metrics: {', '.join(AVAILABLE_METRICS)}"
            ),
            "sources": ["KPI Database"],
            "agent": "api"
        }

    # Step 2 — Try Fetch from Local File (Prioritized)
    file_info = get_kpi_from_file(metric_key)
    
    if file_info:
        data = file_info["data"]
        source = f"KPI File: {file_info['source']}"
    else:
        # Step 3 — Fetch from SQL/Jira (Fallback)
        data = _fetch_data(metric_key)
        source = "Jira" if metric_key.startswith("jira_") else "SQL Database"

    if not data:
        return {
            "answer": f"No data found for metric: {metric_key}",
            "sources": ["KPI Database"],
            "agent": "api"
        }

    # Step 4 — Format with LLM
    answer = _format_response(query, metric_key, data)

    return {
        "answer":  answer,
        "sources": [source, metric_key],
        "agent":   "api"
    }
