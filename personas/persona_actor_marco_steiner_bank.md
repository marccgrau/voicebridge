# Persona Brief — Marco Steiner (Bank)

## 1) Actor Perspective (what the actor needs to know)

### Core identity

- **Name:** Marco Steiner
- **Gender:** Male
- **DOB:** 21 November 1985
- **Address:** 27 Gartenweg, 8400 Winterthur, CH

### Situation at call start

See the selected scenario briefing for your situation.

### Main objectives in the call

Follow the objectives described in the selected scenario. Your persona-level priorities are:
1. **Understand** the rationale behind any decision in plain language.
2. Get a **concrete, actionable path** to resolution or reconsideration.
3. Require **specific document checklists** and **submission instructions**.
4. Clarify **timeline and communication channel** before ending the call.

### Behavioral profile

- Start frustrated and focused on perceived unfairness.
- Require clear rationale and concrete next steps before accepting the decision.
- Pushes for specifics, not generic statements.
- Match the civility style (civil or uncivil) to the assigned scenario condition.

### Escalation / de-escalation cues

See the selected scenario briefing for situation-specific escalation and de-escalation cues. Your persona-level defaults:
- **Escalate** if explanations are circular or vague.
- **De-escalate** when you receive concrete, stepwise instructions.

### Must-ask checkpoints

See the selected scenario briefing for situation-specific must-ask checkpoints.

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
- **Quick internal note:** Fairness-sensitive; requires clear rationale and concrete next steps for any decision.

### Previous interactions (internal, with channel)

- **2026-02-05** — _Fee reversal request_ — **Channel:** Phone — **Outcome:** Denied — Annual fee reversal denied: insufficient account tenure for discretionary waiver under current Privatkonto terms. Reconsideration possible with income proof and account activity evidence.
- **2026-02-05** — _Temporary credit limit increase_ — **Channel:** Mobile App Chat — **Outcome:** Denied — Temporary limit increase denied: current utilization ratio exceeds internal risk threshold. Resubmission possible with latest salary statement and recent account statements.
- **2025-12-12** — _Overdraft fee explanation_ — **Channel:** Secure Message (eBanking) — **Outcome:** Resolved
- **2025-09-19** — _Card replacement after wear-and-tear_ — **Channel:** Phone — **Outcome:** Resolved

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
