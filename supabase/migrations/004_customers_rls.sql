-- Enable Row Level Security on customer tables
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customer_interactions ENABLE ROW LEVEL SECURITY;

-- Customers: read-only for authenticated users, full access for service role
CREATE POLICY "Authenticated users can view customers"
    ON customers FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage customers"
    ON customers FOR ALL
    USING (auth.role() = 'service_role');

-- Customer interactions: read-only for authenticated users, full access for service role
CREATE POLICY "Authenticated users can view interactions"
    ON customer_interactions FOR SELECT
    USING (true);

CREATE POLICY "Service role can manage interactions"
    ON customer_interactions FOR ALL
    USING (auth.role() = 'service_role');
