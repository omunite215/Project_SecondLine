plugins {
    alias(libs.plugins.spring.boot)
}

dependencies {
    implementation(libs.spring.boot.starter.web)
    implementation(libs.spring.boot.starter.actuator)
    implementation(libs.spring.boot.starter.jdbc)
    implementation(libs.flyway.core)
    implementation(libs.flyway.database.postgresql)
    runtimeOnly(libs.postgresql)
    testImplementation(libs.postgresql)
    testImplementation(libs.testcontainers.postgresql)
    testImplementation(libs.testcontainers.junit.jupiter)
    testImplementation(libs.jqwik)
    testImplementation(libs.archunit.junit5)
}

tasks.bootJar {
    archiveFileName = "app.jar"
}

// LedgerDb starts Postgres with the shipped infra/db/init scripts (ADR-019).
tasks.test {
    systemProperty("repo.root", rootProject.projectDir.absolutePath)
}
