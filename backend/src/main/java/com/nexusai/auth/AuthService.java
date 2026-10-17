package com.nexusai.auth;

import com.nexusai.audit.AuditAction;
import com.nexusai.audit.AuditService;
import com.nexusai.common.config.NexusProperties;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.JwtUtil;
import com.nexusai.user.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;
import java.util.HexFormat;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {
    private static final Logger log = LoggerFactory.getLogger(AuthService.class);
    static final int MAX_FAILED_LOGINS = 5;
    static final Duration LOCK_DURATION = Duration.ofMinutes(15);
    private static final SecureRandom RNG = new SecureRandom();

    private final UserRepository users;
    private final RefreshTokenRepository tokens;
    private final PasswordEncoder encoder;
    private final JwtUtil jwt;
    private final NexusProperties props;
    private final AuditService audit;
    private final String dummyHash;

    public AuthService(UserRepository users, RefreshTokenRepository tokens, PasswordEncoder encoder, JwtUtil jwt, NexusProperties props,
                       AuditService audit) {
        this.users = users;
        this.tokens = tokens;
        this.encoder = encoder;
        this.jwt = jwt;
        this.props = props;
        this.audit = audit;
        this.dummyHash = encoder.encode("not-a-real-password-1");   // equalises timing for unknown accounts
    }

    @Transactional
    public AuthResult register(RegisterRequestDTO req, String userAgent) {
        if (!props.registrationOpen()) throw new ForbiddenException("Registration is closed. Ask an administrator to create your account.");
        String email = UserService.normalizeEmail(req.email());
        PasswordPolicy.validate(req.password());
        if (users.existsByEmail(email)) throw new DuplicateResourceException("An account with this email already exists");
        User u = new User();
        u.setEmail(email);
        u.setDisplayName(req.displayName().trim());
        u.setRole(Role.ANALYST);
        u.setPasswordHash(encoder.encode(req.password()));
        try {
            users.saveAndFlush(u);
        } catch (DataIntegrityViolationException e) {
            throw new DuplicateResourceException("An account with this email already exists");
        }
        audit.record(u.getId(), AuditAction.REGISTER, "USER", String.valueOf(u.getId()));
        return issue(u, UUID.randomUUID(), userAgent);
    }

    /** Failures must still commit the lockout counter, hence noRollbackFor. */
    @Transactional(noRollbackFor = InvalidCredentialsException.class)
    public AuthResult login(LoginRequestDTO req, String userAgent) {
        Instant now = Instant.now();
        User u = users.findByEmail(UserService.normalizeEmail(req.email())).orElse(null);
        if (u == null || !u.isEnabled()) {
            encoder.matches(req.password(), dummyHash);
            audit.record(u == null ? null : u.getId(), AuditAction.LOGIN_FAILURE, "USER", u == null ? null : String.valueOf(u.getId()));
            throw new InvalidCredentialsException();
        }
        if (u.getLockedUntil() != null && now.isBefore(u.getLockedUntil())) {
            encoder.matches(req.password(), dummyHash);
            audit.record(u.getId(), AuditAction.LOGIN_BLOCKED, "USER", String.valueOf(u.getId()));
            throw new InvalidCredentialsException();       // same answer as a wrong password: no account-state leak
        }
        if (!encoder.matches(req.password(), u.getPasswordHash())) {
            int failed = u.getFailedLogins() + 1;
            if (failed >= MAX_FAILED_LOGINS) {
                u.setLockedUntil(now.plus(LOCK_DURATION));
                failed = 0;
            }
            u.setFailedLogins(failed);
            users.saveAndFlush(u);
            audit.record(u.getId(), AuditAction.LOGIN_FAILURE, "USER", String.valueOf(u.getId()));
            throw new InvalidCredentialsException();
        }
        u.setFailedLogins(0);
        u.setLockedUntil(null);
        audit.record(u.getId(), AuditAction.LOGIN_SUCCESS, "USER", String.valueOf(u.getId()));
        return issue(u, UUID.randomUUID(), userAgent);
    }

    /**
     * Rotating refresh. A token presented twice (already revoked) means theft or replay: the whole family is revoked.
     * Failures commit their revocations, hence noRollbackFor.
     */
    @Transactional(noRollbackFor = {UnauthenticatedException.class, TokenExpiredException.class})
    public AuthResult refresh(String rawToken, String userAgent) {
        if (rawToken == null || rawToken.isBlank()) throw new UnauthenticatedException("No session");
        Instant now = Instant.now();
        RefreshToken t = tokens.findByTokenHash(hash(rawToken)).orElseThrow(() -> new UnauthenticatedException("Invalid session"));
        if (t.getRevokedAt() != null) {
            reuseDetected(t, now);
            throw new UnauthenticatedException("Session revoked");
        }
        if (t.getExpiresAt().isBefore(now)) throw new TokenExpiredException("Session expired");
        if (tokens.revokeIfActive(t.getId(), now) == 0) {      // lost a race against a concurrent use of the same token
            reuseDetected(t, now);
            throw new UnauthenticatedException("Session revoked");
        }
        User u = users.findById(t.getUserId()).orElse(null);
        if (u == null || !u.isEnabled()) {
            tokens.revokeFamily(t.getFamilyId(), now);
            throw new UnauthenticatedException("Account disabled");
        }
        return issue(u, t.getFamilyId(), userAgent);
    }

    @Transactional
    public void logout(String rawToken) {
        if (rawToken == null || rawToken.isBlank()) return;
        tokens.findByTokenHash(hash(rawToken)).ifPresent(t -> tokens.revokeFamily(t.getFamilyId(), Instant.now()));
    }

    /** Keeps the table small while retaining revoked rows long enough for reuse detection (they expire with the token). */
    @Scheduled(cron = "0 17 3 * * *")
    public void purgeExpired() {
        int n = tokens.deleteExpiredBefore(Instant.now().minus(Duration.ofDays(1)));
        if (n > 0) log.info("Purged {} expired refresh tokens", n);
    }

    private void reuseDetected(RefreshToken t, Instant now) {
        tokens.revokeFamily(t.getFamilyId(), now);
        audit.record(t.getUserId(), AuditAction.REFRESH_REUSE, "USER", String.valueOf(t.getUserId()));
        log.warn("Refresh token reuse detected for user {}: family revoked", t.getUserId());
    }

    private AuthResult issue(User u, UUID family, String userAgent) {
        byte[] bytes = new byte[32];
        RNG.nextBytes(bytes);
        String raw = Base64.getUrlEncoder().withoutPadding().encodeToString(bytes);
        RefreshToken rt = new RefreshToken();
        rt.setUserId(u.getId());
        rt.setTokenHash(hash(raw));
        rt.setFamilyId(family);
        rt.setExpiresAt(Instant.now().plus(Duration.ofDays(props.jwt().refreshDays())));
        rt.setUserAgent(userAgent == null ? null : userAgent.substring(0, Math.min(255, userAgent.length())));
        tokens.save(rt);
        String access = jwt.createAccessToken(u.getId(), u.getRole(), family);
        return new AuthResult(new AuthResponseDTO(access, jwt.accessTtlSeconds(), UserDTO.from(u)), raw);
    }

    static String hash(String raw) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(raw.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
