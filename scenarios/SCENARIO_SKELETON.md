# Step Architecture for High-Complexity Customer Service Scenarios

_Last updated: 2026-02-17_

This document defines a standardized step architecture for two experiment scenarios across banking and health insurance contexts.
Goal: keep **interaction structure constant** while allowing domain-specific nouns/policies.

---

## Global Design Rules (applies to all scripts)

1. **Identity & security first** before account/policy actions.
2. **One primary objective per step** (easy actor pacing and coding).
3. **Progressive disclosure**: customer reveals more details when prompted.
4. **At least one urgency/exception branch** to test boundary handling.
5. **Mandatory recap before close**: action, timeline, communication channel.
6. **Tone control**: actor starts concerned/frustrated, de-escalates when agent is clear.
7. **Policy-line moments**: include at least one “cannot do X instantly” step.
8. **Comparable step count** across bank and insurance variants.

---

## Scenario 1 Architecture: Unauthorized Transaction / Suspicious Claim

### Purpose

Test policy adherence under stress, empathy, and step sequencing in fraud-like conditions.

### Canonical Step Flow

1. **Opening alert**
   - Customer reports suspicious activity and urgency.
2. **Identity verification**
   - Name, DOB, registered address (or equivalent required factors).
3. **Immediate security action**
   - Block/freeze card or lock claim pathway/policy usage flag.
4. **Recent activity capture**
   - Last known legitimate usage + suspicious item details.
5. **Dispute/Fraud case initiation**
   - Open formal dispute/investigation and provide reference expectation.
6. **Downstream containment action**
   - Bank: replacement card process.
   - Insurance: temporary protection note / fraud watch on claim flow.
7. **Preference capture**
   - Delivery (bank) or communication method (insurance).
8. **Boundary challenge**
   - Customer requests instant resolution or guaranteed timing.
9. **Policy-consistent response**
   - Agent sets realistic constraints and offers best available alternative.
10. **Notifications and tracking**
    - SMS/email/callback setup for updates.
11. **Final clarification**
    - PIN/credential or “what if another suspicious event appears?” question.
12. **Structured close**
    - Recap actions, expected timeline, next customer obligations.

### Fidelity Checks (for coders)

- Was identity completed before sensitive action?
- Was security action executed before explanation-heavy discussion?
- Was a formal case/dispute opened?
- Were timeline and uncertainty communicated clearly?
- Was a communication channel explicitly confirmed?

---

## Scenario 2 Architecture: Denied Service/Claim with Appeal Request

### Purpose

Test explanation quality, fairness perception, documentation guidance, and escalation discipline.

### Canonical Step Flow

1. **Opening complaint**
   - Customer reports denial and perceived unfairness.
2. **Identity verification**
   - Standard verification before case discussion.
3. **Decision explanation**
   - Agent explains denial basis/reason code in plain language.
4. **Gap diagnosis**
   - Identify missing criteria, documents, thresholds, or evidence.
5. **Reconsideration path offer**
   - Explain appeal/review option and requirements.
6. **Evidence collection guidance**
   - Specify exactly what documents are needed and format constraints.
7. **Submission method selection**
   - Portal/email/branch/post/fax (as applicable).
8. **Interim support request (branch)**
   - Customer asks what can be done while waiting.
9. **Escalation or interim option**
   - Agent offers temporary workaround where policy allows.
10. **Timeline + SLA communication**
    - Expected review duration + milestone updates.
11. **Communication preference**
    - Confirm preferred notification channel.
12. **Structured close**
    - Recap submitted/required items, deadline, and next contact trigger.

### Fidelity Checks (for coders)

- Did the agent provide a reason in understandable terms?
- Were required documents listed concretely?
- Was the appeal route initiated or clearly instructed?
- Were interim options addressed without overpromising?
- Was a realistic timeline and channel confirmed?

---

## Actor Delivery Guidance

- Keep utterances **short and natural** (1–2 sentences).
- Ask one follow-up at a time; avoid combining multiple requests unless scripted.
- If agent is vague, use scripted probe (“Can you tell me exactly what happens next?”).
- Maintain consistent intensity curve:
  - Start: concern/frustration
  - Middle: urgency/challenge
  - End: cooperative if handled well

---

## Suggested Metadata Fields for JSON Scripts

- `scenario_id`
- `scenario_family`
- `title`
- `domain`
- `behavioral_condition.civility_condition`
- `background`
- `customer_goal`
- `guidelines`
- `conversation[]` with:
  - `id`
  - `customer_msg`
  - `actor_intent`
  - `tone`
  - `advice_instructional`
  - `next_id`
