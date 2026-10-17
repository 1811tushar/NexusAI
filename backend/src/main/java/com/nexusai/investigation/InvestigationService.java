package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nexusai.ai.AiInvestigateRequest;
import com.nexusai.ai.AiServiceClient;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.common.util.PageUtil;
import com.nexusai.document.Document;
import com.nexusai.document.DocumentRepository;
import com.nexusai.document.DocumentStatus;
import com.nexusai.user.Role;
import java.time.Instant;
import java.util.*;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

/**
 * Investigation rules (BE-IV-01/04/05, contract 4.3): validation and options, per-user concurrency cap, scoped reads (a foreign id is a
 * 404 for analysts), cancel, feedback. The run itself is executed by RunRelayService in the background.
 */
@Service
public class InvestigationService {
    private static final Logger log = LoggerFactory.getLogger(InvestigationService.class);
    private static final Set<String> SORTABLE = Set.of("createdAt", "status", "confidence", "loopsUsed");

    private final InvestigationRepository invs;
    private final AgentStepRepository steps;
    private final DocumentRepository documents;
    private final RunProperties props;
    private final RunRelayService relay;
    private final InvestigationEventPersister persister;
    private final InvestigationEventService events;
    private final InvestigationMapper mapper;
    private final AiServiceClient ai;
    private final ObjectMapper json;
    private final TransactionTemplate tx;
    private final Object[] userLocks = new Object[64];

    public InvestigationService(InvestigationRepository invs, AgentStepRepository steps, DocumentRepository documents, RunProperties props,
                                RunRelayService relay, InvestigationEventPersister persister, InvestigationEventService events,
                                InvestigationMapper mapper, AiServiceClient ai, ObjectMapper json, TransactionTemplate tx) {
        this.invs = invs;
        this.steps = steps;
        this.documents = documents;
        this.props = props;
        this.relay = relay;
        this.persister = persister;
        this.events = events;
        this.mapper = mapper;
        this.ai = ai;
        this.json = json;
        this.tx = tx;
        for (int i = 0; i < userLocks.length; i++) userLocks[i] = new Object();
    }

    // ---------------- start ----------------

    public InvestigationDTO start(StartInvestigationRequestDTO req, AuthenticatedUser actor) {
        if (actor.role() == Role.APPROVER) throw new ForbiddenException("Approvers cannot start investigations");
        String question = req == null || req.question() == null ? "" : req.question().trim();
        if (question.length() < 10 || question.length() > 2000) {
            throw new ValidationFailedException("The question must be 10 to 2000 characters", Map.of("question", "must be 10 to 2000 characters"));
        }
        StartInvestigationRequestDTO.Options o = req.options();
        boolean webSearch = o == null || o.webSearch() == null || o.webSearch();
        boolean useMemory = o == null || o.useMemory() == null || o.useMemory();
        int maxLoops = o == null || o.maxLoops() == null ? Math.min(props.defaultMaxLoops(), props.maxLoopsLimit()) : o.maxLoops();
        if (maxLoops < 1 || maxLoops > props.maxLoopsLimit()) {
            throw new ValidationFailedException("Invalid maxLoops", Map.of("maxLoops", "must be between 1 and " + props.maxLoopsLimit()));
        }
        List<Long> docIds = o == null || o.documentIds() == null || o.documentIds().isEmpty() ? null : List.copyOf(new LinkedHashSet<>(o.documentIds()));
        if (docIds != null) validateDocuments(docIds);

        ObjectNode options = json.createObjectNode();
        options.put("webSearch", webSearch);
        options.put("useMemory", useMemory);
        options.put("maxLoops", maxLoops);
        if (docIds == null) options.putNull("documentIds"); else options.set("documentIds", json.valueToTree(docIds));

        Investigation created;
        synchronized (userLocks[(int) (actor.id() % userLocks.length)]) {       // count + insert must not interleave for one user
            created = tx.execute(s -> {
                if (invs.countByUserIdAndStatus(actor.id(), InvestigationStatus.RUNNING) >= props.maxConcurrentPerUser()) {
                    throw new QuotaExceededException("You already have " + props.maxConcurrentPerUser() + " investigations running. Wait for one to finish or cancel it.");
                }
                Investigation i = new Investigation();
                i.setUserId(actor.id());
                i.setQuestion(question);
                i.setStatus(InvestigationStatus.RUNNING);
                i.setOptions(options);
                i.setThreadId(UUID.randomUUID());
                i.setPlan(json.createArrayNode());
                i.setRecommendations(json.createArrayNode());
                return invs.saveAndFlush(i);
            });
        }
        AiInvestigateRequest request = new AiInvestigateRequest(created.getId(), created.getThreadId().toString(), actor.id(), question,
                new AiInvestigateRequest.Options(webSearch, docIds, useMemory, maxLoops), Instant.now().toString());
        relay.startAsync(created.getId(), request);
        return mapper.toDto(created);
    }

