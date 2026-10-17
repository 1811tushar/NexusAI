package com.nexusai.investigation;

import com.nexusai.approval.ApprovalRepository;
import com.nexusai.approval.ApprovalStatus;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.document.DocumentRepository;
import com.nexusai.document.DocumentStatus;
import com.nexusai.user.Role;
import java.time.Duration;
import java.time.Instant;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/** Role-scoped dashboard (FE-DB-01): analysts see their own numbers, approvers and admins see everything. */
@Service
public class DashboardService {
    private final InvestigationRepository invs;
    private final ApprovalRepository approvals;
    private final DocumentRepository documents;
    private final InvestigationMapper mapper;

    public DashboardService(InvestigationRepository invs, ApprovalRepository approvals, DocumentRepository documents, InvestigationMapper mapper) {
        this.invs = invs;
        this.approvals = approvals;
        this.documents = documents;
        this.mapper = mapper;
    }

    @Transactional(readOnly = true)
    public DashboardSummaryDTO summary(AuthenticatedUser actor) {
        boolean own = actor.role() == Role.ANALYST;
        Map<InvestigationStatus, Long> byStatus = new EnumMap<>(InvestigationStatus.class);
        for (InvestigationStatus s : InvestigationStatus.values()) byStatus.put(s, 0L);
        for (Object[] row : own ? invs.countByStatusForUser(actor.id()) : invs.countByStatusAll()) byStatus.put((InvestigationStatus) row[0], (Long) row[1]);
        Instant since = Instant.now().minus(Duration.ofDays(30));
        Double avg = own ? invs.avgConfidenceSinceForUser(actor.id(), since) : invs.avgConfidenceSince(since);
        long pending = own ? approvals.countPendingForOwner(actor.id()) : approvals.countByStatus(ApprovalStatus.PENDING);
        List<Investigation> recent = own ? invs.findTop10ByUserIdOrderByCreatedAtDesc(actor.id()) : invs.findTop10ByOrderByCreatedAtDesc();
        return new DashboardSummaryDTO(byStatus, pending, documents.countByStatus(DocumentStatus.READY), avg, mapper.toDtos(recent));
    }
}
