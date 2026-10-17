package com.nexusai.approval;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import java.util.List;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * The ONLY place where an action "happens" (BE-AP-02), and it is simulated: it writes action_log and nothing else.
 * Invariant (tested): a HIGH-risk action is executed only for an approval whose stored status is APPROVED with a human decider.
 */
@Service
public class ActionExecutor {
    public static final String SIMULATED = "Simulated execution; no external system was changed.";
    public static final String AUTO_REJECT_PREFIX = "Rejected automatically: ";
    private static final Logger log = LoggerFactory.getLogger(ActionExecutor.class);

    private final ActionLogRepository logs;
    private final ApprovalRepository approvals;
    private final ActionCatalogue catalogue;

    public ActionExecutor(ActionLogRepository logs, ApprovalRepository approvals, ActionCatalogue catalogue) {
        this.logs = logs;
        this.approvals = approvals;
        this.catalogue = catalogue;
    }

    /** LOW-risk actions only. Unknown types or invalid params are recorded as FAILED; a HIGH-risk type is a programming error. */
    @Transactional
    public ActionLog executeAutomatic(long investigationId, String rawType, JsonNode params) {
        JsonNode p = params == null ? JsonNodeFactory.instance.objectNode() : params;
        Optional<ActionType> type = catalogue.parse(rawType);
        if (type.isEmpty()) {
            return save(investigationId, null, "UNKNOWN", p, Risk.HIGH, ActionStatus.FAILED, true,
                    "Unknown action type '" + safe(rawType) + "': not executed. " + SIMULATED);
        }
        ActionType t = type.get();
        if (catalogue.riskOf(t) != Risk.LOW) {
            throw new IllegalStateException("HIGH-risk action " + t + " cannot be executed automatically; it needs a stored APPROVE");
        }
        List<String> errors = catalogue.validate(t, p);
        if (!errors.isEmpty()) {
            return save(investigationId, null, t.name(), p, Risk.LOW, ActionStatus.FAILED, true,
                    "Invalid parameters (" + String.join("; ", errors) + "): not executed. " + SIMULATED);
        }
        return save(investigationId, null, t.name(), p, Risk.LOW, ActionStatus.EXECUTED, true, SIMULATED);
    }

    /** Executes an approved action. Refuses (IllegalStateException) unless the stored decision is APPROVED by a human. Idempotent. */
    @Transactional
    public ActionLog executeApproved(long approvalId) {
        Approval a = approvals.findById(approvalId).orElseThrow(() -> new IllegalStateException("Unknown approval " + approvalId));
        if (a.getStatus() != ApprovalStatus.APPROVED || a.getDecidedBy() == null) {
            throw new IllegalStateException("No stored APPROVE for approval " + approvalId + ": refusing to execute");
        }
        Optional<ActionLog> existing = logs.findFirstByApprovalIdOrderByIdAsc(approvalId);
        if (existing.isPresent()) return existing.get();
        Optional<ActionType> type = catalogue.parse(a.getActionType());
        if (type.isEmpty()) {
            return save(a.getInvestigationId(), a.getId(), "UNKNOWN", a.getParams(), Risk.HIGH, ActionStatus.FAILED, false,
                    "Unknown action type: not executed. " + SIMULATED);
        }
        List<String> errors = catalogue.validate(type.get(), a.getParams());
        if (!errors.isEmpty()) {
            return save(a.getInvestigationId(), a.getId(), type.get().name(), a.getParams(), catalogue.riskOf(type.get()), ActionStatus.FAILED, false,
                    "Invalid parameters (" + String.join("; ", errors) + "): not executed. " + SIMULATED);
        }
        return save(a.getInvestigationId(), a.getId(), type.get().name(), a.getParams(), catalogue.riskOf(type.get()), ActionStatus.EXECUTED, false, SIMULATED);
    }

    /** REJECTED / EXPIRED / FAILED outcome for an approval: logged, never executed. Idempotent. */
    @Transactional
    public ActionLog logNotExecuted(Approval a, ActionStatus status, String reason) {
        if (status == ActionStatus.EXECUTED) throw new IllegalArgumentException("Use executeApproved for executions");
        Optional<ActionLog> existing = logs.findFirstByApprovalIdOrderByIdAsc(a.getId());
        if (existing.isPresent()) return existing.get();
        Risk risk = catalogue.parse(a.getActionType()).map(catalogue::riskOf).orElse(Risk.HIGH);
        return save(a.getInvestigationId(), a.getId(), a.getActionType(), a.getParams(), risk, status, false, reason + " " + SIMULATED);
    }

    private ActionLog save(long investigationId, Long approvalId, String type, JsonNode params, Risk risk, ActionStatus status,
                           boolean automatic, String note) {
        ActionLog l = new ActionLog();
        l.setInvestigationId(investigationId);
        l.setApprovalId(approvalId);
        l.setActionType(type);
        l.setParams(params);
        l.setRisk(risk);
        l.setStatus(status);
        l.setAutomatic(automatic);
        l.setNote(note);
        ActionLog saved = logs.save(l);
        log.info("Action {} {} (automatic={}, investigation={})", type, status, automatic, investigationId);
        return saved;
    }

    private static String safe(String s) {
        if (s == null) return "";
        String t = s.replaceAll("\\p{Cntrl}", " ");
        return t.length() > 40 ? t.substring(0, 40) : t;
    }
}
