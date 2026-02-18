import type {
  Customer,
  Scenario,
  ScenarioConversationStep,
} from "@voicebridge/contracts";

function formatHumanDate(value: string | null | undefined): string {
  if (!value) {
    return "";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toLocaleDateString(undefined, {
    day: "2-digit",
    month: "long",
    year: "numeric",
  });
}

function customerAddressTokens(customer: Customer) {
  const street = customer.address?.street ?? "";
  const postalCode = customer.address?.postalCode ?? "";
  const city = customer.address?.city ?? "";
  const country = customer.address?.country ?? "";
  const full = [street, [postalCode, city].filter(Boolean).join(" "), country]
    .filter(Boolean)
    .join(", ");

  return {
    street,
    postalCode,
    city,
    country,
    full,
  };
}

export function renderScenarioText(
  template: string,
  customer: Customer
): string {
  const dobHuman = formatHumanDate(customer.dateOfBirth);
  const address = customerAddressTokens(customer);

  const replacements: Array<[string, string]> = [
    ["{{customer_name}}", customer.name],
    ["{{customer_dob_human}}", dobHuman],
    ["{{customer_dob_iso}}", customer.dateOfBirth ?? ""],
    ["{{customer_address_street}}", address.street],
    ["{{customer_address_postal_code}}", address.postalCode],
    ["{{customer_address_city}}", address.city],
    ["{{customer_address_country}}", address.country],
    ["{{customer_address_full}}", address.full],
  ];

  return replacements.reduce(
    (text, [token, value]) => text.split(token).join(value),
    template
  );
}

export function renderScenarioConversation(
  scenario: Scenario,
  customer: Customer
): ScenarioConversationStep[] {
  return scenario.conversation.map((step: ScenarioConversationStep) => ({
    ...step,
    customerMsg: renderScenarioText(step.customerMsg, customer),
  }));
}

export function renderActorGuidanceTexts(
  texts: string[],
  customer: Customer
): string[] {
  return texts.map((text) => renderScenarioText(text, customer));
}
