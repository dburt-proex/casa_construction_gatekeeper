"""Audit serialization plus local and hosted audit persistence."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Mapping
from urllib import error, parse, request

from casa_gatekeeper.models import AuditRecord

DEFAULT_AUDIT_LOG_PATH = "audit_log.jsonl"
DEFAULT_AIRTABLE_TIMEOUT_SECONDS = 10.0


class AuditSinkError(RuntimeError):
    """Raised when an enabled audit sink cannot persist the record."""


class AirtableAuditError(AuditSinkError):
    """Raised when Airtable audit persistence fails."""


def to_serializable_dict(record: AuditRecord) -> Dict[str, Any]:
    """Return a JSON-ready dictionary for Pydantic v1 or v2."""

    if hasattr(record, "model_dump"):
        return record.model_dump(mode="json")
    return json.loads(record.json())


def serialize_audit_record(record: AuditRecord) -> str:
    """Serialize an audit record as a stable JSON string."""

    return json.dumps(to_serializable_dict(record), sort_keys=True)


def save_audit_record(record: AuditRecord, filepath: str = DEFAULT_AUDIT_LOG_PATH) -> None:
    """Append an audit record to a JSONL audit log."""

    path = Path(filepath)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a", encoding="utf-8") as audit_file:
        audit_file.write(serialize_audit_record(record) + "\n")


def _env_flag(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _airtable_token(env: Mapping[str, str]) -> str | None:
    return env.get("AIRTABLE_API_KEY") or env.get("AIRTABLE_PERSONAL_ACCESS_TOKEN")


def airtable_audit_enabled(env: Mapping[str, str] | None = None) -> bool:
    """Return whether Airtable audit persistence should run."""

    resolved_env = os.environ if env is None else env
    explicit = resolved_env.get("AIRTABLE_AUDIT_ENABLED")
    if explicit is not None:
        return _env_flag(explicit)

    return bool(
        _airtable_token(resolved_env)
        and resolved_env.get("AIRTABLE_BASE_ID")
        and (resolved_env.get("AIRTABLE_AUDIT_TABLE_NAME") or resolved_env.get("AIRTABLE_TABLE_NAME"))
    )


def _required_airtable_config(env: Mapping[str, str]) -> tuple[str, str, str]:
    token = _airtable_token(env)
    base_id = env.get("AIRTABLE_BASE_ID")
    table_name = env.get("AIRTABLE_AUDIT_TABLE_NAME") or env.get("AIRTABLE_TABLE_NAME")

    missing = []
    if not token:
        missing.append("AIRTABLE_API_KEY")
    if not base_id:
        missing.append("AIRTABLE_BASE_ID")
    if not table_name:
        missing.append("AIRTABLE_AUDIT_TABLE_NAME")

    if missing:
        raise AirtableAuditError(f"Airtable audit sink is enabled but missing: {', '.join(missing)}")

    return token, base_id, table_name


def build_airtable_audit_fields(record: AuditRecord) -> Dict[str, Any]:
    """Map an audit record into the Airtable fields expected by the pilot table."""

    audit_record = to_serializable_dict(record)
    document = audit_record["document"]
    decision = audit_record["decision"]

    return {
        "Timestamp": audit_record["timestamp"],
        "Decision": decision["decision"],
        "Source": audit_record["source"],
        "Document Type": document["document_type"],
        "Project ID": document["project_id"],
        "Spec Section": document["spec_section"],
        "Priority Level": decision["priority_level"],
        "Assigned Subcontractor": document["assigned_subcontractor"],
        "Confidence Score": document["confidence_score"],
        "Human Review Required": document["human_review_required"],
        "Required Action": decision["required_action"],
        "Reason": decision["reason"],
        "Audit Tags": ", ".join(decision["audit_tags"]),
        "Detected Risks": ", ".join(document["detected_risks"]),
        "Missing Fields": ", ".join(document["missing_fields"]),
        "Summary": document["summary"],
        "System Version": audit_record["system_version"],
        "Audit Record JSON": json.dumps(audit_record, sort_keys=True),
    }


def save_audit_record_to_airtable(
    record: AuditRecord,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_AIRTABLE_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Persist an audit record to Airtable when the sink is enabled."""

    resolved_env = os.environ if env is None else env
    if not airtable_audit_enabled(resolved_env):
        return {"enabled": False, "status": "skipped"}

    token, base_id, table_name = _required_airtable_config(resolved_env)
    endpoint = "https://api.airtable.com/v0/{base_id}/{table_name}".format(
        base_id=parse.quote(base_id, safe=""),
        table_name=parse.quote(table_name, safe=""),
    )
    payload = json.dumps(
        {
            "records": [{"fields": build_airtable_audit_fields(record)}],
            "typecast": True,
        }
    ).encode("utf-8")
    airtable_request = request.Request(
        endpoint,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with request.urlopen(airtable_request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise AirtableAuditError(f"Airtable audit write failed with HTTP {exc.code}: {response_body}") from exc
    except error.URLError as exc:
        raise AirtableAuditError(f"Airtable audit write failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise AirtableAuditError("Airtable audit write timed out") from exc

    if not response_body:
        return {"enabled": True, "status": "saved", "response": {}}

    return {"enabled": True, "status": "saved", "response": json.loads(response_body)}


def persist_audit_record(record: AuditRecord, filepath: str | None = None) -> Dict[str, Any]:
    """Persist to JSONL and any enabled hosted audit sinks."""

    jsonl_path = filepath or os.getenv("CASA_AUDIT_LOG_PATH", DEFAULT_AUDIT_LOG_PATH)
    save_audit_record(record, filepath=jsonl_path)
    airtable_result = save_audit_record_to_airtable(record)

    return {
        "jsonl": {"enabled": True, "status": "saved", "path": jsonl_path},
        "airtable": airtable_result,
    }
