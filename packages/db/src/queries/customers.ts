import type { SupabaseClient } from "@supabase/supabase-js";
import type { Customer, CustomerInteraction } from "@voicebridge/contracts";

export interface CustomerRow {
  id: string;
  name: string;
  gender: string;
  email: string | null;
  phone: string | null;
  customer_since: string;
  classification: string;
  products: string[];
  preferred_language: string;
  notes: string | null;
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
    name: row.name,
    gender: row.gender as "male" | "female" | "other",
    email: row.email,
    phone: row.phone,
    customerSince: row.customer_since,
    classification: row.classification as Customer["classification"],
    products: row.products,
    preferredLanguage: row.preferred_language,
    notes: row.notes,
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
  };
}
