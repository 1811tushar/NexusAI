package com.nexusai.user;

import java.time.Instant;

public record UserDTO(Long id, String email, String displayName, Role role, boolean enabled, Instant createdAt) {
    public static UserDTO from(User u) {
        return new UserDTO(u.getId(), u.getEmail(), u.getDisplayName(), u.getRole(), u.isEnabled(), u.getCreatedAt());
    }
}
