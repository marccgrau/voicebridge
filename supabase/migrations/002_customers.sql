-- 002_customers.sql
-- Add customers, customer_interactions tables, and customer_id to sessions

-- =============================================================================
-- CUSTOMERS TABLE
-- =============================================================================
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    gender TEXT NOT NULL CHECK (gender IN ('male', 'female', 'other')),
    email TEXT,
    phone TEXT,
    customer_since DATE NOT NULL,
    classification TEXT NOT NULL CHECK (classification IN ('basis', 'affluent', 'HNWI', 'UHNWI')),
    products JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferred_language TEXT NOT NULL DEFAULT 'de',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customers_classification ON customers(classification);

-- Reuse existing trigger for updated_at
CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- CUSTOMER INTERACTIONS TABLE
-- =============================================================================
CREATE TABLE customer_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN ('phone', 'chat', 'branch_visit', 'email')),
    date TIMESTAMPTZ NOT NULL,
    summary TEXT NOT NULL,
    outcome TEXT,
    agent_name TEXT,
    channel_detail TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customer_interactions_customer_date ON customer_interactions(customer_id, date DESC);

-- =============================================================================
-- ADD customer_id TO SESSIONS
-- =============================================================================
ALTER TABLE sessions ADD COLUMN customer_id UUID REFERENCES customers(id);
CREATE INDEX idx_sessions_customer_id ON sessions(customer_id) WHERE customer_id IS NOT NULL;

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- Customer 1: Basis classification
INSERT INTO customers (id, name, gender, email, phone, customer_since, classification, products, preferred_language, notes)
VALUES (
    'c1a1a1a1-1111-1111-1111-111111111111',
    'Anna Müller',
    'female',
    'anna.mueller@example.ch',
    '+41 79 123 4567',
    '2023-06-15',
    'basis',
    '["Savings Account", "Debit Card"]',
    'de',
    'Young professional, prefers digital banking'
);

-- Customer 2: Affluent classification
INSERT INTO customers (id, name, gender, email, phone, customer_since, classification, products, preferred_language, notes)
VALUES (
    'c2b2b2b2-2222-2222-2222-222222222222',
    'Thomas Weber',
    'male',
    'thomas.weber@example.ch',
    '+41 79 234 5678',
    '2021-03-10',
    'affluent',
    '["Savings Account", "Investment Portfolio", "Credit Card", "Mortgage"]',
    'de',
    'Entrepreneur, interested in investment opportunities'
);

-- Customer 3: HNWI classification
INSERT INTO customers (id, name, gender, email, phone, customer_since, classification, products, preferred_language, notes)
VALUES (
    'c3c3c3c3-3333-3333-3333-333333333333',
    'Sophie Dubois',
    'female',
    'sophie.dubois@example.ch',
    '+41 79 345 6789',
    '2019-11-22',
    'HNWI',
    '["Private Banking", "Investment Portfolio", "Wealth Management", "Real Estate Financing"]',
    'fr',
    'Art collector, requires personalized service'
);

-- Customer 4: HNWI classification
INSERT INTO customers (id, name, gender, email, phone, customer_since, classification, products, preferred_language, notes)
VALUES (
    'c4d4d4d4-4444-4444-4444-444444444444',
    'Marco Bianchi',
    'male',
    'marco.bianchi@example.ch',
    '+41 79 456 7890',
    '2018-07-08',
    'HNWI',
    '["Private Banking", "Investment Portfolio", "Tax Advisory", "Estate Planning"]',
    'it',
    'Business owner, interested in succession planning'
);

-- Customer 5: UHNWI classification
INSERT INTO customers (id, name, gender, email, phone, customer_since, classification, products, preferred_language, notes)
VALUES (
    'c5e5e5e5-5555-5555-5555-555555555555',
    'Elisabeth von Grünigen',
    'female',
    'elisabeth.vongruenigen@example.ch',
    '+41 79 567 8901',
    '2015-01-20',
    'UHNWI',
    '["Private Banking", "Wealth Management", "Family Office Services", "Philanthropy Advisory", "Art & Collectibles"]',
    'de',
    'Family office client, multiple entities and trusts'
);

-- =============================================================================
-- INTERACTIONS FOR ANNA MÜLLER (Basis)
-- =============================================================================
INSERT INTO customer_interactions (customer_id, type, date, summary, outcome, agent_name, channel_detail)
VALUES
    ('c1a1a1a1-1111-1111-1111-111111111111', 'chat', '2025-11-10 14:23:00+00', 'Question about online banking login', 'Resolved - password reset', 'System', 'Website Chat'),
    ('c1a1a1a1-1111-1111-1111-111111111111', 'phone', '2025-12-05 09:15:00+00', 'Inquiry about debit card fees', 'Explained fee structure', 'Maria Schmidt', NULL),
    ('c1a1a1a1-1111-1111-1111-111111111111', 'email', '2026-01-08 16:45:00+00', 'Request for account statement', 'Statement sent', 'Paul Meyer', NULL);

