import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

const PCC_AGENT_URL = process.env.PCC_AGENT_URL || "http://localhost:7860";
const DAILY_API_KEY = process.env.DAILY_API_KEY || "";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

type RoutingSource = "direct" | "voice_ai";

interface RoutingPayload {
  source?: RoutingSource;
  handoff_summary?: string;
  handoffSummary?: string;
  transfer_reason?: string;
  transferReason?: string;
}

interface CreateSessionRequestBody {
  customer_id?: string;
  scenario_id?: string;
  routing?: RoutingPayload;
}

function getSupabaseAdmin() {
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
}

function getPccHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (process.env.PIPECAT_CLOUD_API_KEY) {
    headers["Authorization"] = `Bearer ${process.env.PIPECAT_CLOUD_API_KEY}`;
  }
  return headers;
}

async function createDailyToken(
  roomName: string,
  isOwner: boolean
): Promise<string> {
  const res = await fetch("https://api.daily.co/v1/meeting-tokens", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${DAILY_API_KEY}`,
    },
    body: JSON.stringify({
      properties: {
        room_name: roomName,
        is_owner: isOwner,
        exp: Math.floor(Date.now() / 1000) + 3600,
      },
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Daily token creation failed: ${err}`);
  }

  const data = await res.json();
  return data.token as string;
}

function normalizeText(value: unknown): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function normalizeRouting(payload?: RoutingPayload) {
  const handoffSummary =
    normalizeText(payload?.handoff_summary) ??
    normalizeText(payload?.handoffSummary);
  const transferReason =
    normalizeText(payload?.transfer_reason) ??
    normalizeText(payload?.transferReason);

  let source: RoutingSource;
  if (payload?.source === "voice_ai") {
    source = "voice_ai";
  } else if (payload?.source === "direct") {
    source = "direct";
  } else {
    source = handoffSummary || transferReason ? "voice_ai" : "direct";
  }

  return {
    source,
    handoffSummary,
    transferReason,
  };
}

export async function POST(request: Request) {
  try {
    const body = (await request
      .json()
      .catch(() => ({}))) as CreateSessionRequestBody;
    const normalizedCustomerId = normalizeText(body.customer_id);
    const normalizedScenarioId = normalizeText(body.scenario_id);

    if (!normalizedCustomerId || !normalizedScenarioId) {
      return NextResponse.json(
        { detail: "customer_id and scenario_id are required" },
        { status: 400 }
      );
    }

    const routing = normalizeRouting(body.routing);
    const sessionId = crypto.randomUUID();
    const supabase = getSupabaseAdmin();

    const [
      { data: customer, error: customerError },
      { data: scenario, error: scenarioError },
    ] = await Promise.all([
      supabase
        .from("customers")
        .select("id")
        .eq("id", normalizedCustomerId)
        .single(),
      supabase
        .from("scenarios")
        .select(
          "scenario_id, scenario_family, domain, civility_condition, title"
        )
        .eq("scenario_id", normalizedScenarioId)
        .eq("status", "active")
        .single(),
    ]);

    if (customerError || !customer) {
      return NextResponse.json(
        { detail: "Customer not found" },
        { status: 404 }
      );
    }

    if (scenarioError || !scenario) {
      return NextResponse.json(
        { detail: "Scenario not found" },
        { status: 404 }
      );
    }

    // 1. Start unified PCC service — it creates the Daily room
    const pccResponse = await fetch(`${PCC_AGENT_URL}/start`, {
      method: "POST",
      headers: getPccHeaders(),
      body: JSON.stringify({
        createDailyRoom: true,
        body: {
          session_id: sessionId,
          metadata: {
            scenario_id: scenario.scenario_id,
            scenario_family: scenario.scenario_family,
            domain: scenario.domain,
          },
        },
      }),
    });

    if (!pccResponse.ok) {
      const err = await pccResponse.text();
      throw new Error(`PCC agent start failed: ${err}`);
    }

    const pccData = await pccResponse.json();
    const roomUrl = pccData.dailyRoom as string | undefined;
    const roomToken = pccData.dailyToken as string | undefined;
    if (!roomUrl || !roomToken) {
      throw new Error("PCC agent returned incomplete Daily room data");
    }
    const roomName = roomUrl.split("/").pop() || "";

    // 2. Create customer + agent tokens via Daily REST API
    const [customerToken, agentToken] = await Promise.all([
      createDailyToken(roomName, false),
      createDailyToken(roomName, true),
    ]);

    // 3. Insert pending session into Supabase
    const { error: insertError } = await supabase.from("sessions").insert({
      id: sessionId,
      room_url: roomUrl,
      room_name: roomName,
      agent_token: agentToken,
      customer_id: customer.id,
      scenario_id: scenario.scenario_id,
      scenario_family: scenario.scenario_family,
      civility_condition: scenario.civility_condition,
      status: "pending",
      customer_joined_at: new Date().toISOString(),
      state: {
        customer_id: customer.id,
        scenario_id: scenario.scenario_id,
        scenario_family: scenario.scenario_family,
        scenario_title: scenario.title,
        civility_condition: scenario.civility_condition,
        domain: scenario.domain,
        routing: {
          source: routing.source,
          handoff_summary: routing.handoffSummary,
          transfer_reason: routing.transferReason,
        },
        routing_source: routing.source,
        handoff_summary: routing.handoffSummary,
        transfer_reason: routing.transferReason,
      },
    });

    if (insertError) {
      throw new Error(`Session insert failed: ${insertError.message}`);
    }

    // 4. Return customer credentials
    return NextResponse.json({
      session_id: sessionId,
      room_url: roomUrl,
      customer_token: customerToken,
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
