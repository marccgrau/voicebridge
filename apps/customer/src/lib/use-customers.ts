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
            name: row.name as string,
            gender: row.gender as "male" | "female" | "other",
            email: row.email as string | null,
            phone: row.phone as string | null,
            customerSince: row.customer_since as string,
            classification: row.classification as Customer["classification"],
            products: row.products as string[],
            preferredLanguage: row.preferred_language as string,
            notes: row.notes as string | null,
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
