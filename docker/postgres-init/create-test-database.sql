-- Runs once, when the Compose volume is created: a separate database for the integration
-- tests (TEST_DATABASE_URL=postgresql+psycopg://tracker:tracker@localhost:5432/tracker_test),
-- so they never drop the app's own tables.
CREATE DATABASE tracker_test;
