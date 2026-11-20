plugins {
    alias(libs.plugins.spring.boot)
}

dependencies {
    implementation(project(":libs:contracts-java"))
    implementation(libs.spring.boot.starter.web)
    implementation(libs.spring.boot.starter.actuator)
    implementation(libs.spring.boot.starter.jdbc)
    // OM-07: one filter chain per realm; the gateway service JWT is Ed25519 (Nimbus needs Tink for OKP).
    implementation(libs.spring.boot.starter.security)
    implementation(libs.nimbus.jose.jwt)
    implementation(libs.tink)
    implementation(libs.flyway.core)
    implementation(libs.flyway.database.postgresql)
    runtimeOnly(libs.postgresql)
    testImplementation(libs.postgresql)
    testImplementation(libs.testcontainers.postgresql)
    testImplementation(libs.testcontainers.junit.jupiter)
    testImplementation(libs.jqwik)
    testImplementation(libs.archunit.junit5)
    // OM-05 Task 6: the real gateway pipeline driven against the real ledger (gateway → ledger only; not the reverse).
    testImplementation(project(":services:gateway"))
    testImplementation("org.yaml:snakeyaml") // version from the Boot BOM; T-SEC-01 walks every route in ledger-*.yaml
}

tasks.bootJar {
    archiveFileName = "app.jar"
}

// LedgerDb starts Postgres with the shipped infra/db/init scripts (ADR-019).
tasks.test {
    systemProperty("repo.root", rootProject.projectDir.absolutePath)
    // JDK HttpServer stubs: without TCP_NODELAY each round trip stalls ~40 ms (Nagle + delayed ACK). The JDK reads this
    // once per JVM, so it must be set before the first stub starts, not inside one test class (OM-05 bench).
    systemProperty("sun.net.httpserver.nodelay", "true")
    systemProperty("contracts.root", rootProject.file("packages/contracts").absolutePath)
}
