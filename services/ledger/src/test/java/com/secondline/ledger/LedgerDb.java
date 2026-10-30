package com.secondline.ledger;

import java.nio.file.Path;
import java.util.UUID;
import javax.sql.DataSource;
import org.flywaydb.core.Flyway;
import org.postgresql.ds.PGSimpleDataSource;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.MountableFile;

/**
 * One Postgres per test JVM (Om's 16 GB laptop), initialised with the shipped infra/db/init scripts, so
 * the roles under test are the roles compose creates. Flyway runs as ledger_migrator (ADR-019).
 */
public final class LedgerDb {
    static final String APP_PW = "test-ledger-svc";
    static final String MIGRATOR_PW = "test-ledger-migrator";
    private static final PostgreSQLContainer<?> PG = start();
    private static volatile boolean migrated;

    private LedgerDb() {}

    @SuppressWarnings("resource") // singleton, stopped by Testcontainers' reaper at JVM exit
    private static PostgreSQLContainer<?> start() {
        Path init = Path.of(System.getProperty("repo.root"), "infra/db/init");
        PostgreSQLContainer<?> pg = new PostgreSQLContainer<>("postgres:17.11-alpine")
                .withDatabaseName("secondline").withUsername("postgres").withPassword("test-postgres")
                .withEnv("LEDGER_SVC_PASSWORD", APP_PW)
                .withEnv("LEDGER_MIGRATOR_PASSWORD", MIGRATOR_PW)
                .withEnv("GRADER_SVC_PASSWORD", "test-grader")
                .withEnv("OPERATOR_SVC_PASSWORD", "test-operator")
                .withCopyFileToContainer(MountableFile.forHostPath(init.resolve("00-roles.sql")),
                        "/docker-entrypoint-initdb.d/00-roles.sql")
                .withCopyFileToContainer(MountableFile.forHostPath(init.resolve("01-logins.sh"), 0755),
                        "/docker-entrypoint-initdb.d/01-logins.sh");
        pg.start();
        return pg;
    }

    public static String jdbcUrl() {
        return PG.getJdbcUrl() + (PG.getJdbcUrl().contains("?") ? "&" : "?") + "currentSchema=ledger";
    }

    private static DataSource as(String user, String password) {
        PGSimpleDataSource ds = new PGSimpleDataSource();
        ds.setUrl(jdbcUrl());
        ds.setUser(user);
        ds.setPassword(password);
        return ds;
    }

    public static DataSource app() {
        return as("ledger_svc", APP_PW);
    }

    public static DataSource migrator() {
        return as("ledger_migrator_svc", MIGRATOR_PW);
    }

    public static DataSource superuser() {
        return as("postgres", "test-postgres");
    }

    /** Applies pending migrations as ledger_migrator; returns how many ran. Safe to call from every test. */
    public static synchronized int migrate() {
        int applied = Flyway.configure().dataSource(migrator()).schemas("ledger").defaultSchema("ledger")
                .initSql("SET ROLE ledger_migrator").load().migrate().migrationsExecuted;
        migrated = true;
        return applied;
    }

    public static UUID newNamespace() {
        if (!migrated) migrate();
        UUID ns = UUID.randomUUID();
        try (var c = app().getConnection(); var st = c.prepareStatement(
                "INSERT INTO ledger.namespaces (ns, snapshot_id) VALUES (?, ?)")) {
            st.setObject(1, ns);
            st.setString(2, "sha256:" + "0".repeat(64));
            st.executeUpdate();
        } catch (java.sql.SQLException e) {
            throw new IllegalStateException(e);
        }
        return ns;
    }
}
