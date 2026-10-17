package com.nexusai.user;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record ChangePasswordRequestDTO(@NotBlank @Size(max = 128) String currentPassword, @NotBlank @Size(max = 128) String newPassword) { }
