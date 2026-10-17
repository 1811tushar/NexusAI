package com.nexusai.approval;

import com.nexusai.investigation.InvestigationRepository;
import com.nexusai.investigation.InvestigationStatus;
import java.time.Instant;
import java.util.LinkedHashSet;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * PENDING approvals past expires_at become EXPIRED (decision treated as REJECT with comment "expired"), then the run is resumed. Also a
 * safety net: an AWAITING_APPROVAL run that has no pending approval left (e.g. a crash between the last decision and the resume) is settled.
 */
@Component
public class ApprovalExpiryJob {
    private static final Logger log = LoggerFactory.getLogger(ApprovalExpiryJob.class);
    private final ApprovalRepository approvals;
    private final InvestigationRepository invs;
    private final ApprovalFlowService flow;

    public ApprovalExpiryJob(ApprovalRepository approvals, InvestigationRepository invs, ApprovalFlowService flow) {
        this.approvals = approvals;
        this.invs = invs;
        this.flow = flow;
    }

    @Scheduled(fixedDelayString = "${nexus.runs.expiry-job-interval-ms:60000}", initialDelayString = "${nexus.runs.expiry-job-interval-ms:60000}")
    public void run() {
        try {
            Instant now = Instant.now();
            Set<Long> touched = new LinkedHashSet<>();
            for (Approval a : approvals.findByStatusAndExpiresAtBefore(ApprovalStatus.PENDING, now)) {
                if (approvals.expireIfPending(a.getId(), now, "expired") == 1) {
                    flow.emitSystemRejection(a);
                    touched.add(a.getInvestigationId());
                    log.info("Approval {} expired", a.getId());
                }
            }
            invs.findByStatus(InvestigationStatus.AWAITING_APPROVAL).forEach(i -> touched.add(i.getId()));
            for (Long id : touched) flow.finalizeIfComplete(id);        // no-op while approvals are still pending
        } catch (RuntimeException e) {
            log.error("Approval expiry job failed", e);
        }
    }
}
