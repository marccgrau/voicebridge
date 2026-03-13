"use client";

import { useState, useEffect } from "react";
import { supabase } from "./supabase";
import type { Customer } from "@voicebridge/contracts";

export function useCustomers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchCustomers() {
      try {
        const { data, error } = await supabase
          .from("customers")
          .select("*")
          .order("name", { ascending: true });

        if (error) {
          console.error("Failed to fetch customers:", error);
          return;
        }

        if (data) {
          const customers = data.map((row) => ({
            id: row.id as string,
            customerCode: (row.customer_code as string | null) ?? null,
            name: row.name as string,
            gender: row.gender as "male" | "female" | "other",
            dateOfBirth: (row.date_of_birth as string | null) ?? null,
            email: row.email as string | null,
            phone: row.phone as string | null,
            address: {
              street: (row.address_street as string | null) ?? null,
              postalCode: (row.address_postal_code as string | null) ?? null,
              city: (row.address_city as string | null) ?? null,
              country: (row.address_country as string | null) ?? null,
            },
            customerSince: row.customer_since as string,
            classification: row.classification as Customer["classification"],
            products: row.products as string[],
            preferredLanguage: row.preferred_language as string,
            preferredContactChannel:
              (row.preferred_contact_channel as string | null) ?? null,
            notes: row.notes as string | null,
            quickInternalNote:
              (row.quick_internal_note as string | null) ?? null,
            domain: (row.domain as string | null) ?? null,
            scenarioId: (row.scenario_id as string | null) ?? null,
          }));
          setCustomers(customers);
        }
      } catch (error) {
        console.error("Error fetching customers:", error);
      } finally {
        setIsLoading(false);
      }
    }

    fetchCustomers();
  }, []);

  return { customers, isLoading };
}
