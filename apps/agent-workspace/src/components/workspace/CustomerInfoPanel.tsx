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
        className="panel-morph flex w-full items-center gap-3 rounded-2xl border border-border/60 bg-card px-4 py-3 text-left shadow-sm hover:shadow-md transition-shadow"
      >
        {isLoading ? (
          <>
            <span className="h-8 w-8 animate-pulse rounded-full bg-muted" />
            <span className="text-sm text-muted-foreground">
              Loading customer brief...
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
                {customer.preferredLanguage.toUpperCase()} ·{" "}
                {resolvedRouting.source === "voice_ai"
                  ? "Voice AI transfer"
                  : "Direct queue"}
              </p>
            </div>
            <ClassificationBadge classification={customer.classification} />
          </>
        ) : (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="text-sm text-muted-foreground">
              Customer Brief
            </span>
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
        className="flex items-center justify-between border-b border-border/60 px-5 py-4 text-left disabled:cursor-default"
      >
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Customer Brief
        </span>
        {customer && (
          <span className="font-mono-ui text-xs uppercase tracking-wide text-muted-foreground">
            {interactions.length} interaction
            {interactions.length === 1 ? "" : "s"}
          </span>
        )}
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
            <CustomerIdentityCard
              customer={customer}
              interactionCount={interactions.length}
            />
            <RoutingContextCard
              routingContext={resolvedRouting}
              lastInteraction={interactions[0] ?? null}
            />
            <div className="grid gap-3 md:grid-cols-[0.9fr_1.1fr]">
              <CustomerEssentialsCard
                customer={customer}
                interactionCount={interactions.length}
              />
              <ProductPortfolioCard products={customer.products} />
            </div>
            <ServiceNoteCard notes={customer.notes} />
            <RecentInteractionsCard interactions={interactions} />
          </div>
        )}
      </div>
    </div>
  );
}

const classificationStyles = {
  basis: "border-blue-500/40 bg-blue-500/10 text-blue-700",
  affluent: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700",
  HNWI: "border-amber-500/40 bg-amber-500/10 text-amber-700",
  UHNWI: "border-rose-500/40 bg-rose-500/10 text-rose-700",
};

function LoadingState() {
  return (
    <div className="space-y-3">
      <div className="h-20 animate-pulse rounded-2xl bg-muted" />
      <div className="h-24 animate-pulse rounded-2xl bg-muted" />
      <div className="h-24 animate-pulse rounded-2xl bg-muted" />
      <div className="h-28 animate-pulse rounded-2xl bg-muted" />
    </div>
  );
}

function ClassificationBadge({
  classification,
}: {
  classification: Customer["classification"];
}) {
  const badgeClass =
    classificationStyles[classification as keyof typeof classificationStyles] ??
    classificationStyles.basis;

  return (
    <span
      className={`font-mono-ui rounded-lg border px-2 py-0.5 text-xs font-medium ${badgeClass}`}
    >
      {classification}
    </span>
  );
}

function CustomerIdentityCard({
  customer,
  interactionCount,
}: {
  customer: Customer;
  interactionCount: number;
}) {
  return (
    <section className="rounded-2xl border border-border/70 bg-gradient-to-r from-card via-card to-muted/45 p-4 shadow-sm">
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
            {customer.gender} · customer since{" "}
            {formatMonthYear(customer.customerSince)}
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            {interactionCount} historical interaction
            {interactionCount === 1 ? "" : "s"} available for context
          </p>
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
      <section className="rounded-2xl border-2 border-accent/45 bg-accent/10 p-4 shadow-sm">
        <SectionTitle number="1" title="Routing Context" />
        <p className="mt-2 text-sm font-semibold text-foreground">
          Arrived via Voice AI triage
        </p>
        <p className="mt-1 text-sm leading-relaxed text-foreground">
          {routingContext.handoffSummary ?? "No AI handoff summary provided."}
        </p>
        <div className="mt-3 rounded-xl border border-accent/35 bg-card/90 px-3 py-2">
          <p className="font-mono-ui text-[11px] uppercase tracking-wide text-muted-foreground">
            Transfer Reason
          </p>
          <p className="mt-1 text-sm font-medium text-foreground">
            {routingContext.transferReason ??
              "No explicit transfer reason provided."}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-border/70 bg-card p-4 shadow-sm">
      <SectionTitle number="1" title="Routing Context" />
      <p className="mt-2 text-sm font-semibold text-foreground">
        Arrived directly in agent queue
      </p>
      {lastInteraction ? (
        <div className="mt-2 rounded-xl border border-border/70 bg-muted/30 p-3">
          <p className="font-mono-ui text-[11px] uppercase tracking-wide text-muted-foreground">
            Last customer interaction · {formatMonthDay(lastInteraction.date)}
          </p>
          <p className="mt-1 text-sm leading-relaxed text-foreground">
            {lastInteraction.summary}
          </p>
          {lastInteraction.outcome && (
            <p className="mt-2 text-xs text-muted-foreground">
              Outcome: {lastInteraction.outcome}
            </p>
          )}
        </div>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">
          No prior interaction history available.
        </p>
      )}
    </section>
  );
}

