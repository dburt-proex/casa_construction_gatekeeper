"""Validated schemas for CASA Construction Gatekeeper."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Supported construction intake document categories."""

    RFI = "RFI"
    SUBMITTAL = "SUBMITTAL"
    CHANGE_ORDER = "CHANGE_ORDER"
    FIELD_ISSUE = "FIELD_ISSUE"
    SAFETY_ISSUE = "SAFETY_ISSUE"
    UNKNOWN = "UNKNOWN"


class DecisionType(str, Enum):
    """Governance routing decisions."""

    ALLOW = "ALLOW"
    REVIEW = "REVIEW"
    HALT = "HALT"


class ConstructionDocument(BaseModel):
    """Structured representation extracted from unstructured construction text."""

    project_id: Optional[str] = None
    spec_section: Optional[str] = None
    document_type: DocumentType = DocumentType.UNKNOWN
    priority_level: int = Field(default=3, ge=1, le=5)
    assigned_subcontractor: Optional[str] = None
    summary: str
    detected_risks: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    human_review_required: bool = False
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)


class GovernanceDecision(BaseModel):
    """Policy outcome for a classified construction document."""

    decision: DecisionType
    reason: str
    priority_level: int = Field(ge=1, le=5)
    required_action: str
    audit_tags: List[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    """Audit-grade record of intake, extraction, and governance decision."""

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    document: ConstructionDocument
    decision: GovernanceDecision
    source: str = "manual"
    system_version: str = "0.1.0"
