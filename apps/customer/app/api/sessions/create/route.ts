import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

const PCC_AGENT_URL = process.env.PCC_AGENT_URL || "http://localhost:7860";
const DAILY_API_KEY = process.env.DAILY_API_KEY || "";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

function getSupabaseAdmin() {
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
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

export async function POST(request: Request) {
  try {
    const body = await request.json().catch(() => ({}));
    const customerId = (body as { customer_id?: string }).customer_id;

    // 1. Start PCC bot — it creates a Daily room and joins
    const pccHeaders: Record<string, string> = {
      "Content-Type": "application/json",
    };
    if (process.env.PIPECAT_CLOUD_API_KEY) {
      pccHeaders["Authorization"] =
        `Bearer ${process.env.PIPECAT_CLOUD_API_KEY}`;
    }

    const pccResponse = await fetch(`${PCC_AGENT_URL}/start`, {
      method: "POST",
      headers: pccHeaders,
      body: JSON.stringify({ createDailyRoom: true }),
    });

    if (!pccResponse.ok) {
      const err = await pccResponse.text();
      throw new Error(`PCC start failed: ${err}`);
    }

    const pccData = await pccResponse.json();
    const roomUrl = pccData.dailyRoom as string;
    const roomName = roomUrl.split("/").pop() || "";

    // 2. Create customer + agent tokens via Daily REST API
    const [customerToken, agentToken] = await Promise.all([
      createDailyToken(roomName, false),
      createDailyToken(roomName, true),
    ]);

    // 3. Insert pending session into Supabase
    const supabase = getSupabaseAdmin();
    const sessionId = crypto.randomUUID();

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
