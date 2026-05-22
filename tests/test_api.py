import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from casa_gatekeeper.api import (
    DEMO_COOKIE_NAME,
    MAX_DOCUMENT_TEXT_LENGTH,
    MAX_SOURCE_LENGTH,
    RouteDocumentRequest,
    demo_dashboard,
    demo_route_document_endpoint,
    health,
    route_document_endpoint,
)


def _request_with_cookies(cookies=None) -> Request:
    cookie_value = "; ".join(f"{key}={value}" for key, value in (cookies or {}).items())
    headers = []
    if cookie_value:
        headers.append((b"cookie", cookie_value.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/demo",
        "scheme": "http",
        "server": ("testserver", 80),
        "headers": headers,
        "query_string": b"",
    }
    return Request(scope)


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
                "Submitted by Mechanical Trade Partner."
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
                "Submitted by Mechanical Trade Partner."
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


def test_demo_dashboard_requires_demo_configuration(monkeypatch):
    monkeypatch.delenv("CASA_DEMO_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc_info:
        demo_dashboard(_request_with_cookies())

    assert exc_info.value.status_code == 503


def test_demo_dashboard_rejects_missing_demo_token(monkeypatch):
    monkeypatch.setenv("CASA_DEMO_TOKEN", "demo-secret")

    with pytest.raises(HTTPException) as exc_info:
        demo_dashboard(_request_with_cookies())

    assert exc_info.value.status_code == 401


def test_demo_dashboard_accepts_demo_token_and_sets_cookie(monkeypatch):
    monkeypatch.setenv("CASA_DEMO_TOKEN", "demo-secret")

    response = demo_dashboard(_request_with_cookies(), token="demo-secret")

    assert response.status_code == 200
    assert b"CASA Construction Gatekeeper" in response.body
    assert DEMO_COOKIE_NAME in response.headers["set-cookie"]


def test_demo_dashboard_accepts_demo_cookie(monkeypatch):
    monkeypatch.setenv("CASA_DEMO_TOKEN", "demo-secret")

    first_response = demo_dashboard(_request_with_cookies(), token="demo-secret")
    second_response = demo_dashboard(_request_with_cookies({DEMO_COOKIE_NAME: "demo-secret"}))

    assert first_response.status_code == 200
    assert second_response.status_code == 200


def test_demo_route_rejects_wrong_demo_token(monkeypatch):
    monkeypatch.setenv("CASA_DEMO_TOKEN", "demo-secret")

    with pytest.raises(HTTPException) as exc_info:
        demo_route_document_endpoint(
            RouteDocumentRequest(text="RFI for Project #8821. Need clarification.", source="customer-demo"),
            _request_with_cookies(),
            demo_token="wrong-token",
        )

    assert exc_info.value.status_code == 401


def test_demo_route_uses_demo_token_without_exposing_api_token(monkeypatch):
    monkeypatch.setenv("CASA_DEMO_TOKEN", "demo-secret")
    monkeypatch.setenv("CASA_API_TOKEN", "api-secret")
    persisted_records = []

    def fake_persist_audit_record(record):
        persisted_records.append(record)
        return {"jsonl": {"status": "saved"}, "airtable": {"status": "skipped"}}

    monkeypatch.setattr("casa_gatekeeper.api.persist_audit_record", fake_persist_audit_record)

    response = demo_route_document_endpoint(
        RouteDocumentRequest(
            text=(
                "RFI for Project #8821. Need clarification for spec section 23 00 00. "
                "Submitted by Mechanical Trade Partner."
            ),
            source="customer-demo",
        ),
        _request_with_cookies(),
        demo_token="demo-secret",
    )

    assert response.decision == "ALLOW"
    assert persisted_records


def test_public_route_still_rejects_missing_api_token_when_configured(monkeypatch):
    monkeypatch.setenv("CASA_API_TOKEN", "api-secret")

    with pytest.raises(HTTPException) as exc_info:
        route_document_endpoint(
            RouteDocumentRequest(text="RFI for Project #8821. Need clarification.", source="test-api")
        )

    assert exc_info.value.status_code == 401
