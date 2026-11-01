plugins {
    alias(libs.plugins.spring.boot)
}

dependencies {
    implementation(project(":libs:contracts-java"))
    implementation(libs.spring.boot.starter.web)
    implementation(libs.spring.boot.starter.actuator)
    implementation(libs.nimbus.jose.jwt)
    implementation(libs.tink)
    implementation(libs.micrometer.tracing.bridge.otel)
    testImplementation(libs.opentelemetry.sdk.testing)
}

// Gateway tests read the contracts (gateway-tools.yaml, tools/INDEX.json) straight from the repo.
tasks.test {
    systemProperty("contracts.root", rootProject.file("packages/contracts").absolutePath)
}

tasks.bootJar {
    archiveFileName = "app.jar"
}
