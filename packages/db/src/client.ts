import { createClient, SupabaseClient } from "@supabase/supabase-js";

let supabaseClient: SupabaseClient | null = null;

export interface DatabaseConfig {
  url: string;
  anonKey?: string;
  serviceRoleKey?: string;
}

/**
 * Get or create a Supabase client instance
 */
export function getSupabaseClient(config?: DatabaseConfig): SupabaseClient {
  if (supabaseClient) {
    return supabaseClient;
  }

  const url = config?.url ?? process.env.NEXT_PUBLIC_SUPABASE_URL ?? process.env.SUPABASE_URL;
  const key =
    config?.serviceRoleKey ??
    config?.anonKey ??
    process.env.SUPABASE_SERVICE_ROLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url || !key) {
    throw new Error("Missing Supabase URL or key. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.");
  }

  supabaseClient = createClient(url, key, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });

  return supabaseClient;
}

/**
 * Create a new Supabase client (does not cache)
 */
export function createSupabaseClient(config: DatabaseConfig): SupabaseClient {
  const key = config.serviceRoleKey ?? config.anonKey;
  if (!key) {
    throw new Error("Either serviceRoleKey or anonKey must be provided");
  }

  return createClient(config.url, key, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}

/**
 * Reset the cached client (useful for testing)
 */
export function resetSupabaseClient(): void {
  supabaseClient = null;
}
