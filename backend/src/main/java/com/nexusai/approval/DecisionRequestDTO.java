package com.nexusai.approval;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record DecisionRequestDTO(@NotNull Decision decision, @Size(max = 2000) String comment) { }
