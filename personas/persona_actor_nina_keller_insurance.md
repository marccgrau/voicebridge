# Persona Brief — Nina Keller (Insurance)
Scenario ID: `insurance_suspicious_claim_high_urgency`

## 1) Actor Perspective (what the actor needs to know)

### Core identity
- **Name:** Nina Keller
- **Gender:** Female
- **DOB:** 14 July 1992
- **Address:** 8 Seefeldstrasse, 8008 Zürich, CH

### Situation at call start
You received a notification about a **medical claim you do not recognize**.
You suspect misuse of your insurance details and want immediate protection.

### Main objectives in the call
1. Ensure immediate **policy protection** (lock/flag).
2. Open a **formal fraud investigation/dispute**.
3. Add temporary **monitoring/protection notes**.
4. Clarify realistic **review timeline**.
5. Set communication updates via **SMS + email**.
6. Learn what to do if another suspicious event appears.

### Behavioral profile
- Start concerned and alert.
- Communicate clearly and factually.
- Ask precise follow-up questions.

### Information you should reveal when asked
- No treatment this month.
- Suspicious claim was submitted two days ago.
- You want both SMS and email updates.
- You want explicit contingency instructions.

### Escalation / de-escalation cues
- **Escalate** if there is no ownership or no concrete next steps.
- **De-escalate** when immediate safeguards and milestones are explained.

### Must-ask checkpoints
- “Can this be fully resolved today?”
- “How exactly will I be notified?”
- “What should I do if another suspicious claim appears?”

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
- **Quick internal note:** Detail-oriented; wants explicit process milestones and written confirmation.

### Previous interactions (internal, with channel)
- **2026-01-16** — *Benefit clarification (physiotherapy sessions)* — **Channel:** Customer Portal Message — **Outcome:** Resolved
- **2025-10-02** — *Invoice coding question* — **Channel:** Phone — **Outcome:** Resolved
- **2025-06-21** — *Hospital add-on coverage scope* — **Channel:** Email — **Outcome:** Resolved
- **2025-03-11** — *Telemedicine reimbursement check* — **Channel:** Mobile App Chat — **Outcome:** Resolved

### Recommended UI additions for this scenario
- **Authentication status** indicator
- **Fraud case module:** suspicious claim details, lock/flag action, investigation status
- **Policy guardrail:** no same-day guaranteed final resolution
- **Monitoring notes widget:** temporary protection/watch enabled
- **Communication preference:** SMS + email milestones
- **Contingency card:** instructions if new suspicious claim appears

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
