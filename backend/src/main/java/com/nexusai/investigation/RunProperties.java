package com.nexusai.investigation;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.boot.context.properties.bind.DefaultValue;

/** Backend B settings (contract section 11): MAX_CONCURRENT_RUNS_PER_USER, APPROVAL_TTL_DAYS, MAX_LOOPS. Defaults apply without any yml. */
@ConfigurationProperties(prefix = "nexus.runs")
public record RunProperties(@DefaultValue("2") int maxConcurrentPerUser, @DefaultValue("7") int approvalTtlDays,
                            @DefaultValue("3") int defaultMaxLoops, @DefaultValue("5") int maxLoopsLimit,
                            @DefaultValue("300") int streamIdleTimeoutSec, @DefaultValue("60000") long expiryJobIntervalMs,
                            @DefaultValue("300") int orphanGraceSec, @DefaultValue("15") int heartbeatSeconds) { }
