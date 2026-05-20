"""HTTP API for hosted CASA Construction Gatekeeper deployments."""

from __future__ import annotations

from typing import Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from casa_gatekeeper import __version__
from casa_gatekeeper.audit import AuditSinkError, persist_audit_record, to_serializable_dict
from casa_gatekeeper.router import route_document

load_dotenv()


class RouteDocumentRequest(BaseModel):
    """Incoming document payload for automation platforms."""

    text: str = Field(min_length=1, description="Raw RFI, submittal, change order, or field issue text.")
    source: str = Field(default="api", description="Source system label, such as activepieces, n8n, zapier, or procore.")


class RouteDocumentResponse(BaseModel):
    """Flattened routing response for no-code automation tools."""

    decision: str
    document_type: str
    project_id: str | None
    spec_section: str | None
    priority_level: int
    assigned_subcontractor: str | None
    confidence_score: float
    detected_risks: list[str]
    missing_fields: list[str]
    human_review_required: bool
    reason: str
    required_action: str
    audit_tags: list[str]
    audit_record: Dict[str, Any]


app = FastAPI(
    title="CASA Construction Gatekeeper API",
    description="Deterministic construction document intake, governance, and routing API.",
    version=__version__,
)


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint for hosting providers and workflow tools."""

    return {"status": "ok", "system": "casa-construction-gatekeeper", "version": __version__}


@app.post("/route-document", response_model=RouteDocumentResponse)
def route_document_endpoint(payload: RouteDocumentRequest) -> RouteDocumentResponse:
    """Classify and route a construction document."""

    result = route_document(payload.text, source=payload.source)
    try:
        persist_audit_record(result["audit_record"])
    except AuditSinkError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    audit_record = to_serializable_dict(result["audit_record"])
    document = audit_record["document"]
    decision = audit_record["decision"]

    return RouteDocumentResponse(
        decision=decision["decision"],
        document_type=document["document_type"],
        project_id=document["project_id"],
        spec_section=document["spec_section"],
        priority_level=decision["priority_level"],
        assigned_subcontractor=document["assigned_subcontractor"],
        confidence_score=document["confidence_score"],
        detected_risks=document["detected_risks"],
        missing_fields=document["missing_fields"],
        human_review_required=document["human_review_required"],
        reason=decision["reason"],
        required_action=decision["required_action"],
        audit_tags=decision["audit_tags"],
        audit_record=audit_record,
    )
