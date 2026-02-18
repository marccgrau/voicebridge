# Persona Brief — Alex Meyer (Bank)

## 1) Actor Perspective (what the actor needs to know)

### Core identity

- **Name:** Alex Meyer
- **Gender:** Male
- **DOB:** 03 March 1989
- **Address:** 45 Lindenstrasse, 8001 Zürich, CH
- **Language in call:** German-speaking customer context (DE), but you can use concise neutral wording in rehearsal.

### Situation at call start

See the selected scenario briefing for your situation.

### Main objectives in the call

Follow the objectives described in the selected scenario. Your persona-level priorities are:
1. Get **fast, concrete action** — not promises.
2. Demand **specific timelines** for every next step.
3. Require a **structured recap** before ending the call.

### Behavioral profile

- Start **anxious and urgent**.
- Keep focus on immediate protective action and concrete timelines.
- Increase pressure when answers are vague; ease when actions and milestones are clear.
- Match the civility style (civil or uncivil) to the assigned scenario condition.

### Escalation / de-escalation cues

See the selected scenario briefing for situation-specific escalation and de-escalation cues. Your persona-level defaults:
- **Escalate slightly** if the agent does not take immediate action or gives vague answers.
- **De-escalate** when the agent summarizes actions and timeline clearly.

### Must-ask checkpoints

See the selected scenario briefing for situation-specific must-ask checkpoints.

---

## 2) Company Perspective (what to show agent in UI)

### Pre-call customer snapshot

- **Customer ID:** BK-CH-784291
- **Full name:** Alex Meyer
- **Gender:** male
- **DOB:** 1989-03-03
- **Language:** DE
- **Email:** alex.meyer@examplemail.ch
- **Phone:** +41 79 555 41 22
- **Address:** 45 Lindenstrasse, 8001 Zürich, CH
- **Customer since:** 2018-09-01
- **Internal classification:** Affluent
- **Products:** Privatkonto Plus, Debitkarte Visa, Sparkonto, eBanking + Mobile Banking, Business Lite Account
- **Previous interactions:** See interaction list below (date, topic, channel, outcome).
- **Quick internal note:** Time-pressured; expects immediate protective action and clear timelines.

### Previous interactions (internal, with channel)

- **2026-01-28** — _Card limit clarification_ — **Channel:** Mobile App Chat — **Outcome:** Resolved
- **2025-11-09** — _Address update_ — **Channel:** Branch Visit — **Outcome:** Resolved
- **2025-08-14** — _Fee reversal request_ — **Channel:** Phone — **Outcome:** Denied — Annual maintenance fee reversal denied; fee is contractual under Privatkonto Plus terms. Reconsideration possible with documented financial hardship or loyalty context.
- **2025-05-03** — _Travel notice for card usage abroad_ — **Channel:** Phone — **Outcome:** Resolved

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
