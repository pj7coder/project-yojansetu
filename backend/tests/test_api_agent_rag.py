import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_api_get_agent_tools():
    """Verify GET /api/v1/agent/tools returns OpenAPI function calling schemas."""
    response = client.get("/api/v1/agent/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    tool_names = [t["function"]["name"] for t in data["tools"]]
    assert "evaluate_citizen_eligibility" in tool_names
    assert "calculate_scheme_benefits" in tool_names
    assert "query_circular_documents_rag" in tool_names
    assert "get_required_documents_checklist" in tool_names
    assert "find_nearby_emitra_kiosk" in tool_names


def test_api_post_agent_tool_call_direct():
    """Verify POST /api/v1/agent/tool-call executes tool directly and returns results."""
    response = client.post(
        "/api/v1/agent/tool-call",
        json={
            "tool_name": "calculate_scheme_benefits",
            "arguments": {
                "scheme_code": "RJ-PENSION-VRIDHJAN",
                "age": 76,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tool_name"] == "calculate_scheme_benefits"
    result = data["result"]
    assert result["status"] == "success"
    assert result["result"]["monthly_payout_inr"] == 1500
    assert result["result"]["benefit_type"] == "MONTHLY_PENSION"


def test_api_post_agent_query_multi_step():
    """Verify POST /api/v1/agent/query executes full ReAct loop end-to-end."""
    response = client.post(
        "/api/v1/agent/query",
        json={
            "query": "I am a 68-year-old widow living in Alwar. What monthly pension will I get and what documents to take to e-Mitra?",
            "context": {"age": 68, "gender": "female", "is_widow": True, "district": "Alwar"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "final_answer" in data
    assert len(data["steps"]) >= 2
    assert "structured_data" in data
    assert "execution_time_ms" in data
    assert data["execution_time_ms"] > 0
    # Verify thoughts and tool calls in trace
    step_tools = [s["tool_name"] for s in data["steps"]]
    assert "evaluate_citizen_eligibility" in step_tools


def test_api_post_rag_query():
    """Verify POST /api/v1/rag/query performs hybrid dense + keyword search on gazetted circulars."""
    response = client.post(
        "/api/v1/rag/query",
        json={
            "query": "Kisan Samman Nidhi quarterly installment DBT",
            "top_k": 3,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total_retrieved"] >= 1
    chunk = data["chunks"][0]
    assert "circular_id" in chunk
    assert "citation_tag" in chunk
    assert len(chunk["text"]) > 0


def test_api_get_rag_chunks():
    """Verify GET /api/v1/rag/chunks lists circular chunks with page numbers."""
    response = client.get("/api/v1/rag/chunks?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    assert len(data["chunks"]) <= 5
    assert "chunk_title" in data["chunks"][0]
