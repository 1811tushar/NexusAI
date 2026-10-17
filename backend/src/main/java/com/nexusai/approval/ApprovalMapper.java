package com.nexusai.approval;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.common.dto.UserRefDTO;
import com.nexusai.investigation.Investigation;
import com.nexusai.investigation.InvestigationRepository;
import com.nexusai.user.User;
import com.nexusai.user.UserRepository;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

/** Entities never leave the service layer: this builds the DTOs with batch lookups (no N+1). */
@Component
public class ApprovalMapper {
    private final InvestigationRepository invs;
    private final UserRepository users;
    private final ObjectMapper mapper;

    public ApprovalMapper(InvestigationRepository invs, UserRepository users, ObjectMapper mapper) {
        this.invs = invs;
        this.users = users;
        this.mapper = mapper;
    }

    public List<ApprovalDTO> toDtos(List<Approval> list) {
        if (list.isEmpty()) return List.of();
        Map<Long, Investigation> inv = invs.findAllById(list.stream().map(Approval::getInvestigationId).collect(Collectors.toSet())).stream()
                .collect(Collectors.toMap(Investigation::getId, Function.identity()));
        Set<Long> userIds = new HashSet<>();
        list.forEach(a -> { if (a.getDecidedBy() != null) userIds.add(a.getDecidedBy()); });
        Map<Long, User> byId = users.findAllById(userIds).stream().collect(Collectors.toMap(User::getId, Function.identity()));
        return list.stream().map(a -> {
            Investigation i = inv.get(a.getInvestigationId());
            User d = a.getDecidedBy() == null ? null : byId.get(a.getDecidedBy());
            return new ApprovalDTO(a.getId(), a.getInvestigationId(), i == null ? null : i.getQuestion(), a.getActionKey(), a.getActionType(), a.getTitle(),
                    a.getDescription(), a.getParams(), a.getRisk(), a.getRationale(), keys(a.getEvidenceKeys()), i == null ? null : i.getConfidence(),
                    a.getStatus(), a.getRequestedAt(), d == null ? null : new UserRefDTO(d.getId(), d.getDisplayName()), a.getDecidedAt(), a.getComment());
        }).toList();
    }

    public ApprovalDTO toDto(Approval a) { return toDtos(List.of(a)).get(0); }

    public static ActionLogDTO toDto(ActionLog l) {
        return new ActionLogDTO(l.getId(), l.getInvestigationId(), l.getApprovalId(), l.getActionType(), l.getParams(), l.getRisk(), l.getStatus(),
                l.isAutomatic(), l.getExecutedAt(), l.getNote());
    }

    public List<String> keys(JsonNode node) {
        if (node == null || !node.isArray()) return List.of();
        return mapper.convertValue(node, new TypeReference<List<String>>() { });
    }
}
