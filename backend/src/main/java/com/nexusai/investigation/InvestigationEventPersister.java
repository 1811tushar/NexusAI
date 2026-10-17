package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nexusai.approval.*;
import com.nexusai.common.exception.InvalidStateException;
import com.nexusai.common.metrics.NexusMetrics;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Persists ONE event atomically (BE-IV-02): takes the investigation row lock, applies the event's semantics (plan, evidence, claims,
 * loops, approvals, report, terminal status) through the state machine, allocates the next seq with an atomic UPDATE ... RETURNING
 * and stores the step. Events arriving after a terminal state are dropped. The caller publishes AFTER this transaction commits.
 */
@Service
public class InvestigationEventPersister {
    private static final Logger log = LoggerFactory.getLogger(InvestigationEventPersister.class);
    private static final int MAX_EVIDENCE_ROWS = 50;
    public static final String CANCEL_REASON = "The investigation ended before this approval was decided.";

    private final InvestigationRepository invs;
    private final AgentStepRepository steps;
    private final EvidenceRepository evidence;
    private final ClaimRepository claims;
    private final ApprovalRepository approvals;
    private final ActionLogRepository actionLogs;
    private final JdbcTemplate jdbc;
    private final ObjectMapper mapper;
    private final ActionCatalogue catalogue;
    private final RunProperties props;
    private final NexusMetrics metrics;

    public InvestigationEventPersister(InvestigationRepository invs, AgentStepRepository steps, EvidenceRepository evidence, ClaimRepository claims,
                                       ApprovalRepository approvals, ActionLogRepository actionLogs, JdbcTemplate jdbc, ObjectMapper mapper,
                                       ActionCatalogue catalogue, RunProperties props, NexusMetrics metrics) {
        this.invs = invs;
        this.steps = steps;
        this.evidence = evidence;
        this.claims = claims;
        this.approvals = approvals;
        this.actionLogs = actionLogs;
        this.jdbc = jdbc;
        this.mapper = mapper;
        this.catalogue = catalogue;
        this.props = props;
        this.metrics = metrics;
    }

    /** @return empty when the investigation is unknown, already terminal, or the event is not valid in the current state. */
    @Transactional
    public Optional<PersistedEvent> persist(long investigationId, String type, JsonNode payload) {
        Investigation inv = invs.findByIdForUpdate(investigationId).orElse(null);
        if (inv == null) return Optional.empty();
        if (inv.getStatus().isTerminal()) {
            log.debug("Dropping {} for terminal investigation {}", type, investigationId);
            return Optional.empty();
        }
        return persistLocked(inv, type, payload);
    }

    /** User cancel: CANCELLED + pending approvals expired + a synthesised done event, all in one transaction. */
    @Transactional
    public PersistedEvent cancel(long investigationId) {
        Investigation inv = invs.findByIdForUpdate(investigationId).orElseThrow(() -> new InvalidStateException("Investigation not found"));
        if (!InvestigationStateMachine.canCancel(inv.getStatus())) {
            throw new InvalidStateException("Only a RUNNING or AWAITING_APPROVAL investigation can be cancelled");
        }
        ObjectNode done = mapper.createObjectNode();
        done.put("status", "CANCELLED");
        if (inv.getConfidence() != null) done.put("confidence", inv.getConfidence()); else done.putNull("confidence");
        done.put("loopsUsed", inv.getLoopsUsed());
        done.putObject("usage").put("inputTokens", 0).put("outputTokens", 0);
        done.put("latencyMs", Duration.between(inv.getCreatedAt(), Instant.now()).toMillis());
        return persistLocked(inv, "done", done).orElseThrow(() -> new InvalidStateException("Investigation can no longer be cancelled"));
    }

    private Optional<PersistedEvent> persistLocked(Investigation inv, String type, JsonNode payload) {
        JsonNode stored = payload;
        switch (type) {
            case "plan" -> applyPlan(inv, payload);
            case "step_status" -> applyStepStatus(inv, payload);
            case "evidence_added" -> applyEvidence(inv, payload);
            case "claim_verified" -> applyClaim(inv, payload);
            case "confidence", "loop" -> bumpLoops(inv, payload);
            case "report_ready" -> applyReport(inv, payload);
            case "approval_required" -> {
                stored = applyApprovalRequired(inv, payload);
                if (stored == null) return Optional.empty();
            }
            case "done" -> { if (!applyDone(inv, payload)) return Optional.empty(); }
            case "error" -> { if (!applyError(inv, payload)) return Optional.empty(); }
            default -> { }
        }
        int seq = nextSeq(inv.getId());
        AgentStep s = new AgentStep();
        s.setInvestigationId(inv.getId());
        s.setSeq(seq);
        s.setType(type);
        s.setPayload(stored);
        steps.save(s);
        if (inv.getStatus().isTerminal()) {
            long ms = inv.getLatencyMs() == null ? Duration.between(inv.getCreatedAt(), Instant.now()).toMillis() : inv.getLatencyMs();
            metrics.runFinished(inv.getStatus().name(), ms, inv.getLoopsUsed());
        }
        return Optional.of(new PersistedEvent(seq, type, stored));
    }

