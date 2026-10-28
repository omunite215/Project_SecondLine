#!/bin/sh
# OM-01: login users for the group roles in 00-roles.sql. Passwords come from .env (make bootstrap) via the
# container environment and are passed as psql variables, never written to a file or the command line.
set -eu
psql -v ON_ERROR_STOP=1 -U postgres -d "$POSTGRES_DB" \
  -v ledger_pw="$LEDGER_SVC_PASSWORD" -v grader_pw="$GRADER_SVC_PASSWORD" -v operator_pw="$OPERATOR_SVC_PASSWORD" <<'SQL'
CREATE ROLE ledger_svc   LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'ledger_pw'   IN ROLE ledger_app;
CREATE ROLE grader_svc   LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'grader_pw'   IN ROLE grader_ro;
CREATE ROLE operator_svc LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'operator_pw' IN ROLE operator;
SQL
