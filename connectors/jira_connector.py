"""
Jira Connector — fetches project/sprint data from Jira REST API v3
Pattern: try real Jira API → fall back to mock data

Production: set JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN in .env
Local dev:  uses MOCK_JIRA_DATA — no Jira instance needed
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ── Mock Jira data (local dev) ───────────────────────
MOCK_JIRA_SPRINTS = [
    {
        "sprint": "Sprint 14", "state": "active", "team": "Team B",
        "start": "2024-12-01", "end": "2024-12-14",
        "committed": 42, "completed": 38, "remaining": 4,
        "velocity": 38, "stories": 8, "bugs": 3
    },
    {
        "sprint": "Sprint 13", "state": "closed", "team": "Team B",
        "start": "2024-11-17", "end": "2024-11-30",
        "committed": 40, "completed": 37, "remaining": 3,
        "velocity": 37, "stories": 7, "bugs": 2
    },
    {
        "sprint": "Sprint 12", "state": "closed", "team": "Team B",
        "start": "2024-11-03", "end": "2024-11-16",
        "committed": 45, "completed": 40, "remaining": 5,
        "velocity": 40, "stories": 9, "bugs": 4
    },
]

MOCK_JIRA_ISSUES = [
    {"key": "ALPHA-101", "type": "Bug",   "summary": "Login page timeout on mobile",     "status": "In Progress", "priority": "High",   "assignee": "Rahul S."},
    {"key": "ALPHA-102", "type": "Story", "summary": "Implement dashboard export to PDF", "status": "To Do",      "priority": "Medium", "assignee": "Priya M."},
    {"key": "ALPHA-103", "type": "Bug",   "summary": "Report date filter not working",    "status": "Open",       "priority": "High",   "assignee": "Amit K."},
    {"key": "ALPHA-104", "type": "Task",  "summary": "Update Q4 stakeholder deck",        "status": "Done",       "priority": "Low",    "assignee": "Sneha R."},
    {"key": "ALPHA-105", "type": "Story", "summary": "Add KPI trend charts",              "status": "In Review",  "priority": "Medium", "assignee": "Vikram P."},
    {"key": "BETA-201",  "type": "Bug",   "summary": "API rate limiting not enforced",    "status": "Open",       "priority": "Critical","assignee": "Deepak L."},
    {"key": "BETA-202",  "type": "Story", "summary": "User role management module",       "status": "In Progress","priority": "High",   "assignee": "Neha G."},
]

MOCK_JIRA_PROJECTS = [
    {"key": "ALPHA", "name": "Project Alpha", "lead": "Rajesh K.", "type": "Scrum",  "issues_total": 87, "issues_open": 23},
    {"key": "BETA",  "name": "Project Beta",  "lead": "Meera S.",  "type": "Scrum",  "issues_total": 54, "issues_open": 12},
    {"key": "GAMMA", "name": "Project Gamma", "lead": "Suresh P.", "type": "Kanban", "issues_total": 41, "issues_open": 18},
]


def _is_configured() -> bool:
    return bool(os.getenv("JIRA_URL") and os.getenv("JIRA_API_TOKEN"))


def _get_auth():
    """Build Jira basic auth tuple."""
    return (os.getenv("JIRA_EMAIL"), os.getenv("JIRA_API_TOKEN"))


def _jira_get(endpoint: str) -> dict:
    """Make authenticated GET request to Jira REST API."""
    import requests
    base_url = os.getenv("JIRA_URL").rstrip("/")
    resp = requests.get(
        f"{base_url}/rest/api/3/{endpoint}",
        auth=_get_auth(),
        headers={"Accept": "application/json"},
        timeout=10
    )
    resp.raise_for_status()
    return resp.json()


def get_sprints(board_id: str = None) -> list[dict]:
    """Get sprint data — velocity, committed vs completed points."""
    if _is_configured():
        try:
            data = _jira_get(f"board/{board_id or '1'}/sprint?state=active,closed&maxResults=5")
            sprints = []
            for s in data.get("values", []):
                sprints.append({
                    "sprint": s["name"],
                    "state": s["state"],
                    "start": s.get("startDate", ""),
                    "end": s.get("endDate", ""),
                })
            return sprints
        except Exception as e:
            logger.warning(f"Jira sprint fetch failed: {e} — using mock")

    logger.info("[MOCK] Returning mock sprint data")
    return MOCK_JIRA_SPRINTS


def get_issues(project_key: str = "ALPHA", status: str = None) -> list[dict]:
    """Get issues from a Jira project, optionally filtered by status."""
    if _is_configured():
        try:
            jql = f"project={project_key}"
            if status:
                jql += f" AND status='{status}'"
            jql += " ORDER BY priority DESC"

            data = _jira_get(f"search?jql={jql}&maxResults=20")
            issues = []
            for i in data.get("issues", []):
                fields = i["fields"]
                issues.append({
                    "key": i["key"],
                    "type": fields["issuetype"]["name"],
                    "summary": fields["summary"],
                    "status": fields["status"]["name"],
                    "priority": fields["priority"]["name"],
                    "assignee": fields.get("assignee", {}).get("displayName", "Unassigned"),
                })
            return issues
        except Exception as e:
            logger.warning(f"Jira issues fetch failed: {e} — using mock")

    # Mock fallback — filter by project key
    logger.info(f"[MOCK] Returning mock issues for {project_key}")
    results = [i for i in MOCK_JIRA_ISSUES if i["key"].startswith(project_key)]
    if status:
        results = [i for i in results if i["status"].lower() == status.lower()]
    return results or MOCK_JIRA_ISSUES


def get_projects() -> list[dict]:
    """List all Jira projects."""
    if _is_configured():
        try:
            data = _jira_get("project")
            return [{"key": p["key"], "name": p["name"], "lead": p.get("lead", {}).get("displayName", "")} for p in data]
        except Exception as e:
            logger.warning(f"Jira projects fetch failed: {e} — using mock")

    logger.info("[MOCK] Returning mock projects")
    return MOCK_JIRA_PROJECTS


def get_velocity() -> list[dict]:
    """Get velocity trend (points completed per sprint)."""
    sprints = get_sprints()
    return [{"sprint": s["sprint"], "velocity": s.get("velocity", 0)} for s in sprints]
