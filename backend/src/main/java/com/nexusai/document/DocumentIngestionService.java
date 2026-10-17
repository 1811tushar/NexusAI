package com.nexusai.document;

import com.nexusai.ai.AiIngestRequest;
import com.nexusai.ai.AiIngestResponse;
import com.nexusai.ai.AiServiceClient;
import com.nexusai.common.config.AsyncConfig;
import com.nexusai.common.config.NexusProperties;
import com.nexusai.common.exception.AiServiceUnavailableException;
import com.nexusai.common.exception.IngestionFailedException;
import com.nexusai.common.exception.LlmRateLimitedException;
import com.nexusai.common.metrics.NexusMetrics;
import com.nexusai.common.security.RequestIdFilter;
import com.nexusai.common.storage.FileStorage;
import java.time.Instant;
import java.util.EnumSet;
import java.util.concurrent.Executor;
import java.util.concurrent.Semaphore;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Service;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

/**
 * BE-DC-02: UPLOADED -> INGESTING -> READY/FAILED. Runs on virtual threads after the upload transaction commits; a semaphore keeps
 * the (CPU/RAM heavy) Python embedder from being flooded. Documents text is never logged.
 */
@Service
public class DocumentIngestionService {
    private static final Logger log = LoggerFactory.getLogger(DocumentIngestionService.class);

    private final DocumentRepository repo;
    private final FileStorage storage;
    private final AiServiceClient ai;
    private final Executor executor;
    private final Semaphore permits;
    private final NexusMetrics metrics;

    public DocumentIngestionService(DocumentRepository repo, FileStorage storage, AiServiceClient ai,
                                    @Qualifier(AsyncConfig.VIRTUAL_THREAD_EXECUTOR) Executor executor, NexusProperties props, NexusMetrics metrics) {
        this.repo = repo;
        this.storage = storage;
        this.ai = ai;
        this.executor = executor;
        this.permits = new Semaphore(Math.max(1, props.upload().ingestConcurrency()));
        this.metrics = metrics;
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT, fallbackExecution = true)
    public void onRequested(DocumentIngestionRequested e) {
        executor.execute(() -> run(e.documentId(), e.requestId()));
    }

    /** Public so tests (and a future manual trigger) can call it synchronously. */
    public void run(long documentId, String requestId) {
        MDC.put(RequestIdFilter.MDC_KEY, requestId);
        try {
            permits.acquire();
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
            MDC.remove(RequestIdFilter.MDC_KEY);
            return;
        }
        try {
            process(documentId);
        } finally {
            permits.release();
            MDC.remove(RequestIdFilter.MDC_KEY);
        }
    }

    private void process(long id) {
        if (repo.transition(id, EnumSet.of(DocumentStatus.UPLOADED), DocumentStatus.INGESTING, Instant.now()) == 0) return;
        Document d = repo.findById(id).orElse(null);
        if (d == null) return;
        long t0 = System.nanoTime();
        try {
            byte[] content = storage.read(d.getStorageKey());
            AiIngestResponse r = ai.ingest(new AiIngestRequest(id, d.getUploadedById(), d.getSourceType(), d.getTitle(), d.getOriginalFilename()),
                    d.getOriginalFilename(), content);
            if (r.warnings() != null && !r.warnings().isEmpty()) log.info("Ingestion of document {} finished with {} warning(s)", id, r.warnings().size());
            metrics.ingestion("READY", (System.nanoTime() - t0) / 1_000_000);
            if (repo.markReady(id, r.pageCount(), r.chunkCount(), Instant.now()) == 0) {
                // The document was deleted (or timed out) while the AI service worked: do not leave orphan vectors behind.
                log.warn("Document {} changed state during ingestion; removing its chunks", id);
                try { ai.deleteDocument(id); } catch (RuntimeException ex) { log.warn("Could not clean up chunks of document {}", id); }
            }
        } catch (IngestionFailedException e) {
            metrics.ingestion("FAILED", (System.nanoTime() - t0) / 1_000_000);
            fail(id, e.getMessage());
        } catch (AiServiceUnavailableException | LlmRateLimitedException e) {
            metrics.ingestion("FAILED", (System.nanoTime() - t0) / 1_000_000);
            fail(id, "The AI service was unavailable. Use Reindex to try again.");
        } catch (RuntimeException e) {
            log.error("Unexpected error while ingesting document {}", id, e);
            metrics.ingestion("FAILED", (System.nanoTime() - t0) / 1_000_000);
            fail(id, "Ingestion failed unexpectedly. Use Reindex to try again.");
        }
    }

    private void fail(long id, String message) {
        repo.markFailed(id, message, Instant.now());
        log.info("Document {} ingestion FAILED", id);
    }
}
