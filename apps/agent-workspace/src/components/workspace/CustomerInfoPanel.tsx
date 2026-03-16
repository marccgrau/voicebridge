"use client";

import { useCustomer } from "@/lib/use-customer";
import type { PanelVariant } from "@/lib/use-phase";
import type { Customer, CustomerInteraction } from "@voicebridge/contracts";

export interface RoutingContext {
  source: "direct" | "voice_ai";
  handoffSummary: string | null;
  transferReason: string | null;
}

interface CustomerInfoPanelProps {
  customerId: string | null;
  routingContext?: RoutingContext | null;
  isConnected: boolean;
  variant?: PanelVariant;
  onToggle?: () => void;
}

const DEFAULT_ROUTING_CONTEXT: RoutingContext = {
  source: "direct",
  handoffSummary: null,
  transferReason: null,
};

export function CustomerInfoPanel({
  customerId,
  routingContext,
  isConnected,
  variant = "expanded",
  onToggle,
}: CustomerInfoPanelProps) {
  const { customer, interactions, isLoading } = useCustomer(customerId);
  const resolvedRouting = routingContext ?? DEFAULT_ROUTING_CONTEXT;

  if (variant === "compact") {
    return (
      <button
        onClick={onToggle}
        className="panel-morph flex w-full items-center gap-3 rounded-2xl border border-border bg-white px-4 py-3 text-left shadow-card hover:shadow-card-hover transition-shadow"
      >
        {isLoading ? (
          <>
            <span className="h-8 w-8 animate-pulse rounded-full bg-muted" />
            <span className="text-sm text-muted-foreground">
              Kundenprofil wird geladen...
            </span>
          </>
        ) : customer ? (
          <>
            <span className="flex h-8 w-8 items-center justify-center rounded-full gradient-accent text-xs font-medium text-white">
              {getInitials(customer.name)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-foreground">
                {customer.name}
              </p>
              <p className="font-mono-ui text-[11px] uppercase tracking-wide text-muted-foreground">
                {resolvedRouting.source === "voice_ai"
                  ? "Voice-AI-Übergabe"
                  : "Direkte Warteschlange"}
              </p>
            </div>
            <ClassificationBadge classification={customer.classification} />
          </>
        ) : (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="text-sm text-muted-foreground">Kundenprofil</span>
          </>
        )}
      </button>
    );
  }

  return (
    <div className="panel-morph flex h-full min-h-0 flex-col">
      <button
        onClick={onToggle}
        disabled={!onToggle}
        className="flex items-center justify-between border-b border-border px-5 py-4 text-left disabled:cursor-default"
      >
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Kundenprofil
        </span>
      </button>

      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <LoadingState />
        ) : !customer ? (
          <EmptyCustomerState
            customerId={customerId}
            isConnected={isConnected}
          />
        ) : (
          <div className="space-y-4">
            <CustomerIdentityCard customer={customer} />
            <RoutingContextCard
              routingContext={resolvedRouting}
              lastInteraction={interactions[0] ?? null}
            />
            <ServiceNoteCard
              notes={customer.quickInternalNote ?? customer.notes}
            />
            <RecentInteractionsCard interactions={interactions} />
          </div>
        )}
      </div>
    </div>
  );
}

const classificationStyles = {
  basis: "border-blue-500/40 bg-blue-50 text-blue-700",
  "basis plus": "border-blue-500/40 bg-blue-50 text-blue-700",
  standard: "border-blue-500/40 bg-blue-50 text-blue-700",
  "standard plus": "border-blue-500/40 bg-blue-50 text-blue-700",
  affluent: "border-emerald-500/40 bg-emerald-50 text-emerald-700",
  hnwi: "border-amber-500/40 bg-amber-50 text-amber-700",
  uhnwi: "border-rose-500/40 bg-rose-50 text-rose-700",
};

function LoadingState() {
  return (
    <div className="space-y-3">
      <div className="h-20 animate-pulse rounded-2xl bg-muted" />
      <div className="h-24 animate-pulse rounded-2xl bg-muted" />
      <div className="h-24 animate-pulse rounded-2xl bg-muted" />
    </div>
  );
}

