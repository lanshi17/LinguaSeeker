-- Seed data for initial setup
-- Safe inserts using NOT EXISTS to avoid duplicates

INSERT INTO users (username, email)
SELECT 'system', 'system@example.com'
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE username = 'system'
);

INSERT INTO users (username, email)
SELECT 'admin', 'admin@example.com'
WHERE NOT EXISTS (
    SELECT 1 FROM users WHERE username = 'admin'
);
