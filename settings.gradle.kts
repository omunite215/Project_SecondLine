rootProject.name = "second-line"

// One place for repositories; a subproject adding its own fails the build (dependency-source control).
dependencyResolutionManagement {
    repositoriesMode = RepositoriesMode.FAIL_ON_PROJECT_REPOS
    repositories {
        mavenCentral()
    }
}

include("services:ledger", "services:gateway", "libs:contracts-java")