function CustomerEssentialsCard({
  customer,
  interactionCount,
}: {
  customer: Customer;
  interactionCount: number;
}) {
  return (
    <section className="rounded-2xl border border-border/70 bg-card p-4 shadow-sm">
      <SectionTitle number="2" title="Customer Essentials" />
      <div className="mt-3 grid grid-cols-2 gap-2">
        <FactTile
          label="Language"
          value={customer.preferredLanguage.toUpperCase()}
        />
        <FactTile label="Segment" value={customer.classification} />
        <FactTile
          label="Since"
          value={formatMonthYear(customer.customerSince)}
        />
        <FactTile label="History" value={String(interactionCount)} />
      </div>
    </section>
  );
}

function FactTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-border/60 bg-muted/25 px-3 py-2">
      <p className="font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function ProductPortfolioCard({ products }: { products: string[] }) {
  return (
    <section className="rounded-2xl border border-border/70 bg-card p-4 shadow-sm">
      <SectionTitle number="3" title="Product Portfolio" />
      {products.length === 0 ? (
        <p className="mt-3 text-sm text-muted-foreground">
          No products on file.
        </p>
      ) : (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          {products.map((product) => (
            <article
              key={product}
              className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2"
            >
              <p className="font-mono-ui text-[10px] uppercase tracking-wide text-muted-foreground">
                {getProductFamily(product)}
              </p>
              <p className="mt-1 text-sm font-medium text-foreground">
                {product}
              </p>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ServiceNoteCard({ notes }: { notes: string | null }) {
  return (
    <section className="rounded-2xl border-2 border-warning/45 bg-warning/10 p-4 shadow-sm">
      <SectionTitle number="4" title="Priority Service Note" />
      <p className="mt-2 text-sm leading-relaxed text-foreground">
        {notes ??
          "No service notes available for this customer. Confirm expectations explicitly during this call."}
      </p>
    </section>
  );
}

function RecentInteractionsCard({
  interactions,
}: {
  interactions: CustomerInteraction[];
}) {
  const recentInteractions = interactions.slice(0, 4);

  return (
    <section className="rounded-2xl border border-border/70 bg-card p-4 shadow-sm">
      <SectionTitle number="5" title="Recent Interactions" />
      {recentInteractions.length === 0 ? (
        <p className="mt-2 text-sm text-muted-foreground">
          No previous interactions.
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
      label: "Phone",
      tagClass: "border-blue-500/40 bg-blue-500/10 text-blue-700",
    },
    chat: {
      label: "Chat",
      tagClass: "border-emerald-500/40 bg-emerald-500/10 text-emerald-700",
    },
    branch_visit: {
      label: "Branch Visit",
      tagClass: "border-amber-500/40 bg-amber-500/10 text-amber-700",
    },
    email: {
      label: "Email",
      tagClass: "border-cyan-500/40 bg-cyan-500/10 text-cyan-700",
    },
  };

  const config = typeConfig[interaction.type as keyof typeof typeConfig] ?? {
    label: interaction.type,
    tagClass: "border-border bg-muted text-foreground",
  };

  return (
    <article className="rounded-xl border border-border/60 bg-muted/20 px-3 py-2.5">
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
          Outcome: {interaction.outcome}
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
    ? "Customer profile not found for this session."
    : isConnected
      ? "No customer profile is linked to this active call."
      : "No customer profile linked. Select a pending call to preview context.";

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
      <span className="font-mono-ui inline-flex h-5 w-5 items-center justify-center rounded-full bg-accent/15 text-[10px] font-semibold text-accent">
        {number}
      </span>
      <p className="font-mono-ui text-[11px] uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
    </div>
  );
}

function getProductFamily(product: string): string {
  const normalized = product.toLowerCase();

  if (normalized.includes("family office") || normalized.includes("wealth")) {
    return "Wealth Management";
  }
  if (normalized.includes("private banking")) {
    return "Private Banking";
  }
  if (normalized.includes("portfolio") || normalized.includes("investment")) {
    return "Investments";
  }
  if (
    normalized.includes("mortgage") ||
    normalized.includes("financing") ||
    normalized.includes("loan")
  ) {
    return "Lending";
  }
  if (
    normalized.includes("tax") ||
    normalized.includes("estate") ||
    normalized.includes("advisory") ||
    normalized.includes("philanthropy")
  ) {
    return "Advisory";
  }
  if (normalized.includes("card")) {
    return "Cards & Payments";
  }
  if (normalized.includes("account") || normalized.includes("savings")) {
    return "Accounts";
  }

  return "Specialty Services";
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
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
  });
}

function formatMonthDay(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}
