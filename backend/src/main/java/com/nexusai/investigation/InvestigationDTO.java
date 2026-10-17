package com.nexusai.investigation;

import com.nexusai.common.dto.UserRefDTO;
import java.time.Instant;

public record InvestigationDTO(Long id, String question, InvestigationStatus status, Double confidence, int loopsUsed, String summary,
                               UserRefDTO owner, long pendingApprovals, Instant createdAt, Instant completedAt) { }
