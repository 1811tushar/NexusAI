package com.nexusai.approval;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nexusai.ai.AiResumeRequest;
import com.nexusai.investigation.*;
import com.nexusai.user.User;
import com.nexusai.user.UserRepository;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.event.EventListener;
import org.springframework.stereotype.Service;

/**
 * Settles an investigation once no approval is PENDING (BE-AP-02): claims the AWAITING_APPROVAL -> RUNNING transition with a
 * compare-and-set (exactly one caller wins, however many approvers decide at once), executes APPROVED actions through ActionExecutor,
 * logs rejected / expired / invalid ones, then resumes the Python run with every decision of this round.
 */
@Service
public class ApprovalFlowService {
    private static final Logger log = LoggerFactory.getLogger(ApprovalFlowService.class);
    private static final String SYSTEM = "system";

    private final ApprovalRepository approvals;
    private final ActionLogRepository actionLogs;
    private final InvestigationRepository invs;
    private final UserRepository users;
    private final ActionExecutor executor;
    private final InvestigationEventService events;
    private final RunRelayService relay;
    private final ObjectMapper mapper;

    public ApprovalFlowService(ApprovalRepository approvals, ActionLogRepository actionLogs, InvestigationRepository invs, UserRepository users,
                               ActionExecutor executor, InvestigationEventService events, RunRelayService relay, ObjectMapper mapper) {
        this.approvals = approvals;
        this.actionLogs = actionLogs;
        this.invs = invs;
        this.users = users;
        this.executor = executor;
        this.events = events;
        this.relay = relay;
        this.mapper = mapper;
    }

    @EventListener
    public void onMaybeSettled(ApprovalsMaybeSettled e) { finalizeIfComplete(e.investigationId()); }

    /** Safe to call repeatedly and from any thread. */
    public void finalizeIfComplete(long investigationId) {
        if (approvals.countByInvestigationIdAndStatus(investigationId, ApprovalStatus.PENDING) > 0) return;
        if (invs.transition(investigationId, InvestigationStatus.AWAITING_APPROVAL, InvestigationStatus.RUNNING) == 0) return;   // someone else settled it
        try {
            Investigation inv = invs.findById(investigationId).orElseThrow();
            List<Approval> round = approvals.findByInvestigationIdOrderByIdAsc(investigationId).stream()
                    .filter(a -> !actionLogs.existsByApprovalId(a.getId())).toList();
            Map<Long, String> names = users.findAllById(round.stream().map(Approval::getDecidedBy).filter(java.util.Objects::nonNull).collect(Collectors.toSet()))
                    .stream().collect(Collectors.toMap(User::getId, User::getDisplayName));

            List<AiResumeRequest.Decision> decisions = new ArrayList<>();
            for (Approval a : round) {
                ActionLog l = switch (a.getStatus()) {
                    case APPROVED -> executor.executeApproved(a.getId());
                    case EXPIRED -> executor.logNotExecuted(a, ActionStatus.EXPIRED, "Not executed: the approval expired before a decision.");
                    case REJECTED -> a.getDecidedBy() == null
                            ? executor.logNotExecuted(a, ActionStatus.FAILED, "Not executed: " + safe(a.getComment()))
                            : executor.logNotExecuted(a, ActionStatus.REJECTED, "Not executed: rejected by an approver.");
                    case PENDING -> throw new IllegalStateException("Pending approval during finalisation");
                };
                events.emit(investigationId, "action_executed", relay.executedPayload(l, a.getActionKey()));
                boolean approved = a.getStatus() == ApprovalStatus.APPROVED;
                String by = a.getDecidedBy() == null ? SYSTEM : names.getOrDefault(a.getDecidedBy(), SYSTEM);
                String comment = a.getStatus() == ApprovalStatus.EXPIRED ? "expired" : a.getComment();
                decisions.add(new AiResumeRequest.Decision(a.getActionKey(), a.getId(), approved ? "APPROVE" : "REJECT", by, comment));
            }
            relay.resumeAsync(investigationId, inv.getThreadId(), new AiResumeRequest(investigationId, decisions));
        } catch (RuntimeException e) {
            log.error("Could not settle approvals of investigation {}", investigationId, e);
            relay.failRun(investigationId, "The run could not be resumed after the approval decisions.", "INTERNAL_ERROR");
        }
    }

    /** approval_decided for a decision that was not made by a person (expiry). */
    public void emitSystemRejection(Approval a) {
        ObjectNode n = mapper.createObjectNode();
        n.put("approvalId", a.getId());
        n.put("actionKey", a.getActionKey());
        n.put("decision", "REJECT");
        n.put("decidedBy", SYSTEM);
        n.put("comment", "expired");
        events.emit(a.getInvestigationId(), "approval_decided", n);
    }

    private static String safe(String s) { return s == null ? "invalid action." : s; }
}
