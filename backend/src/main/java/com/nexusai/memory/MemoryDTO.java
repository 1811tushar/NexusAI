package com.nexusai.memory;

import java.time.Instant;

public record MemoryDTO(Long id, String summary, Long sourceInvestigationId, double importance, Instant createdAt, Instant lastAccessedAt) { }
