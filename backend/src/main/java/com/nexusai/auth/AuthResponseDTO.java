package com.nexusai.auth;

import com.nexusai.user.UserDTO;

public record AuthResponseDTO(String accessToken, long expiresInSeconds, UserDTO user) { }