-- =============================================================================
-- INTERACTIONS FOR THOMAS WEBER (Affluent)
-- =============================================================================
INSERT INTO customer_interactions (customer_id, type, date, summary, outcome, agent_name, channel_detail)
VALUES
    ('c2b2b2b2-2222-2222-2222-222222222222', 'branch_visit', '2025-10-12 10:30:00+00', 'Consultation about mortgage refinancing', 'Scheduled follow-up with advisor', 'Lisa Keller', 'Zurich Main Branch'),
    ('c2b2b2b2-2222-2222-2222-222222222222', 'phone', '2025-11-18 15:20:00+00', 'Question about investment portfolio performance', 'Sent detailed report', 'Andreas Huber', NULL),
    ('c2b2b2b2-2222-2222-2222-222222222222', 'email', '2025-12-22 11:05:00+00', 'Request to increase credit limit', 'Approved - limit increased', 'Lisa Keller', NULL),
    ('c2b2b2b2-2222-2222-2222-222222222222', 'branch_visit', '2026-01-15 14:00:00+00', 'Annual portfolio review meeting', 'Rebalanced portfolio', 'Andreas Huber', 'Zurich Main Branch');

-- =============================================================================
-- INTERACTIONS FOR SOPHIE DUBOIS (HNWI)
-- =============================================================================
INSERT INTO customer_interactions (customer_id, type, date, summary, outcome, agent_name, channel_detail)
VALUES
    ('c3c3c3c3-3333-3333-3333-333333333333', 'branch_visit', '2025-09-20 09:00:00+00', 'Quarterly wealth management review', 'Asset allocation adjusted', 'Pierre Laurent', 'Geneva Private Banking'),
    ('c3c3c3c3-3333-3333-3333-333333333333', 'phone', '2025-10-28 16:30:00+00', 'Art financing inquiry for auction purchase', 'Structured financing approved', 'Pierre Laurent', NULL),
    ('c3c3c3c3-3333-3333-3333-333333333333', 'email', '2025-12-03 10:15:00+00', 'Tax optimization discussion', 'Scheduled meeting with tax advisor', 'Céline Moreau', NULL),
    ('c3c3c3c3-3333-3333-3333-333333333333', 'branch_visit', '2026-01-10 11:00:00+00', 'Review of real estate holdings', 'Diversification recommendations provided', 'Pierre Laurent', 'Geneva Private Banking'),
    ('c3c3c3c3-3333-3333-3333-333333333333', 'phone', '2026-02-01 14:45:00+00', 'Currency hedging strategy discussion', 'Implemented CHF/EUR hedge', 'Céline Moreau', NULL);

-- =============================================================================
-- INTERACTIONS FOR MARCO BIANCHI (HNWI)
-- =============================================================================
INSERT INTO customer_interactions (customer_id, type, date, summary, outcome, agent_name, channel_detail)
VALUES
    ('c4d4d4d4-4444-4444-4444-444444444444', 'branch_visit', '2025-08-15 10:00:00+00', 'Business succession planning workshop', 'Created initial succession roadmap', 'Roberto Conte', 'Lugano Private Office'),
    ('c4d4d4d4-4444-4444-4444-444444444444', 'phone', '2025-10-05 13:30:00+00', 'Tax advisory for corporate restructuring', 'Coordinated with tax specialists', 'Roberto Conte', NULL),
    ('c4d4d4d4-4444-4444-4444-444444444444', 'email', '2025-11-20 09:45:00+00', 'Estate planning documentation request', 'Documents prepared and sent', 'Giulia Rossi', NULL),
    ('c4d4d4d4-4444-4444-4444-444444444444', 'branch_visit', '2025-12-18 15:00:00+00', 'Year-end tax planning session', 'Optimized tax strategy for 2025', 'Roberto Conte', 'Lugano Private Office');

-- =============================================================================
-- INTERACTIONS FOR ELISABETH VON GRÜNIGEN (UHNWI)
-- =============================================================================
INSERT INTO customer_interactions (customer_id, type, date, summary, outcome, agent_name, channel_detail)
VALUES
    ('c5e5e5e5-5555-5555-5555-555555555555', 'branch_visit', '2025-07-10 09:00:00+00', 'Family office quarterly governance meeting', 'Updated investment policy statement', 'Dr. Hans Müller', 'Zurich Family Office'),
    ('c5e5e5e5-5555-5555-5555-555555555555', 'phone', '2025-08-22 11:30:00+00', 'Philanthropy foundation setup discussion', 'Coordinated with legal team', 'Dr. Hans Müller', NULL),
    ('c5e5e5e5-5555-5555-5555-555555555555', 'branch_visit', '2025-10-01 14:00:00+00', 'Art collection valuation and insurance review', 'Updated coverage and appraisals', 'Claudia Fischer', 'Zurich Family Office'),
    ('c5e5e5e5-5555-5555-5555-555555555555', 'email', '2025-11-12 10:00:00+00', 'Trust restructuring proposal review', 'Approved with modifications', 'Dr. Hans Müller', NULL),
    ('c5e5e5e5-5555-5555-5555-555555555555', 'branch_visit', '2026-01-20 10:00:00+00', 'Next generation wealth transfer planning', 'Educational session with heirs scheduled', 'Dr. Hans Müller', 'Zurich Family Office');
