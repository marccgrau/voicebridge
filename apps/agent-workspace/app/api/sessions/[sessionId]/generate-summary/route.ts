import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import OpenAI from "openai";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const SUPABASE_SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY || "";

function getSupabaseAdmin() {
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY);
}

export async function POST(
  request: Request,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  try {
    const { sessionId } = await params;

    if (!OPENAI_API_KEY) {
      return NextResponse.json(
        { detail: "OpenAI API key not configured" },
        { status: 500 }
      );
    }

    const supabase = getSupabaseAdmin();

    // 1. Fetch session to validate it's in a terminal state
    const { data: session, error: sessionError } = await supabase
      .from("sessions")
      .select("id, status")
      .eq("id", sessionId)
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
          detail: `Cannot generate summary for session with status: ${session.status}`,
        },
        { status: 400 }
      );
    }

    // 2. Fetch transcript segments
    const { data: segments, error: transcriptError } = await supabase
      .from("transcript_segments")
      .select("speaker, text, ts")
      .eq("session_id", sessionId)
      .eq("is_final", true)
      .order("ts", { ascending: true });

    if (transcriptError) {
      return NextResponse.json(
        { detail: `Failed to fetch transcript: ${transcriptError.message}` },
        { status: 500 }
      );
    }

    if (!segments || segments.length === 0) {
      return NextResponse.json(
        { detail: "No transcript available for this session" },
        { status: 400 }
      );
    }

    // 3. Build transcript text
    const transcriptText = segments
      .map((seg) => `[${seg.speaker}]: ${seg.text}`)
      .join("\n");

    // 4. Call OpenAI to generate summary
    const openai = new OpenAI({ apiKey: OPENAI_API_KEY });

    const completion = await openai.chat.completions.create({
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content:
            "You are a customer service call summarizer. Generate a concise, professional summary of the call transcript. Include: (1) Customer issue or request, (2) Actions taken, (3) Outcome/resolution, (4) Any follow-up needed. Keep it under 200 words.",
        },
        {
          role: "user",
          content: `Summarize this customer service call:\n\n${transcriptText}`,
        },
      ],
      temperature: 0.7,
      max_tokens: 500,
    });

    const summaryText =
      completion.choices[0]?.message?.content?.trim() ||
      "Failed to generate summary.";

    // 5. Return summary (don't save yet - user will review and save manually)
    return NextResponse.json({ summary_text: summaryText });
  } catch (error) {
    console.error("Summary generation error:", error);
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
