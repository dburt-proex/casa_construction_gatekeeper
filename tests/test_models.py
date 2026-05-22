import json

from casa_gatekeeper.audit import serialize_audit_record
from casa_gatekeeper.models import (
    AuditRecord,
    ConstructionDocument,
    DecisionType,
    DocumentType,
    GovernanceDecision,
)


def test_audit_record_can_serialize():
    document = ConstructionDocument(
        project_id="8821",
        spec_section="23 00 00",
        document_type=DocumentType.RFI,
        priority_level=2,
        assigned_subcontractor="Mechanical Trade Partner",
        summary="RFI for HVAC clash.",
        detected_risks=["coordination_conflict"],
        missing_fields=[],
        human_review_required=False,
        confidence_score=0.94,
    )
    decision = GovernanceDecision(
        decision=DecisionType.ALLOW,
        reason="Ready for routing.",
        priority_level=2,
        required_action="Continue standard routing workflow.",
        audit_tags=["standard_routing"],
    )

    serialized = serialize_audit_record(AuditRecord(document=document, decision=decision))
    data = json.loads(serialized)

    assert data["document"]["document_type"] == "RFI"
    assert data["decision"]["decision"] == "ALLOW"
    assert data["system_version"] == "0.1.0"
