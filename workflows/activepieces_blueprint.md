# Activepieces Free-Tier Blueprint

This blueprint uses Activepieces as the no-code automation layer and Render Free as the hosted CASA API.

## Required Pieces

- Trigger: `Webhook`
- Action: `HTTP`
- Branching: `Condition`
- Notification: Slack, Gmail, Microsoft Teams, or email
- Optional logging: Google Sheets, Airtable, Notion, or another table/database

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
  -> Condition: decision == "ALLOW"
       -> Standard routing placeholder
  -> Condition: decision == "REVIEW"
       -> Notify PM / document control
  -> Condition: decision == "HALT"
       -> Urgent safety or leadership alert
  -> Optional: log full audit_record to a sheet/database
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
  "required_action": "Continue standard routing workflow."
}
```

## Routing Notes

- `ALLOW`: continue to Procore, document control, or standard project routing.
- `REVIEW`: send to project manager, project engineer, or document control queue.
- `HALT`: send immediate safety/leadership alert and stop automated routing.

## Free-Tier Constraints

- Render Free sleeps after inactivity, so the first request after idle may be slow.
- Keep document text reasonably small for webhook payloads.
- Do not rely on local `audit_log.jsonl` for permanent hosted storage because free hosting filesystems are ephemeral.
- For a free audit ledger, write `audit_record` to Google Sheets, Airtable free tier, Notion, or a database-backed service.
