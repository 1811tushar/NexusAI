package com.nexusai.investigation;

import java.util.List;
import java.util.Map;

public record DashboardSummaryDTO(Map<InvestigationStatus, Long> investigationsByStatus, long pendingApprovals, long documentsReady,
                                  Double avgConfidence30d, List<InvestigationDTO> recent) { }
