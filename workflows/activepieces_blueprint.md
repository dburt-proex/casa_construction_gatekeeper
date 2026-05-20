# Activepieces Free-Tier Blueprint

This blueprint uses Activepieces as the no-code automation layer and Render Free as the hosted CASA API.

## Required Pieces

- Trigger: `Webhook`
- Action: `HTTP`
- Branching: `Condition`
- Notification: Slack, Gmail, Microsoft Teams, or email
- Audit ledger: Airtable table written by the hosted CASA API

## Render Environment

Set these variables on the Render service before the Benike-style demo:

```text
AIRTABLE_AUDIT_ENABLED=true
AIRTABLE_API_KEY=pat_your_airtable_token
AIRTABLE_BASE_ID=app_your_base_id
AIRTABLE_AUDIT_TABLE_NAME=CASA Audit
CASA_AUDIT_LOG_PATH=audit_log.jsonl
```

The Airtable table should include the fields listed in the README's Airtable Audit Sink section. Each successful `/route-document` call writes one row, so Activepieces does not need a second logging step.

## CASA API Endpoint

After deploying on Render, use:

```text
POST https://YOUR-RENDER-SERVICE.onrender.com/route-document
```

Headers:

```text
Content-Type: application/json
```

Body:

```json
{
  "text": "{{document_text}}",
  "source": "activepieces"
}
```

## Flow

```text
Webhook: Construction document intake
  -> HTTP POST: CASA /route-document
       -> CASA appends JSONL and writes one Airtable audit row
  -> Condition: decision == "ALLOW"
       -> Standard routing placeholder
  -> Condition: decision == "REVIEW"
       -> Notify PM / document control
  -> Condition: decision == "HALT"
       -> Urgent safety or leadership alert
```

## Example Webhook Payload

```json
{
  "document_text": "RFI for Project #8821, HVAC clash, spec section 23 00 00, submitted by Northline Mechanical.",
  "source": "manual-test"
}
```

## Expected CASA Response

```json
{
  "decision": "ALLOW",
  "document_type": "RFI",
  "project_id": "8821",
  "priority_level": 2,
  "reason": "Required fields are present, confidence is acceptable, and no blocking risk was detected.",
  "required_action": "Continue standard routing workflow.",
  "audit_record": {
    "source": "activepieces",
    "document": {
      "document_type": "RFI",
      "project_id": "8821"
    },
    "decision": {
      "decision": "ALLOW",
      "priority_level": 2
    }
  }
}
```

## Routing Notes

- `ALLOW`: continue to Procore, document control, or standard project routing.
- `REVIEW`: send to project manager, project engineer, or document control queue.
- `HALT`: send immediate safety/leadership alert and stop automated routing.
- Airtable persistence happens before the HTTP response succeeds. If the HTTP step receives `502`, treat it as an audit persistence failure and retry or alert the operator.

## Free-Tier Constraints

- Render Free sleeps after inactivity, so the first request after idle may be slow.
- Keep document text reasonably small for webhook payloads.
- Do not rely on local `audit_log.jsonl` for permanent hosted storage because free hosting filesystems are ephemeral.
- Use Airtable as the off-host audit ledger for the hosted pilot; JSONL remains useful for local inspection and Render logs/debugging.
