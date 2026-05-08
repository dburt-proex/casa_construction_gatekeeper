from casa_gatekeeper.api import RouteDocumentRequest, health, route_document_endpoint


def test_health_endpoint_reports_ok():
    response = health()

    assert response["status"] == "ok"
    assert response["system"] == "casa-construction-gatekeeper"


def test_route_document_endpoint_returns_flattened_response():
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
