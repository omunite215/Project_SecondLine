#!/bin/sh
# OM-01: login users for the group roles in 00-roles.sql. Passwords come from .env (make bootstrap) via the
# container environment. They reach psql on stdin (\set), never argv (visible in `ps`), and the session
# raises log_min_error_statement so a failing CREATE ROLE ... PASSWORD isn't echoed into the server log.
set -eu
for pw in "$LEDGER_SVC_PASSWORD" "$GRADER_SVC_PASSWORD" "$OPERATOR_SVC_PASSWORD"; do
  case "$pw" in *\'*|*\\*|'') echo "01-logins.sh: empty password or one containing ' or \\" >&2; exit 1 ;; esac
done
psql -v ON_ERROR_STOP=1 -U postgres -d "$POSTGRES_DB" -q <<SQL
SET log_min_error_statement = panic;
\set ledger_pw '$LEDGER_SVC_PASSWORD'
\set grader_pw '$GRADER_SVC_PASSWORD'
\set operator_pw '$OPERATOR_SVC_PASSWORD'
CREATE ROLE ledger_svc   LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'ledger_pw'   IN ROLE ledger_app;
CREATE ROLE grader_svc   LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'grader_pw'   IN ROLE grader_ro;
CREATE ROLE operator_svc LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'operator_pw' IN ROLE operator;
SQL
