"""Deterministic keyword classifier and extractor for prototype intake."""

from __future__ import annotations

import re
from typing import List, Optional

from casa_gatekeeper.models import ConstructionDocument, DocumentType
from casa_gatekeeper.policies import SAFETY_CRITICAL_TERMS, SCHEDULE_IMPACT_TERMS


RFI_PATTERNS = (
    r"\brfi\b",
    r"\brequest for information\b",
    r"\bclarification\b",
)

SUBMITTAL_PATTERNS = (
    r"\bsubmittal\b",
    r"\bshop drawing\b",
    r"\bproduct data\b",
)

CHANGE_ORDER_PATTERNS = (
    r"\bchange order\b",
    r"\bco\b",
    r"\bcost impact\b",
    r"\bscope change\b",
)

FIELD_ISSUE_PATTERNS = (
    r"\bfield issue\b",
    r"\bclash\b",
    r"\bconflict\b",
    r"\bcannot proceed\b",
    r"\bblocked\b",
)

PROJECT_PATTERNS = (
    r"\bProject\s*#\s*([A-Za-z0-9][A-Za-z0-9_-]*)",
    r"\bProject\s+ID\s*:?\s*([A-Za-z0-9][A-Za-z0-9_-]*)",
    r"\bProcore\s+Project\s*:?\s*([A-Za-z0-9][A-Za-z0-9_-]*)",
)

SPEC_SECTION_PATTERN = r"\b(\d{2}\s+\d{2}\s+\d{2})\b"

SUBCONTRACTOR_PATTERN = (
    r"\b(?:Submitted by|Contractor|Subcontractor)\s*:?\s*"
    r"([A-Za-z0-9&.,' -]+?)(?:\.|,|\n|$)"
)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def _contains_term(text: str, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", text, flags=re.IGNORECASE) is not None


def _extract_first(patterns: tuple[str, ...], text: str) -> Optional[str]:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def _extract_spec_section(text: str) -> Optional[str]:
    match = re.search(SPEC_SECTION_PATTERN, text)
    if not match:
        return None
    return " ".join(match.group(1).split())


def _extract_subcontractor(text: str) -> Optional[str]:
    match = re.search(SUBCONTRACTOR_PATTERN, text, flags=re.IGNORECASE)
    if not match:
        return None
    return match.group(1).strip(" .,-")


def _summarize(text: str) -> str:
    normalized = " ".join(text.strip().split())
    if not normalized:
        return "No document text provided."
    return normalized[:240]


def _classify_document_type(text: str) -> DocumentType:
    if any(_contains_term(text, term) for term in SAFETY_CRITICAL_TERMS):
        return DocumentType.SAFETY_ISSUE
    if _matches_any(text, RFI_PATTERNS):
        return DocumentType.RFI
    if _matches_any(text, SUBMITTAL_PATTERNS):
        return DocumentType.SUBMITTAL
    if _matches_any(text, CHANGE_ORDER_PATTERNS):
        return DocumentType.CHANGE_ORDER
    if _matches_any(text, FIELD_ISSUE_PATTERNS):
        return DocumentType.FIELD_ISSUE
    return DocumentType.UNKNOWN


def _detect_risks(text: str) -> List[str]:
    risks: List[str] = []

    if any(_contains_term(text, term) for term in SAFETY_CRITICAL_TERMS):
        risks.append("safety_critical")

    if any(_contains_term(text, term) for term in SCHEDULE_IMPACT_TERMS):
        risks.append("schedule_impact")

    if _contains_term(text, "cost impact"):
        risks.append("cost_impact")

    if _contains_term(text, "scope change"):
        risks.append("scope_change")

    if any(_contains_term(text, term) for term in ("clash", "conflict", "coordination")):
        risks.append("coordination_conflict")

    return risks


def _base_priority(document_type: DocumentType, risks: List[str]) -> int:
    if "safety_critical" in risks or "schedule_impact" in risks:
        return 5
    if document_type == DocumentType.FIELD_ISSUE:
        return 4
    if document_type == DocumentType.CHANGE_ORDER:
        return 3
    if document_type in {DocumentType.RFI, DocumentType.SUBMITTAL}:
        return 2
    return 3


def _missing_fields(
    document_type: DocumentType,
    project_id: Optional[str],
    spec_section: Optional[str],
    summary: str,
) -> List[str]:
    missing: List[str] = []

    if not project_id:
        missing.append("project_id")

    if document_type == DocumentType.UNKNOWN:
        missing.append("document_type")

    if document_type in {DocumentType.RFI, DocumentType.SUBMITTAL} and not spec_section:
        missing.append("spec_section")

    if not summary or summary == "No document text provided.":
        missing.append("summary")

    return missing


def _confidence_score(
    document_type: DocumentType,
    project_id: Optional[str],
    spec_section: Optional[str],
    subcontractor: Optional[str],
    summary: str,
) -> float:
    if document_type == DocumentType.UNKNOWN:
        base = 0.35
    elif document_type == DocumentType.SAFETY_ISSUE:
        base = 0.92
    else:
        base = 0.78

    if project_id:
        base += 0.06
    else:
        base -= 0.08

    if spec_section:
        base += 0.06

    if subcontractor:
        base += 0.04

    if len(summary) < 24:
        base -= 0.10

    return round(max(0.0, min(1.0, base)), 2)


def classify_text(text: str) -> ConstructionDocument:
    """Classify construction text and extract deterministic fields."""

    document_type = _classify_document_type(text)
    project_id = _extract_first(PROJECT_PATTERNS, text)
    spec_section = _extract_spec_section(text)
    subcontractor = _extract_subcontractor(text)
    summary = _summarize(text)
    risks = _detect_risks(text)
    missing = _missing_fields(document_type, project_id, spec_section, summary)
    confidence = _confidence_score(document_type, project_id, spec_section, subcontractor, summary)

    return ConstructionDocument(
        project_id=project_id,
        spec_section=spec_section,
        document_type=document_type,
        priority_level=_base_priority(document_type, risks),
        assigned_subcontractor=subcontractor,
        summary=summary,
        detected_risks=risks,
        missing_fields=missing,
        human_review_required=bool(missing) or confidence < 0.70 or bool({"safety_critical", "schedule_impact"} & set(risks)),
        confidence_score=confidence,
    )


def extract_with_llm_placeholder(text: str) -> ConstructionDocument:
    """Future extension point for a paid LLM/Pydantic AI extractor.

    The production pattern should keep this output behind the same
    ConstructionDocument schema and deterministic policy layer used by the
    keyword classifier.
    """

    return classify_text(text)
