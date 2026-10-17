-- LOCAL USE ONLY (evaluation / tests without the Spring backend): the business tables exactly as Flyway V6__create_business_data.sql (contract 10.1).
-- In the real stack Spring's Flyway creates these; do NOT run this next to Flyway. Load order: this file, then V7__seed_business_data.sql.
CREATE TABLE IF NOT EXISTS regions (id SMALLINT PRIMARY KEY, name VARCHAR(40) NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS products (id INT PRIMARY KEY, sku VARCHAR(20) NOT NULL UNIQUE, name VARCHAR(80) NOT NULL, category VARCHAR(30) NOT NULL,
  unit_price NUMERIC(10,2) NOT NULL, unit_cost NUMERIC(10,2) NOT NULL);
CREATE TABLE IF NOT EXISTS sales (id BIGSERIAL PRIMARY KEY, sale_month DATE NOT NULL, region_id SMALLINT NOT NULL REFERENCES regions(id),
  product_id INT NOT NULL REFERENCES products(id), units INT NOT NULL, revenue NUMERIC(14,2) NOT NULL, cost NUMERIC(14,2) NOT NULL,
  UNIQUE (sale_month, region_id, product_id));
CREATE TABLE IF NOT EXISTS marketing_spend (id BIGSERIAL PRIMARY KEY, month DATE NOT NULL, region_id SMALLINT NOT NULL REFERENCES regions(id),
  channel VARCHAR(30) NOT NULL, spend NUMERIC(12,2) NOT NULL, UNIQUE (month, region_id, channel));
CREATE TABLE IF NOT EXISTS customer_metrics (id BIGSERIAL PRIMARY KEY, month DATE NOT NULL, region_id SMALLINT NOT NULL REFERENCES regions(id),
  active_customers INT NOT NULL, new_customers INT NOT NULL, churned_customers INT NOT NULL, UNIQUE (month, region_id));
DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ai_readonly') THEN
  GRANT USAGE ON SCHEMA public TO ai_readonly;
  GRANT SELECT ON regions, products, sales, marketing_spend, customer_metrics TO ai_readonly; END IF; END $$;