    /** Atomic and gap-free per investigation: the row is locked, so concurrent emitters (relay, approvers, cancel) serialise. */
    private int nextSeq(long id) {
        Integer seq = jdbc.queryForObject("update investigations set last_seq = last_seq + 1 where id = ? returning last_seq", Integer.class, id);
        return seq == null ? 0 : seq;
    }

    // ---------------- semantics ----------------

    private void applyPlan(Investigation inv, JsonNode p) {
        ArrayNode out = mapper.createArrayNode();
        for (JsonNode s : array(p, "steps")) {
            ObjectNode n = mapper.createObjectNode();
            n.put("id", text(s, "id", UUID.randomUUID().toString()));
            n.put("description", text(s, "description", ""));
            n.put("agent", text(s, "agent", "PLANNER"));
            n.put("status", text(s, "status", "PENDING"));
            out.add(n);
        }
        inv.setPlan(out);
    }

    private void applyStepStatus(Investigation inv, JsonNode p) {
        String stepId = text(p, "stepId", null);
        String status = text(p, "status", null);
        if (stepId == null || status == null || !inv.getPlan().isArray()) return;
        ArrayNode copy = ((ArrayNode) inv.getPlan()).deepCopy();
        for (JsonNode n : copy) if (stepId.equals(n.path("id").asText())) ((ObjectNode) n).put("status", status);
        inv.setPlan(copy);
    }

    private void applyEvidence(Investigation inv, JsonNode p) {
        JsonNode e = p.path("evidence");
        UUID key = uuid(text(e, "evidenceKey", null));
        if (key == null) { log.warn("evidence_added without a valid evidenceKey ignored (investigation {})", inv.getId()); return; }
        if (evidence.existsByInvestigationIdAndEvidenceKey(inv.getId(), key)) return;
        Evidence ev = new Evidence();
        ev.setInvestigationId(inv.getId());
        ev.setEvidenceKey(key);
        try {
            ev.setKind(EvidenceKind.valueOf(text(e, "kind", "DOCUMENT")));
        } catch (IllegalArgumentException ex) {
            ev.setKind(EvidenceKind.DOCUMENT);
        }
        ev.setTitle(cut(text(e, "title", "Evidence"), 255));
        ev.setSnippet(cut(text(e, "snippet", ""), 20000));
        ev.setSource(e.has("source") && e.get("source").isObject() ? e.get("source") : mapper.createObjectNode());
        ev.setData(capRows(e.get("data")));
        ev.setChart(e.hasNonNull("chart") ? e.get("chart") : null);
        ev.setScore(e.path("score").isNumber() ? e.get("score").asDouble() : null);
        evidence.save(ev);
    }

    /** Evidence data previews are capped at 50 rows (BE-IV-08). */
    private JsonNode capRows(JsonNode data) {
        if (data == null || !data.isObject()) return null;
        JsonNode rows = data.get("rows");
        if (rows == null || !rows.isArray() || rows.size() <= MAX_EVIDENCE_ROWS) return data;
        ObjectNode copy = ((ObjectNode) data).deepCopy();
        ArrayNode cut = mapper.createArrayNode();
        for (int i = 0; i < MAX_EVIDENCE_ROWS; i++) cut.add(rows.get(i));
        copy.set("rows", cut);
        copy.put("truncated", true);
        return copy;
    }

