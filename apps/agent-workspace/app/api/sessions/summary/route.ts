import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

function getSupabaseAdmin() {
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { session_id, summary_text } = body as {
      session_id: string;
      summary_text: string;
    };

    if (!session_id || !summary_text) {
      return NextResponse.json(
        { detail: "session_id and summary_text are required" },
        { status: 400 }
      );
    }

    const supabase = getSupabaseAdmin();

    // 1. Validate session exists and is in terminal state
    const { data: session, error: sessionError } = await supabase
      .from("sessions")
      .select("id, status")
      .eq("id", session_id)
      .single();

    if (sessionError || !session) {
      return NextResponse.json(
        { detail: "Session not found" },
        { status: 404 }
      );
    }

    const terminalStatuses = ["completed", "abandoned", "escalated"];
    if (!terminalStatuses.includes(session.status)) {
      return NextResponse.json(
        {
          detail: `Cannot save summary for session with status: ${session.status}`,
        },
        { status: 400 }
      );
    }

    // 2. Save summary
    const { error: updateError } = await supabase
      .from("sessions")
      .update({
        summary_text,
        summary_updated_at: new Date().toISOString(),
        summary_updated_by: "agent", // Could be enhanced with actual user ID
      })
      .eq("id", session_id);

    if (updateError) {
      return NextResponse.json(
        { detail: `Failed to save summary: ${updateError.message}` },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true });
  } catch (error) {
    console.error("Summary save error:", error);
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
