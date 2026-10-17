package com.nexusai.approval;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.common.dto.UserRefDTO;
import java.time.Instant;
import java.util.List;

public record ApprovalDTO(Long id, Long investigationId, String investigationQuestion, String actionKey, String actionType, String title,
                          String description, JsonNode params, Risk risk, String rationale, List<String> evidenceKeys, Double confidence,
                          ApprovalStatus status, Instant requestedAt, UserRefDTO decidedBy, Instant decidedAt, String comment) { }
