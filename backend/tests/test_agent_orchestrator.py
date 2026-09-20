"""
Integration tests for JanSetu's ReAct Welfare Agent Orchestrator.
Tests multi-step reasoning, tool sequencing, grounded citation generation, and vernacular synthesis.
"""

import pytest
from app.agent.orchestrator import WelfareAgentOrchestrator


def test_agent_multi_step_senior_widow_query():
    """
    Test multi-step query:
    'I am a 68-year-old widow from Pali earning 40,000 per year.
     What schemes can I get, how much pension per month, and what circulars back this?'
    """
    query = (
        "I am a 68-year-old widow from Pali earning 40,000 per year. "
        "What schemes can I get, how much pension per month, and what circulars back this?"
    )

    result = WelfareAgentOrchestrator.process_query(query=query, language_preference="en")

    # 1. Verification of execution trace
    assert len(result.reasoning_steps) >= 4
    tool_names = [s.tool_name for s in result.reasoning_steps]
    assert "evaluate_citizen_eligibility" in tool_names
    assert "calculate_scheme_benefits" in tool_names
    assert "query_circular_documents_rag" in tool_names
    assert "get_required_documents_checklist" in tool_names

    # Check step structure
    for step in result.reasoning_steps:
        assert len(step.thought) > 10
        assert step.duration_ms >= 0

    # 2. Verification of extracted profile
    assert result.profile_extracted.get("age") == 68
    assert result.profile_extracted.get("gender") == "FEMALE"
    assert result.profile_extracted.get("marital_status") == "WIDOWED"
    assert result.profile_extracted.get("annual_income") == 40000

    # 3. Verification of recommended schemes
    assert len(result.recommended_schemes) >= 1
    matched_codes = [s.get("scheme_code", "") for s in result.recommended_schemes]
    assert any("VRIDHJAN" in c or "EKAL" in c for c in matched_codes)

    # 4. Verification of grounded RAG citations
    assert len(result.citations) >= 1
    first_cit = result.citations[0]
    assert "[Circular:" in first_cit["citation_tag"]
    assert "Page:" in first_cit["citation_tag"]

    # 5. Verification of required documents
    assert len(result.required_documents) >= 2
    doc_names = [d["document_name"] for d in result.required_documents]
    assert any("Jan Aadhaar" in n for n in doc_names)

    # 6. Verification of natural answer
    assert "Eligible Scheme" in result.answer or "Mukhyamantri" in result.answer
    assert "₹1,000" in result.answer or "₹1,500" in result.answer
    assert "[Circular:" in result.answer


def test_agent_hindi_farmer_query():
    """
    Test vernacular Hindi query for small farmer:
    'मैं कोटा से 52 साल का किसान हूँ, मेरे पास 3 बीघा ज़मीन है और 45000 आय है। मुझे क्या सहायता मिलेगी?'
    """
    query = "मैं कोटा से 52 साल का किसान हूँ, मेरे पास 3 बीघा ज़मीन है और 45000 आय है। मुझे क्या सहायता मिलेगी?"

    result = WelfareAgentOrchestrator.process_query(query=query)

    assert result.language == "hi"
    assert result.profile_extracted.get("age") == 52
    assert result.profile_extracted.get("occupation") == "FARMER"
    assert result.profile_extracted.get("land_area_bigha") == 3.0
    assert result.profile_extracted.get("district") == "Kota"

    # Verifies tool execution sequence
    tool_names = [s.tool_name for s in result.reasoning_steps]
    assert "evaluate_citizen_eligibility" in tool_names
    assert "calculate_scheme_benefits" in tool_names

    # Recommended scheme should include Kisan Samman
    matched_codes = [s.get("scheme_code", "") for s in result.recommended_schemes]
    assert any("KISAN" in c or "MAA" in c for c in matched_codes)

    # Vernacular synthesized answer
    assert "नमस्ते" in result.answer
    assert "पात्र योजना" in result.answer or "योजना" in result.answer
    assert "₹" in result.answer


def test_agent_student_scooty_query():
    """
    Test student merit query:
    'My daughter scored 82% in Class 12 in Jaipur. Can she get a scooty or scholarship?'
    """
    query = "My daughter scored 82% in Class 12 in Jaipur. Can she get a scooty or scholarship?"

    result = WelfareAgentOrchestrator.process_query(query=query, language_preference="en")

    assert result.profile_extracted.get("is_student") is True
    assert result.profile_extracted.get("marks_percentage_12") == 82.0
    assert result.profile_extracted.get("gender") == "FEMALE"

    # Should find and reason about Scooty / Anuprati
    matched_names = [s.get("name_en", "") for s in result.recommended_schemes]
    assert any("Scooty" in n or "Coaching" in n or "Ayushman" in n for n in matched_names)


def test_agent_graceful_edge_cases():
    """Verify that agent does not crash on vague or minimal input and fails gracefully."""
    vague_query = "Hello, tell me about government help."
    result = WelfareAgentOrchestrator.process_query(query=vague_query)

    assert result.answer is not None
    assert len(result.reasoning_steps) >= 1
    assert result.total_execution_time_ms > 0
