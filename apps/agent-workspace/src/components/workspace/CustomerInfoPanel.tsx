"use client";

import { useCustomer } from "@/lib/use-customer";
import type { Customer, CustomerInteraction } from "@voicebridge/contracts";
import type { PanelVariant } from "@/lib/use-phase";

interface CustomerInfoPanelProps {
  customerId: string | null;
  isConnected: boolean;
  variant?: PanelVariant;
  onToggle?: () => void;
}

export function CustomerInfoPanel({
  customerId,
  isConnected,
  variant = "expanded",
  onToggle,
}: CustomerInfoPanelProps) {
  const { customer, interactions, isLoading } = useCustomer(customerId);

  if (variant === "compact") {
    return (
      <button
        onClick={onToggle}
        className="panel-morph flex w-full items-center gap-3 rounded-2xl border border-border/60 bg-card px-4 py-3 text-left shadow-sm hover:shadow-md transition-shadow"
      >
        {customer ? (
          <>
            <span className="flex h-8 w-8 items-center justify-center rounded-full gradient-accent text-xs font-medium text-white">
              {customer.name
                .split(" ")
                .map((n) => n[0])
                .join("")
                .slice(0, 2)}
            </span>
            <span className="text-sm font-medium text-foreground">
              {customer.name}
            </span>
            <ClassificationBadge classification={customer.classification} />
            {customer.products.length > 0 && (
              <span className="rounded-lg bg-accent/10 px-2 py-0.5 text-xs text-accent">
                {customer.products.length} products
              </span>
            )}
          </>
        ) : (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="text-sm text-muted-foreground">Customer Info</span>
          </>
        )}
      </button>
    );
  }

  return (
    <div className="panel-morph flex h-full flex-col">
      {/* Header */}
      <button
        onClick={onToggle}
        disabled={!onToggle}
        className="flex items-center justify-between border-b border-border/60 px-5 py-4 text-left disabled:cursor-default"
      >
        <span className="font-mono-ui flex items-center gap-2 text-sm uppercase tracking-wide text-muted-foreground">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Customer Info
        </span>
        {customer && (
          <span className="text-sm text-muted-foreground">
            {interactions.length} interactions
          </span>
        )}
      </button>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-muted-foreground">Loading...</p>
          </div>
        ) : !customer ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-center text-sm text-muted-foreground">
              {isConnected
                ? "No customer linked to this session"
                : "Connect to a call to view customer info"}
            </p>
          </div>
        ) : (
          <div className="space-y-6">
            {/* Customer Profile */}
            <CustomerProfile customer={customer} />

            {/* Previous Interactions */}
            {interactions.length > 0 && (
              <div className="space-y-3">
                <h3 className="text-sm font-medium text-muted-foreground">
                  Previous Interactions
                </h3>
                <div className="space-y-2">
                  {interactions.map((interaction) => (
                    <InteractionCard
                      key={interaction.id}
                      interaction={interaction}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

const classificationStyles = {
  basis: "border-blue-500/50 bg-blue-500/5 text-blue-600",
  affluent: "border-purple-500/50 bg-purple-500/5 text-purple-600",
  HNWI: "border-amber-500/50 bg-amber-500/5 text-amber-600",
  UHNWI: "border-rose-500/50 bg-rose-500/5 text-rose-600",
};

function ClassificationBadge({
  classification,
}: {
  classification: Customer["classification"];
}) {
  return (
    <span
      className={`font-mono-ui rounded-lg border px-2 py-0.5 text-xs font-medium ${classificationStyles[classification]}`}
    >
      {classification}
    </span>
  );
}

function CustomerProfile({ customer }: { customer: Customer }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">
            {customer.name}
          </h3>
          <p className="font-mono-ui text-xs text-muted-foreground capitalize">
            {customer.gender}
          </p>
        </div>
        <ClassificationBadge classification={customer.classification} />
      </div>

      <div className="grid grid-cols-2 gap-x-4 gap-y-2.5 text-sm">
        {customer.email && (
          <>
            <span className="text-muted-foreground">Email</span>
            <span className="font-medium text-right">{customer.email}</span>
          </>
        )}
        {customer.phone && (
          <>
            <span className="text-muted-foreground">Phone</span>
            <span className="font-medium text-right">{customer.phone}</span>
          </>
        )}
        <span className="text-muted-foreground">Customer since</span>
        <span className="font-medium text-right">
          {new Date(customer.customerSince).toLocaleDateString(undefined, {
            year: "numeric",
            month: "short",
          })}
        </span>
        <span className="text-muted-foreground">Language</span>
        <span className="font-mono-ui font-medium uppercase text-right">
          {customer.preferredLanguage}
        </span>
      </div>

      {customer.products.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">Products</p>
          <div className="flex flex-wrap gap-1.5">
            {customer.products.map((product, idx) => (
              <span
                key={idx}
                className="rounded-lg bg-accent/10 px-2.5 py-1 text-xs text-accent"
              >
                {product}
              </span>
            ))}
          </div>
        </div>
      )}

      {customer.notes && (
        <div className="space-y-2">
          <p className="text-sm font-medium text-muted-foreground">Notes</p>
          <p className="text-sm text-foreground leading-relaxed">
            {customer.notes}
          </p>
        </div>
      )}
    </div>
  );
}

function InteractionCard({
  interaction,
}: {
  interaction: CustomerInteraction;
}) {
  const typeConfig = {
    phone: { icon: "📞", label: "Phone", color: "from-info/20 to-transparent" },
    chat: {
      icon: "💬",
      label: "Chat",
      color: "from-success/20 to-transparent",
    },
    branch_visit: {
      icon: "🏦",
      label: "Branch Visit",
      color: "from-warning/20 to-transparent",
    },
    email: {
      icon: "✉️",
      label: "Email",
      color: "from-accent/20 to-transparent",
    },
  };

  const config = typeConfig[interaction.type as keyof typeof typeConfig] ?? {
    icon: "📋",
    label: interaction.type,
    color: "from-muted to-transparent",
  };

  return (
    <div
      className={`rounded-xl border border-border/60 bg-gradient-to-r ${config.color} p-3 border-l-2 border-l-accent/40 shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all`}
    >
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-accent/10 text-sm">
            {config.icon}
          </span>
          <span className="font-mono-ui text-xs font-medium uppercase tracking-wide text-foreground">
            {config.label}
          </span>
          {interaction.channelDetail && (
            <span className="text-xs text-muted-foreground">
              • {interaction.channelDetail}
            </span>
          )}
        </div>
        <span className="font-mono-ui text-xs text-muted-foreground">
          {new Date(interaction.date).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })}
        </span>
      </div>

      <p className="mb-1 text-sm text-foreground leading-relaxed">
        {interaction.summary}
      </p>

      {interaction.outcome && (
        <p className="text-xs text-muted-foreground">
          Outcome: {interaction.outcome}
        </p>
      )}

      {interaction.agentName && (
        <p className="mt-1 text-xs text-muted-foreground">
          Agent: {interaction.agentName}
        </p>
      )}
    </div>
  );
}
