package com.nexusai.auth;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record LoginRequestDTO(@NotBlank @Size(max = 254) String email, @NotBlank @Size(max = 128) String password) { }
