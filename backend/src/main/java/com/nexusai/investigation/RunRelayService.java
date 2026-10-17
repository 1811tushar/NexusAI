package com.nexusai.investigation;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.nexusai.ai.*;
import com.nexusai.approval.ActionCatalogue;
import com.nexusai.approval.ActionExecutor;
import com.nexusai.approval.ActionLog;
import com.nexusai.approval.ActionType;
import com.nexusai.approval.Risk;
import com.nexusai.common.config.AsyncConfig;
import com.nexusai.common.exception.BusinessException;
import com.nexusai.common.exception.QuotaExceededException;
import com.nexusai.common.security.RequestIdFilter;
import java.time.Duration;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executor;
import java.util.function.Supplier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.core.task.TaskRejectedException;
import org.springframework.stereotype.Service;
import reactor.core.Disposable;
import reactor.core.Exceptions;
import reactor.core.publisher.Flux;
import reactor.core.publisher.Sinks;

/**
 * The heart of the backend (BE-IV-01/02): ONE background task per run consumes the Python SSE stream, persists every event with a Spring
 * sequence number and applies the contract's semantics. It runs on the bounded relay executor and is completely independent of any
 * browser connection. A stream that ends after approval_required is NOT terminal: the run waits for decisions and is resumed later
 * (same investigation, same seq counter) by ApprovalFlowService.
 */
@Service
public class RunRelayService {
    private static final Logger log = LoggerFactory.getLogger(RunRelayService.class);

    /** Event types the Python service may send. Spring-originated types (run_started, approval_decided, action_executed) are NOT accepted from it. */
    static final Set<String> PYTHON_EVENTS = Set.of("memory_recalled", "supervisor_routed", "plan", "step_status", "agent_started", "tool_call",
            "tool_result", "evidence_added", "claims_drafted", "claim_verified", "confidence", "loop", "action_proposed", "approval_required",
            "guardrail_triggered", "report_delta", "report_ready", "memory_saved", "error", "done");

    /** Live relay bookkeeping (also tells the sweeper which RUNNING runs are really being worked on). */
    static final class RunHandle {
        final Sinks.Empty<Void> cancelSignal = Sinks.empty();
        volatile boolean cancelRequested;
        void cancel() {
            cancelRequested = true;
            cancelSignal.tryEmitEmpty();
        }
    }

    private static final class RunState {
        boolean terminal;
        boolean awaitingApproval;
        final Set<String> autoExecuted = new HashSet<>();
    }

    private final ConcurrentHashMap<Long, RunHandle> live = new ConcurrentHashMap<>();
    private final InvestigationEventService events;
    private final InvestigationRepository invs;
    private final ActionExecutor actionExecutor;
    private final ActionCatalogue catalogue;
    private final AiServiceClient ai;
    private final ObjectMapper mapper;
    private final Executor relayExecutor;
    private final ApplicationEventPublisher publisher;
    private final RunProperties props;

    public RunRelayService(InvestigationEventService events, InvestigationRepository invs, ActionExecutor actionExecutor, ActionCatalogue catalogue,
                           AiServiceClient ai, ObjectMapper mapper, @Qualifier(AsyncConfig.RUN_RELAY_EXECUTOR) Executor relayExecutor,
                           ApplicationEventPublisher publisher, RunProperties props) {
        this.events = events;
        this.invs = invs;
        this.actionExecutor = actionExecutor;
        this.catalogue = catalogue;
        this.ai = ai;
        this.mapper = mapper;
        this.relayExecutor = relayExecutor;
        this.publisher = publisher;
        this.props = props;
    }

    // ---------------- entry points ----------------

    /** Starts the run in the background. Throws QuotaExceededException (and marks the run FAILED) when every relay slot is busy. */
    public void startAsync(long investigationId, AiInvestigateRequest request) {
        RunHandle h = register(investigationId);
        try {
            relayExecutor.execute(() -> runNew(investigationId, request, h));
        } catch (TaskRejectedException e) {
            live.remove(investigationId, h);
            failRun(investigationId, "The server is at capacity. Please try again in a moment.", "QUOTA_EXCEEDED");
            throw new QuotaExceededException("The server is at capacity running investigations; try again in a moment");
        }
    }

    /** Continues a paused run after the approval decisions (called by ApprovalFlowService). */
    public void resumeAsync(long investigationId, UUID threadId, AiResumeRequest request) {
        RunHandle h = register(investigationId);
        try {
            relayExecutor.execute(() -> runResume(investigationId, threadId, request, h));
        } catch (TaskRejectedException e) {
            live.remove(investigationId, h);
            failRun(investigationId, "The server is at capacity. The run could not be resumed; start it again.", "QUOTA_EXCEEDED");
        }
    }

    /** Stops consuming the upstream stream (the cancelled state itself is persisted by InvestigationService). */
    public void signalCancel(long investigationId) {
        RunHandle h = live.get(investigationId);
        if (h != null) h.cancel();
    }

    public boolean isLive(long investigationId) { return live.containsKey(investigationId); }
    public int liveCount() { return live.size(); }

    private RunHandle register(long id) {
        RunHandle h = new RunHandle();
        live.put(id, h);
        return h;
    }

    // ---------------- run bodies ----------------

