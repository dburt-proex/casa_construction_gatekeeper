# CASA Construction Gatekeeper

CASA Construction Gatekeeper is a deterministic AI governance layer for construction operations. It classifies incoming construction documents, extracts structured fields, applies explicit policy rules, and decides whether each item can continue through standard routing or must be reviewed or halted.

CASA stands for Controlled Awareness Systems Architecture. This repository implements the Construction Gatekeeper as a pre-execution control layer before workflow automation.

The service-product version is packaged as a managed construction-intake governance API: Render hosts the routing service, Airtable stores the off-host audit ledger, and Activepieces handles operator workflow branching.

## Problem

Construction teams lose time when RFIs, submittals, change orders, and urgent field issues are routed with missing context, low confidence, or unmanaged risk. A misrouted safety issue, incomplete RFI, or delayed inspection notice can create downstream cost, schedule, and liability exposure.

This prototype demonstrates a governed intake pattern:

1. Convert unstructured construction text into a validated schema.
2. Apply deterministic policy rules.
3. Produce an audit-grade routing decision.

No external API calls are required for the core prototype. Hosted deployments can optionally write audit records to Airtable.

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

Optional local auth check:

```powershell
$env:CASA_API_TOKEN="local-dev-token"
uvicorn casa_gatekeeper.api:app --reload
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

Route a document:

```powershell
curl -X POST http://127.0.0.1:8000/route-document `
  -H "X-CASA-API-Key: local-dev-token" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"RFI for Project #8821, HVAC clash, spec section 23 00 00, submitted by Mechanical Trade Partner.\",\"source\":\"local-api\"}"
```

The API returns a flattened response for no-code automation tools plus the full audit record.

Successful API requests also append the full audit record to the JSONL audit log. Set `CASA_AUDIT_LOG_PATH` to choose the local path; it defaults to `audit_log.jsonl`.

### Hosted API Security

Set `CASA_API_TOKEN` on hosted deployments to require this header on `POST /route-document`:

```text
X-CASA-API-Key: your-private-token
```

If `CASA_API_TOKEN` is unset or blank, `/route-document` remains open for local development. `GET /health` remains unauthenticated for uptime checks.

Payload bounds:

- `text`: 1 to 20,000 characters.
- `source`: 1 to 80 characters.

### Private Demo Dashboard

Set `CASA_DEMO_TOKEN` on hosted deployments to enable the customer-facing demo dashboard:

```text
CASA_DEMO_TOKEN=your-private-demo-token
```

Open the dashboard with:

```text
https://YOUR-RENDER-SERVICE.onrender.com/demo?token=your-private-demo-token
```

The dashboard stores demo access in a short-lived HTTP-only cookie and posts to `POST /demo/route`. The browser never receives `CASA_API_TOKEN`; that token remains reserved for direct API clients such as Activepieces or scripted smoke tests.

## Airtable Audit Sink

For a hosted pilot, Render's local filesystem is ephemeral. Keep JSONL enabled for local debugging, and turn on Airtable when every `ALLOW`, `REVIEW`, and `HALT` decision needs to persist off-host.

Set these environment variables on Render:

```text
CASA_API_TOKEN=your-private-token
CASA_DEMO_TOKEN=your-private-demo-token
AIRTABLE_AUDIT_ENABLED=true
AIRTABLE_API_KEY=pat_your_airtable_token
AIRTABLE_BASE_ID=app_your_base_id
AIRTABLE_AUDIT_TABLE_NAME=CASA Audit
CASA_AUDIT_LOG_PATH=audit_log.jsonl
```

`AIRTABLE_PERSONAL_ACCESS_TOKEN` is also accepted in place of `AIRTABLE_API_KEY`. If `AIRTABLE_AUDIT_ENABLED` is omitted, the sink turns on automatically when the Airtable token, base ID, and table name are present.

Create an Airtable table with these fields:

| Field | Suggested type |
| --- | --- |
| `Timestamp` | Date/time |
| `Decision` | Single select: `ALLOW`, `REVIEW`, `HALT` |
| `Source` | Single line text |
| `Document Type` | Single line text |
| `Project ID` | Single line text |
| `Spec Section` | Single line text |
| `Priority Level` | Number |
| `Assigned Subcontractor` | Single line text |
| `Confidence Score` | Number |
| `Human Review Required` | Checkbox |
| `Required Action` | Long text |
| `Reason` | Long text |
| `Audit Tags` | Long text |
| `Detected Risks` | Long text |
| `Missing Fields` | Long text |
| `Summary` | Long text |
| `System Version` | Single line text |
| `Audit Record JSON` | Long text |

When Airtable is enabled, `/route-document` returns a success response only after the JSONL append and Airtable write complete. If Airtable rejects the record or is unreachable, the API returns `502` so the automation does not treat an unpersisted decision as complete.

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

Required launch environment:

```text
CASA_API_TOKEN
CASA_DEMO_TOKEN
CASA_AUDIT_LOG_PATH
AIRTABLE_AUDIT_ENABLED
AIRTABLE_API_KEY
AIRTABLE_BASE_ID
AIRTABLE_AUDIT_TABLE_NAME
```

After deployment, call:

```text
POST https://YOUR-RENDER-SERVICE.onrender.com/route-document
```

Customer demo dashboard:

```text
GET https://YOUR-RENDER-SERVICE.onrender.com/demo?token=YOUR_DEMO_TOKEN
```

Render Free may sleep after inactivity, so first requests after idle can be slow. For a free pilot, that is acceptable. For production, use a paid always-on service.

## Activepieces Automation

Use `workflows/activepieces_blueprint.md` for the free-tier automation plan:

```text
Webhook intake
-> HTTP POST to CASA API
-> Include X-CASA-API-Key header
-> Condition on decision
-> ALLOW: standard routing
-> REVIEW: PM/document-control alert
-> HALT: urgent safety/leadership alert
-> Airtable audit row written by hosted CASA API
```

## Run Tests

```powershell
python -m pytest
```

## Operator Demo Script

Use these three requests to demonstrate the full decision range. Replace `YOUR_RENDER_SERVICE` and `YOUR_TOKEN` before running.

ALLOW:

```powershell
curl -X POST https://YOUR_RENDER_SERVICE.onrender.com/route-document `
  -H "X-CASA-API-Key: YOUR_TOKEN" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"RFI for Project #8821. Need clarification for spec section 23 00 00. Submitted by Mechanical Trade Partner.\",\"source\":\"launch-smoke-test\"}"