    private void applyClaim(Investigation inv, JsonNode p) {
        String key = text(p, "claimKey", null);
        ClaimStatus status;
        try {
            status = ClaimStatus.valueOf(text(p, "status", ""));
        } catch (IllegalArgumentException ex) {
            log.warn("claim_verified with unknown status ignored (investigation {})", inv.getId());
            return;
        }
        if (key == null) return;
        Claim c = new Claim();
        c.setInvestigationId(inv.getId());
        c.setClaimKey(cut(key, 40));
        c.setText(text(p, "text", ""));
        c.setStatus(status);
        c.setConfidence(clamp01(p.path("confidence").asDouble(0.0)));
        c.setKey(isKeyClaim(inv.getId(), key));
        c.setEvidenceKeys(p.has("evidenceKeys") && p.get("evidenceKeys").isArray() ? p.get("evidenceKeys") : mapper.createArrayNode());
        c.setLoop(inv.getLoopsUsed());
        claims.save(c);
    }

    /** The key-claim flag is only sent in claims_drafted; look it up there (survives restarts, no in-memory state). */
    private boolean isKeyClaim(long investigationId, String claimKey) {
        for (AgentStep s : steps.findByInvestigationIdAndTypeOrderBySeqAsc(investigationId, "claims_drafted")) {
            for (JsonNode c : array(s.getPayload(), "claims")) {
                if (claimKey.equals(c.path("claimKey").asText())) return c.path("isKey").asBoolean(false);
            }
        }
        return false;
    }

    private void bumpLoops(Investigation inv, JsonNode p) {
        int loop = p.path("loop").asInt(0);
        if (loop > inv.getLoopsUsed()) inv.setLoopsUsed(loop);
    }

    private void applyReport(Investigation inv, JsonNode p) {
        inv.setReportMarkdown(text(p, "reportMarkdown", null));
        inv.setSummary(text(p, "summary", null));
        inv.setRecommendations(p.has("recommendations") && p.get("recommendations").isArray() ? p.get("recommendations") : mapper.createArrayNode());
        if (p.path("confidence").isNumber()) inv.setConfidence(clamp01(p.get("confidence").asDouble()));
    }

    /**
     * Creates approval rows (expires_at = now + APPROVAL_TTL_DAYS) and pauses the run. Risk comes from the catalogue; a forged or
     * invalid action gets a row that is already REJECTED (no decider) so the run can still resume with an explicit decision for it.
     * @return the payload to store/publish (each action enriched with approvalId), or null when the event is not valid now.
     */
    private JsonNode applyApprovalRequired(Investigation inv, JsonNode p) {
        if (!InvestigationStateMachine.canTransition(inv.getStatus(), InvestigationStatus.AWAITING_APPROVAL)) {
            log.warn("approval_required ignored in state {} (investigation {})", inv.getStatus(), inv.getId());
            return null;
        }
        Instant now = Instant.now();
        ObjectNode out = mapper.createObjectNode();
        ArrayNode outActions = out.putArray("actions");
        for (JsonNode a : array(p, "actions")) {
            String key = cut(text(a, "actionKey", UUID.randomUUID().toString()), 40);
            ObjectNode enriched = ((ObjectNode) a).deepCopy();
            Approval existing = approvals.findByInvestigationIdAndActionKey(inv.getId(), key).orElse(null);
            if (existing != null) {
                enriched.put("approvalId", existing.getId());
                outActions.add(enriched);
                continue;
            }
            String rawType = text(a, "actionType", "");
            Optional<ActionType> type = catalogue.parse(rawType);
            JsonNode params = a.has("params") && a.get("params").isObject() ? a.get("params") : mapper.createObjectNode();
            List<String> errors = type.map(t -> catalogue.validate(t, params)).orElse(List.of("unknown action type"));

            Approval ap = new Approval();
            ap.setInvestigationId(inv.getId());
            ap.setActionKey(key);
            ap.setActionType(type.map(ActionType::name).orElse("UNKNOWN"));
            ap.setTitle(cut(text(a, "title", "Action requires approval"), 255));
            ap.setDescription(text(a, "description", ""));
            ap.setParams(params);
            ap.setRisk(type.map(catalogue::riskOf).orElse(Risk.HIGH));
            ap.setRationale(text(a, "rationale", ""));
            ap.setEvidenceKeys(a.has("evidenceKeys") && a.get("evidenceKeys").isArray() ? a.get("evidenceKeys") : mapper.createArrayNode());
            ap.setRequestedAt(now);
            ap.setExpiresAt(now.plus(Duration.ofDays(props.approvalTtlDays())));
            if (errors.isEmpty()) {
                ap.setStatus(ApprovalStatus.PENDING);
            } else {
                ap.setStatus(ApprovalStatus.REJECTED);
                ap.setDecidedAt(now);
                ap.setComment(ActionExecutor.AUTO_REJECT_PREFIX + String.join("; ", errors));
            }
            Approval saved = approvals.save(ap);
            enriched.put("approvalId", saved.getId());
            outActions.add(enriched);
        }
        inv.setStatus(InvestigationStatus.AWAITING_APPROVAL);
        return out;
    }