    private void runNew(long id, AiInvestigateRequest request, RunHandle h) {
        MDC.put(RequestIdFilter.MDC_KEY, UUID.randomUUID().toString());
        try {
            ObjectNode started = mapper.createObjectNode();
            started.put("investigationId", id);
            started.put("threadId", request.threadId());
            started.put("startedAt", java.time.Instant.now().toString());
            events.emit(id, "run_started", started);
            relay(id, h, () -> ai.investigateStream(request));
        } finally {
            live.remove(id, h);
            MDC.remove(RequestIdFilter.MDC_KEY);
        }
    }

    private void runResume(long id, UUID threadId, AiResumeRequest request, RunHandle h) {
        MDC.put(RequestIdFilter.MDC_KEY, UUID.randomUUID().toString());
        try {
            relay(id, h, () -> ai.resumeStream(threadId, request));
        } finally {
            live.remove(id, h);
            MDC.remove(RequestIdFilter.MDC_KEY);
        }
    }

    private void relay(long id, RunHandle h, Supplier<Flux<AiEvent>> source) {
        RunState st = new RunState();
        Iterator<AiEvent> it = null;
        try {
            Flux<AiEvent> flux = source.get()
                    .timeout(Duration.ofSeconds(props.streamIdleTimeoutSec()))
                    .takeUntilOther(h.cancelSignal.asMono());
            it = flux.toIterable().iterator();
            while (it.hasNext()) {
                if (!process(id, it.next(), st)) break;
            }
            if (st.terminal || h.cancelRequested) return;
            if (st.awaitingApproval) {
                publisher.publishEvent(new ApprovalsMaybeSettled(id));      // resumes immediately if no approval is actually pending
                return;
            }
            failRun(id, "The AI service ended the stream before the run finished.", "AI_SERVICE_UNAVAILABLE");
        } catch (Throwable t) {
            if (h.cancelRequested) return;
            BusinessException be = ai.mapStreamError(Exceptions.unwrap(t));
            log.warn("Run {} failed: {}", id, be.getMessage());
            failRun(id, be.getMessage(), be.getCode().name());
        } finally {
            if (it instanceof Disposable d) d.dispose();
        }
    }

    /** @return false when the stream should stop being read. */
    private boolean process(long id, AiEvent ev, RunState st) {
        String type = ev.type();
        if (!PYTHON_EVENTS.contains(type)) {
            log.warn("Ignoring unexpected event type '{}' from the AI service (run {})", type, id);
            return true;
        }
        JsonNode payload;
        try {
            payload = mapper.readTree(ev.data());
        } catch (JsonProcessingException | RuntimeException e) {
            log.warn("Ignoring malformed {} event (run {})", type, id);
            return true;
        }
        if (payload == null || payload.isMissingNode() || payload.isNull()) payload = mapper.createObjectNode();

        if ("report_delta".equals(type)) {
            events.publishLive(id, type, payload);
            return true;
        }
        Optional<PersistedEvent> persisted = events.emit(id, type, payload);
        if (persisted.isEmpty()) {
            // either the run is already terminal (cancelled/failed elsewhere): stop reading; or the event is invalid in this state: skip it
            return invs.findById(id).map(i -> !i.getStatus().isTerminal()).orElse(false);
        }
        switch (type) {
            case "action_proposed" -> autoExecuteIfLow(id, payload, st);
            case "approval_required" -> st.awaitingApproval = true;
            case "done", "error" -> {
                st.terminal = true;
                return false;
            }
            default -> { }
        }
        return true;
    }

    /**
     * LOW-risk actions are executed automatically by Spring (never by Python). The risk is looked up in the catalogue: an event that
     * claims LOW for a HIGH-risk type is ignored here, so nothing HIGH can ever run without a stored APPROVE.
     */
    private void autoExecuteIfLow(long id, JsonNode payload, RunState st) {
        String actionKey = InvestigationEventPersister.text(payload, "actionKey", null);
        String rawType = InvestigationEventPersister.text(payload, "actionType", "");
        Optional<ActionType> type = catalogue.parse(rawType);
        boolean low = type.map(t -> catalogue.riskOf(t) == Risk.LOW).orElse("LOW".equals(InvestigationEventPersister.text(payload, "risk", "")));
        if (!low) return;
        if (actionKey != null && !st.autoExecuted.add(actionKey)) return;     // a re-proposed action is not executed twice in one stream
        try {
            ActionLog l = actionExecutor.executeAutomatic(id, rawType, payload.get("params"));
            events.emit(id, "action_executed", executedPayload(l, actionKey));
        } catch (RuntimeException e) {
            log.error("Automatic action failed for run {}", id, e);
        }
    }

    public ObjectNode executedPayload(ActionLog l, String actionKey) {
        ObjectNode n = mapper.createObjectNode();
        n.put("actionLogId", l.getId());
        if (actionKey != null) n.put("actionKey", actionKey); else n.putNull("actionKey");
        n.put("actionType", l.getActionType());
        n.put("status", l.getStatus().name());
        n.put("automatic", l.isAutomatic());
        n.put("note", l.getNote());
        return n;
    }

    /** Whole-run failure: error event + FAILED, partial trace preserved (ADD-FH-03). */
    public void failRun(long id, String message, String code) {
        ObjectNode n = mapper.createObjectNode();
        n.put("code", code);
        n.put("message", message);
        n.put("retryable", true);
        try {
            events.emit(id, "error", n);
        } catch (RuntimeException e) {
            log.error("Could not record failure of run {}", id, e);
        }
    }

    public List<Long> liveIds() { return List.copyOf(live.keySet()); }
}
