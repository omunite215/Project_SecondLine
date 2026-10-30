// Root of the Java multi-project build (OM-01). Spring Boot 3.5.x pinned in gradle/libs.versions.toml;
// 4.0.x only via ADR. Dependency versions come from the Boot BOM (no dependency-management plugin, ADR-010).
plugins {
    alias(libs.plugins.spring.boot) apply false
}

subprojects {
    apply(plugin = "java")

    extensions.configure<JavaPluginExtension> {
        toolchain.languageVersion = JavaLanguageVersion.of(rootProject.libs.versions.java.get())
    }

    dependencies {
        "implementation"(platform(org.springframework.boot.gradle.plugin.SpringBootPlugin.BOM_COORDINATES))
        "testImplementation"(rootProject.libs.spring.boot.starter.test)
        "testRuntimeOnly"(rootProject.libs.junit.platform.launcher)
    }

    tasks.withType<Test>().configureEach {
        useJUnitPlatform()
        maxHeapSize = "512m"
    }
}
