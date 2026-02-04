-- Process catalog table
CREATE TABLE process_catalog (
    process_key TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL,
    queue_tag TEXT,
    locale TEXT NOT NULL DEFAULT 'en',
    version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    process_text TEXT NOT NULL,
    steps_json JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for process_catalog
CREATE INDEX idx_process_catalog_status_locale ON process_catalog(status, locale);
CREATE INDEX idx_process_catalog_domain_queue ON process_catalog(domain, queue_tag);
CREATE INDEX idx_process_catalog_name_trgm ON process_catalog USING GIN (name gin_trgm_ops);

-- Full-text search index on process_text
CREATE INDEX idx_process_catalog_fts ON process_catalog
    USING GIN (to_tsvector('simple', process_text));

-- KB snippets table
CREATE TABLE kb_snippets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    process_key TEXT NOT NULL REFERENCES process_catalog(process_key) ON DELETE CASCADE,
    step_key TEXT,
    intent_key TEXT,
    template TEXT NOT NULL,
    constraints JSONB,
    priority INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kb_snippets_process_key ON kb_snippets(process_key);
CREATE INDEX idx_kb_snippets_step_key ON kb_snippets(process_key, step_key) WHERE step_key IS NOT NULL;
CREATE INDEX idx_kb_snippets_intent_key ON kb_snippets(intent_key) WHERE intent_key IS NOT NULL;

-- Apply updated_at trigger to process_catalog
CREATE TRIGGER update_process_catalog_updated_at
    BEFORE UPDATE ON process_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply updated_at trigger to kb_snippets
CREATE TRIGGER update_kb_snippets_updated_at
    BEFORE UPDATE ON kb_snippets
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Enable RLS
ALTER TABLE process_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE kb_snippets ENABLE ROW LEVEL SECURITY;

-- RLS Policies for process_catalog (read-only for all)
CREATE POLICY "Anyone can view active processes"
    ON process_catalog FOR SELECT
    USING (status = 'active');

CREATE POLICY "Service can manage processes"
    ON process_catalog FOR ALL
    USING (true);

-- RLS Policies for kb_snippets (read-only for all)
CREATE POLICY "Anyone can view kb snippets"
    ON kb_snippets FOR SELECT
    USING (true);

CREATE POLICY "Service can manage kb snippets"
    ON kb_snippets FOR ALL
    USING (true);

-- Function for full-text search with ranking
CREATE OR REPLACE FUNCTION search_processes(
    search_query TEXT,
    search_locale TEXT DEFAULT 'en',
    search_domain TEXT DEFAULT NULL,
    search_queue_tag TEXT DEFAULT NULL,
    result_limit INTEGER DEFAULT 5
)
RETURNS TABLE (
    process_key TEXT,
    name TEXT,
    domain TEXT,
    queue_tag TEXT,
    locale TEXT,
    version TEXT,
    status TEXT,
    process_text TEXT,
    steps_json JSONB,
    updated_at TIMESTAMPTZ,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        pc.process_key,
        pc.name,
        pc.domain,
        pc.queue_tag,
        pc.locale,
        pc.version,
        pc.status,
        pc.process_text,
        pc.steps_json,
        pc.updated_at,
        ts_rank(
            to_tsvector('simple', pc.process_text),
            plainto_tsquery('simple', search_query)
        ) +
        CASE WHEN pc.name ILIKE '%' || search_query || '%' THEN 0.5 ELSE 0 END +
        similarity(pc.name, search_query) * 0.3 AS rank
    FROM process_catalog pc
    WHERE
        pc.status = 'active'
        AND pc.locale = search_locale
        AND (search_domain IS NULL OR pc.domain = search_domain)
        AND (search_queue_tag IS NULL OR pc.queue_tag = search_queue_tag)
        AND (
            to_tsvector('simple', pc.process_text) @@ plainto_tsquery('simple', search_query)
            OR pc.name ILIKE '%' || search_query || '%'
            OR similarity(pc.name, search_query) > 0.3
        )
    ORDER BY rank DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Insert sample process data for testing
INSERT INTO process_catalog (process_key, name, domain, queue_tag, locale, version, status, process_text, steps_json) VALUES
(
    'billing-dispute',
    'Billing Dispute Resolution',
    'billing',
    'billing-support',
    'en',
    '1.0.0',
    'active',
    'Handle customer billing disputes and charge corrections. This process covers unauthorized charges, duplicate billing, incorrect amounts, and refund requests. Agent should verify account ownership, review transaction history, identify the disputed charges, and process appropriate adjustments or escalate to billing specialists.',
    '[
        {"key": "verify-identity", "label": "Verify Customer Identity", "description": "Confirm account ownership with security questions"},
        {"key": "identify-charge", "label": "Identify Disputed Charge", "description": "Locate the specific transaction in question"},
        {"key": "review-history", "label": "Review Transaction History", "description": "Check for patterns or related transactions"},
        {"key": "determine-resolution", "label": "Determine Resolution", "description": "Decide on refund, credit, or escalation"},
        {"key": "process-adjustment", "label": "Process Adjustment", "description": "Apply the approved resolution"},
        {"key": "confirm-resolution", "label": "Confirm with Customer", "description": "Verify customer satisfaction with outcome"}
    ]'::jsonb
),
(
    'account-password-reset',
    'Account Password Reset',
    'account',
    'account-support',
    'en',
    '1.0.0',
    'active',
    'Assist customers with password reset and account recovery. Process includes identity verification, security question validation, email/SMS verification, and password reset link generation. Handle locked accounts and suspicious activity flags.',
    '[
        {"key": "verify-identity", "label": "Verify Identity", "description": "Confirm customer identity through security questions"},
        {"key": "check-account-status", "label": "Check Account Status", "description": "Review any locks or security flags"},
        {"key": "send-reset-link", "label": "Send Reset Link", "description": "Generate and send password reset email/SMS"},
        {"key": "confirm-reset", "label": "Confirm Reset Complete", "description": "Verify customer can access account"}
    ]'::jsonb
),
(
    'order-status-inquiry',
    'Order Status Inquiry',
    'orders',
    'order-support',
    'en',
    '1.0.0',
    'active',
    'Provide customers with order status updates and shipping information. Look up orders by order number, email, or phone. Provide tracking numbers, estimated delivery dates, and handle delivery issues like delays or missing packages.',
    '[
        {"key": "locate-order", "label": "Locate Order", "description": "Find order in system by order number or customer info"},
        {"key": "provide-status", "label": "Provide Current Status", "description": "Share order status and tracking information"},
        {"key": "address-concerns", "label": "Address Concerns", "description": "Handle any issues with the order"},
        {"key": "set-expectations", "label": "Set Expectations", "description": "Confirm delivery timeline and next steps"}
    ]'::jsonb
),
(
    'product-return',
    'Product Return Request',
    'orders',
    'returns-support',
    'en',
    '1.0.0',
    'active',
    'Process product return requests and exchanges. Verify return eligibility based on return policy, generate return labels, process refunds or exchanges, and handle exceptions for damaged or defective items.',
    '[
        {"key": "verify-purchase", "label": "Verify Purchase", "description": "Confirm original order and purchase date"},
        {"key": "check-eligibility", "label": "Check Return Eligibility", "description": "Verify item is within return window and policy"},
        {"key": "determine-type", "label": "Determine Return Type", "description": "Refund, exchange, or store credit"},
        {"key": "generate-label", "label": "Generate Return Label", "description": "Create prepaid shipping label if applicable"},
        {"key": "process-return", "label": "Process Return", "description": "Complete return in system"},
        {"key": "confirm-next-steps", "label": "Confirm Next Steps", "description": "Explain refund timeline and process"}
    ]'::jsonb
),
(
    'technical-troubleshooting',
    'Technical Troubleshooting',
    'technical',
    'tech-support',
    'en',
    '1.0.0',
    'active',
    'Diagnose and resolve technical issues with products or services. Guide customers through troubleshooting steps, check system status, identify known issues, and escalate to tier 2 support when needed. Cover connectivity issues, software problems, and hardware diagnostics.',
    '[
        {"key": "gather-info", "label": "Gather Issue Details", "description": "Understand the technical problem and symptoms"},
        {"key": "check-status", "label": "Check System Status", "description": "Verify no known outages or issues"},
        {"key": "basic-troubleshoot", "label": "Basic Troubleshooting", "description": "Guide through standard resolution steps"},
        {"key": "advanced-diagnosis", "label": "Advanced Diagnosis", "description": "Deeper technical investigation if needed"},
        {"key": "resolve-or-escalate", "label": "Resolve or Escalate", "description": "Fix issue or escalate to specialists"},
        {"key": "confirm-resolution", "label": "Confirm Resolution", "description": "Verify issue is resolved"}
    ]'::jsonb
);

