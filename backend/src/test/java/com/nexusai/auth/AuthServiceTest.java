package com.nexusai.auth;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.nexusai.audit.AuditAction;
import com.nexusai.audit.AuditService;
import com.nexusai.common.TestProps;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.JwtUtil;
import com.nexusai.user.Role;
import com.nexusai.user.User;
import com.nexusai.user.UserRepository;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class AuthServiceTest {
    @Mock UserRepository users;
    @Mock RefreshTokenRepository tokens;
    @Mock AuditService audit;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(4);
    private AuthService service;
    private User user;

    @BeforeEach
    void setUp() {
        service = new AuthService(users, tokens, encoder, new JwtUtil(TestProps.props()), TestProps.props(), audit);
        user = new User();
        user.setId(7L);
        user.setEmail("a@test.local");
        user.setRole(Role.ANALYST);
        user.setDisplayName("A");
        user.setPasswordHash(encoder.encode("Passw0rd-test1"));
        when(users.findByEmail("a@test.local")).thenReturn(Optional.of(user));
        when(users.findById(7L)).thenReturn(Optional.of(user));
        when(tokens.save(any())).thenAnswer(i -> i.getArgument(0));
    }

    private static LoginRequestDTO login(String pw) { return new LoginRequestDTO("A@Test.local ", pw); }

    @Test void unknownEmailIsGenericAndAudited() {
        assertThatThrownBy(() -> service.login(new LoginRequestDTO("nobody@test.local", "whatever1234"), "ua")).isInstanceOf(InvalidCredentialsException.class);
        verify(audit).record(null, AuditAction.LOGIN_FAILURE, "USER", null);
    }

    @Test void wrongPasswordCountsFailuresAndFifthLocks() {
        for (int i = 1; i <= 4; i++) {
            assertThatThrownBy(() -> service.login(login("wrong-Password1"), "ua")).isInstanceOf(InvalidCredentialsException.class);
            assertThat(user.getFailedLogins()).isEqualTo(i);
            assertThat(user.getLockedUntil()).isNull();
        }
        assertThatThrownBy(() -> service.login(login("wrong-Password1"), "ua")).isInstanceOf(InvalidCredentialsException.class);
        assertThat(user.getLockedUntil()).isAfter(Instant.now());
        assertThat(user.getFailedLogins()).isZero();
    }

    @Test void lockedAccountRejectsCorrectPassword() {
        user.setLockedUntil(Instant.now().plusSeconds(300));
        assertThatThrownBy(() -> service.login(login("Passw0rd-test1"), "ua")).isInstanceOf(InvalidCredentialsException.class);
        verify(audit).record(7L, AuditAction.LOGIN_BLOCKED, "USER", "7");
        verify(tokens, never()).save(any());
    }

    @Test void disabledAccountIsIndistinguishable() {
        user.setEnabled(false);
        assertThatThrownBy(() -> service.login(login("Passw0rd-test1"), "ua")).isInstanceOf(InvalidCredentialsException.class);
    }

    @Test void successResetsCounterAndStoresOnlyTheHashOfTheRefreshToken() {
        user.setFailedLogins(3);
        AuthResult r = service.login(login("Passw0rd-test1"), "ua");
        assertThat(user.getFailedLogins()).isZero();
        assertThat(r.body().accessToken()).isNotBlank();
        ArgumentCaptor<RefreshToken> cap = ArgumentCaptor.forClass(RefreshToken.class);
        verify(tokens).save(cap.capture());
        assertThat(cap.getValue().getTokenHash()).hasSize(64).isEqualTo(AuthService.hash(r.refreshToken())).isNotEqualTo(r.refreshToken());
    }

    private RefreshToken stored(String raw, Instant expires, Instant revoked) {
        RefreshToken t = new RefreshToken();
        t.setId(1L);
        t.setUserId(7L);
        t.setFamilyId(UUID.randomUUID());
        t.setTokenHash(AuthService.hash(raw));
        t.setExpiresAt(expires);
        t.setRevokedAt(revoked);
        when(tokens.findByTokenHash(t.getTokenHash())).thenReturn(Optional.of(t));
        return t;
    }

    @Test void refreshRotatesWithinTheSameFamily() {
        RefreshToken old = stored("raw-1", Instant.now().plusSeconds(600), null);
        when(tokens.revokeIfActive(anyLong(), any())).thenReturn(1);
        AuthResult r = service.refresh("raw-1", "ua");
        ArgumentCaptor<RefreshToken> cap = ArgumentCaptor.forClass(RefreshToken.class);
        verify(tokens).save(cap.capture());
        assertThat(cap.getValue().getFamilyId()).isEqualTo(old.getFamilyId());
        assertThat(r.refreshToken()).isNotEqualTo("raw-1");
    }

    @Test void presentingARevokedTokenRevokesTheFamilyAndAuditsReuse() {
        RefreshToken old = stored("raw-2", Instant.now().plusSeconds(600), Instant.now().minusSeconds(5));
        assertThatThrownBy(() -> service.refresh("raw-2", "ua")).isInstanceOf(UnauthenticatedException.class);
        verify(tokens).revokeFamily(any(), any());
        verify(audit).record(7L, AuditAction.REFRESH_REUSE, "USER", "7");
        assertThat(old.getFamilyId()).isNotNull();
    }

    @Test void losingTheRotationRaceIsTreatedAsReuse() {
        stored("raw-3", Instant.now().plusSeconds(600), null);
        when(tokens.revokeIfActive(anyLong(), any())).thenReturn(0);
        assertThatThrownBy(() -> service.refresh("raw-3", "ua")).isInstanceOf(UnauthenticatedException.class);
        verify(tokens).revokeFamily(any(), any());
    }

    @Test void expiredRefreshTokenIsReportedAsExpired() {
        stored("raw-4", Instant.now().minusSeconds(5), null);
        assertThatThrownBy(() -> service.refresh("raw-4", "ua")).isInstanceOf(TokenExpiredException.class);
    }

    @Test void refreshForDisabledUserRevokesFamily() {
        stored("raw-5", Instant.now().plusSeconds(600), null);
        when(tokens.revokeIfActive(anyLong(), any())).thenReturn(1);
        user.setEnabled(false);
        assertThatThrownBy(() -> service.refresh("raw-5", "ua")).isInstanceOf(UnauthenticatedException.class);
        verify(tokens).revokeFamily(any(), any());
    }

    @Test void missingOrBlankCookieIsUnauthenticated() {
        assertThatThrownBy(() -> service.refresh(null, "ua")).isInstanceOf(UnauthenticatedException.class);
        assertThatThrownBy(() -> service.refresh("  ", "ua")).isInstanceOf(UnauthenticatedException.class);
    }

    @Test void registerIsForbiddenWhenClosed() {
        AuthService closed = new AuthService(users, tokens, encoder, new JwtUtil(TestProps.props(false, 500)), TestProps.props(false, 500), audit);
        assertThatThrownBy(() -> closed.register(new RegisterRequestDTO("n@test.local", "Str0ngPassw0rd", "N"), "ua")).isInstanceOf(ForbiddenException.class);
    }

    @Test void registerCreatesAnalystWithNormalisedEmail() {
        when(users.existsByEmail("new@test.local")).thenReturn(false);
        when(users.saveAndFlush(any())).thenAnswer(i -> { User u = i.getArgument(0); u.setId(9L); return u; });
        AuthResult r = service.register(new RegisterRequestDTO(" New@Test.local", "Str0ngPassw0rd", " New "), "ua");
        assertThat(r.body().user().role()).isEqualTo(Role.ANALYST);
        assertThat(r.body().user().email()).isEqualTo("new@test.local");
        assertThat(r.body().user().displayName()).isEqualTo("New");
    }

    @Test void registerRejectsDuplicateEmail() {
        when(users.existsByEmail("a@test.local")).thenReturn(true);
        assertThatThrownBy(() -> service.register(new RegisterRequestDTO("a@test.local", "Str0ngPassw0rd", "A"), "ua")).isInstanceOf(DuplicateResourceException.class);
    }
}
