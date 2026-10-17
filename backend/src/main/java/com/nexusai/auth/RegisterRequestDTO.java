package com.nexusai.auth;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RegisterRequestDTO(@NotBlank @Email @Size(max = 254) String email, @NotBlank @Size(max = 128) String password,
                                 @NotBlank @Size(max = 80) String displayName) { }
