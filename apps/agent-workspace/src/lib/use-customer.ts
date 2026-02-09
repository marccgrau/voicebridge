"use client";

import { useState, useEffect } from "react";
import { supabase } from "@/lib/supabase";
import type { Customer, CustomerInteraction } from "@voicebridge/contracts";

export function useCustomer(customerId: string | null) {
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [interactions, setInteractions] = useState<CustomerInteraction[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    if (!customerId) {
      setCustomer(null);
      setInteractions([]);
      setIsLoading(false);
      return;
    }

    let isMounted = true;

    async function fetchCustomerData() {
      setIsLoading(true);
      try {
        // Fetch customer profile
        const { data: customerData, error: customerError } = await supabase
          .from("customers")
          .select("*")
          .eq("id", customerId)
          .single();

        if (customerError || !isMounted) {
          if (customerError)
            console.error("Failed to fetch customer:", customerError);
          return;
        }

        if (customerData) {
          const customer: Customer = {
            id: customerData.id,
            name: customerData.name,
            gender: customerData.gender as "male" | "female" | "other",
            email: customerData.email,
            phone: customerData.phone,
            customerSince: customerData.customer_since,
            classification:
              customerData.classification as Customer["classification"],
            products: customerData.products,
            preferredLanguage: customerData.preferred_language,
            notes: customerData.notes,
          };
          setCustomer(customer);

          // Fetch customer interactions (limit to 10 most recent)
          const { data: interactionsData, error: interactionsError } =
            await supabase
              .from("customer_interactions")
              .select("*")
              .eq("customer_id", customerId)
              .order("date", { ascending: false })
              .limit(10);

          if (!isMounted) return;

          if (interactionsError) {
            console.error("Failed to fetch interactions:", interactionsError);
            setInteractions([]);
          } else if (interactionsData) {
            const interactions: CustomerInteraction[] = interactionsData.map(
              (row) => ({
                id: row.id as string,
                customerId: row.customer_id as string,
                type: row.type as CustomerInteraction["type"],
                date: row.date as string,
                summary: row.summary as string,
                outcome: row.outcome as string | null,
                agentName: row.agent_name as string | null,
                channelDetail: row.channel_detail as string | null,
              })
            );
            setInteractions(interactions);
          }
        } else {
          setCustomer(null);
          setInteractions([]);
        }
      } catch (error) {
        console.error("Failed to fetch customer data:", error);
        if (isMounted) {
          setCustomer(null);
          setInteractions([]);
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    fetchCustomerData();

    return () => {
      isMounted = false;
    };
  }, [customerId]);

  return { customer, interactions, isLoading };
}
