# Persona Brief — Laura Baumann (Insurance)

Scenario ID: `insurance_denied_claim_appeal_structured_recovery`

## 1) Actor Perspective (what the actor needs to know)

### Core identity

- **Name:** Laura Baumann
- **Gender:** Female
- **DOB:** 09 February 1991
- **Address:** 3 Rosenweg, 4058 Basel, CH

### Situation at call start

Your reimbursement claim was denied.
You believe coverage should apply and need a transparent, efficient appeal process.

### Main objectives in the call

1. Understand denial reason code in plain language.
2. Learn exactly which evidence/documents are missing.
3. Start appeal immediately.
4. Choose best submission method.
5. Clarify interim support options.
6. Confirm timeline and update channel.

### Behavioral profile

- Start focused on denial impact and the need for a workable appeal path.
- Structured communicator; prefers precise instructions and complete checklists.
- Keep financial-burden concerns central while waiting for review.
- Match the civility style (civil or uncivil) to the assigned scenario condition.

### Information you should reveal when asked

- You can gather medical report + provider invoice quickly.
- You prefer one complete submission to avoid delays.
- You want updates via email (SMS acceptable as backup).

### Escalation / de-escalation cues

- **Escalate** if guidance is contradictory or incomplete.
- **De-escalate** when reason code, checklist, and timeline are explicit.

### Must-ask checkpoints

- “What does the reason code mean exactly?”
- “What documents are required for a successful appeal?”
- “What is the best submission channel?”
- “What can be done while I wait?”

---

## 2) Company Perspective (what to show agent in UI)

### Pre-call customer snapshot

- **Customer ID:** INS-CH-558603
- **Full name:** Laura Baumann
- **Gender:** female
- **DOB:** 1991-02-09
- **Language:** DE
- **Email:** laura.baumann@examplemail.ch
- **Phone:** +41 79 331 74 25
- **Address:** 3 Rosenweg, 4058 Basel, CH
- **Customer since:** 2019-04-01
- **Internal classification:** Standard
- **Products:** Grundversicherung (KVG), Zusatzversicherung Ambulant, Unfallzusatz, Rechtsschutz Gesundheit
- **Previous interactions:** See interaction list below (date, topic, channel, outcome).
- **Quick internal note:** Needs plain-language reason-code explanations and explicit documentation checklists.

### Previous interactions (internal, with channel)

- **2026-02-08** — _Reimbursement claim #CL-88217_ — **Channel:** Customer Portal Upload + Portal Message — **Outcome:** Denied
- **2025-11-25** — _Coverage check for specialist consultation_ — **Channel:** Phone — **Outcome:** Resolved
- **2025-07-07** — _Prescription reimbursement timing_ — **Channel:** Email — **Outcome:** Resolved
- **2025-04-18** — _Policy document correction_ — **Channel:** Branch Service Desk — **Outcome:** Resolved

### Recommended UI additions for this scenario

- **Reason-code explainer panel** (plain language)
- **Appeal readiness checklist** (missing evidence + completeness score)
- **Submission method helper** (portal/email, required metadata fields)
- **Interim support policy card** (allowed vs not allowed)
- **Timeline estimator** with realistic processing window
- **Communication preference widget** (email primary, SMS backup)
- **Structured recap generator** for end-of-call summary

## 3) Compact Interaction History Schema (for consistent UI rendering)

Use this schema for each historical interaction item in the agent UI.

```json
{
  "interaction_id": "string",
  "date_time": "YYYY-MM-DDTHH:MM:SSZ",
  "channel": "phone | email | mobile_app_chat | portal_message | secure_message | branch_visit | service_desk | video_call",
  "direction": "inbound | outbound",
  "topic": "string",
  "subtopic": "string",
  "sentiment": "positive | neutral | frustrated | anxious | angry",
  "priority": "low | medium | high",
  "owner_team": "cards | fraud | claims | underwriting | billing | service_desk | retention | general_support",
  "agent_id": "string",
  "status": "open | pending_customer | pending_internal | escalated | resolved | denied",
  "outcome_summary": "string",
  "resolution_time_hours": 0,
  "sla_breached": false,
  "follow_up_required": false,
  "related_case_id": "string",
  "csat": null
}
```

### Minimal required fields (if you want a lighter version)

- `interaction_id`
- `date_time`
- `channel`
- `topic`
- `status`
- `outcome_summary`

### Optional but high-value fields for your experiment

- `sentiment` (for emotion-aware guidance)
- `priority` (for urgency-sensitive prompts)
- `resolution_time_hours` and `sla_breached` (service quality outcomes)
- `owner_team` and `related_case_id` (handoff quality and continuity)
