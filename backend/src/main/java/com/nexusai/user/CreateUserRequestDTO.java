package com.nexusai.user;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CreateUserRequestDTO(@NotBlank @Email @Size(max = 254) String email, @NotBlank @Size(max = 80) String displayName,
                                   @NotNull Role role, @NotBlank @Size(max = 128) String temporaryPassword) { }
