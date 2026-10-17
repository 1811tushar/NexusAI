package com.nexusai.common.security;

import com.nexusai.common.config.NexusProperties;
import com.nexusai.user.Role;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import io.jsonwebtoken.security.Keys;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.Date;
import java.util.UUID;
import javax.crypto.SecretKey;
import org.springframework.stereotype.Component;

@Component
public class JwtUtil {
    private static final String ISSUER = "nexusai";
    private final SecretKey key;
    private final Duration accessTtl;

    public JwtUtil(NexusProperties props) {
        String secret = props.jwt().secret();
        if (secret == null || secret.getBytes(StandardCharsets.UTF_8).length < 32) {
            throw new IllegalStateException("JWT_SECRET must be at least 32 bytes");
        }
        this.key = Keys.hmacShaKeyFor(secret.getBytes(StandardCharsets.UTF_8));
        this.accessTtl = Duration.ofMinutes(props.jwt().accessMinutes());
    }

    public String createAccessToken(long userId, Role role, UUID sessionId) {
        Instant now = Instant.now();
        return Jwts.builder().issuer(ISSUER).subject(Long.toString(userId)).claim("role", role.name()).claim("sid", sessionId.toString())
                .issuedAt(Date.from(now)).expiration(Date.from(now.plus(accessTtl))).signWith(key, Jwts.SIG.HS256).compact();
    }

    /** @throws io.jsonwebtoken.ExpiredJwtException when expired; other JwtException/IllegalArgumentException when invalid. */
    public AuthenticatedUser parse(String token) {
        Claims c = Jwts.parser().verifyWith(key).requireIssuer(ISSUER).build().parseSignedClaims(token).getPayload();
        try {
            return new AuthenticatedUser(Long.parseLong(c.getSubject()), Role.valueOf(c.get("role", String.class)), UUID.fromString(c.get("sid", String.class)));
        } catch (RuntimeException e) {
            throw new JwtException("Malformed claims", e);
        }
    }

    public long accessTtlSeconds() { return accessTtl.toSeconds(); }
}
