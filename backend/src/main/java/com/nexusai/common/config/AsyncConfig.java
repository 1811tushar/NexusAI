package com.nexusai.common.config;

import java.util.concurrent.Executor;
import java.util.concurrent.Executors;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;

/**
 * Two named executors:
 * <ul>
 *   <li>{@code virtualThreadExecutor}: unbounded virtual threads for blocking I/O work (document ingestion, deletion retries).</li>
 *   <li>{@code runRelayExecutor}: BOUNDED pool reserved for Backend B's investigation run relays (one task per run, each holds an
 *       upstream SSE connection open for minutes, so the pool size is the global cap on concurrent runs).</li>
 * </ul>
 */
@Configuration
public class AsyncConfig {
    public static final String VIRTUAL_THREAD_EXECUTOR = "virtualThreadExecutor";
    public static final String RUN_RELAY_EXECUTOR = "runRelayExecutor";

    @Bean(name = VIRTUAL_THREAD_EXECUTOR, destroyMethod = "close")
    public java.util.concurrent.ExecutorService virtualThreadExecutor() {
        return Executors.newThreadPerTaskExecutor(Thread.ofVirtual().name("nx-virtual-", 0).factory());
    }

    @Bean(name = RUN_RELAY_EXECUTOR)
    public Executor runRelayExecutor() {
        ThreadPoolTaskExecutor ex = new ThreadPoolTaskExecutor();
        ex.setThreadNamePrefix("nx-run-relay-");
        ex.setCorePoolSize(4);
        ex.setMaxPoolSize(16);
        ex.setQueueCapacity(0);                       // reject instead of queueing a run behind others
        ex.setWaitForTasksToCompleteOnShutdown(false);
        ex.initialize();
        return ex;
    }
}
