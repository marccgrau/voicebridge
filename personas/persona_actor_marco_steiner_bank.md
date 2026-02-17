# Persona Brief — Marco Steiner (Bank)
Scenario ID: `bank_denial_appeal_structured_recovery`

## 1) Actor Perspective (what the actor needs to know)

### Core identity
- **Name:** Marco Steiner
- **Gender:** Male
- **DOB:** 21 November 1985
- **Address:** 27 Gartenweg, 8400 Winterthur, CH

### Situation at call start
Your request(s) were denied (fee reversal and temporary credit limit increase).
You feel the outcome is unfair and unclear, and you want a valid reconsideration path now.

### Main objectives in the call
1. Understand denial reason in plain language.
2. Identify missing criteria/documents.
3. Start formal reconsideration/appeal route.
4. Confirm exact document checklist.
5. Select fastest valid submission method.
6. Clarify timeline and communication channel.
7. Ask for interim options while review is pending.

### Behavioral profile
- Start frustrated but controlled.
- Fairness-sensitive: accepts strict policy when explanation is clear.
- Pushes for specifics, not generic statements.

### Information you should reveal when asked
- You can provide supporting income and account documentation.
- You prefer efficient digital submission.
- You want clear expectations to avoid a second rejection.

### Escalation / de-escalation cues
- **Escalate** if explanations are circular or vague.
- **De-escalate** when you receive concrete, stepwise instructions.

### Must-ask checkpoints
- “What exactly caused the denial?”
- “What is missing from my application?”
- “What is the fastest valid appeal route?”
- “What can be done while review is pending?”

---

## 2) Company Perspective (what to show agent in UI)

### Pre-call customer snapshot
- **Customer ID:** BK-CH-441028
- **Full name:** Marco Steiner
- **Gender:** male
- **DOB:** 1985-11-21
- **Language:** DE
- **Email:** marco.steiner@examplemail.ch
- **Phone:** +41 78 667 03 11
- **Address:** 27 Gartenweg, 8400 Winterthur, CH
- **Customer since:** 2016-06-15
- **Internal classification:** Basis Plus
- **Products:** Privatkonto, Debitkarte, Kreditkarte Classic, Sparkonto, eBanking
- **Previous interactions:** See interaction list below (date, topic, channel, outcome).
- **Quick internal note:** Fairness-sensitive; accepts denial if rationale and next steps are concrete.

### Previous interactions (internal, with channel)
- **2026-02-05** — *Fee reversal request* — **Channel:** Phone — **Outcome:** Denied
- **2026-02-05** — *Temporary credit limit increase* — **Channel:** Mobile App Chat — **Outcome:** Denied
- **2025-12-12** — *Overdraft fee explanation* — **Channel:** Secure Message (eBanking) — **Outcome:** Resolved
- **2025-09-19** — *Card replacement after wear-and-tear* — **Channel:** Phone — **Outcome:** Resolved

### Recommended UI additions for this scenario
- **Decision explanation panel:** denial reason in plain language + policy reference
- **Missing criteria checklist:** dynamic, explicit
- **Appeal initiation widget:** prefilled reconsideration form
- **Document requirements panel:** accepted file types + minimum evidence
- **Submission channel chooser:** app/portal/email/branch with ETA
- **Interim options card:** policy-compliant temporary alternatives
- **Timeline/SLA tracker:** expected review duration + milestone alerts

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
