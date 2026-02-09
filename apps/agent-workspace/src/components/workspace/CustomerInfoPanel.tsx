"use client";

import { useCustomer } from "@/lib/use-customer";
import type { Customer, CustomerInteraction } from "@voicebridge/contracts";

interface CustomerInfoPanelProps {
  customerId: string | null;
  isConnected: boolean;
}

export function CustomerInfoPanel({
  customerId,
  isConnected,
}: CustomerInfoPanelProps) {
  const { customer, interactions, isLoading } = useCustomer(customerId);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="font-semibold">Customer Info</h2>
        {customer && (
          <span className="text-xs text-muted-foreground">
            {interactions.length} interactions
          </span>
        )}
      </div>

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
                <h3 className="text-sm font-semibold text-foreground">
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

function CustomerProfile({ customer }: { customer: Customer }) {
  const classificationStyles = {
    basis: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
    affluent: "bg-purple-500/10 text-purple-600 dark:text-purple-400",
    HNWI: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
    UHNWI: "bg-rose-500/10 text-rose-600 dark:text-rose-400",
  };

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-lg font-semibold">{customer.name}</h3>
          <p className="text-xs text-muted-foreground capitalize">
            {customer.gender}
          </p>
        </div>
        <span
          className={`rounded-full px-2.5 py-1 text-xs font-medium ${
            classificationStyles[customer.classification]
          }`}
        >
          {customer.classification}
        </span>
      </div>

      <div className="space-y-2 text-sm">
        {customer.email && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Email:</span>
            <span className="font-medium">{customer.email}</span>
          </div>
        )}
        {customer.phone && (
          <div className="flex justify-between">
            <span className="text-muted-foreground">Phone:</span>
            <span className="font-medium">{customer.phone}</span>
          </div>
        )}
        <div className="flex justify-between">
          <span className="text-muted-foreground">Customer since:</span>
          <span className="font-medium">
            {new Date(customer.customerSince).toLocaleDateString(undefined, {
              year: "numeric",
              month: "short",
            })}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-muted-foreground">Language:</span>
          <span className="font-medium uppercase">
            {customer.preferredLanguage}
          </span>
        </div>
      </div>

      {customer.products.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Products:</p>
          <div className="flex flex-wrap gap-1.5">
            {customer.products.map((product, idx) => (
              <span
                key={idx}
                className="rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground"
              >
                {product}
              </span>
            ))}
          </div>
        </div>
      )}

      {customer.notes && (
        <div className="space-y-1.5">
          <p className="text-xs font-medium text-muted-foreground">Notes:</p>
          <p className="text-sm text-foreground">{customer.notes}</p>
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
  const typeIcons = {
    phone: "📞",
    chat: "💬",
    branch_visit: "🏦",
    email: "✉️",
  };

  const typeLabels = {
    phone: "Phone",
    chat: "Chat",
    branch_visit: "Branch Visit",
    email: "Email",
  };

  return (
    <div className="rounded-lg border border-border bg-card p-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-base">
            {typeIcons[interaction.type] ?? "📋"}
          </span>
          <span className="text-xs font-medium text-foreground">
            {typeLabels[interaction.type] ?? interaction.type}
          </span>
          {interaction.channelDetail && (
            <span className="text-xs text-muted-foreground">
              • {interaction.channelDetail}
            </span>
          )}
        </div>
        <span className="text-xs text-muted-foreground">
          {new Date(interaction.date).toLocaleDateString(undefined, {
            month: "short",
            day: "numeric",
          })}
        </span>
      </div>

      <p className="mb-1 text-sm text-foreground">{interaction.summary}</p>

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
