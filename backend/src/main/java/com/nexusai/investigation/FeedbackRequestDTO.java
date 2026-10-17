package com.nexusai.investigation;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record FeedbackRequestDTO(@NotNull Integer rating, @Size(max = 2000) String comment) { }
