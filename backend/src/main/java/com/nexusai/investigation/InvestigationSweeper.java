package com.nexusai.investigation;

import java.time.Duration;
import java.time.Instant;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.context.event.ApplicationReadyEvent;
import org.springframework.context.event.EventListener;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/**
 * BE-IV-06: at startup every RUNNING run has lost its relay (the JVM that held it is gone), so it is marked FAILED "interrupted by restart".
 * AWAITING_APPROVAL runs are left alone: their checkpoint lives in Python and their approvals live in Postgres. A periodic check catches a
 * RUNNING run with no live relay and no recent activity (e.g. a relay that died); a grace period protects runs that are just being resumed.
 */
@Component
public class InvestigationSweeper {
    private static final Logger log = LoggerFactory.getLogger(InvestigationSweeper.class);
    private final InvestigationRepository invs;
    private final AgentStepRepository steps;
    private final RunRelayService relay;
    private final InvestigationEventService events;
    private final com.fasterxml.jackson.databind.ObjectMapper mapper;
    private final RunProperties props;

    public InvestigationSweeper(InvestigationRepository invs, AgentStepRepository steps, RunRelayService relay, InvestigationEventService events,
                                com.fasterxml.jackson.databind.ObjectMapper mapper, RunProperties props) {
        this.invs = invs;
        this.steps = steps;
        this.relay = relay;
        this.events = events;
        this.mapper = mapper;
        this.props = props;
    }

    @EventListener(ApplicationReadyEvent.class)
    public void onStartup() { recoverOrphans(Duration.ZERO); }

    @Scheduled(fixedDelayString = "${nexus.runs.expiry-job-interval-ms:60000}", initialDelayString = "${nexus.runs.expiry-job-interval-ms:60000}")
    public void periodic() { recoverOrphans(Duration.ofSeconds(props.orphanGraceSec())); }

    /** @return number of runs marked FAILED. Public so tests (and operators) can trigger it. */
    public int recoverOrphans(Duration grace) {
        int n = 0;
        Instant cutoff = Instant.now().minus(grace);
        for (Investigation i : invs.findByStatus(InvestigationStatus.RUNNING)) {
            if (relay.isLive(i.getId())) continue;
            Instant last = steps.lastActivity(i.getId());
            if (last == null) last = i.getCreatedAt();
            if (last.isAfter(cutoff)) continue;
            var err = mapper.createObjectNode();
            err.put("code", "INTERNAL_ERROR");
            err.put("message", "The investigation was interrupted by a restart. Start it again.");
            err.put("retryable", true);
            if (events.emit(i.getId(), "error", err).isPresent()) {
                n++;
                log.warn("Investigation {} marked FAILED: interrupted by restart", i.getId());
            }
        }
        return n;
    }
}
