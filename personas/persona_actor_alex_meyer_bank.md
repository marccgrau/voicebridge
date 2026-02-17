# Persona Brief — Alex Meyer (Bank)
Scenario ID: `bank_unauthorized_transaction_high_urgency`

## 1) Actor Perspective (what the actor needs to know)

### Core identity
- **Name:** Alex Meyer
- **Gender:** Male
- **DOB:** 03 March 1989
- **Address:** 45 Lindenstrasse, 8001 Zürich, CH
- **Language in call:** German-speaking customer context (DE), but you can use concise neutral wording in rehearsal.

### Situation at call start
You noticed a **card transaction you did not authorize** this morning (CHF 286).
You need immediate containment because you still have upcoming payments this week.

### Main objectives in the call
1. Get the card/account risk **secured immediately**.
2. Open a **formal dispute/fraud case**.
3. Arrange a **replacement card**.
4. Clarify **delivery timeline**.
5. Set **SMS updates**.
6. Clarify **PIN continuity**.

### Behavioral profile
- Start **anxious and urgent**, but stay polite.
- You are cooperative if the agent is structured and concrete.
- You become pressing if answers are vague.

### Information you should reveal when asked
- Last legitimate payment: yesterday at a supermarket.
- Suspicious transaction: this morning, CHF 286.
- Delivery preference: home address.
- Update preference: SMS.
- Final PIN preference: keep same PIN unless advised otherwise.

### Escalation / de-escalation cues
- **Escalate slightly** if the agent does not take immediate protective action.
- **De-escalate** when the agent summarizes actions and timeline clearly.

### Must-ask checkpoints (if agent does not cover them)
- “How long does replacement delivery take?”
- “Can you guarantee faster delivery?”
- “How will I be updated?”
- “Will my PIN stay the same?”

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
- **Quick internal note:** Friendly but time-pressured. Expects immediate protective action and clear timelines.

### Previous interactions (internal, with channel)
- **2026-01-28** — *Card limit clarification* — **Channel:** Mobile App Chat — **Outcome:** Resolved
- **2025-11-09** — *Address update* — **Channel:** Branch Visit — **Outcome:** Resolved
- **2025-08-14** — *Travel notice for card usage abroad* — **Channel:** Phone — **Outcome:** Resolved
- **2025-05-03** — *Duplicate card charge inquiry* — **Channel:** Secure Message (eBanking) — **Outcome:** Resolved (no fraud)

### Recommended UI additions for this scenario
- **Authentication status:** `not_started` → `verified`
- **Fraud workflow panel:** security action, dispute opened, case reference
- **Replacement card panel:** delivery option + ETA (3–5 business days)
- **Policy guardrail:** no guaranteed instant physical delivery
- **Communication preference control:** SMS/Email toggle with confirmation
- **Recap checklist:** block/freeze completed, dispute opened, replacement ordered, notifications set, PIN explained

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
