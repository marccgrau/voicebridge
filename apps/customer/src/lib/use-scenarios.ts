"use client";

import { useEffect, useState } from "react";
import type {
  Scenario,
  ScenarioConversationStep,
} from "@voicebridge/contracts";

import { supabase } from "./supabase";

interface RawScenarioRow {
  scenario_id: string;
  scenario_family: string;
  title: string;
  domain: string;
  background: string;
  customer_goal: string;
  guidelines: Record<string, unknown>;
  conversation: unknown;
  civility_condition: "civil" | "uncivil";
  behavior_instruction: string;
  status: "active" | "inactive";
}

function toConversationStep(value: unknown): ScenarioConversationStep | null {
  if (!value || typeof value !== "object") {
    return null;
  }

  const row = value as Record<string, unknown>;
  if (
    typeof row.id !== "string" ||
    typeof row.customer_msg !== "string" ||
    typeof row.actor_intent !== "string" ||
    typeof row.tone !== "string" ||
    typeof row.advice_instructional !== "string"
  ) {
    return null;
  }

  return {
    id: row.id,
    customerMsg: row.customer_msg,
    actorIntent: row.actor_intent,
    tone: row.tone,
    adviceInstructional: row.advice_instructional,
    nextId: typeof row.next_id === "string" ? row.next_id : null,
  };
}

function toScenario(row: RawScenarioRow): Scenario {
  const conversation = Array.isArray(row.conversation)
    ? row.conversation
        .map((item) => toConversationStep(item))
        .filter((item): item is ScenarioConversationStep => item !== null)
    : [];

  return {
    scenarioId: row.scenario_id,
    scenarioFamily: row.scenario_family,
    title: row.title,
    domain: row.domain,
    background: row.background,
    customerGoal: row.customer_goal,
    guidelines: row.guidelines ?? {},
    conversation,
    behavioralCondition: {
      civilityCondition: row.civility_condition,
      instruction: row.behavior_instruction,
    },
    status: row.status,
  };
}

export function useScenarios() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchScenarios() {
      try {
        const { data, error } = await supabase
          .from("scenarios")
          .select(
            "scenario_id, scenario_family, title, domain, background, customer_goal, guidelines, conversation, civility_condition, behavior_instruction, status"
          )
          .eq("status", "active")
          .order("scenario_id", { ascending: true });

        if (error) {
          setError(error.message);
          return;
        }

        const parsed = (data ?? []).map((row) =>
          toScenario(row as RawScenarioRow)
        );
        setScenarios(parsed);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to fetch scenarios"
        );
      } finally {
        setIsLoading(false);
      }
    }

    fetchScenarios();
  }, []);

  return { scenarios, isLoading, error };
}
