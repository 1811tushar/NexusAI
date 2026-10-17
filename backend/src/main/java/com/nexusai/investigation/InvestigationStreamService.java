package com.nexusai.investigation;

import com.nexusai.common.config.AsyncConfig;
import com.nexusai.common.security.AuthenticatedUser;
import java.io.IOException;
import java.util.List;
import java.util.concurrent.Executor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

/**
 * Browser stream (BE-IV-03): authorise, subscribe to the hub FIRST, replay agent_steps with seq > Last-Event-ID, then tail live events.
 * Every frame carries id = seq. Out-of-order or missed live events are repaired from the database, duplicates are dropped, ": ping" goes out every
 * 15 s, and the stream closes after the terminal event (done / error). Each viewer runs on its own virtual thread; the run never depends on it.
 */
@Service
public class InvestigationStreamService {
    private static final Logger log = LoggerFactory.getLogger(InvestigationStreamService.class);
    private static final int PAGE = 200;

    private final InvestigationService investigations;
    private final InvestigationRepository invs;
    private final AgentStepRepository steps;
    private final StreamHub hub;
    private final Executor executor;
    private final RunProperties props;

    public InvestigationStreamService(InvestigationService investigations, InvestigationRepository invs, AgentStepRepository steps, StreamHub hub,
                                      @Qualifier(AsyncConfig.VIRTUAL_THREAD_EXECUTOR) Executor executor, RunProperties props) {
        this.investigations = investigations;
        this.invs = invs;
        this.steps = steps;
        this.hub = hub;
        this.executor = executor;
        this.props = props;
    }

    public SseEmitter open(long id, int afterSeq, AuthenticatedUser actor) {
        investigations.requireVisible(id, actor);                          // 404 for a foreign id, before any stream is opened
        SseEmitter emitter = new SseEmitter(0L);                           // no server-side timeout: runs and approvals can take long
        AtomicBoolean closed = new AtomicBoolean(false);
        emitter.onCompletion(() -> closed.set(true));
        emitter.onTimeout(() -> closed.set(true));
        emitter.onError(e -> closed.set(true));
        StreamHub.Subscriber sub = hub.subscribe(id);                      // subscribe before reading the DB: nothing can fall in between
        try {
            executor.execute(() -> pump(id, Math.max(afterSeq, 0), emitter, sub, closed));
        } catch (RuntimeException e) {
            hub.unsubscribe(id, sub);
            throw e;
        }
        return emitter;
    }

    private void pump(long id, int after, SseEmitter emitter, StreamHub.Subscriber sub, AtomicBoolean closed) {
        int[] last = {after};
        try {
            if (catchUp(id, last, emitter, closed)) { finish(emitter); return; }
            if (invs.findById(id).map(i -> i.getStatus().isTerminal()).orElse(true) && !closed.get()) {
                // terminal run whose last events were already replayed (e.g. a run recovered after a restart): nothing more will come
                if (catchUp(id, last, emitter, closed)) { finish(emitter); return; }
                finish(emitter);
                return;
            }
            while (!closed.get()) {
                if (sub.overflowed()) break;                               // too slow: the client reconnects with Last-Event-ID and catches up from the DB
                StreamHub.Event ev = sub.queue().poll(Math.max(1, props.heartbeatSeconds()), TimeUnit.SECONDS);
                if (ev == null) {
                    if (sub.overflowed()) break;                           // too slow: the client reconnects with Last-Event-ID
                    emitter.send(SseEmitter.event().comment(" ping"));
                    continue;
                }
                if (ev.liveOnly()) {
                    emitter.send(SseEmitter.event().name(ev.type()).data(ev.json()));
                    continue;
                }
                if (ev.seq() <= last[0]) continue;                         // duplicate of something already replayed
                if (ev.seq() == last[0] + 1) {
                    send(emitter, ev.seq(), ev.type(), ev.json());
                    last[0] = ev.seq();
                    if (isTerminalType(ev.type())) { finish(emitter); return; }
                } else if (catchUp(id, last, emitter, closed)) {           // gap (events published out of order): repair from the DB
                    finish(emitter);
                    return;
                }
            }
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        } catch (IOException | IllegalStateException e) {
            log.debug("Viewer of investigation {} went away: {}", id, e.toString());   // browser closed: normal, the run is unaffected
        } catch (RuntimeException e) {
            log.warn("Stream of investigation {} failed", id, e);
        } finally {
            hub.unsubscribe(id, sub);
            try { emitter.complete(); } catch (RuntimeException ignored) { /* already completed */ }
        }
    }

    /** Sends every persisted event after last[0]; @return true when a terminal event was sent. */
    private boolean catchUp(long id, int[] last, SseEmitter emitter, AtomicBoolean closed) throws IOException {
        while (!closed.get()) {
            List<AgentStep> page = steps.findByInvestigationIdAndSeqGreaterThanOrderBySeqAsc(id, last[0], PageRequest.of(0, PAGE));
            if (page.isEmpty()) return false;
            for (AgentStep s : page) {
                send(emitter, s.getSeq(), s.getType(), s.getPayload().toString());
                last[0] = s.getSeq();
                if (isTerminalType(s.getType())) return true;
            }
        }
        return false;
    }

    private static void send(SseEmitter emitter, int seq, String type, String json) throws IOException {
        emitter.send(SseEmitter.event().id(Integer.toString(seq)).name(type).data(json));
    }

    private static boolean isTerminalType(String type) { return "done".equals(type) || "error".equals(type); }

    private static void finish(SseEmitter emitter) { emitter.complete(); }
}
