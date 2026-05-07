"""Deterministic governance policies for construction document routing."""

from __future__ import annotations

import re
from typing import Iterable, List

from casa_gatekeeper.models import ConstructionDocument, DecisionType, DocumentType, GovernanceDecision


SAFETY_CRITICAL_TERMS = (
    "safety",
    "injury",
    "fire",
    "collapse",
    "hazardous",
    "osha",
    "structural failure",
    "immediate danger",
)

SCHEDULE_IMPACT_TERMS = (
    "schedule impact",
    "delay",
    "failed inspection",
    "site stoppage",
    "blocked crew",
    "urgent",
    "cannot proceed",
)


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _contains_term(text: str, term: str) -> bool:
    pattern = rf"\b{re.escape(term.lower())}\b"
    return re.search(pattern, text.lower()) is not None


def _matched_terms(text: str, terms: Iterable[str]) -> List[str]:
    return [term for term in terms if _contains_term(text, term)]


def apply_governance_policies(
    document: ConstructionDocument,
    original_text: str = "",
) -> GovernanceDecision:
    """Apply deterministic CASA routing rules to a classified document."""

    text = original_text or document.summary
    safety_terms = _matched_terms(text, SAFETY_CRITICAL_TERMS)
    schedule_terms = _matched_terms(text, SCHEDULE_IMPACT_TERMS)

    document_type = _enum_value(document.document_type)
    risk_set = set(document.detected_risks)
    has_safety_risk = (
        bool(safety_terms)
        or "safety_critical" in risk_set
        or document_type == DocumentType.SAFETY_ISSUE.value
    )
    has_schedule_risk = bool(schedule_terms) or "schedule_impact" in risk_set

    priority_level = 5 if has_safety_risk or has_schedule_risk else document.priority_level

    if has_safety_risk:
        tags = ["safety_critical", "halt_required"]
        if safety_terms:
            tags.extend(f"term:{term}" for term in safety_terms)
        return GovernanceDecision(
            decision=DecisionType.HALT,
            reason="Safety-critical language was detected; automated routing must stop.",
            priority_level=5,
            required_action="Stop automated routing and notify the safety owner and project leadership immediately.",
            audit_tags=tags,
        )

    review_reasons: List[str] = []
    audit_tags: List[str] = []

    if not document.project_id:
        review_reasons.append("Project ID is missing.")
        audit_tags.append("missing_project_id")

    if document_type == DocumentType.UNKNOWN.value:
        review_reasons.append("Document type is unknown.")
        audit_tags.append("unknown_document_type")

    if document.confidence_score < 0.70:
        review_reasons.append("Classifier confidence is below 0.70.")
        audit_tags.append("low_confidence")

    if document_type in {DocumentType.RFI.value, DocumentType.SUBMITTAL.value} and not document.spec_section:
        review_reasons.append("Spec section is required for RFI and submittal routing.")
        audit_tags.append("missing_spec_section")

    if has_schedule_risk:
        review_reasons.append("Schedule-impact language requires human review.")
        audit_tags.append("schedule_impact")
        audit_tags.extend(f"term:{term}" for term in schedule_terms)

    if review_reasons:
        action = "Human reviewer must validate missing or high-risk fields before routing."
        if has_schedule_risk:
            action = "Escalate to the project manager for same-day review before routing."

        return GovernanceDecision(
            decision=DecisionType.REVIEW,
            reason=" ".join(review_reasons),
            priority_level=priority_level,
            required_action=action,
            audit_tags=audit_tags,
        )

    return GovernanceDecision(
        decision=DecisionType.ALLOW,
        reason="Required fields are present, confidence is acceptable, and no blocking risk was detected.",
        priority_level=priority_level,
        required_action="Continue standard routing workflow.",
        audit_tags=["standard_routing"],
    )