    private boolean applyDone(Investigation inv, JsonNode p) {
        InvestigationStatus target;
        switch (text(p, "status", "COMPLETED")) {
            case "COMPLETED" -> target = InvestigationStatus.COMPLETED;
            case "CANCELLED" -> target = InvestigationStatus.CANCELLED;
            case "REFUSED" -> target = InvestigationStatus.REFUSED;
            default -> { log.warn("done with unknown status ignored (investigation {})", inv.getId()); return false; }
        }
        if (!InvestigationStateMachine.canTransition(inv.getStatus(), target)) {
            log.warn("done({}) ignored in state {} (investigation {})", target, inv.getStatus(), inv.getId());
            return false;
        }
        if (target == InvestigationStatus.CANCELLED) expirePending(inv.getId(), CANCEL_REASON);
        if (p.path("confidence").isNumber()) inv.setConfidence(clamp01(p.get("confidence").asDouble()));
        if (p.path("loopsUsed").isInt() && p.get("loopsUsed").asInt() >= inv.getLoopsUsed()) inv.setLoopsUsed(p.get("loopsUsed").asInt());
        long latency = p.path("latencyMs").isNumber() ? p.get("latencyMs").asLong() : Duration.between(inv.getCreatedAt(), Instant.now()).toMillis();
        ObjectNode usage = mapper.createObjectNode();
        usage.put("inputTokens", p.path("usage").path("inputTokens").asLong(0));
        usage.put("outputTokens", p.path("usage").path("outputTokens").asLong(0));
        usage.put("latencyMs", latency);
        inv.setUsage(usage);
        inv.setLatencyMs((int) Math.min(Integer.MAX_VALUE, latency));
        inv.setStatus(target);
        inv.setCompletedAt(Instant.now());
        return true;
    }

    private boolean applyError(Investigation inv, JsonNode p) {
        if (!InvestigationStateMachine.canTransition(inv.getStatus(), InvestigationStatus.FAILED)) return false;
        expirePending(inv.getId(), CANCEL_REASON);
        inv.setErrorMessage(cut(text(p, "message", "The investigation failed."), 2000));
        inv.setLatencyMs((int) Math.min(Integer.MAX_VALUE, Duration.between(inv.getCreatedAt(), Instant.now()).toMillis()));
        inv.setStatus(InvestigationStatus.FAILED);
        inv.setCompletedAt(Instant.now());
        return true;
    }

    /** Pending approvals of an investigation that ended: logged as EXPIRED, never executed. Plain JDBC so the JPA context is not cleared. */
    private void expirePending(long investigationId, String reason) {
        for (Approval a : approvals.findByInvestigationIdAndStatus(investigationId, ApprovalStatus.PENDING)) {
            ActionLog l = new ActionLog();
            l.setInvestigationId(investigationId);
            l.setApprovalId(a.getId());
            l.setActionType(a.getActionType());
            l.setParams(a.getParams());
            l.setRisk(a.getRisk());
            l.setStatus(ActionStatus.EXPIRED);
            l.setAutomatic(false);
            l.setNote(reason + " " + ActionExecutor.SIMULATED);
            actionLogs.save(l);
        }
        jdbc.update("update approvals set status = 'EXPIRED', decided_at = now(), comment = ? where investigation_id = ? and status = 'PENDING'",
                reason, investigationId);
    }

    // ---------------- helpers ----------------

    static String text(JsonNode n, String field, String def) {
        JsonNode v = n == null ? null : n.get(field);
        return v != null && v.isTextual() ? v.asText() : def;
    }
    private static ArrayNode array(JsonNode n, String field) {
        JsonNode v = n == null ? null : n.get(field);
        return v != null && v.isArray() ? (ArrayNode) v : com.fasterxml.jackson.databind.node.JsonNodeFactory.instance.arrayNode();
    }
    private static UUID uuid(String s) {
        try { return s == null ? null : UUID.fromString(s); } catch (IllegalArgumentException e) { return null; }
    }
    private static String cut(String s, int max) { return s == null || s.length() <= max ? s : s.substring(0, max); }
    private static double clamp01(double v) { return Math.max(0.0, Math.min(1.0, v)); }
}
