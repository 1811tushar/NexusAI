# syntax=docker/dockerfile:1
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build
COPY pom.xml .
# Maven Central occasionally answers 502/503: retry a few times before failing the build.
RUN for i in 1 2 3 4; do mvn -B -q dependency:go-offline && exit 0; echo "mvn go-offline attempt $i failed, retrying"; sleep $((i*15)); done; exit 1
COPY src ./src
# Image build does not need test sources: skip their compilation as well (tests run in backend-ci).
RUN for i in 1 2 3; do mvn -B -q -Dmaven.test.skip=true package && cp target/nexusai-backend-*.jar app.jar && exit 0; echo "mvn package attempt $i failed, retrying"; sleep $((i*15)); done; exit 1

FROM eclipse-temurin:21-jre
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system nexus && useradd --system --gid nexus --home /app nexus \
    && mkdir -p /data/uploads && chown -R nexus:nexus /data
WORKDIR /app
COPY --from=build /build/app.jar app.jar
USER nexus
ENV SPRING_PROFILES_ACTIVE=prod UPLOAD_DIR=/data/uploads JAVA_OPTS="-XX:MaxRAMPercentage=75"
EXPOSE 8080
HEALTHCHECK --interval=15s --timeout=5s --start-period=60s --retries=5 \
  CMD curl -fsS http://localhost:8080/actuator/health || exit 1
ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar app.jar"]
