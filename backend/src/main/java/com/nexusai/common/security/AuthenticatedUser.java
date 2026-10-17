package com.nexusai.common.security;

import com.nexusai.user.Role;
import java.util.UUID;

/** Principal placed in the SecurityContext by JwtAuthFilter. sessionId = refresh-token family id (JWT claim "sid"). */
public record AuthenticatedUser(long id, Role role, UUID sessionId) { }
