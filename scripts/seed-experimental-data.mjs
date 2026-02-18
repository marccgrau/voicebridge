import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { execFileSync } from "node:child_process";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const requireFromCustomer = createRequire(
  path.join(repoRoot, "apps", "customer", "package.json")
);
const { createClient } = requireFromCustomer("@supabase/supabase-js");

const PERSONA_DIR = path.join(repoRoot, "personas");
const SCENARIO_DIR = path.join(repoRoot, "scenarios");

function parseEnvFile(content) {
  const vars = {};
  for (const line of content.split(/\r?\n/u)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const idx = trimmed.indexOf("=");
    if (idx <= 0) {
      continue;
    }

    const key = trimmed.slice(0, idx).trim();
    const raw = trimmed.slice(idx + 1).trim();
    const value = raw.replace(/^['"]|['"]$/gu, "");
    vars[key] = value;
  }
  return vars;
}

function runSupabaseCommand(args) {
  return execFileSync("supabase", args, {
    cwd: repoRoot,
    encoding: "utf8",
    stdio: ["ignore", "pipe", "ignore"],
  });
}

function loadSupabaseStatusDefaults() {
  try {
    const output = runSupabaseCommand(["status", "-o", "env"]);

    return parseEnvFile(output);
  } catch {
    return {};
  }
}

function loadLinkedProjectRef() {
  try {
    return execFileSync("cat", ["supabase/.temp/project-ref"], {
      cwd: repoRoot,
      encoding: "utf8",
      stdio: ["ignore", "pipe", "ignore"],
    }).trim();
  } catch {
    return null;
  }
}

function loadLinkedServiceRoleKey(projectRef) {
  try {
    const response = runSupabaseCommand([
      "projects",
      "api-keys",
      "--project-ref",
      projectRef,
      "-o",
      "json",
    ]);

    const keys = JSON.parse(response);
    const serviceRole = keys.find(
      (item) => item.id === "service_role" || item.name === "service_role"
    );

    if (serviceRole && typeof serviceRole.api_key === "string") {
      return serviceRole.api_key;
    }
  } catch {
    // Fall through to explicit env key requirement.
  }

  return null;
}

async function loadLocalEnvDefaults() {
  const envPaths = [
    path.join(repoRoot, ".env"),
    path.join(repoRoot, "apps", "customer", ".env.local"),
    path.join(repoRoot, "apps", "agent-workspace", ".env.local"),
  ];

  for (const envPath of envPaths) {
    try {
      const content = await readFile(envPath, "utf8");
      const parsed = parseEnvFile(content);
      for (const [key, value] of Object.entries(parsed)) {
        if (!process.env[key]) {
          process.env[key] = value;
        }
      }
    } catch {
      // Optional env file.
    }
  }
}

function deterministicUuid(seed) {
  const bytes = Buffer.from(
    createHash("sha256").update(seed).digest().subarray(0, 16)
  );
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = bytes.toString("hex");
  return [
    hex.slice(0, 8),
    hex.slice(8, 12),
    hex.slice(12, 16),
    hex.slice(16, 20),
    hex.slice(20, 32),
  ].join("-");
}

function ensureArray(value, fieldName) {
  if (!Array.isArray(value)) {
    throw new Error(`${fieldName} must be an array`);
  }
  return value;
}

function deriveScenarioFamily(scenarioId) {
  return scenarioId.replace(/_(civil|uncivil)$/u, "");
}

function buildInteractionSummary(interaction) {
  const topic =
    typeof interaction.topic === "string" ? interaction.topic.trim() : "";
  const subtopic =
    typeof interaction.subtopic === "string" ? interaction.subtopic.trim() : "";

  if (topic && subtopic) {
    return `${topic}: ${subtopic}`;
  }
  if (topic) {
    return topic;
  }
  if (subtopic) {
    return subtopic;
  }

  return typeof interaction.outcome_summary === "string"
    ? interaction.outcome_summary
    : "Interaction";
}

function buildChannelDetail(interaction) {
  const parts = [];

  if (
    typeof interaction.direction === "string" &&
    interaction.direction.trim()
  ) {
    parts.push(interaction.direction.trim());
  }

  if (
    typeof interaction.owner_team === "string" &&
    interaction.owner_team.trim()
  ) {
    parts.push(interaction.owner_team.trim());
  }

  return parts.length > 0 ? parts.join(" · ") : null;
}

async function loadPersonaProfiles() {
  const files = (await readdir(PERSONA_DIR)).filter(
    (name) => name.startsWith("customer_profile_") && name.endsWith(".json")
  );

  if (files.length === 0) {
    throw new Error("No persona profile JSON files found in personas/");
  }

  const profiles = [];
  for (const file of files) {
    const fullPath = path.join(PERSONA_DIR, file);
    const payload = JSON.parse(await readFile(fullPath, "utf8"));

    const profile = payload.customer_profile;
    if (!profile || typeof profile !== "object") {
      throw new Error(`${file}: missing customer_profile object`);
    }

    if (
      typeof profile.customer_id !== "string" ||
      !profile.customer_id.trim()
    ) {
      throw new Error(`${file}: customer_profile.customer_id is required`);
    }

    const dbCustomerId = deterministicUuid(profile.customer_id);
    const interactions = ensureArray(
      payload.interaction_history ?? [],
      `${file}: interaction_history`
    );

    profiles.push({
      file,
      dbCustomerId,
      payload,
      profile,
      interactions,
    });
  }

  return profiles;
}

async function loadScenarios() {
  const files = (await readdir(SCENARIO_DIR)).filter(
    (name) => name.startsWith("scenario_") && name.endsWith(".json")
  );

  if (files.length === 0) {
    throw new Error("No scenario JSON files found in scenarios/");
  }

  const scenarios = [];
  for (const file of files) {
    const fullPath = path.join(SCENARIO_DIR, file);
    const payload = JSON.parse(await readFile(fullPath, "utf8"));

    if (
      typeof payload.scenario_id !== "string" ||
      !payload.scenario_id.trim()
    ) {
      throw new Error(`${file}: scenario_id is required`);
    }

    if (typeof payload.title !== "string" || !payload.title.trim()) {
      throw new Error(`${file}: title is required`);
    }

    if (typeof payload.domain !== "string" || !payload.domain.trim()) {
      throw new Error(`${file}: domain is required`);
    }

    const conversation = ensureArray(
      payload.conversation ?? [],
      `${file}: conversation`
    );
    const behavioralCondition = payload.behavioral_condition ?? {};
    const civilityCondition = behavioralCondition.civility_condition;

    if (civilityCondition !== "civil" && civilityCondition !== "uncivil") {
      throw new Error(
        `${file}: behavioral_condition.civility_condition must be civil|uncivil`
      );
    }

    for (const step of conversation) {
      if (!step || typeof step !== "object") {
        throw new Error(`${file}: conversation contains an invalid step`);
      }
      if (typeof step.id !== "string" || !step.id.trim()) {
        throw new Error(`${file}: every conversation step requires id`);
      }
      if (typeof step.customer_msg !== "string" || !step.customer_msg.trim()) {
        throw new Error(`${file}: step ${step.id} is missing customer_msg`);
      }
    }

    scenarios.push({
      scenario_id: payload.scenario_id,
      scenario_family: deriveScenarioFamily(payload.scenario_id),
      title: payload.title,
      domain: payload.domain,
      civility_condition: civilityCondition,
      behavior_instruction:
        typeof behavioralCondition.instruction === "string"
          ? behavioralCondition.instruction
          : "",
      background:
        typeof payload.background === "string" ? payload.background : "",
      customer_goal:
        typeof payload.customer_goal === "string" ? payload.customer_goal : "",
      guidelines: payload.guidelines ?? {},
      conversation,
      actor_guidance:
        payload.actor_guidance && typeof payload.actor_guidance === "object"
          ? payload.actor_guidance
          : null,
      status: "active",
    });
  }

  return scenarios;
}

async function main() {
  const seedTarget = (process.env.SEED_TARGET ?? "local").toLowerCase();

  if (seedTarget === "linked" || seedTarget === "remote") {
    const projectRef = loadLinkedProjectRef();

    if (!projectRef) {
      throw new Error(
        "No linked project ref found. Run `supabase link --project-ref <ref>` first."
      );
    }

    if (!process.env.NEXT_PUBLIC_SUPABASE_URL) {
      process.env.NEXT_PUBLIC_SUPABASE_URL = `https://${projectRef}.supabase.co`;
    }

    if (!process.env.SUPABASE_SERVICE_ROLE_KEY) {
      const linkedServiceRoleKey = loadLinkedServiceRoleKey(projectRef);
      if (linkedServiceRoleKey) {
        process.env.SUPABASE_SERVICE_ROLE_KEY = linkedServiceRoleKey;
      }
    }
  } else {
    const localStatusDefaults = loadSupabaseStatusDefaults();

    if (!process.env.NEXT_PUBLIC_SUPABASE_URL && localStatusDefaults.API_URL) {
      process.env.NEXT_PUBLIC_SUPABASE_URL = localStatusDefaults.API_URL;
    }

    if (
      !process.env.SUPABASE_SERVICE_ROLE_KEY &&
      localStatusDefaults.SERVICE_ROLE_KEY
    ) {
      process.env.SUPABASE_SERVICE_ROLE_KEY =
        localStatusDefaults.SERVICE_ROLE_KEY;
    }

    await loadLocalEnvDefaults();
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!supabaseUrl || !serviceRoleKey) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY in environment. For linked remote seeding, set SEED_TARGET=linked and ensure `supabase link` is configured."
    );
  }

  console.log(`Seeding target: ${seedTarget}`);
  console.log(`Supabase URL: ${supabaseUrl}`);

  const supabase = createClient(supabaseUrl, serviceRoleKey);

  const personas = await loadPersonaProfiles();
  const scenarios = await loadScenarios();

  const customerRows = personas.map(({ dbCustomerId, profile, payload }) => ({
    id: dbCustomerId,
    customer_code: profile.customer_id,
    name: profile.full_name,
    gender: profile.gender,
    date_of_birth: profile.date_of_birth,
    email: profile.email ?? null,
    phone: profile.phone ?? null,
    address_street: profile.address?.street ?? null,
    address_postal_code: profile.address?.postal_code ?? null,
    address_city: profile.address?.city ?? null,
    address_country: profile.address?.country ?? null,
    customer_since: profile.customer_since,
    classification: profile.internal_classification,
    products: ensureArray(profile.products ?? [], "profile.products"),
    preferred_language:
      typeof profile.language === "string"
        ? profile.language.toLowerCase()
        : "de",
    preferred_contact_channel: profile.preferred_contact_channel ?? null,
    notes: profile.quick_internal_note ?? null,
    quick_internal_note: profile.quick_internal_note ?? null,
    domain: typeof payload.domain === "string" ? payload.domain : null,
  }));

  const interactionRows = personas.flatMap(({ dbCustomerId, interactions }) =>
    interactions.map((entry) => ({
      customer_id: dbCustomerId,
      type: entry.channel,
      date: entry.date_time,
      summary: buildInteractionSummary(entry),
      outcome: entry.outcome_summary ?? null,
      agent_name: entry.agent_id ?? null,
      channel_detail: buildChannelDetail(entry),
      direction: entry.direction ?? null,
      topic: entry.topic ?? null,
      subtopic: entry.subtopic ?? null,
      sentiment: entry.sentiment ?? null,
      priority: entry.priority ?? null,
      owner_team: entry.owner_team ?? null,
      status: entry.status ?? null,
      resolution_time_hours:
        typeof entry.resolution_time_hours === "number"
          ? entry.resolution_time_hours
          : null,
      sla_breached:
        typeof entry.sla_breached === "boolean" ? entry.sla_breached : null,
      follow_up_required:
        typeof entry.follow_up_required === "boolean"
          ? entry.follow_up_required
          : null,
      related_case_id: entry.related_case_id ?? null,
      csat: typeof entry.csat === "number" ? entry.csat : null,
    }))
  );

  const deletions = [
    ["session_events", "id"],
    ["transcript_segments", "id"],
    ["sessions", "id"],
    ["customer_interactions", "id"],
    ["customers", "id"],
    ["scenarios", "scenario_id"],
  ];

  for (const [table, key] of deletions) {
    const { error } = await supabase.from(table).delete().not(key, "is", null);
    if (error) {
      if (
        error.code === "PGRST205" ||
        (typeof error.message === "string" &&
          error.message.includes("Could not find the table"))
      ) {
        throw new Error(
          `Table ${table} is missing. Run database migrations first (for example: make db-reset).`
        );
      }
      throw new Error(`Failed clearing ${table}: ${error.message}`);
    }
  }

  const { error: customerError } = await supabase
    .from("customers")
    .upsert(customerRows, { onConflict: "id" });
  if (customerError) {
    throw new Error(`Failed inserting customers: ${customerError.message}`);
  }

  const { error: interactionError } = await supabase
    .from("customer_interactions")
    .insert(interactionRows);
  if (interactionError) {
    throw new Error(
      `Failed inserting customer interactions: ${interactionError.message}`
    );
  }

  const { error: scenarioError } = await supabase
    .from("scenarios")
    .upsert(scenarios, { onConflict: "scenario_id" });
  if (scenarioError) {
    throw new Error(`Failed inserting scenarios: ${scenarioError.message}`);
  }

  console.log(`Seeded ${customerRows.length} customers`);
  console.log(`Seeded ${interactionRows.length} customer interactions`);
  console.log(`Seeded ${scenarios.length} scenarios`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
