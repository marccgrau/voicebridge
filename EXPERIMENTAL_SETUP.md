# Experimental Flow Specification

_Last updated: 2026-02-17_

## Purpose and Intent of the Experiment

This experiment evaluates whether a **novel agent-assistance tool** improves customer-service performance during live, role-played calls.

The tool supports agents in real time with:

1. **Actionable suggestions** (what to do/say next),
2. **Process illustration** (where the agent is in the workflow),
3. **Live transcript** (what the customer is saying).

The core research intent is to test if guided agents handle complex calls better, especially under different customer behavior conditions (civil vs. uncivil), while maintaining policy adherence and call quality.

---

## Roles in the Experiment

### 1) Actor (Customer role)

- Simulates a customer using a predefined persona + scenario.
- Initiates the call from the customer frontend.

### 2) Agent (Customer-service role)

- Handles incoming calls in the agent workspace.
- Uses provided customer information and live guidance to resolve the case.

### 3) Experimental System

- Routes calls from customer frontend to agent workspace.
- Loads persona and scenario catalogs from Supabase (seeded from repository JSON files).
- Provides real-time support features and post-call summary.

---

## High-Level User Journey

1. Actor opens customer frontend.
2. Actor selects **persona** and **scenario** from dropdowns.
3. Actor is routed to a prep page with persona/scenario briefing.
4. Actor starts the call.
5. Call is routed to agent workspace.
6. Agent sees pre-call customer information, accepts call, and starts handling.
7. During the call, agent receives suggestions, process view, and transcript.
8. When resolved, call ends and agent receives call summary.

---

## How Personas and Scenarios Are Defined and Loaded

### Definition (repo files)

1. **Personas** are defined in `personas/customer_profile_*.json`.
   - Core sections: `customer_profile`, `case_context`, `interaction_history`.
2. **Scenarios** are defined in `scenarios/scenario_*.json`.
   - Core sections: `scenario_id`, `title`, `background`, `customer_goal`, `guidelines`, `conversation`, `behavioral_condition`.

### Load path (seed -> runtime)

1. Seeder script `scripts/seed-experimental-data.mjs` reads both directories.
2. Personas are loaded into `customers` + `customer_interactions`.
3. Scenarios are loaded into `scenarios` (`scenario_family` derived from `scenario_id`; `civility_condition` preserved per variant).
4. Customer app loads personas via `useCustomers()` and scenarios via `useScenarios()`.
5. Customer app renders scenario placeholders from selected persona values via `scenario-render.ts`.
6. On call start, `/api/sessions/create` validates `customer_id` + `scenario_id` and writes selected scenario metadata onto `sessions` and `sessions.state`.

---

## Detailed Step-by-Step Flow

## Phase A: Actor Preparation

### Step A1 — Open Customer Frontend

- Actor lands on a start page for call simulation.

### Step A2 — Select Persona

- Actor chooses one persona (e.g., Alex Meyer, Nina Keller, Marco Steiner, Laura Baumann).
- Persona determines identity, communication style, and behavior profile.
- Source at runtime: `customers` table (seeded from `personas/customer_profile_*.json`).

### Step A3 — Select Scenario

- Actor chooses one scenario variant from dropdown:
  - Unauthorized transaction / suspicious claim (civil or uncivil),
  - Denied service/claim with appeal request (civil or uncivil).
- Scenario determines required steps and call objectives.
- Source at runtime: active rows in `scenarios` (seeded from `scenarios/scenario_*.json`).

### Step A4 — Review Briefing Page

- System routes actor to a briefing page.
- Actor sees:
  - Persona overview,
  - Scenario background,
  - Customer goals,
  - Behavior instruction from the selected scenario variant,
  - Must-ask checkpoints.

### Step A5 — Ready State and Call Start

- Actor confirms readiness and clicks **Start Call**.

---

## Phase B: Call Routing and Agent Onboarding

### Step B1 — Route Call to Agent Workspace

- System creates a call session ID and validates selected persona/scenario IDs.
- System persists scenario metadata (`scenario_id`, `scenario_family`, `civility_condition`) in session records.
- Incoming call appears in the agent workspace.

### Step B2 — Pre-Call Customer Context for Agent

Before accepting, agent sees a concise customer snapshot:

- Name, gender, language (DE),
- Contact details,
- Customer since date,
- Internal classification,
- Products,
- Previous interactions (with channel + outcome),
- Quick internal note.

### Step B3 — Agent Accepts Call

- Agent clicks **Accept**.
- Call becomes active and transcript starts.

---

## Phase C: Active Call Handling

### Step C1 — Real-Time Transcript

- System streams customer utterances to transcript panel.

### Step C2 — Guidance Suggestions

- Agent receives context-aware suggestions for next action and phrasing.

### Step C3 — Process Illustration

- Agent sees visual workflow state (e.g., verify identity → secure account → dispute → recap).
- Current step and pending steps are explicit.

### Step C4 — Policy and Process Compliance

- Agent uses guidance to:
  - Follow mandatory sequence,
  - Apply policy constraints,
  - Communicate timelines and options,
  - Handle emotional tone appropriately.

### Step C5 — Resolution Confirmation

- Agent closes call only after required scenario steps are completed.

---

## Phase D: Post-Call Closure

### Step D1 — Call Completion

- Call is ended after resolution and recap.

### Step D2 — Agent Summary View

- Agent receives structured summary:
  - Main issue,
  - Actions performed,
  - Decisions/policy points communicated,
  - Open follow-ups (if any),
  - Communication commitments.

### Step D3 — Data Logging for Experiment

System stores:

- Scenario/persona IDs,
- Civility condition,
- Transcript,
- Guidance timeline,
- Step completion markers,
- Call duration and interaction events.

---

## Experimental Logic and Control

To preserve internal validity:

1. Keep scenario structure constant across conditions.
2. Vary only intended manipulations (e.g., civil vs. uncivil behavior, tool condition if applicable).
3. Use standardized persona and scenario briefings.
4. Track objective process adherence (step completion/order).
5. Separate actor instructions from agent UI information.

---

## Minimum Success Criteria per Call

A call is considered successfully completed when:

1. Mandatory verification/security steps are completed (where applicable),
2. Core process actions are executed in sequence,
3. Customer receives clear next steps and timeline,
4. Agent provides a structured recap before closing.

---

## Why This Flow Exists

This flow is designed to create a realistic but controlled service interaction that allows robust evaluation of whether the assistance tool improves:

- process quality,
- compliance,
- communication clarity,
- and handling of emotionally difficult customer behavior.

---

## Reference Locations

For implementation and operational use:

- Scenario definitions: `/scenarios/scenario_*.json`
- Persona definitions: `/personas/customer_profile_*.json`
- Seed loader: `scripts/seed-experimental-data.mjs`
- Customer runtime loaders: `apps/customer/src/lib/use-customers.ts`, `apps/customer/src/lib/use-scenarios.ts`
- Placeholder rendering: `apps/customer/src/lib/scenario-render.ts`
- Session creation + metadata persistence: `apps/customer/app/api/sessions/create/route.ts`
