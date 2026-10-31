package com.secondline.ledger;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.SQLException;
import javax.sql.DataSource;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.Test;

/** OM-03 ADR-019 SEC-12: the running ledger can't rewrite its own schema; only ledger_migrator can. */
class OM_03_RolesTest {

    @BeforeAll
    static void schema() {
        LedgerDb.migrate();
    }

    static void exec(DataSource ds, String sql) throws SQLException {
        try (var c = ds.getConnection(); var st = c.createStatement()) {
            st.execute(sql);
        }
    }

    static String query(DataSource ds, String sql) throws SQLException {
        try (var c = ds.getConnection(); var st = c.createStatement(); var rs = st.executeQuery(sql)) {
            rs.next();
            return rs.getString(1);
        }
    }

    @Test
    void OM_03_appCannotDropSchemaOrDisableTriggers() {
        assertThatThrownBy(() -> exec(LedgerDb.app(), "DROP SCHEMA ledger CASCADE"))
                .isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("42501");
        assertThatThrownBy(() -> exec(LedgerDb.app(), "ALTER TABLE ledger.namespaces DISABLE TRIGGER ALL"))
                .isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("42501");
    }

    @Test
    void OM_03_appCannotCreateTables() {
        assertThatThrownBy(() -> exec(LedgerDb.app(), "CREATE TABLE ledger.x (i int)"))
                .isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("42501");
    }

    @Test
    void OM_03_migratorOwnsSchemaAndTables() throws SQLException {
        assertThat(query(LedgerDb.superuser(), "SELECT nspowner::regrole::text FROM pg_namespace WHERE nspname = 'ledger'"))
                .isEqualTo("ledger_migrator");
        assertThat(query(LedgerDb.superuser(),
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'ledger' AND tableowner <> 'ledger_migrator'"))
                .isEqualTo("0");
    }

    @Test
    void OM_03_migrationsApplyCleanly() throws SQLException {
        assertThat(LedgerDb.migrate()).isZero();
        assertThat(query(LedgerDb.superuser(), "SELECT count(*) FROM ledger.flyway_schema_history WHERE NOT success"))
                .isEqualTo("0");
    }

    @Test
    void OM_03_appCannotForgeMigrationHistory() {
        // A forged "applied" row would make Flyway skip a later (e.g. hardening) migration.
        assertThatThrownBy(() -> exec(LedgerDb.app(),
                "INSERT INTO ledger.flyway_schema_history (installed_rank, version, description, type, script,"
                        + " installed_by, execution_time, success) VALUES (999, '999', 'x', 'SQL', 'x', 'x', 0, true)"))
                .isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("42501");
    }

    @Test
    void OM_03_tablesCreatedBySuperuserGiveTheAppNoUpdateOrDelete() throws SQLException {
        // ADR-019 "never DELETE" must hold even for a table someone creates as postgres in schema ledger.
        exec(LedgerDb.superuser(), "CREATE TABLE ledger.om03_superuser_probe (ns uuid PRIMARY KEY)");
        try {
            assertThatThrownBy(() -> exec(LedgerDb.app(), "DELETE FROM ledger.om03_superuser_probe"))
                    .isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("42501");
            assertThatThrownBy(() -> exec(LedgerDb.app(), "UPDATE ledger.om03_superuser_probe SET ns = ns"))
                    .isInstanceOf(SQLException.class).extracting("SQLState").isEqualTo("42501");
        } finally {
            exec(LedgerDb.superuser(), "DROP TABLE ledger.om03_superuser_probe");
        }
    }

    @Test
    void OM_03_appCanReadAndInsertNamespaces() {
        assertThat(LedgerDb.newNamespace()).isNotNull();
    }
}
