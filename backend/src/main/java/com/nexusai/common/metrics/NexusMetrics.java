package com.nexusai.common.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.DistributionSummary;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.time.Duration;
import org.springframework.stereotype.Component;

/**
 * BE-PL-08 business metrics (Prometheus names in brackets):
 * run duration [nexus_run_duration_seconds], loops per run [nexus_run_loops], finished runs [nexus_runs_finished_total],
 * AI errors [nexus_ai_errors_total], ingestion duration [nexus_ingestion_duration_seconds].
 * Gauges (pending approvals [nexus_approvals_pending], live relays [nexus_runs_live]) are registered by MetricsConfig.
 * Tags are low-cardinality enums only: never user ids, questions or document names.
 */
@Component
public class NexusMetrics {
    private final MeterRegistry registry;
    public NexusMetrics(MeterRegistry registry) { this.registry = registry; }

    public void runFinished(String status, long durationMs, int loops) {
        Timer.builder("nexus.run.duration").description("Investigation run duration").tag("status", status).register(registry)
                .record(Duration.ofMillis(Math.max(durationMs, 0)));
        DistributionSummary.builder("nexus.run.loops").description("Confidence loops used per run").tag("status", status).register(registry).record(loops);
        Counter.builder("nexus.runs.finished").description("Finished investigation runs").tag("status", status).register(registry).increment();
    }

    public void aiError(String code) {
        Counter.builder("nexus.ai.errors").description("Failed calls to the AI service").tag("code", code).register(registry).increment();
    }

    public void ingestion(String outcome, long durationMs) {
        Timer.builder("nexus.ingestion.duration").description("Document ingestion duration").tag("outcome", outcome).register(registry)
                .record(Duration.ofMillis(Math.max(durationMs, 0)));
    }
}
