"""
Unit and integration tests for JanSetu's decorated Python tool calling framework.
Verifies that all tools adhere to typing, generate valid schemas, and execute real domain logic.
"""

import pytest
from app.agent.tools import (
    TOOL_REGISTRY,
    calculate_scheme_benefits,
    evaluate_citizen_eligibility,
    execute_tool,
    find_nearby_emitra_kiosk,
    get_required_documents_checklist,
    get_tool_registry,
    get_tools_schema,
    query_circular_documents_rag,
    search_welfare_schemes,
)


def test_tool_registration_and_schemas():
    """Verify that all 6 core welfare tools are registered and generate valid OpenAPI/JSON schemas."""
    tools = get_tool_registry()
    expected_tools = [
        "evaluate_citizen_eligibility",
        "calculate_scheme_benefits",
        "query_circular_documents_rag",
        "search_welfare_schemes",
        "get_required_documents_checklist",
        "find_nearby_emitra_kiosk",
    ]

    for tool_name in expected_tools:
        assert tool_name in tools, f"Missing expected tool {tool_name}"
        t = tools[tool_name]
        schema = t.to_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == tool_name
        assert len(schema["function"]["description"]) > 10
        assert "properties" in schema["function"]["parameters"]

    all_schemas = get_tools_schema()
    assert len(all_schemas) >= 6


def test_evaluate_citizen_eligibility_senior_female():
    """Verify deterministic eligibility for a 68-year-old woman in Rajasthan earning ₹40,000."""
    result = evaluate_citizen_eligibility(
        age=68,
        annual_income=40000,
        gender="FEMALE",
    )

    assert result["evaluated_count"] > 0
    assert result["eligible_count"] >= 1

    matched_codes = [s["scheme_code"] for s in result["matched_schemes"]]
    # Should qualify for Mukhyamantri Vridhjan Samman Pension
    assert any("VRIDHJAN" in code for code in matched_codes)


def test_evaluate_citizen_eligibility_farmer():
    """Verify deterministic eligibility for a farmer with 2.5 Bigha land."""
    result = evaluate_citizen_eligibility(
        land_area_bigha=2.5,
        annual_income=50000,
    )

    assert result["evaluated_count"] > 0
    matched_codes = [s["scheme_code"] for s in result["matched_schemes"]]
    assert any("KISAN" in code for code in matched_codes)


def test_calculate_scheme_benefits_slabs():
    """Verify calculation logic across age slabs for Vridhjan pension."""
    # Under 75 years
    b_65 = calculate_scheme_benefits(scheme_code="RJ-PENSION-VRIDHJAN", age=65)
    assert b_65["monthly_payout_inr"] == 1000
    assert b_65["annual_total_inr"] == 12000
    assert "Up to 75 Years" in b_65["slab_applied"]

    # 75 years and above
    b_78 = calculate_scheme_benefits(scheme_code="RJ-PENSION-VRIDHJAN", age=78)
    assert b_78["monthly_payout_inr"] == 1500
    assert b_78["annual_total_inr"] == 18000
    assert "Above 75 Years" in b_78["slab_applied"]


def test_calculate_scheme_benefits_health_and_kisan():
    """Verify health insurance and kisan subsidy computations."""
    b_health = calculate_scheme_benefits(scheme_code="RJ-HEALTH-MAA")
    assert b_health["annual_total_inr"] == 2500000

    b_kisan = calculate_scheme_benefits(scheme_code="RJ-AGRI-KISAN-SAMMAN", land_area_bigha=4.0)
    assert b_kisan["annual_total_inr"] == 8000
    assert len(b_kisan["breakdown"]) == 3


def test_query_circular_documents_rag():
    """Verify grounded retrieval returns verbatim citations with page numbers."""
    res = query_circular_documents_rag(query="वृद्धावस्था पेंशन आयु सीमा", top_k=2)
    assert res["total_found"] > 0
    first = res["citations"][0]
    assert "page_start" in first
    assert first["page_start"] >= 1
    assert "citation_tag" in first
    assert "[Circular:" in first["citation_tag"]
    assert "Page:" in first["citation_tag"]
    assert len(first["text"]) > 20


def test_get_required_documents_checklist():
    """Verify document checklist returns Jan Aadhaar with issuance guidelines."""
    res = get_required_documents_checklist(scheme_code="RJ-PENSION-VRIDHJAN")
    assert res["total_documents"] >= 3
    doc_names = [d["document_name"] for d in res["documents"]]
    assert any("Jan Aadhaar" in n for n in doc_names)
    assert any("Income" in n for n in doc_names)


def test_find_nearby_emitra_kiosk():
    """Verify e-Mitra directory lookup for Jodhpur district."""
    res = find_nearby_emitra_kiosk(district="Jodhpur")
    assert res["district"] == "Jodhpur"
    assert "181" in res["toll_free_helpline"]
    assert len(res["service_kiosks"]) >= 1


def test_execute_tool_dispatch():
    """Verify safe dynamic dispatcher for registered tools."""
    res = execute_tool(
        tool_name="calculate_scheme_benefits",
        arguments={"scheme_code": "RJ-HEALTH-MAA"},
    )
    assert res["status"] == "success"
    assert res["result"]["annual_total_inr"] == 2500000

    # Non-existent tool handling
    err = execute_tool(tool_name="non_existent_tool", arguments={})
    assert err["status"] == "error"
