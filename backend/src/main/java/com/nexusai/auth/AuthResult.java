package com.nexusai.auth;

/** Body for the client plus the raw refresh token that the controller turns into the httpOnly cookie. */
public record AuthResult(AuthResponseDTO body, String refreshToken) { }
