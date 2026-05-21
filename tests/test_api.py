import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from casa_gatekeeper.api import (
    MAX_DOCUMENT_TEXT_LENGTH,
    MAX_SOURCE_LENGTH,
    RouteDocumentRequest,
    health,
    route_document_endpoint,
)


def test_health_endpoint_reports_ok():
    response = health()

    assert response["status"] == "ok"
    assert response["system"] == "casa-construction-gatekeeper"


def test_route_document_endpoint_returns_flattened_response_without_auth_when_unconfigured(monkeypatch):
    monkeypatch.delenv("CASA_API_TOKEN", raising=False)
    persisted_records = []

    def fake_persist_audit_record(record):
        persisted_records.append(record)
        return {"jsonl": {"status": "saved"}, "airtable": {"status": "skipped"}}

    monkeypatch.setattr("casa_gatekeeper.api.persist_audit_record", fake_persist_audit_record)

    response = route_document_endpoint(
        RouteDocumentRequest(
            text=(
                "RFI for Project #8821. Need clarification for spec section 23 00 00. "
                "Submitted by Northline Mechanical."
            ),
            source="test-api",
        )
    )

    assert response.decision == "ALLOW"
    assert response.document_type == "RFI"
    assert response.project_id == "8821"
    assert response.priority_level == 2
    assert response.audit_record["source"] == "test-api"
    assert persisted_records
    assert persisted_records[0].source == "test-api"


def test_route_document_endpoint_rejects_missing_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("CASA_API_TOKEN", "secret-token")

    with pytest.raises(HTTPException) as exc_info:
        route_document_endpoint(
            RouteDocumentRequest(text="RFI for Project #8821. Need clarification.", source="test-api")
        )

    assert exc_info.value.status_code == 401


def test_route_document_endpoint_rejects_invalid_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("CASA_API_TOKEN", "secret-token")

    with pytest.raises(HTTPException) as exc_info:
        route_document_endpoint(
            RouteDocumentRequest(text="RFI for Project #8821. Need clarification.", source="test-api"),
            api_key="wrong-token",
        )

    assert exc_info.value.status_code == 401


def test_route_document_endpoint_accepts_valid_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("CASA_API_TOKEN", "secret-token")
    persisted_records = []

    def fake_persist_audit_record(record):
        persisted_records.append(record)
        return {"jsonl": {"status": "saved"}, "airtable": {"status": "skipped"}}

    monkeypatch.setattr("casa_gatekeeper.api.persist_audit_record", fake_persist_audit_record)

    response = route_document_endpoint(
        RouteDocumentRequest(
            text=(
                "RFI for Project #8821. Need clarification for spec section 23 00 00. "
                "Submitted by Northline Mechanical."
            ),
            source="test-api",
        ),
        api_key="secret-token",
    )

    assert response.decision == "ALLOW"
    assert persisted_records


def test_route_document_request_rejects_oversized_payload_fields():
    with pytest.raises(ValidationError):
        RouteDocumentRequest(text="x" * (MAX_DOCUMENT_TEXT_LENGTH + 1), source="test-api")

    with pytest.raises(ValidationError):
        RouteDocumentRequest(text="RFI for Project #8821.", source="x" * (MAX_SOURCE_LENGTH + 1))
