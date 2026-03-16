"use client";

import { useState } from "react";
import Link from "next/link";
import { SessionList } from "@/components/admin/SessionList";
import { SessionDetail } from "@/components/admin/SessionDetail";

export default function AdminPageClient() {
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(
    null
  );

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex h-14 items-center justify-between border-b border-border px-6">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold">VoiceBridge Admin</h1>
        </div>
        <Link
          href="/"
          className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          Zurück zum Arbeitsbereich
        </Link>
      </header>

      {/* Master-Detail Layout */}
      <div className="flex flex-1 overflow-hidden">
        {/* Master: Session List (Left) */}
        <div className="w-96">
          <SessionList
            onSelectSession={setSelectedSessionId}
            selectedSessionId={selectedSessionId}
          />
        </div>

        {/* Detail: Session Detail (Right) */}
        <div className="flex-1 overflow-hidden">
          <SessionDetail sessionId={selectedSessionId} />
        </div>
      </div>
    </div>
  );
}
