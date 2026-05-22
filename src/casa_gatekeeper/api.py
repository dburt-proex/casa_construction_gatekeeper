"""HTTP API for hosted CASA Construction Gatekeeper deployments."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Annotated, Any, Dict

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field
from starlette.responses import HTMLResponse

from casa_gatekeeper import __version__
from casa_gatekeeper.audit import AuditSinkError, persist_audit_record, to_serializable_dict
from casa_gatekeeper.router import route_document

load_dotenv()

MAX_DOCUMENT_TEXT_LENGTH = 20000
MAX_SOURCE_LENGTH = 80
API_KEY_HEADER_NAME = "X-CASA-API-Key"
DEMO_TOKEN_HEADER_NAME = "X-CASA-Demo-Token"
DEMO_COOKIE_NAME = "casa_demo_access"
DEMO_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 6
DEMO_HTML_PATH = Path(__file__).with_name("static") / "demo.html"


class RouteDocumentRequest(BaseModel):
    """Incoming document payload for automation platforms."""

    text: str = Field(
        min_length=1,
        max_length=MAX_DOCUMENT_TEXT_LENGTH,
        description="Raw RFI, submittal, change order, or field issue text.",
    )
    source: str = Field(
        default="api",
        min_length=1,
        max_length=MAX_SOURCE_LENGTH,
        description="Source system label, such as activepieces, n8n, zapier, or procore.",
    )


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


def _configured_api_token() -> str | None:
    token = os.getenv("CASA_API_TOKEN", "").strip()
    return token or None


def _configured_demo_token() -> str | None:
    token = os.getenv("CASA_DEMO_TOKEN", "").strip()
    return token or None


def _require_api_token(provided_api_key: str | None) -> None:
    configured_token = _configured_api_token()
    if not configured_token:
        return

    if not provided_api_key or not secrets.compare_digest(provided_api_key, configured_token):
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")


def _require_demo_token(provided_demo_token: str | None) -> None:
    configured_token = _configured_demo_token()
    if not configured_token:
        raise HTTPException(status_code=503, detail="CASA demo dashboard is not configured.")

    if not provided_demo_token or not secrets.compare_digest(provided_demo_token, configured_token):
        raise HTTPException(status_code=401, detail="Missing or invalid demo token.")


def _route_document(payload: RouteDocumentRequest) -> RouteDocumentResponse:
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


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint for hosting providers and workflow tools."""

    return {"status": "ok", "system": "casa-construction-gatekeeper", "version": __version__}


@app.get("/demo", response_class=HTMLResponse, include_in_schema=False)
def demo_dashboard(
    request: Request,
    token: Annotated[str | None, Query(alias="token")] = None,
) -> HTMLResponse:
    """Serve the private customer-facing demo dashboard."""

    demo_token = token or request.cookies.get(DEMO_COOKIE_NAME)
    _require_demo_token(demo_token)

    response = HTMLResponse(DEMO_HTML_PATH.read_text(encoding="utf-8"))
    if token:
        response.set_cookie(
            key=DEMO_COOKIE_NAME,
            value=token,
            max_age=DEMO_COOKIE_MAX_AGE_SECONDS,
            httponly=True,
            secure=request.url.scheme == "https",
            samesite="lax",
        )
    return response


@app.post("/demo/route", response_model=RouteDocumentResponse, include_in_schema=False)
def demo_route_document_endpoint(
    payload: RouteDocumentRequest,
    request: Request,
    demo_token: Annotated[str | None, Header(alias=DEMO_TOKEN_HEADER_NAME)] = None,
) -> RouteDocumentResponse:
    """Route a document from the private demo dashboard."""

    _require_demo_token(demo_token or request.cookies.get(DEMO_COOKIE_NAME))
    return _route_document(payload)


@app.post("/route-document", response_model=RouteDocumentResponse)
def route_document_endpoint(
    payload: RouteDocumentRequest,
    api_key: Annotated[str | None, Header(alias=API_KEY_HEADER_NAME)] = None,
) -> RouteDocumentResponse:
    """Classify and route a construction document."""

    _require_api_token(api_key)
    return _route_document(payload)