    private void validateDocuments(List<Long> ids) {
        Map<Long, Document> found = documents.findAllById(ids).stream().collect(Collectors.toMap(Document::getId, d -> d));
        for (Long id : ids) {
            Document d = found.get(id);
            if (d == null || d.getStatus() != DocumentStatus.READY) {
                throw new ValidationFailedException("A selected document is not available", Map.of("documentIds", "document " + id + " does not exist or is not READY"));
            }
        }
    }

    // ---------------- reads ----------------

    public PagedResponseDTO<InvestigationDTO> list(InvestigationStatus status, String q, boolean mine, int page, int size, String sort, AuthenticatedUser actor) {
        Pageable pageable = PageUtil.of(page, size, sort, SORTABLE, "createdAt", Sort.Direction.DESC);
        Long owner = actor.role() == Role.ANALYST || mine ? actor.id() : null;
        Page<Investigation> result = invs.findAll(InvestigationSpecs.filter(owner, status, q), pageable);
        return new PagedResponseDTO<>(mapper.toDtos(result.getContent()), result.getNumber(), result.getSize(), result.getTotalElements(), result.getTotalPages());
    }

    public InvestigationDetailDTO get(long id, AuthenticatedUser actor) { return mapper.toDetail(requireVisible(id, actor)); }

    public List<AgentStepDTO> steps(long id, AuthenticatedUser actor) {
        requireVisible(id, actor);
        return steps.findByInvestigationIdOrderBySeqAsc(id).stream().map(s -> new AgentStepDTO(s.getSeq(), s.getType(), s.getPayload(), s.getCreatedAt())).toList();
    }

    /** Analysts only see their own investigations: a foreign id looks exactly like a missing one. */
    public Investigation requireVisible(long id, AuthenticatedUser actor) {
        Investigation i = invs.findById(id).orElseThrow(() -> new ResourceNotFoundException("Investigation not found"));
        if (actor.role() == Role.ANALYST && !i.getUserId().equals(actor.id())) throw new ResourceNotFoundException("Investigation not found");
        return i;
    }

    // ---------------- cancel / feedback ----------------

    public void cancel(long id, AuthenticatedUser actor) {
        Investigation inv = requireVisible(id, actor);
        if (actor.role() != Role.ADMIN && !inv.getUserId().equals(actor.id())) throw new ForbiddenException("Only the owner or an administrator can cancel an investigation");
        PersistedEvent done = persister.cancel(id);                  // CANCELLED + pending approvals expired + done event, atomically; 409 if not cancellable
        relay.signalCancel(id);                                      // stop reading the upstream stream
        events.publish(id, done);
        try {
            ai.cancel(inv.getThreadId());
        } catch (RuntimeException e) {
            log.warn("Could not tell the AI service to cancel run {}: {}", id, e.getMessage());
        }
    }

    public void feedback(long id, FeedbackRequestDTO req, AuthenticatedUser actor) {
        if (req.rating() != 1 && req.rating() != -1) throw new ValidationFailedException("Invalid rating", Map.of("rating", "must be 1 or -1"));
        tx.executeWithoutResult(s -> {
            Investigation inv = requireVisible(id, actor);
            if (!inv.getUserId().equals(actor.id())) throw new ForbiddenException("Only the owner can leave feedback");
            if (!inv.getStatus().isTerminal()) throw new InvalidStateException("Feedback is possible once the investigation has finished");
            inv.setFeedbackRating(req.rating().shortValue());
            inv.setFeedbackComment(req.comment() == null || req.comment().isBlank() ? null : req.comment().trim());
            invs.save(inv);
        });
    }

}
