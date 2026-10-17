package com.nexusai.user;

import com.nexusai.audit.AuditAction;
import com.nexusai.audit.AuditService;
import com.nexusai.auth.RefreshTokenRepository;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.common.util.PageUtil;
import java.time.Instant;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class UserService {
    private static final Set<String> SORTABLE = Set.of("createdAt", "email", "displayName", "role");

    private final UserRepository users;
    private final RefreshTokenRepository tokens;
    private final PasswordEncoder encoder;
    private final AuditService audit;

    public UserService(UserRepository users, RefreshTokenRepository tokens, PasswordEncoder encoder, AuditService audit) {
        this.users = users;
        this.tokens = tokens;
        this.encoder = encoder;
        this.audit = audit;
    }

    public static String normalizeEmail(String email) { return email.trim().toLowerCase(Locale.ROOT); }

    @Transactional(readOnly = true)
    public UserDTO me(long userId) {
        return UserDTO.from(users.findById(userId).orElseThrow(() -> new UnauthenticatedException("Account no longer exists")));
    }

    @Transactional
    public UserDTO updateProfile(long userId, String displayName) {
        User u = users.findById(userId).orElseThrow(() -> new UnauthenticatedException("Account no longer exists"));
        u.setDisplayName(displayName.trim());
        return UserDTO.from(u);
    }

    /** Revokes every other session (refresh-token family) of the caller; the current session (JWT "sid") is kept. */
    @Transactional
    public void changePassword(AuthenticatedUser actor, String currentPassword, String newPassword) {
        User u = users.findById(actor.id()).orElseThrow(() -> new UnauthenticatedException("Account no longer exists"));
        if (!encoder.matches(currentPassword, u.getPasswordHash())) {
            throw new ValidationFailedException("Current password is incorrect", Map.of("currentPassword", "is incorrect"));
        }
        PasswordPolicy.validate(newPassword, "newPassword");
        if (newPassword.equals(currentPassword)) {
            throw new ValidationFailedException("New password must differ", Map.of("newPassword", "must differ from the current password"));
        }
        u.setPasswordHash(encoder.encode(newPassword));
        u.setFailedLogins(0);
        u.setLockedUntil(null);
        tokens.revokeAllForUserExceptFamily(u.getId(), actor.sessionId(), Instant.now());
        audit.record(u.getId(), AuditAction.PASSWORD_CHANGE, "USER", String.valueOf(u.getId()));
    }

    // ---- admin ----

    @Transactional(readOnly = true)
    public PagedResponseDTO<UserDTO> list(String q, Role role, int page, int size, String sort) {
        Pageable pageable = PageUtil.of(page, size, sort, SORTABLE, "createdAt", Sort.Direction.DESC);
        Page<User> result = users.findAll(UserSpecs.search(q, role), pageable);
        return PagedResponseDTO.from(result, UserDTO::from);
    }

    @Transactional
    public UserDTO create(CreateUserRequestDTO req, long actorId) {
        String email = normalizeEmail(req.email());
        PasswordPolicy.validate(req.temporaryPassword(), "temporaryPassword");
        if (users.existsByEmail(email)) throw new DuplicateResourceException("A user with this email already exists");
        User u = new User();
        u.setEmail(email);
        u.setDisplayName(req.displayName().trim());
        u.setRole(req.role());
        u.setPasswordHash(encoder.encode(req.temporaryPassword()));
        users.saveAndFlush(u);
        audit.record(actorId, AuditAction.USER_CREATE, "USER", String.valueOf(u.getId()));
        return UserDTO.from(u);
    }

    @Transactional
    public UserDTO patch(long targetId, PatchUserRequestDTO req, long actorId) {
        if (req.role() == null && req.enabled() == null) {
            throw new ValidationFailedException("Nothing to change", Map.of("role", "role or enabled is required"));
        }
        User target = users.findById(targetId).orElseThrow(() -> new ResourceNotFoundException("User not found"));
        boolean demotes = req.role() != null && req.role() != Role.ADMIN && target.getRole() == Role.ADMIN;
        boolean disables = Boolean.FALSE.equals(req.enabled()) && target.isEnabled();

        if (target.getId() == actorId && (demotes || disables)) {
            throw new ForbiddenException("You cannot demote or disable your own account");
        }
        if (target.getRole() == Role.ADMIN && target.isEnabled() && (demotes || disables)) {
            if (users.lockEnabledAdmins().size() <= 1) {
                throw new InvalidStateException("The last administrator cannot be demoted or disabled");
            }
        }
        if (req.role() != null && req.role() != target.getRole()) {
            audit.record(actorId, AuditAction.ROLE_CHANGE, "USER", target.getId() + ":" + target.getRole() + "->" + req.role());
            target.setRole(req.role());
        }
        if (req.enabled() != null && req.enabled() != target.isEnabled()) {
            target.setEnabled(req.enabled());
            audit.record(actorId, req.enabled() ? AuditAction.USER_ENABLE : AuditAction.USER_DISABLE, "USER", String.valueOf(target.getId()));
            if (!req.enabled()) tokens.revokeAllForUser(target.getId(), Instant.now());
        }
        return UserDTO.from(target);
    }
}
