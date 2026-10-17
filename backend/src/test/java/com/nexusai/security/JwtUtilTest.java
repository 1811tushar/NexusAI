package com.nexusai.security;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.nexusai.common.config.NexusProperties;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.common.security.JwtUtil;
import com.nexusai.user.Role;
import io.jsonwebtoken.ExpiredJwtException;
import io.jsonwebtoken.JwtException;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class JwtUtilTest {
    private static NexusProperties props(String secret, int minutes) {
        return new NexusProperties(new NexusProperties.Jwt(secret, minutes, 14), false, true, 4, new NexusProperties.Admin("", ""), "k",
                new NexusProperties.Ai("http://x", 1, 1, 1), new NexusProperties.Upload("/tmp", 20, 500, 2), "http://localhost",
                new NexusProperties.RateLimit(10, 20, 6), new NexusProperties.Sweeper(1000, 10), false);
    }
    private static final String SECRET = "unit-test-secret-0123456789abcdef-0123456789";

    @Test
    void roundTripKeepsIdRoleAndSession() {
        JwtUtil jwt = new JwtUtil(props(SECRET, 15));
        UUID sid = UUID.randomUUID();
        AuthenticatedUser u = jwt.parse(jwt.createAccessToken(42, Role.APPROVER, sid));
        assertThat(u).isEqualTo(new AuthenticatedUser(42, Role.APPROVER, sid));
    }

    @Test
    void rejectsTamperedAndForeignSignedTokens() {
        JwtUtil a = new JwtUtil(props(SECRET, 15));
        JwtUtil b = new JwtUtil(props("another-secret-0123456789abcdef-0123456789xx", 15));
        String t = a.createAccessToken(1, Role.ADMIN, UUID.randomUUID());
        assertThatThrownBy(() -> b.parse(t)).isInstanceOf(JwtException.class);
        assertThatThrownBy(() -> a.parse(t.substring(0, t.length() - 2) + "xx")).isInstanceOf(JwtException.class);
    }

    @Test
    void rejectsExpired() {
        JwtUtil jwt = new JwtUtil(props(SECRET, -1));
        String t = jwt.createAccessToken(1, Role.ADMIN, UUID.randomUUID());
        assertThatThrownBy(() -> jwt.parse(t)).isInstanceOf(ExpiredJwtException.class);
    }

    @Test
    void failsFastOnShortSecret() {
        assertThatThrownBy(() -> new JwtUtil(props("short", 15))).isInstanceOf(IllegalStateException.class);
    }
}