function ClassificationBadge({
  classification,
}: {
  classification: Customer["classification"];
}) {
  const normalizedClassification = classification.toLowerCase();
  const badgeClass =
    classificationStyles[
      normalizedClassification as keyof typeof classificationStyles
    ] ?? classificationStyles.basis;

  return (
    <span
      className={`font-mono-ui rounded-lg border px-2 py-0.5 text-xs font-medium ${badgeClass}`}
    >
      {classification}
    </span>
  );
}

function CustomerIdentityCard({ customer }: { customer: Customer }) {
  return (
    <section className="rounded-2xl border border-border bg-gradient-to-r from-white via-white to-muted/30 p-4 shadow-card">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full gradient-accent text-sm font-semibold text-white">
          {getInitials(customer.name)}
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-lg font-semibold text-foreground">
              {customer.name}
            </h3>
            <ClassificationBadge classification={customer.classification} />
          </div>
          <p className="font-mono-ui mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
            Kunde seit {formatMonthYear(customer.customerSince)}
            {customer.dateOfBirth
              ? ` · Geb. ${formatMonthDayYear(customer.dateOfBirth)}`
              : ""}
          </p>
          {customer.products.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {customer.products.map((product) => (
                <span
                  key={product}
                  className="rounded-md border border-border/60 bg-background px-2 py-0.5 text-xs text-foreground"
                >
                  {product}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function RoutingContextCard({
  routingContext,
  lastInteraction,
}: {
  routingContext: RoutingContext;
  lastInteraction: CustomerInteraction | null;
}) {
  if (routingContext.source === "voice_ai") {
    return (
      <section className="rounded-2xl border-2 border-accent/40 bg-accent/5 p-4 shadow-card">
        <SectionTitle number="1" title="Routing-Kontext" />
        <p className="mt-2 text-sm font-semibold text-foreground">
          Via Voice-AI-Triage eingegangen
        </p>
        <p className="mt-1 text-sm leading-relaxed text-foreground">
          {routingContext.handoffSummary ??
            "Keine KI-Übergabezusammenfassung vorhanden."}
        </p>
        <div className="mt-3 rounded-xl border border-accent/30 bg-white/80 px-3 py-2">
          <p className="font-mono-ui text-[11px] uppercase tracking-wide text-muted-foreground">
            Übergabegrund
          </p>
          <p className="mt-1 text-sm font-medium text-foreground">
            {routingContext.transferReason ??
              "Kein expliziter Übergabegrund angegeben."}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border bg-white p-4 shadow-card">
      <SectionTitle number="1" title="Routing-Kontext" />
      <p className="mt-2 text-sm font-semibold text-foreground">
        Direkt in Agent-Warteschlange eingegangen
      </p>
      {lastInteraction ? (
        <div className="mt-2 rounded-xl border border-border bg-muted/30 p-3">
          <p className="font-mono-ui text-[11px] uppercase tracking-wide text-muted-foreground">
            Letzte Kundeninteraktion · {formatMonthDay(lastInteraction.date)}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-foreground">
            {lastInteraction.summary}
          </p>
          {lastInteraction.outcome && (
            <p className="mt-2 text-xs text-muted-foreground">
              Ergebnis: {lastInteraction.outcome}
            </p>
          )}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          Keine bisherige Interaktionshistorie vorhanden.
        </p>
      )}
    </section>
  );
}

function ServiceNoteCard({ notes }: { notes: string | null }) {
  return (
    <section className="rounded-2xl border-2 border-warning/40 bg-warning/5 p-4 shadow-card">
      <SectionTitle number="2" title="Prioritäts-Servicenotiz" />
      <p className="mt-2 text-sm leading-relaxed text-foreground">
        {notes ??
          "Keine Servicenotizen vorhanden. Erwartungen während des Gesprächs explizit klären."}
      </p>
    </section>
  );
}

function RecentInteractionsCard({
  interactions,
}: {
  interactions: CustomerInteraction[];
}) {
  const recentInteractions = interactions.slice(0, 2);

  return (
    <section className="rounded-2xl border border-border bg-white p-4 shadow-card">
      <SectionTitle number="3" title="Letzte Interaktionen" />
      {recentInteractions.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          Keine bisherigen Interaktionen.
        </p>
      ) : (
        <div className="mt-3 space-y-2">
          {recentInteractions.map((interaction) => (
            <InteractionRow key={interaction.id} interaction={interaction} />
          ))}
        </div>
      )}
    </section>
  );
}

function InteractionRow({ interaction }: { interaction: CustomerInteraction }) {
  const typeConfig = {
    phone: {
      label: "Telefon",
      tagClass: "border-blue-500/40 bg-blue-50 text-blue-700",
    },
    chat: {
      label: "Chat",
      tagClass: "border-emerald-500/40 bg-emerald-50 text-emerald-700",
    },
    mobile_app_chat: {
      label: "App-Chat",
      tagClass: "border-sky-500/40 bg-sky-50 text-sky-700",
    },
    portal_message: {
      label: "Portal-Nachricht",
      tagClass: "border-violet-500/40 bg-violet-50 text-violet-700",
    },
    secure_message: {
      label: "Sichere Nachricht",
      tagClass: "border-indigo-500/40 bg-indigo-50 text-indigo-700",
    },
    branch_visit: {
      label: "Filialbesuch",
      tagClass: "border-amber-500/40 bg-amber-50 text-amber-700",
    },
    service_desk: {
      label: "Service-Desk",
      tagClass: "border-orange-500/40 bg-orange-50 text-orange-700",
    },
    video_call: {
      label: "Videoanruf",
      tagClass: "border-teal-500/40 bg-teal-50 text-teal-700",
    },
    email: {
      label: "E-Mail",
      tagClass: "border-cyan-500/40 bg-cyan-50 text-cyan-700",
    },
  };

  const config = typeConfig[interaction.type as keyof typeof typeConfig] ?? {
    label: interaction.type,
    tagClass: "border-border bg-muted text-foreground",
  };

  return (
    <article className="rounded-xl border border-border/60 bg-background px-3 py-2.5">
      <div className="flex items-center justify-between gap-2">
        <span
          className={`font-mono-ui rounded-md border px-2 py-0.5 text-[10px] uppercase tracking-wide ${config.tagClass}`}
        >
          {config.label}
        </span>
        <span className="font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground">
          {formatMonthDay(interaction.date)}
        </span>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed text-foreground">
        {interaction.summary}
      </p>
      {interaction.outcome && (
        <p className="mt-1 text-xs text-muted-foreground">
          Ergebnis: {interaction.outcome}
        </p>
      )}
    </article>
  );
}

function EmptyCustomerState({
  customerId,
  isConnected,
}: {
  customerId: string | null;
  isConnected: boolean;
}) {
  const message = customerId
    ? "Kundenprofil für diese Sitzung nicht gefunden."
    : isConnected
      ? "Kein Kundenprofil mit diesem aktiven Anruf verknüpft."
      : "Kein Kundenprofil verknüpft. Wählen Sie einen wartenden Anruf zur Kontextvorschau.";

  return (
    <div className="flex h-full items-center justify-center">
      <div className="max-w-sm rounded-xl border border-dashed border-border px-4 py-6 text-center">
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </div>
  );
}

function SectionTitle({ number, title }: { number: string; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-mono-ui inline-flex h-5 w-5 items-center justify-center rounded-full bg-accent/10 text-[10px] font-semibold text-accent">
        {number}
      </span>
      <p className="font-mono-ui text-[11px] uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
    </div>
  );
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function formatMonthYear(value: string): string {
  return new Date(value).toLocaleDateString("de-DE", {
    year: "numeric",
    month: "short",
  });
}

function formatMonthDay(value: string): string {
  return new Date(value).toLocaleDateString("de-DE", {
    month: "short",
    day: "numeric",
  });
}

function formatMonthDayYear(value: string): string {
  return new Date(value).toLocaleDateString("de-DE", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
