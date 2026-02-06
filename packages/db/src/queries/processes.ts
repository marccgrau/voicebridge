import type { SupabaseClient } from "@supabase/supabase-js";
import type {
  ProcessDefinition,
  ProcessLookupOutput,
} from "@voicebridge/contracts";

export interface ProcessCatalogRow {
  process_key: string;
  name: string;
  domain: string;
  queue_tag: string | null;
  locale: string;
  version: string;
  status: string;
  process_text: string;
  steps_json: unknown;
  updated_at: string;
}

/**
 * Full-text search for processes
 */
export async function searchProcesses(
  client: SupabaseClient,
  query: string,
  options?: {
    locale?: string;
    domain?: string;
    queueTag?: string;
    limit?: number;
  }
): Promise<ProcessLookupOutput> {
  const startTime = performance.now();
  const limit = options?.limit ?? 5;

  // Build the search query using Postgres full-text search
  const rpcQuery = client.rpc("search_processes", {
    search_query: query,
    search_locale: options?.locale ?? "en",
    search_domain: options?.domain,
    search_queue_tag: options?.queueTag,
    result_limit: limit,
  });

  const { data, error } = await rpcQuery;

  if (error) {
    throw new Error(`Process search failed: ${error.message}`);
  }

  const queryTime = performance.now() - startTime;

  return {
    results: (data ?? []).map((row: ProcessCatalogRow & { rank: number }) => ({
      processKey: row.process_key,
      name: row.name,
      domain: row.domain,
      version: row.version,
      score: row.rank,
      processText: row.process_text,
      stepsJson: row.steps_json,
    })),
    queryTime,
  };
}

/**
 * Get process by key
 */
export async function getProcess(
  client: SupabaseClient,
  processKey: string
): Promise<ProcessCatalogRow | null> {
  const { data, error } = await client
    .from("process_catalog")
    .select("*")
    .eq("process_key", processKey)
    .single();

  if (error) {
    if (error.code === "PGRST116") {
      return null;
    }
    throw new Error(`Failed to get process: ${error.message}`);
  }

  return data;
}

/**
 * Convert database row to ProcessDefinition
 */
export function rowToProcessDefinition(
  row: ProcessCatalogRow
): ProcessDefinition {
  return {
    processKey: row.process_key,
    name: row.name,
    domain: row.domain,
    queueTag: row.queue_tag ?? undefined,
    locale: row.locale,
    version: row.version,
    status: row.status as "active" | "inactive",
    processText: row.process_text,
    stepsJson: row.steps_json as ProcessDefinition["stepsJson"],
    updatedAt: row.updated_at,
  };
}

/**
 * List processes by domain
 */
export async function listProcessesByDomain(
  client: SupabaseClient,
  domain: string,
  options?: {
    status?: "active" | "inactive";
    locale?: string;
  }
): Promise<ProcessCatalogRow[]> {
  let query = client.from("process_catalog").select("*").eq("domain", domain);

  if (options?.status) {
    query = query.eq("status", options.status);
  }

  if (options?.locale) {
    query = query.eq("locale", options.locale);
  }

  const { data, error } = await query.order("name");

  if (error) {
    throw new Error(`Failed to list processes: ${error.message}`);
  }

  return data ?? [];
}