-- Insert sample KB snippets
INSERT INTO kb_snippets (process_key, step_key, intent_key, template, constraints, priority) VALUES
(
    'billing-dispute',
    'verify-identity',
    'greeting',
    'I''d be happy to help you with that billing concern. For security purposes, could you please verify the last four digits of the card on file and your billing zip code?',
    '{"requires": ["account_verified"]}',
    10
),
(
    'billing-dispute',
    'identify-charge',
    'locate-transaction',
    'I can see the charge you''re referring to. It shows as {{merchant_name}} for {{amount}} on {{date}}. Is this the transaction you''d like to dispute?',
    '{"requires": ["transaction_found"]}',
    10
),
(
    'billing-dispute',
    'process-adjustment',
    'approve-refund',
    'I''ve processed a refund of {{amount}} to your account. You should see this reflected within 3-5 business days.',
    '{"requires": ["refund_approved"]}',
    10
),
(
    'account-password-reset',
    'verify-identity',
    'security-question',
    'Thank you for that information. As an additional security step, could you please tell me {{security_question}}?',
    '{}',
    10
),
(
    'account-password-reset',
    'send-reset-link',
    'confirm-email',
    'I''ll send a password reset link to the email address ending in {{email_masked}}. The link will be valid for 24 hours.',
    '{"requires": ["identity_verified"]}',
    10
),
(
    'order-status-inquiry',
    'provide-status',
    'in-transit',
    'Great news! Your order is currently in transit. According to the tracking, it''s expected to arrive by {{delivery_date}}. Would you like me to send you the tracking link?',
    '{"requires": ["order_found", "tracking_available"]}',
    10
),
(
    'product-return',
    'check-eligibility',
    'within-policy',
    'Good news - your purchase from {{purchase_date}} is within our {{return_window}}-day return window. Would you like a refund to your original payment method or an exchange?',
    '{"requires": ["purchase_verified"]}',
    10
),
(
    'technical-troubleshooting',
    'basic-troubleshoot',
    'restart-device',
    'Let''s try a quick restart first. Please turn off your {{device_type}}, wait 30 seconds, then turn it back on. Let me know once it''s back up.',
    '{}',
    5
);
