package com.nexusai.common;

import com.nexusai.common.config.NexusProperties;

/** Builds NexusProperties for plain unit tests (no Spring context). */
public final class TestProps {
    public static final String SECRET = "unit-test-secret-0123456789abcdef-0123456789";
    private TestProps() { }

    public static NexusProperties props() { return props(true, 500); }

    public static NexusProperties props(boolean registrationOpen, int maxDocs) {
        return new NexusProperties(new NexusProperties.Jwt(SECRET, 15, 14), false, registrationOpen, 4, new NexusProperties.Admin("", ""), "key",
                new NexusProperties.Ai("http://localhost:1", 1000, 5, 5), new NexusProperties.Upload("/tmp", 20, maxDocs, 2), "http://localhost",
                new NexusProperties.RateLimit(10, 20, 6), new NexusProperties.Sweeper(1000, 10), false);
    }
}
