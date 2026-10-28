"""OM-01 DB roles (§7 §9, golden rules 1 + 4): truth (eval) never readable by the ledger or the console role;
audit is append-only from the ledger; the grader only reads. Needs `make up PROFILES="core"`.
Run: python3 -m unittest discover -s tests/infra"""
import os
import subprocess
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMPOSE = ["docker", "compose", "-f", str(ROOT / "infra/compose/docker-compose.yml"),
           "--env-file", os.environ.get("ENV_FILE", str(ROOT / ".env"))]
DENIED = "permission denied"


def psql(user: str, sql: str) -> tuple[int, str]:
    r = subprocess.run(COMPOSE + ["exec", "-T", "postgres", "psql", "-v", "ON_ERROR_STOP=1", "-qtA",
                                  "-U", user, "-d", "secondline", "-c", sql],
                       capture_output=True, text=True, timeout=30)
    return r.returncode, (r.stdout + r.stderr).strip()


class DbRoles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rc, out = psql("postgres", "select 1")
        if rc != 0:
            msg = f"core stack not up (make up PROFILES=core): {out[:200]}"
            if os.environ.get("CI"):
                raise AssertionError(msg)  # CI must never skip the truth-isolation check
            raise unittest.SkipTest(msg)
        # Probes are created AFTER init, so default privileges are what's under test.
        rc, out = psql("postgres", "create table ledger.om01_probe(x int); create table audit.om01_probe(x int);"
                                   " create table eval.om01_probe(x int); insert into eval.om01_probe values (1);")
        assert rc == 0, out

    @classmethod
    def tearDownClass(cls):
        psql("postgres", "drop table if exists ledger.om01_probe, audit.om01_probe, eval.om01_probe")

    def assertDenied(self, user: str, sql: str):
        rc, out = psql(user, sql)
        self.assertNotEqual(rc, 0, f"{user} was allowed: {sql}")
        self.assertIn(DENIED, out)

    def assertAllowed(self, user: str, sql: str):
        rc, out = psql(user, sql)
        self.assertEqual(rc, 0, f"{user}: {sql}: {out}")

    def test_OM_01_schemas_exist(self):
        rc, out = psql("postgres", "select string_agg(nspname, ',' order by nspname) from pg_namespace"
                                   " where nspname in ('ledger','audit','eval')")
        self.assertEqual(out, "audit,eval,ledger")

    def test_OM_01_ledger_cannot_read_eval(self):
        self.assertDenied("ledger_svc", "select * from eval.om01_probe")

    def test_OM_01_operator_cannot_read_eval(self):
        self.assertDenied("operator_svc", "select * from eval.om01_probe")

    def test_OM_01_ledger_audit_insert_only(self):
        self.assertAllowed("ledger_svc", "insert into audit.om01_probe values (1)")
        self.assertAllowed("ledger_svc", "select * from audit.om01_probe")
        for sql in ("update audit.om01_probe set x = 2", "delete from audit.om01_probe", "truncate audit.om01_probe"):
            self.assertDenied("ledger_svc", sql)

    def test_OM_01_ledger_cannot_create_in_audit(self):
        self.assertDenied("ledger_svc", "create table audit.om01_owned(x int)")

    def test_OM_01_ledger_owns_ledger_schema(self):
        self.assertAllowed("ledger_svc", "create table ledger.om01_owned(x int); drop table ledger.om01_owned")

    def test_OM_01_grader_read_only(self):
        for schema in ("ledger", "audit", "eval"):
            self.assertAllowed("grader_svc", f"select * from {schema}.om01_probe")
            self.assertDenied("grader_svc", f"insert into {schema}.om01_probe values (9)")

    def test_OM_01_operator_reads_ledger_and_audit_only(self):
        for schema in ("ledger", "audit"):
            self.assertAllowed("operator_svc", f"select * from {schema}.om01_probe")
            self.assertDenied("operator_svc", f"insert into {schema}.om01_probe values (9)")

    def test_OM_01_public_schema_locked(self):
        for user in ("ledger_svc", "grader_svc", "operator_svc"):
            self.assertDenied(user, "create table public.om01_x(x int)")

    def test_OM_01_service_users_cannot_escalate(self):
        rc, out = psql("postgres", "select string_agg(rolname, ',') from pg_roles where rolname like '%\\_svc'"
                                   " and (rolsuper or rolcreaterole or rolcreatedb or rolbypassrls)")
        self.assertEqual(out, "")

    def test_OM_01_opa_health(self):
        with urllib.request.urlopen("http://127.0.0.1:8181/health", timeout=5) as r:
            self.assertEqual(r.status, 200)


if __name__ == "__main__":
    unittest.main()
