# syntax=docker/dockerfile:1
FROM maven:3.9-eclipse-temurin-26 AS build
WORKDIR /build
COPY pom.xml .
RUN mvn -B -q dependency:go-offline
COPY src ./src
RUN mvn -B -q -DskipTests package && cp target/nexusai-backend-*.jar app.jar

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
