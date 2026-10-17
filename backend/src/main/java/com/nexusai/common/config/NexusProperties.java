package com.nexusai.common.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/** Typed view of contract section 11 (backend variables). All values come from the environment. */
@ConfigurationProperties(prefix = "nexus")
public record NexusProperties(Jwt jwt, boolean cookieSecure, boolean registrationOpen, int bcryptStrength, Admin admin,
                              String internalApiKey, Ai ai, Upload upload, String corsAllowedOrigins, RateLimit rateLimit,
                              Sweeper sweeper, boolean docsPublic) {
    public record Jwt(String secret, int accessMinutes, int refreshDays) { }
    public record Admin(String email, String password) { }
    public record Ai(String url, int connectTimeoutMs, int ingestTimeoutSec, int defaultTimeoutSec) { }
    public record Upload(String dir, int maxMb, int maxDocsTotal, int ingestConcurrency) { }
    public record RateLimit(int authPerMin, int uploadPerMin, int investigationStartPerMin) { }
    public record Sweeper(long intervalMs, int stuckIngestingMinutes) { }
}
