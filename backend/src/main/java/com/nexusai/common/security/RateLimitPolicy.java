package com.nexusai.common.security;

/** Exposed constants for the rate-limit rules (BE-PL-07). Effective limits come from NexusProperties (env). */
public final class RateLimitPolicy {
    public static final int DEFAULT_AUTH_PER_MIN = 10;
    public static final int DEFAULT_UPLOAD_PER_MIN = 20;
    public static final int DEFAULT_INVESTIGATION_START_PER_MIN = 6;

    public static final String PATH_LOGIN = "/api/auth/login";
    public static final String PATH_REGISTER = "/api/auth/register";
    public static final String PATH_REFRESH = "/api/auth/refresh";
    public static final String PATH_UPLOAD = "/api/documents";
    public static final String PATH_INVESTIGATION_START = "/api/investigations";

    private RateLimitPolicy() { }
}
