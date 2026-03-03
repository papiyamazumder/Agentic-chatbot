import pytest
from unittest.mock import patch, MagicMock
from agents.api_agent import run_api_agent
from agents.workflow_agent import run_workflow_agent

@patch("agents.api_agent._extract_metric_intent")
@patch("agents.api_agent._format_response")
def test_api_agent_mock_flow(mock_format, mock_intent):
    """Test API agent logic with mocked LLM."""
    mock_intent.return_value = "budget_burn_rate"
    mock_format.return_value = "Mocked budget response"
    
    result = run_api_agent("how much is the budget?")
    
    assert "Mocked budget response" in result["answer"]
    assert result["agent"] == "api"

@patch("agents.workflow_agent._classify_action")
def test_workflow_agent_classification(mock_classify):
    """Test workflow agent action routing."""
    mock_classify.return_value = {
        "action": "send_email",
        "title": "Test Email",
        "description": "Test body",
        "to_email": "test@kpmg.com"
    }
    
    # We use a wrapper or mock the underlying connector since it might try to do IO
    with patch("agents.workflow_agent.send_email") as mock_email:
        mock_email.return_value = {"status": "sent"}
        result = run_workflow_agent("Email the team about test results")
        
        assert "Email sent" in result["answer"] or "logged" in result["answer"]
        assert "workflow" in result["agent"]

def test_api_agent_unknown_metric():
    """Test API agent handling of unknown metrics."""
    with patch("agents.api_agent._extract_metric_intent", return_value="unknown"):
        result = run_api_agent("what is the weather?")
        assert "couldn't identify a specific KPI" in result["answer"]
