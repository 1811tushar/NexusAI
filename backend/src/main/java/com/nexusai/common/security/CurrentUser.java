package com.nexusai.common.security;

import com.nexusai.common.exception.UnauthenticatedException;
import com.nexusai.user.Role;
import java.util.Optional;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

/** Static helper for the authenticated caller (id, role). Backend B uses this in its services/controllers. */
public final class CurrentUser {
    private CurrentUser() { }

    public static Optional<AuthenticatedUser> get() {
        Authentication a = SecurityContextHolder.getContext().getAuthentication();
        if (a != null && a.getPrincipal() instanceof AuthenticatedUser u) return Optional.of(u);
        return Optional.empty();
    }
    public static AuthenticatedUser require() { return get().orElseThrow(() -> new UnauthenticatedException("Authentication required")); }
    public static long id() { return require().id(); }
    public static Role role() { return require().role(); }
    public static boolean isAdmin() { return role() == Role.ADMIN; }
}
