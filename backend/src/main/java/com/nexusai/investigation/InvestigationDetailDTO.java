package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.approval.ActionLogDTO;
import com.nexusai.approval.ApprovalDTO;
import com.nexusai.common.dto.UserRefDTO;
import java.time.Instant;
import java.util.List;

/** Contract 4.3 InvestigationDetailDTO (extends InvestigationDTO) incl. v2.1 additions limitations + guardrailEvents. */
public record InvestigationDetailDTO(Long id, String question, InvestigationStatus status, Double confidence, int loopsUsed, String summary,
                                     UserRefDTO owner, long pendingApprovals, Instant createdAt, Instant completedAt,
                                     List<PlanStepDTO> plan, String reportMarkdown, List<String> limitations, List<GuardrailEventDTO> guardrailEvents,
                                     List<ClaimDTO> claims, List<EvidenceDTO> evidence, List<RecommendationDTO> recommendations,
                                     List<ApprovalDTO> approvals, List<ActionLogDTO> actions, String errorMessage, JsonNode usage, Integer feedbackRating) { }
