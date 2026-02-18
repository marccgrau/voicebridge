# Persona Brief — Nina Keller (Insurance)

## 1) Actor Perspective (what the actor needs to know)

### Core identity

- **Name:** Nina Keller
- **Gender:** Female
- **DOB:** 14 July 1992
- **Address:** 8 Seefeldstrasse, 8008 Zürich, CH

### Situation at call start

See the selected scenario briefing for your situation.

### Main objectives in the call

Follow the objectives described in the selected scenario. Your persona-level priorities are:
1. Ensure **immediate protective action** is taken.
2. Demand **explicit process milestones** and written confirmation.
3. Get **contingency instructions** for new incidents.
4. Require a **structured recap** before ending the call.

### Behavioral profile

- Start concerned and alert.
- Communicate with clear facts and ask precise follow-up questions.
- Escalate intensity when ownership is unclear; de-escalate when safeguards and milestones are concrete.
- Match the civility style (civil or uncivil) to the assigned scenario condition.

### Escalation / de-escalation cues

See the selected scenario briefing for situation-specific escalation and de-escalation cues. Your persona-level defaults:
- **Escalate** if there is no ownership or no concrete next steps.
- **De-escalate** when immediate safeguards and milestones are explained.

### Must-ask checkpoints

See the selected scenario briefing for situation-specific must-ask checkpoints.

---

## 2) Company Perspective (what to show agent in UI)

### Pre-call customer snapshot

- **Customer ID:** INS-CH-992174
- **Full name:** Nina Keller
- **Gender:** female
- **DOB:** 1992-07-14
- **Language:** DE
- **Email:** nina.keller@examplemail.ch
- **Phone:** +41 76 442 18 90
- **Address:** 8 Seefeldstrasse, 8008 Zürich, CH
- **Customer since:** 2020-01-01
- **Internal classification:** Standard Plus
- **Products:** Grundversicherung (KVG), Zusatzversicherung Ambulant, Spitalzusatz Halbprivat, Telemedizin-Modul
- **Previous interactions:** See interaction list below (date, topic, channel, outcome).
- **Quick internal note:** Detail-oriented; expects explicit process milestones and written confirmation.

### Previous interactions (internal, with channel)

- **2026-01-16** — _Benefit clarification (physiotherapy sessions)_ — **Channel:** Customer Portal Message — **Outcome:** Resolved
- **2025-10-02** — _Invoice coding question_ — **Channel:** Phone — **Outcome:** Resolved
- **2025-06-21** — _Specialist consultation reimbursement_ — **Channel:** Email — **Outcome:** Denied — GP referral letter not attached. Zusatzversicherung Ambulant requires referral for specialist visits. Appeal possible with referral letter and medical report.
- **2025-03-11** — _Hospital add-on coverage scope inquiry_ — **Channel:** Mobile App Chat — **Outcome:** Resolved

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
