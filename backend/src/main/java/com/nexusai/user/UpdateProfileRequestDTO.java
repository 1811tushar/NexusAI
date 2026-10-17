package com.nexusai.user;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record UpdateProfileRequestDTO(@NotBlank @Size(max = 80) String displayName) { }
