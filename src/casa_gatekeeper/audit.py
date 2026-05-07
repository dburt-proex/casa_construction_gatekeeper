"""Audit serialization and JSONL persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from casa_gatekeeper.models import AuditRecord


def to_serializable_dict(record: AuditRecord) -> Dict[str, Any]:
    """Return a JSON-ready dictionary for Pydantic v1 or v2."""

    if hasattr(record, "model_dump"):
        return record.model_dump(mode="json")
    return json.loads(record.json())


def serialize_audit_record(record: AuditRecord) -> str:
    """Serialize an audit record as a stable JSON string."""

    return json.dumps(to_serializable_dict(record), sort_keys=True)


def save_audit_record(record: AuditRecord, filepath: str = "audit_log.jsonl") -> None:
    """Append an audit record to a JSONL audit log."""

    path = Path(filepath)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as audit_file:
        audit_file.write(serialize_audit_record(record) + "\n")
