import json

from casa_gatekeeper.audit import build_airtable_audit_fields, save_audit_record_to_airtable
from casa_gatekeeper.models import (
    AuditRecord,
    ConstructionDocument,
    DecisionType,
    DocumentType,
    GovernanceDecision,
)


def _sample_record() -> AuditRecord:
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
    return AuditRecord(document=document, decision=decision, source="activepieces")


def test_build_airtable_audit_fields_flattens_decision():
    fields = build_airtable_audit_fields(_sample_record())

    assert fields["Decision"] == "ALLOW"
    assert fields["Document Type"] == "RFI"
    assert fields["Project ID"] == "8821"
    assert fields["Audit Tags"] == "standard_routing"
    assert json.loads(fields["Audit Record JSON"])["source"] == "activepieces"


def test_save_audit_record_to_airtable_posts_expected_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return b'{"records":[{"id":"rec123"}]}'

    def fake_urlopen(airtable_request, timeout):
        captured["url"] = airtable_request.full_url
        captured["headers"] = dict(airtable_request.header_items())
        captured["payload"] = json.loads(airtable_request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("casa_gatekeeper.audit.request.urlopen", fake_urlopen)

    result = save_audit_record_to_airtable(
        _sample_record(),
        env={
            "AIRTABLE_AUDIT_ENABLED": "true",
            "AIRTABLE_API_KEY": "pat_test",
            "AIRTABLE_BASE_ID": "app123",
            "AIRTABLE_AUDIT_TABLE_NAME": "CASA Audit",
        },
        timeout_seconds=3.0,
    )

    assert result["status"] == "saved"
    assert captured["url"] == "https://api.airtable.com/v0/app123/CASA%20Audit"
    assert captured["headers"]["Authorization"] == "Bearer pat_test"
    assert captured["timeout"] == 3.0
    assert captured["payload"]["records"][0]["fields"]["Decision"] == "ALLOW"
    assert captured["payload"]["typecast"] is True
