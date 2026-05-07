"""Document routing orchestration."""

from __future__ import annotations

from typing import Any, Dict

from casa_gatekeeper import __version__
from casa_gatekeeper.classifier import classify_text
from casa_gatekeeper.models import AuditRecord, DecisionType
from casa_gatekeeper.policies import apply_governance_policies


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def route_document(text: str, source: str = "manual") -> Dict[str, Any]:
    """Classify, govern, and audit a construction intake item."""

    document = classify_text(text)
    decision = apply_governance_policies(document, original_text=text)

    document.priority_level = decision.priority_level
    document.human_review_required = _enum_value(decision.decision) != DecisionType.ALLOW.value

    record = AuditRecord(
        document=document,
        decision=decision,
        source=source,
        system_version=__version__,
    )

    return {
        "document": document,
        "decision": decision,
        "audit_record": record,
    }
