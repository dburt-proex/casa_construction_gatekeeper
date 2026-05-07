"""CLI entry point for CASA Construction Gatekeeper."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

from casa_gatekeeper.audit import save_audit_record, to_serializable_dict
from casa_gatekeeper.router import route_document


def _enum_value(value: object) -> object:
    return getattr(value, "value", value)


def _result_to_dict(result: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "document": to_serializable_dict(result["audit_record"])["document"],
        "decision": to_serializable_dict(result["audit_record"])["decision"],
        "audit_record": to_serializable_dict(result["audit_record"]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route a construction document through CASA governance.")
    parser.add_argument("filepath", help="Path to a text document to classify and route.")
    parser.add_argument("--source", default="manual", help="Source label for the audit record.")
    parser.add_argument("--audit-log", default="audit_log.jsonl", help="JSONL audit log filepath.")
    parser.add_argument("--no-save", action="store_true", help="Do not append an audit record.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    return parser


def main() -> None:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args()

    filepath = Path(args.filepath)
    text = filepath.read_text(encoding="utf-8")
    result = route_document(text, source=args.source)

    if not args.no_save:
        save_audit_record(result["audit_record"], filepath=args.audit_log)

    if args.json:
        print(json.dumps(_result_to_dict(result), indent=2, sort_keys=True))
        return

    document = result["document"]
    decision = result["decision"]
    print(f"Document Type: {_enum_value(document.document_type)}")
    print(f"Project ID: {document.project_id or 'MISSING'}")
    print(f"Priority: {decision.priority_level}")
    print(f"Decision: {_enum_value(decision.decision)}")
    print(f"Reason: {decision.reason}")
    print(f"Required Action: {decision.required_action}")


if __name__ == "__main__":
    main()
