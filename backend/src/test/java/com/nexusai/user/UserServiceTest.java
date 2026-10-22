package com.nexusai.user;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.nexusai.audit.AuditService;
import com.nexusai.auth.RefreshTokenRepository;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.AuthenticatedUser;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class UserServiceTest {
    @Mock UserRepository users;
    @Mock RefreshTokenRepository tokens;
    @Mock AuditService audit;
    private final BCryptPasswordEncoder encoder = new BCryptPasswordEncoder(4);
    private UserService service;

    @BeforeEach void setUp() { service = new UserService(users, tokens, encoder, audit); }

    private User user(long id, Role role) {
        User u = new User();
        u.setId(id);
        u.setEmail("u" + id + "@test.local");
        u.setDisplayName("U" + id);
        u.setRole(role);
        u.setPasswordHash(encoder.encode("Passw0rd-test1"));
        when(users.findById(id)).thenReturn(Optional.of(u));
        return u;
    }

    @Test void adminCannotDemoteOrDisableSelf() {
        user(1, Role.ADMIN);
        assertThatThrownBy(() -> service.patch(1, new PatchUserRequestDTO(Role.ANALYST, null), 1)).isInstanceOf(ForbiddenException.class);
        assertThatThrownBy(() -> service.patch(1, new PatchUserRequestDTO(null, false), 1)).isInstanceOf(ForbiddenException.class);
    }

    @Test void lastEnabledAdminIsProtected() {
        User target = user(2, Role.ADMIN);
        when(users.lockEnabledAdmins()).thenReturn(List.of(target));
        assertThatThrownBy(() -> service.patch(2, new PatchUserRequestDTO(Role.APPROVER, null), 1)).isInstanceOf(InvalidStateException.class);
        assertThatThrownBy(() -> service.patch(2, new PatchUserRequestDTO(null, false), 1)).isInstanceOf(InvalidStateException.class);
        assertThat(target.getRole()).isEqualTo(Role.ADMIN);
        assertThat(target.isEnabled()).isTrue();
    }

    @Test void demotingOneOfTwoAdminsIsAllowed() {
        User target = user(2, Role.ADMIN);
        User other = user(3, Role.ADMIN);   // create (and stub) first: Mockito forbids stubbing inside thenReturn(...) arguments
        when(users.lockEnabledAdmins()).thenReturn(List.of(target, other));
        assertThat(service.patch(2, new PatchUserRequestDTO(Role.APPROVER, null), 1).role()).isEqualTo(Role.APPROVER);
    }

    @Test void disablingRevokesAllSessions() {
        user(4, Role.ANALYST);
        service.patch(4, new PatchUserRequestDTO(null, false), 1);
        verify(tokens).revokeAllForUser(any(), any());
    }

    @Test void emptyPatchAndUnknownUser() {
        assertThatThrownBy(() -> service.patch(1, new PatchUserRequestDTO(null, null), 1)).isInstanceOf(ValidationFailedException.class);
        when(users.findById(99L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.patch(99, new PatchUserRequestDTO(Role.ANALYST, null), 1)).isInstanceOf(ResourceNotFoundException.class);
    }

    @Test void createNormalisesEmailEnforcesPolicyAndRejectsDuplicates() {
        when(users.existsByEmail("dup@test.local")).thenReturn(true);
        assertThatThrownBy(() -> service.create(new CreateUserRequestDTO("Dup@Test.local", "D", Role.ANALYST, "Temp0raryPass1"), 1)).isInstanceOf(DuplicateResourceException.class);
        assertThatThrownBy(() -> service.create(new CreateUserRequestDTO("n@test.local", "N", Role.ANALYST, "weak"), 1)).isInstanceOf(ValidationFailedException.class);
        verify(users, never()).saveAndFlush(any());
    }

    @Test void changePasswordRejectsWrongCurrentAndReusedPassword() {
        user(5, Role.ANALYST);
        AuthenticatedUser actor = new AuthenticatedUser(5, Role.ANALYST, UUID.randomUUID());
        assertThatThrownBy(() -> service.changePassword(actor, "nope-Password1", "An0therPassword")).isInstanceOf(ValidationFailedException.class);
        assertThatThrownBy(() -> service.changePassword(actor, "Passw0rd-test1", "Passw0rd-test1")).isInstanceOf(ValidationFailedException.class);
        assertThatThrownBy(() -> service.changePassword(actor, "Passw0rd-test1", "short1")).isInstanceOf(ValidationFailedException.class);
        verify(tokens, never()).revokeAllForUserExceptFamily(any(), any(), any());
    }

    @Test void changePasswordRevokesOtherSessionsOnly() {
        User u = user(6, Role.ANALYST);
        UUID sid = UUID.randomUUID();
        service.changePassword(new AuthenticatedUser(6, Role.ANALYST, sid), "Passw0rd-test1", "An0therPassword");
        verify(tokens).revokeAllForUserExceptFamily(org.mockito.ArgumentMatchers.eq(6L), org.mockito.ArgumentMatchers.eq(sid), any());
        assertThat(encoder.matches("An0therPassword", u.getPasswordHash())).isTrue();
    }
}
