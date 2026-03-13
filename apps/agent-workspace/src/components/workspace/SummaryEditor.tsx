"use client";

interface SummaryEditorProps {
  summaryText: string;
  onSummaryChange: (text: string) => void;
  onSave: () => void;
  isGenerating: boolean;
  isSaving: boolean;
  isSaved: boolean;
  error: string | null;
}

export function SummaryEditor({
  summaryText,
  onSummaryChange,
  onSave,
  isGenerating,
  isSaving,
  isSaved,
  error,
}: SummaryEditorProps) {
  return (
    <div className="panel-morph flex h-full flex-col rounded-2xl border border-border bg-white shadow-card">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-5 py-4">
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Gesprächszusammenfassung
        </span>
        {isSaved && (
          <span className="flex items-center gap-1.5 text-xs text-accent font-medium">
            <svg
              className="h-3.5 w-3.5"
              viewBox="0 0 20 20"
              fill="currentColor"
            >
              <path
                fillRule="evenodd"
                d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                clipRule="evenodd"
              />
            </svg>
            Gespeichert
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex flex-1 flex-col p-4 gap-4">
        {isGenerating ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-4">
            <div className="flex items-center gap-3">
              <span className="h-3 w-3 animate-pulse-dot rounded-full gradient-accent" />
              <span className="text-sm text-muted-foreground">
                Zusammenfassung wird erstellt...
              </span>
            </div>
            <p className="text-xs text-muted-foreground/50">
              Transkript wird analysiert und Notizen vorbereitet
            </p>
          </div>
        ) : (
          <>
            <textarea
              value={summaryText}
              onChange={(e) => onSummaryChange(e.target.value)}
              placeholder="Zusammenfassung der Sitzung schreiben..."
              className="flex-1 resize-none rounded-xl border border-border bg-background p-4 text-sm text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-accent/25 focus:border-accent/50 transition-colors"
            />

            {error && <p className="text-xs text-destructive">{error}</p>}

            <button
              onClick={onSave}
              disabled={isSaving || !summaryText.trim()}
              className="gradient-accent rounded-xl px-5 py-2.5 text-sm font-medium text-white hover:-translate-y-0.5 hover:shadow-accent-lg disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-none transition-all"
            >
              {isSaving ? "Speichern..." : "Zusammenfassung speichern"}
            </button>
          </>
        )}
      </div>
    </div>
  );
}
