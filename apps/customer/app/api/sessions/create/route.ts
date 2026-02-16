import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

const PCC_TRANSCRIPT_AGENT_URL =
  process.env.PCC_TRANSCRIPT_AGENT_URL || "http://localhost:7860";
const PCC_PROCESS_AGENT_URL =
  process.env.PCC_PROCESS_AGENT_URL || "http://localhost:7861";
const PCC_SUGGESTION_AGENT_URL =
  process.env.PCC_SUGGESTION_AGENT_URL || "http://localhost:7862";
const DAILY_API_KEY = process.env.DAILY_API_KEY || "";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

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

async function startSecondaryAgent(
  agentUrl: string,
  agentName: string,
  roomUrl: string,
  sessionId: string
): Promise<void> {
  try {
    const res = await fetch(`${agentUrl}/start`, {
      method: "POST",
      headers: getPccHeaders(),
      body: JSON.stringify({ dailyRoom: roomUrl, session_id: sessionId }),
    });
    if (!res.ok) {
      const err = await res.text();
      console.warn(`${agentName} start failed (non-critical): ${err}`);
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown error";
    console.warn(`${agentName} start failed (non-critical): ${message}`);
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const customerId = (body as { customer_id?: string }).customer_id;
    const sessionId = crypto.randomUUID();

    // 1. Start transcript agent — it creates the Daily room
    const transcriptResponse = await fetch(
      `${PCC_TRANSCRIPT_AGENT_URL}/start`,
      {
        method: "POST",
        headers: getPccHeaders(),
        body: JSON.stringify({
          createDailyRoom: true,
          session_id: sessionId,
        }),
      }
    );

    if (!transcriptResponse.ok) {
      const err = await transcriptResponse.text();
      throw new Error(`Transcript agent start failed: ${err}`);
    }

    const transcriptData = await transcriptResponse.json();
    const roomUrl = transcriptData.dailyRoom as string;
    const roomName = roomUrl.split("/").pop() || "";

    // 2. Start process + suggestion agents in parallel (join existing room)
    await Promise.all([
      startSecondaryAgent(
        PCC_PROCESS_AGENT_URL,
        "Process agent",
        roomUrl,
        sessionId
      ),
      startSecondaryAgent(
        PCC_SUGGESTION_AGENT_URL,
        "Suggestion agent",
        roomUrl,
        sessionId
      ),
    ]);

    // 3. Create customer + agent tokens via Daily REST API
    const [customerToken, agentToken] = await Promise.all([
      createDailyToken(roomName, false),
      createDailyToken(roomName, true),
    ]);

    // 4. Insert pending session into Supabase
    const supabase = getSupabaseAdmin();

    const { error: insertError } = await supabase.from("sessions").insert({
      id: sessionId,
      room_url: roomUrl,
      room_name: roomName,
      agent_token: agentToken,
      status: "pending",
      state: { customer_id: customerId || null },
    });

    if (insertError) {
      throw new Error(`Session insert failed: ${insertError.message}`);
    }

    // 5. Return customer credentials
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