```

REVIEW:

```powershell
curl -X POST https://YOUR_RENDER_SERVICE.onrender.com/route-document `
  -H "X-CASA-API-Key: YOUR_TOKEN" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Field issue: blocked crew with schedule impact. Cannot proceed until layout conflict is resolved.\",\"source\":\"launch-smoke-test\"}"
```

HALT:

```powershell
curl -X POST https://YOUR_RENDER_SERVICE.onrender.com/route-document `
  -H "X-CASA-API-Key: YOUR_TOKEN" `
  -H "Content-Type: application/json" `
  -d "{\"text\":\"Project ID: 8821. Field issue: hazardous condition and immediate danger near active work zone.\",\"source\":\"launch-smoke-test\"}"
```

## Service Launch Checklist

- Confirm the repo has no external company-name references in current tracked files.
- Push the latest commit to `main`.
- Confirm Render redeploys the latest commit.
- Set `CASA_API_TOKEN`, `CASA_AUDIT_LOG_PATH`, and Airtable env vars on Render.
- Confirm `GET /health` returns `200`.
- Run the ALLOW, REVIEW, and HALT smoke tests with `X-CASA-API-Key`.
- Open `/demo?token=YOUR_DEMO_TOKEN` and run the same three cases through the dashboard.
- Verify Airtable receives all three audit rows.
- Configure Activepieces webhook -> CASA HTTP step -> decision branch -> routing/review/halt alerts.
- Capture the smoke-test outputs and Airtable rows for the sales/demo handoff.

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
|       |-- main.py
|       `-- static/
|           `-- demo.html
|-- tests/
|   |-- test_api.py
|   |-- test_audit_airtable.py
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

## Compliance Note

CASA Construction Gatekeeper is a neutral product asset. Do not use external company names, customer names, or implied affiliations in demos, source labels, page paths, sales copy, or workflow examples without written permission. CASA provides decision support, routing governance, and audit evidence; it does not replace legal, safety, engineering, or project-authority judgment.
