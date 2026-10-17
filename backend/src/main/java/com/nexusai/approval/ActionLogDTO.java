package com.nexusai.approval;

import com.fasterxml.jackson.databind.JsonNode;
import java.time.Instant;

public record ActionLogDTO(Long id, Long investigationId, Long approvalId, String actionType, JsonNode params, Risk risk, ActionStatus status,
                           boolean automatic, Instant executedAt, String note) { }
