package com.nexusai.investigation;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.approval.*;
import com.nexusai.common.dto.UserRefDTO;
import com.nexusai.user.User;
import com.nexusai.user.UserRepository;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

@Component
public class InvestigationMapper {
    private final UserRepository users;
    private final ApprovalRepository approvals;
    private final ActionLogRepository actionLogs;
    private final ClaimRepository claims;
    private final EvidenceRepository evidence;
    private final AgentStepRepository steps;
    private final ApprovalMapper approvalMapper;
    private final ObjectMapper mapper;

    public InvestigationMapper(UserRepository users, ApprovalRepository approvals, ActionLogRepository actionLogs, ClaimRepository claims,
                               EvidenceRepository evidence, AgentStepRepository steps, ApprovalMapper approvalMapper, ObjectMapper mapper) {
        this.users = users;
        this.approvals = approvals;
        this.actionLogs = actionLogs;
        this.claims = claims;
        this.evidence = evidence;
        this.steps = steps;
        this.approvalMapper = approvalMapper;
        this.mapper = mapper;
    }

    public List<InvestigationDTO> toDtos(List<Investigation> list) {
        if (list.isEmpty()) return List.of();
        Map<Long, User> owners = users.findAllById(list.stream().map(Investigation::getUserId).collect(Collectors.toSet())).stream()
                .collect(Collectors.toMap(User::getId, Function.identity()));
        Map<Long, Long> pending = new HashMap<>();
        for (Object[] row : approvals.pendingCounts(list.stream().map(Investigation::getId).toList())) pending.put((Long) row[0], (Long) row[1]);
        return list.stream().map(i -> new InvestigationDTO(i.getId(), i.getQuestion(), i.getStatus(), i.getConfidence(), i.getLoopsUsed(), i.getSummary(),
                owner(owners.get(i.getUserId()), i.getUserId()), pending.getOrDefault(i.getId(), 0L), i.getCreatedAt(), i.getCompletedAt())).toList();
    }

    public InvestigationDTO toDto(Investigation i) { return toDtos(List.of(i)).get(0); }

    public InvestigationDetailDTO toDetail(Investigation i) {
        InvestigationDTO base = toDto(i);
        List<Approval> aps = approvals.findByInvestigationIdOrderByIdAsc(i.getId());
        List<ActionLog> logs = actionLogs.findByInvestigationIdOrderByIdAsc(i.getId());
        return new InvestigationDetailDTO(base.id(), base.question(), base.status(), base.confidence(), base.loopsUsed(), base.summary(), base.owner(),
                base.pendingApprovals(), base.createdAt(), base.completedAt(), plan(i), i.getReportMarkdown(), limitations(i), guardrailEvents(i.getId()),
                latestClaims(i.getId()), evidence(i.getId()), recommendations(i), approvalMapper.toDtos(aps),
                logs.stream().map(ApprovalMapper::toDto).toList(), i.getErrorMessage(), i.getUsage(),
                i.getFeedbackRating() == null ? null : i.getFeedbackRating().intValue());
    }

    public List<PlanStepDTO> plan(Investigation i) { return convert(i.getPlan(), new TypeReference<List<PlanStepDTO>>() { }); }

    public List<RecommendationDTO> recommendations(Investigation i) { return convert(i.getRecommendations(), new TypeReference<List<RecommendationDTO>>() { }); }

    /** "latest verification per claim_key wins": history rows stay in the table, the API shows only the newest of each key. */
    public List<ClaimDTO> latestClaims(long investigationId) {
        Map<String, Claim> latest = new LinkedHashMap<>();
        for (Claim c : claims.findByInvestigationIdOrderByIdAsc(investigationId)) latest.put(c.getClaimKey(), c);
        return latest.values().stream().map(c -> new ClaimDTO(c.getId(), c.getText(), c.getStatus(), c.getConfidence(), c.isKey(),
                approvalMapper.keys(c.getEvidenceKeys()))).toList();
    }

    public List<EvidenceDTO> evidence(long investigationId) {
        return evidence.findByInvestigationIdOrderByIdAsc(investigationId).stream().map(e -> new EvidenceDTO(e.getEvidenceKey().toString(), e.getKind(),
                e.getTitle(), e.getSnippet(), e.getSource(), e.getData(), e.getChart(), e.getScore(), e.getCreatedAt())).toList();
    }

    public List<GuardrailEventDTO> guardrailEvents(long investigationId) {
        List<GuardrailEventDTO> out = new ArrayList<>();
        for (AgentStep s : steps.findByInvestigationIdAndTypeOrderBySeqAsc(investigationId, "guardrail_triggered")) {
            JsonNode p = s.getPayload();
            out.add(new GuardrailEventDTO(p.path("stage").asText(""), p.path("action").asText(""), p.path("category").asText(""), p.path("detail").asText("")));
        }
        return out;
    }

    /** report_ready.limitations (if the AI stream sends it) wins; otherwise the "Limitations and failures" section of the report is parsed. */
    public List<String> limitations(Investigation i) {
        List<AgentStep> ready = steps.findByInvestigationIdAndTypeOrderBySeqAsc(i.getId(), "report_ready");
        if (!ready.isEmpty()) {
            JsonNode l = ready.get(ready.size() - 1).getPayload().get("limitations");
            if (l != null && l.isArray()) return convert(l, new TypeReference<List<String>>() { });
        }
        return LimitationsParser.parse(i.getReportMarkdown());
    }

    private <T> List<T> convert(JsonNode node, TypeReference<List<T>> type) {
        if (node == null || !node.isArray()) return List.of();
        return mapper.convertValue(node, type);
    }

    private static UserRefDTO owner(User u, Long id) { return new UserRefDTO(id, u == null ? null : u.getDisplayName()); }
}
