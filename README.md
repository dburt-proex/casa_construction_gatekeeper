# CASA Construction Gatekeeper

CASA Construction Gatekeeper is a deterministic AI governance layer for construction operations. It classifies incoming construction documents, extracts structured fields, applies explicit policy rules, and decides whether each item can continue through standard routing or must be reviewed or halted.

CASA stands for Controlled Awareness Systems Architecture. This repository implements the Construction Gatekeeper as a pre-execution control layer before workflow automation.

## Problem

Construction teams lose time when RFIs, submittals, change orders, and urgent field issues are routed with missing context, low confidence, or unmanaged risk. A misrouted safety issue, incomplete RFI, or delayed inspection notice can create downstream cost, schedule, and liability exposure.

This prototype demonstrates a governed intake pattern:

1. Convert unstructured construction text into a validated schema.
2. Apply deterministic policy rules.
3. Produce an audit-grade routing decision.

No external API calls are required for the core prototype.

## Decision Model

Every intake item receives one routing decision:

| Decision | Meaning |
| --- | --- |
| `ALLOW` | The document is classified, required fields are present, confidence is acceptable, and no major risk is detected. |
| `REVIEW` | Required fields are missing, confidence is low, the document is unknown, or the item may affect schedule, cost, inspection, scope, or coordination. |
| `HALT` | Safety-critical or legally risky terms are detected. Automated routing stops. |

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Run CLI

```powershell
python -m casa_gatekeeper.main examples/sample_rfi.txt
```

JSON output for automation:

```powershell
python -m casa_gatekeeper.main examples/sample_urgent_issue.txt --json
```

By default, CLI runs append audit records to `audit_log.jsonl`. Use `--no-save` to skip writing audit output:

```powershell
python -m casa_gatekeeper.main examples/sample_submittal.txt --no-save
```

## Run API

Start the local HTTP API:

```powershell
uvicorn casa_gatekeeper.api:app --reload
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Route a document:

```powershell
curl -X POST http://127.0.0.1:8000/route-document `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"RFI for Project #8821, HVAC clash, spec section 23 00 00, submitted by Northline Mechanical.\",\"source\":\"local-api\"}"
```

The API returns a flattened response for no-code automation tools plus the full audit record.

## Free-Tier Deployment

This repo includes `render.yaml` for Render Free web service deployment.

1. Push this repo to GitHub.
2. Create a Render account.
3. Select **New > Blueprint** or **New > Web Service**.
4. Connect `dburt-proex/casa_construction_gatekeeper`.
5. Use the detected `render.yaml`, or configure manually:

```text
Build Command: pip install -r requirements.txt && pip install -e .
Start Command: uvicorn casa_gatekeeper.api:app --host 0.0.0.0 --port $PORT
```

After deployment, call:

```text
POST https://YOUR-RENDER-SERVICE.onrender.com/route-document
```

Render Free may sleep after inactivity, so first requests after idle can be slow. For a free pilot, that is acceptable. For production, use a paid always-on service.

## Activepieces Automation

Use `workflows/activepieces_blueprint.md` for the free-tier automation plan:

```text
Webhook intake
-> HTTP POST to CASA API
-> Condition on decision
-> ALLOW: standard routing
-> REVIEW: PM/document-control alert
-> HALT: urgent safety/leadership alert
-> Optional audit log to Google Sheets/Airtable/Notion
```

## Run Tests

```powershell
python -m pytest
```

## Repository Structure

```text
casa_construction_gatekeeper/
|-- README.md
|-- requirements.txt
|-- pyproject.toml
|-- render.yaml
|-- .env.example
|-- .gitignore
|-- src/
|   `-- casa_gatekeeper/
|       |-- __init__.py
|       |-- models.py
|       |-- policies.py
|       |-- classifier.py
|       |-- router.py
|       |-- audit.py
|       |-- api.py
|       `-- main.py
|-- tests/
|   |-- test_api.py
|   |-- test_models.py
|   |-- test_policies.py
|   `-- test_router.py
|-- examples/
|   |-- sample_rfi.txt
|   |-- sample_submittal.txt
|   `-- sample_urgent_issue.txt
`-- workflows/
    |-- activepieces_blueprint.md
    `-- n8n_blueprint.json
```

## Policy Rules

The current prototype applies deterministic rules:

- Missing `project_id` requires `REVIEW`.
- `UNKNOWN` document type requires `REVIEW`.
- Confidence below `0.70` requires `REVIEW`.
- Safety-critical language such as safety, injury, fire, collapse, hazardous, OSHA, structural failure, or immediate danger requires `HALT`.
- Schedule-impact language such as schedule impact, delay, failed inspection, site stoppage, blocked crew, urgent, or cannot proceed raises priority to `5` and requires `REVIEW`, unless safety-critical language requires `HALT`.
- Missing `spec_section` for `RFI` or `SUBMITTAL` requires `REVIEW`.
- Complete, sufficiently confident, non-risky documents are `ALLOW`.

## Example

```powershell
python -m casa_gatekeeper.main examples/sample_rfi.txt
```

Expected decision:

```text
Document Type: RFI
Project ID: 8821
Priority: 2
Decision: ALLOW
Reason: Required fields are present, confidence is acceptable, and no blocking risk was detected.
Required Action: Continue standard routing workflow.
```

## Future Roadmap

- Procore API integration for live project and document intake.
- Slack alerts for `REVIEW` and `HALT` decisions.
- Postgres audit ledger with immutable routing history.
- Pydantic AI / LLM extraction layer behind deterministic validation.
- Operator dashboard for exception handling and routing visibility.
- Managed pilot workflow for general contractors.
