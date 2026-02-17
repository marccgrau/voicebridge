import type { SupabaseClient } from "@supabase/supabase-js";
import type { Customer, CustomerInteraction } from "@voicebridge/contracts";

export interface CustomerRow {
  id: string;
  customer_code: string | null;
  name: string;
  gender: string;
  date_of_birth: string | null;
  email: string | null;
  phone: string | null;
  address_street: string | null;
  address_postal_code: string | null;
  address_city: string | null;
  address_country: string | null;
  customer_since: string;
  classification: string;
  products: string[];
  preferred_language: string;
  preferred_contact_channel: string | null;
  notes: string | null;
  quick_internal_note: string | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerInteractionRow {
  id: string;
  customer_id: string;
  type: string;
  date: string;
  summary: string;
  outcome: string | null;
  agent_name: string | null;
  channel_detail: string | null;
  direction: string | null;
  topic: string | null;
  subtopic: string | null;
  sentiment: string | null;
  priority: string | null;
  owner_team: string | null;
  status: string | null;
  resolution_time_hours: number | null;
  sla_breached: boolean | null;
  follow_up_required: boolean | null;
  related_case_id: string | null;
  csat: number | null;
  created_at: string;
}

/**
 * Get customer by ID
 */
export async function getCustomer(
  client: SupabaseClient,
  customerId: string
): Promise<CustomerRow | null> {
  const { data, error } = await client
    .from("customers")
    .select("*")
    .eq("id", customerId)
    .single();

  if (error) {
    if (error.code === "PGRST116") {
      return null;
    }
    throw new Error(`Failed to get customer: ${error.message}`);
  }

  return data;
}

/**
 * Get all customers
 */
export async function getAllCustomers(
  client: SupabaseClient
): Promise<CustomerRow[]> {
  const { data, error } = await client
    .from("customers")
    .select("*")
    .order("name", { ascending: true });

  if (error) {
    throw new Error(`Failed to get customers: ${error.message}`);
  }

  return data ?? [];
}

/**
 * Get customer interactions
 */
export async function getCustomerInteractions(
  client: SupabaseClient,
  customerId: string,
  options?: { limit?: number; offset?: number }
): Promise<CustomerInteractionRow[]> {
  let query = client
    .from("customer_interactions")
    .select("*")
    .eq("customer_id", customerId)
    .order("date", { ascending: false });

  if (options?.limit) {
    query = query.limit(options.limit);
  }

  if (options?.offset) {
    query = query.range(
      options.offset,
      options.offset + (options.limit ?? 10) - 1
    );
  }

  const { data, error } = await query;

  if (error) {
    throw new Error(`Failed to get customer interactions: ${error.message}`);
  }

  return data ?? [];
}

/**
 * Convert database row to Customer
 */
export function rowToCustomer(row: CustomerRow): Customer {
  return {
    id: row.id,
    customerCode: row.customer_code,
    name: row.name,
    gender: row.gender as "male" | "female" | "other",
    dateOfBirth: row.date_of_birth,
    email: row.email,
    phone: row.phone,
    address: {
      street: row.address_street,
      postalCode: row.address_postal_code,
      city: row.address_city,
      country: row.address_country,
    },
    customerSince: row.customer_since,
    classification: row.classification as Customer["classification"],
    products: row.products,
    preferredLanguage: row.preferred_language,
    preferredContactChannel: row.preferred_contact_channel,
    notes: row.notes,
    quickInternalNote: row.quick_internal_note,
  };
}

/**
 * Convert database row to CustomerInteraction
 */
export function rowToCustomerInteraction(
  row: CustomerInteractionRow
): CustomerInteraction {
  return {
    id: row.id,
    customerId: row.customer_id,
    type: row.type as CustomerInteraction["type"],
    date: row.date,
    summary: row.summary,
    outcome: row.outcome,
    agentName: row.agent_name,
    channelDetail: row.channel_detail,
    direction: (row.direction as "inbound" | "outbound" | null) ?? null,
    topic: row.topic,
    subtopic: row.subtopic,
    sentiment: row.sentiment,
    priority: row.priority,
    ownerTeam: row.owner_team,
    status: row.status,
    resolutionTimeHours: row.resolution_time_hours,
    slaBreached: row.sla_breached,
    followUpRequired: row.follow_up_required,
    relatedCaseId: row.related_case_id,
    csat: row.csat,
  };
}
