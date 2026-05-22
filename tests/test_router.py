from casa_gatekeeper.models import DecisionType, DocumentType
from casa_gatekeeper.router import route_document


def test_route_document_allows_clean_rfi():
    result = route_document(
        "RFI for Project #8821. Need clarification for spec section 23 00 00. "
        "Submitted by Mechanical Trade Partner.",
        source="test",
    )

    assert result["document"].document_type == DocumentType.RFI
    assert result["document"].project_id == "8821"
    assert result["document"].spec_section == "23 00 00"
    assert result["decision"].decision == DecisionType.ALLOW
    assert result["audit_record"].source == "test"


def test_route_document_reviews_urgent_missing_project():
    result = route_document(
        "Field issue: blocked crew with schedule impact. Cannot proceed until conflict is resolved.",
        source="test",
    )

    assert result["document"].priority_level == 5
    assert result["decision"].decision == DecisionType.REVIEW
    assert "missing_project_id" in result["decision"].audit_tags
    assert "schedule_impact" in result["decision"].audit_tags


def test_route_document_halts_safety_language():
    result = route_document(
        "Project ID: 8821. Field issue: hazardous condition and immediate danger near active work zone.",
        source="test",
    )

    assert result["document"].document_type == DocumentType.SAFETY_ISSUE
    assert result["decision"].decision == DecisionType.HALT
