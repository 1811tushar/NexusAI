package com.nexusai.audit;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.request.RequestAttributes;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

/**
 * Append-only audit trail. Each call commits in its OWN transaction so a failed login or a rolled-back business
 * operation still leaves its audit row; an audit failure never breaks the caller.
 */
@Service
public class AuditService {
    private static final Logger log = LoggerFactory.getLogger(AuditService.class);
    private final AuditLogRepository repo;

    public AuditService(AuditLogRepository repo) { this.repo = repo; }

    /** Generic entry point. userId may be null (e.g. failed login for an unknown account). */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void record(Long userId, String action, String entity, String entityId) {
        persist(userId, action, entity, entityId);
    }

    /** Backend B calls this when an approver decides an approval. decision = "APPROVE" | "REJECT". */
    @Transactional(propagation = Propagation.REQUIRES_NEW)
    public void approvalDecision(Long deciderUserId, long approvalId, String decision) {
        persist(deciderUserId, AuditAction.APPROVAL_DECISION, "APPROVAL", approvalId + ":" + decision);
    }

    private void persist(Long userId, String action, String entity, String entityId) {
        try {
            AuditLog a = new AuditLog();
            a.setUserId(userId);
            a.setAction(action);
            a.setEntity(entity);
            a.setEntityId(entityId == null ? null : entityId.substring(0, Math.min(50, entityId.length())));
            a.setIp(currentIp());
            repo.save(a);
        } catch (RuntimeException e) {
            log.error("Could not write audit entry {}", action, e);
        }
    }

    private static String currentIp() {
        RequestAttributes attrs = RequestContextHolder.getRequestAttributes();
        if (attrs instanceof ServletRequestAttributes sra) {
            HttpServletRequest req = sra.getRequest();
            return req.getRemoteAddr();
        }
        return null;
    }
}
