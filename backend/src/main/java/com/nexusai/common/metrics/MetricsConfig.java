package com.nexusai.common.metrics;

import com.nexusai.approval.ApprovalRepository;
import com.nexusai.approval.ApprovalStatus;
import com.nexusai.investigation.RunRelayService;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.binder.MeterBinder;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
public class MetricsConfig {
    /**
     * Gauges resolve their beans lazily (at scrape time) through ObjectProviders: binding happens while the MeterRegistry is still being
     * created, and RunRelayService (via AiServiceClient -> NexusMetrics) needs that registry, so eager injection would be a cycle.
     * The Supplier form keeps a strong reference (a state-object gauge would be garbage collected).
     */
    @Bean
    public MeterBinder nexusGauges(ObjectProvider<ApprovalRepository> approvals, ObjectProvider<RunRelayService> relay) {
        return registry -> {
            Gauge.builder("nexus.approvals.pending", () -> approvals.getObject().countByStatus(ApprovalStatus.PENDING))
                    .description("Approvals waiting for a decision").register(registry);
            Gauge.builder("nexus.runs.live", () -> relay.getObject().liveCount())
                    .description("Investigation runs currently being relayed").register(registry);
        };
    }
}
