package com.nexusai.approval;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nexusai.audit.AuditService;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.common.util.PageUtil;
import com.nexusai.investigation.Investigation;
import com.nexusai.investigation.InvestigationEventService;
import com.nexusai.investigation.InvestigationRepository;
import com.nexusai.investigation.InvestigationStatus;
import com.nexusai.user.Role;
import com.nexusai.user.UserRepository;
import java.time.Instant;
import java.util.Set;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;

/**
 * Approval rules (BE-AP-01): APPROVER/ADMIN only, the requester can never decide their own investigation, a comment is required on REJECT,
 * and the decision is a conditional UPDATE ... WHERE status = 'PENDING' so concurrent deciders produce exactly one winner (the loser gets
 * 409 INVALID_STATE). Deliberately not @Transactional: each step commits on its own so events and the resume happen after the decision is durable.
 */
@Service
public class ApprovalService {
    private static final Set<String> SORTABLE = Set.of("requestedAt", "status", "decidedAt");

    private final ApprovalRepository approvals;
    private final InvestigationRepository invs;
    private final UserRepository users;
    private final ApprovalMapper mapper;
    private final ApprovalFlowService flow;
    private final InvestigationEventService events;
    private final AuditService audit;
    private final ObjectMapper json;

    public ApprovalService(ApprovalRepository approvals, InvestigationRepository invs, UserRepository users, ApprovalMapper mapper,
                           ApprovalFlowService flow, InvestigationEventService events, AuditService audit, ObjectMapper json) {
        this.approvals = approvals;
        this.invs = invs;
        this.users = users;
        this.mapper = mapper;
        this.flow = flow;
        this.events = events;
        this.audit = audit;
        this.json = json;
    }

    public PagedResponseDTO<ApprovalDTO> list(ApprovalStatus status, int page, int size, String sort, AuthenticatedUser actor) {
        Pageable pageable = PageUtil.of(page, size, sort, SORTABLE, "requestedAt", Sort.Direction.DESC);
        Page<Approval> result = approvals.findAll(ApprovalSpecs.scoped(scope(actor), status), pageable);
        return new PagedResponseDTO<>(mapper.toDtos(result.getContent()), result.getNumber(), result.getSize(), result.getTotalElements(), result.getTotalPages());
    }

    public ApprovalDTO get(long id, AuthenticatedUser actor) {
        Approval a = approvals.findById(id).orElseThrow(() -> new ResourceNotFoundException("Approval not found"));
        if (scope(actor) != null) {
            Investigation inv = invs.findById(a.getInvestigationId()).orElseThrow(() -> new ResourceNotFoundException("Approval not found"));
            if (!inv.getUserId().equals(actor.id())) throw new ResourceNotFoundException("Approval not found");
        }
        return mapper.toDto(a);
    }

    public long pendingCount(AuthenticatedUser actor) {
        Long owner = scope(actor);
        return owner == null ? approvals.countByStatus(ApprovalStatus.PENDING) : approvals.countPendingForOwner(owner);
    }

    public ApprovalDTO decide(long approvalId, DecisionRequestDTO req, AuthenticatedUser actor) {
        if (actor.role() != Role.APPROVER && actor.role() != Role.ADMIN) throw new ForbiddenException("Only approvers and administrators can decide approvals");
        Approval a = approvals.findById(approvalId).orElseThrow(() -> new ResourceNotFoundException("Approval not found"));
        Investigation inv = invs.findById(a.getInvestigationId()).orElseThrow(() -> new ResourceNotFoundException("Approval not found"));
        if (inv.getUserId().equals(actor.id())) throw new SelfApprovalNotAllowedException();

        String comment = req.comment() == null ? null : req.comment().trim();
        if (req.decision() == Decision.REJECT && (comment == null || comment.isEmpty())) {
            throw new ValidationFailedException("A comment is required when rejecting", java.util.Map.of("comment", "is required when rejecting"));
        }
        if (comment != null && comment.isEmpty()) comment = null;
        if (inv.getStatus() != InvestigationStatus.AWAITING_APPROVAL) {
            throw new InvalidStateException("The investigation is not waiting for approval");
        }
        ApprovalStatus target = req.decision() == Decision.APPROVE ? ApprovalStatus.APPROVED : ApprovalStatus.REJECTED;
        if (approvals.decideIfPending(approvalId, target, actor.id(), Instant.now(), comment) == 0) {
            throw new InvalidStateException("This approval was already decided or has expired");
        }
        audit.approvalDecision(actor.id(), approvalId, req.decision().name());

        ObjectNode n = json.createObjectNode();
        n.put("approvalId", approvalId);
        n.put("actionKey", a.getActionKey());
        n.put("decision", req.decision().name());
        n.put("decidedBy", users.findById(actor.id()).map(u -> u.getDisplayName()).orElse("unknown"));
        if (comment == null) n.putNull("comment"); else n.put("comment", comment);
        events.emit(inv.getId(), "approval_decided", n);

        flow.finalizeIfComplete(inv.getId());
        return mapper.toDto(approvals.findById(approvalId).orElseThrow());
    }

    /** Analysts see approvals of their own investigations; approvers and admins see everything. null = no owner restriction. */
    private static Long scope(AuthenticatedUser actor) { return actor.role() == Role.ANALYST ? actor.id() : null; }
}
