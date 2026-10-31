-- OM-01 §7 §9 (golden rules 1 + 4): schemas and group roles. Runs once, on an empty data volume.
-- ledger : financial state. Schema + tables owned by ledger_migrator (Flyway only, ADR-019); the running
--          ledger (ledger_app) gets DML only, so it can't drop, alter or un-trigger its own tables.
-- audit  : receipts, append-only from the ledger (INSERT + SELECT; tables owned by postgres, never ledger_app).
-- eval   : hidden truth + grades, readable only by grader_ro. Never ledger_app, never operator (console).
\set ON_ERROR_STOP on

REVOKE ALL ON SCHEMA public FROM PUBLIC;

CREATE ROLE ledger_migrator NOLOGIN;
CREATE ROLE ledger_app NOLOGIN;
CREATE ROLE grader_ro  NOLOGIN;
CREATE ROLE operator   NOLOGIN;

CREATE SCHEMA ledger AUTHORIZATION ledger_migrator;
CREATE SCHEMA audit;
CREATE SCHEMA eval;
REVOKE ALL ON SCHEMA ledger, audit, eval FROM PUBLIC;

GRANT USAGE ON SCHEMA ledger TO ledger_app, grader_ro, operator;
GRANT USAGE ON SCHEMA audit  TO ledger_app, grader_ro, operator;
GRANT USAGE ON SCHEMA eval   TO grader_ro;

-- Tables created later (migrations, tests) get these grants automatically.
-- Ledger tables: the app may read and append. UPDATE is granted per table in migrations (mutable read
-- models only, e.g. breaks.state_version); DELETE never. Journals stay append-only even without the trigger.
ALTER DEFAULT PRIVILEGES FOR ROLE ledger_migrator IN SCHEMA ledger GRANT SELECT, INSERT ON TABLES TO ledger_app;
ALTER DEFAULT PRIVILEGES FOR ROLE ledger_migrator IN SCHEMA ledger GRANT USAGE ON SEQUENCES TO ledger_app;
ALTER DEFAULT PRIVILEGES FOR ROLE ledger_migrator IN SCHEMA ledger GRANT SELECT ON TABLES TO grader_ro, operator;
-- (No DML default for tables postgres creates in ledger: ADR-019 "never DELETE" holds for those too.)
ALTER DEFAULT PRIVILEGES FOR ROLE postgres   IN SCHEMA ledger GRANT SELECT ON TABLES TO grader_ro, operator;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres   IN SCHEMA audit  GRANT SELECT, INSERT ON TABLES TO ledger_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres   IN SCHEMA audit  GRANT USAGE ON SEQUENCES TO ledger_app;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres   IN SCHEMA audit  GRANT SELECT ON TABLES TO grader_ro, operator;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres   IN SCHEMA eval   GRANT SELECT ON TABLES TO grader_ro;
