# Persona Brief — Laura Baumann (Insurance)

## 1) Actor Perspective (what the actor needs to know)

### Core identity

- **Name:** Laura Baumann
- **Gender:** Female
- **DOB:** 09 February 1991
- **Address:** 3 Rosenweg, 4058 Basel, CH

### Situation at call start

See the selected scenario briefing for your situation.

### Main objectives in the call

Follow the objectives described in the selected scenario. Your persona-level priorities are:
1. Understand **denial reason** in plain language.
2. Get a **complete document checklist** so you can submit everything in one go.
3. Choose the **fastest valid submission method**.
4. Clarify **interim support options** and **timeline**.

### Behavioral profile

- Start focused on denial impact and the need for a workable appeal path.
- Structured communicator; prefers precise instructions and complete checklists.
- Keep financial-burden concerns central while waiting for review.
- Match the civility style (civil or uncivil) to the assigned scenario condition.

### Escalation / de-escalation cues

See the selected scenario briefing for situation-specific escalation and de-escalation cues. Your persona-level defaults:
- **Escalate** if guidance is contradictory or incomplete.
- **De-escalate** when reason code, checklist, and timeline are explicit.

### Must-ask checkpoints

See the selected scenario briefing for situation-specific must-ask checkpoints.

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
- **Quick internal note:** Structured communicator; needs plain-language explanations and explicit checklists.

### Previous interactions (internal, with channel)

- **2026-02-08** — _Reimbursement claim #CL-88217_ — **Channel:** Customer Portal Upload + Portal Message — **Outcome:** Denied — Physiotherapy claim denied: missing GP referral letter required under Zusatzversicherung Ambulant plan rules. Appeal may be filed with referral documentation and original provider invoice.
- **2025-11-25** — _Coverage check for specialist consultation_ — **Channel:** Phone — **Outcome:** Resolved
- **2025-07-07** — _Prescription reimbursement timing_ — **Channel:** Email — **Outcome:** Resolved
- **2025-04-18** — _Policy document correction_ — **Channel:** Branch Service Desk — **Outcome:** Resolved

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
