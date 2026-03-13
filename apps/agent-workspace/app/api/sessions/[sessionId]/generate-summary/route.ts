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
          content: `Du bist ein Gespr\u00E4chszusammenfasser f\u00FCr Kundenservice-Anrufe im Rahmen eines Experiments. Erstelle eine kurze, professionelle Zusammenfassung, die ausschlie\u00DFlich auf Informationen basiert, die im Transkript genannt werden. Ziehe keine Schlussfolgerungen und f\u00FCge keine Fakten hinzu.
Halte die Zusammenfassung unter 200 W\u00F6rtern und folge der untenstehenden Struktur. Gib nur die Punkte unter "Inhalt" aus. Die Zeilen "Beschreibung" sind nur Hinweise und d\u00FCrfen nicht im Output erscheinen.

## Gespr\u00E4chszusammenfassung

**Anliegen/Request**
[BESCHREIBUNG: Was die Kundin bzw. der Kunde wollte.]

- Inhalt:
  - ...

**Massnahmen**
[BESCHREIBUNG: Konkrete Schritte, die durchgef\u00FChrt wurden (z. B. Reklamation er\u00F6ffnet, Einsprache gestartet, Dokumente angefordert, Ersatz bestellt).]

- Inhalt:
  - ...
  - ...

**Ergebnis/Status**
[BESCHREIBUNG: Erledigt vs. offen]

- Inhalt:
  - Status: [erledigt | offen | teilweise | nicht genannt]
  - Fall: ...
  - Kurzresultat: ...

**Follow-up**
[BESCHREIBUNG: Wer als N\u00E4chstes was tun muss (Kundin/Kunde vs. Unternehmen), \u00FCber welchen Kanal und mit welcher genannten Frist/Zeitangabe.]

- Inhalt:
  - Kundin/Kunde: ... | Kanal: ... | Frist/Zeitangabe: ...
  - Unternehmen: ... | Kanal: ... | Frist/Zeitangabe: ...`,
        },
        {
          role: "user",
          content: `Fasse diesen Kundenservice-Anruf zusammen:\n\n${transcriptText}`,
        },
      ],
      temperature: 0.7,
      max_tokens: 500,
    });

    const summaryText =
      completion.choices[0]?.message?.content?.trim() ||
      "Zusammenfassung konnte nicht generiert werden.";

    // 5. Return summary (don't save yet - user will review and save manually)
    return NextResponse.json({ summary_text: summaryText });
  } catch (error) {
    console.error("Summary generation error:", error);
    const message = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json({ detail: message }, { status: 500 });
  }
}
