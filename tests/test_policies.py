from casa_gatekeeper.models import ConstructionDocument, DecisionType, DocumentType
from casa_gatekeeper.policies import apply_governance_policies


def test_missing_project_id_triggers_review():
    document = ConstructionDocument(
        document_type=DocumentType.RFI,
        spec_section="23 00 00",
        priority_level=2,
        summary="RFI clarification for duct routing.",
        detected_risks=[],
        missing_fields=["project_id"],
        human_review_required=True,
        confidence_score=0.88,
    )

    decision = apply_governance_policies(document)

    assert decision.decision == DecisionType.REVIEW
    assert "missing_project_id" in decision.audit_tags


def test_safety_issue_triggers_halt():
    document = ConstructionDocument(
        project_id="8821",
        document_type=DocumentType.FIELD_ISSUE,
        priority_level=5,
        summary="Immediate danger due to structural failure near the east stair.",
        detected_risks=["safety_critical"],
        missing_fields=[],
        human_review_required=True,
        confidence_score=0.93,
    )

    decision = apply_governance_policies(document)

    assert decision.decision == DecisionType.HALT
    assert decision.priority_level == 5


def test_clean_rfi_with_project_and_spec_triggers_allow():
    document = ConstructionDocument(
        project_id="8821",
        spec_section="23 00 00",
        document_type=DocumentType.RFI,
        priority_level=2,
        summary="RFI requesting clarification on HVAC routing.",
        detected_risks=[],
        missing_fields=[],
        human_review_required=False,
        confidence_score=0.91,
    )

    decision = apply_governance_policies(document)

    assert decision.decision == DecisionType.ALLOW


def test_unknown_document_triggers_review():
    document = ConstructionDocument(
        project_id="8821",
        document_type=DocumentType.UNKNOWN,
        priority_level=3,
        summary="Please see attached notes.",
        detected_risks=[],
        missing_fields=["document_type"],
        human_review_required=True,
        confidence_score=0.35,
    )

    decision = apply_governance_policies(document)

    assert decision.decision == DecisionType.REVIEW
    assert "unknown_document_type" in decision.audit_tags


def test_urgent_schedule_impact_raises_priority_to_five():
    document = ConstructionDocument(
        project_id="7712",
        document_type=DocumentType.FIELD_ISSUE,
        priority_level=3,
        summary="Blocked crew with schedule impact. Cannot proceed until layout conflict is resolved.",
        detected_risks=["schedule_impact"],
        missing_fields=[],
        human_review_required=True,
        confidence_score=0.88,
    )

    decision = apply_governance_policies(document)

    assert decision.decision == DecisionType.REVIEW
    assert decision.priority_level == 5
    assert "schedule_impact" in decision.audit_tags
