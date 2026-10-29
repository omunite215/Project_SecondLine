# OM-01: multi-stage build from the repo root (make up PROFILES="core app"); the host needs no JDK.
FROM eclipse-temurin:21.0.12.1_1-jdk-noble AS build
WORKDIR /src
COPY gradlew settings.gradle.kts build.gradle.kts gradle.properties ./
COPY gradle gradle
COPY libs libs
COPY services/ledger services/ledger
COPY services/gateway services/gateway
RUN ./gradlew :services:gateway:bootJar --no-daemon -q

FROM eclipse-temurin:21.0.12.1_1-jre-noble
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
 && useradd --system --uid 10001 --no-create-home app
WORKDIR /app
COPY --from=build /src/services/gateway/build/libs/app.jar app.jar
USER app
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
