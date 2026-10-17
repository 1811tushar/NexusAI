package com.nexusai.document;

import com.nexusai.common.config.NexusProperties;
import java.time.Duration;
import java.time.Instant;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

/** BE-DC-03: repairs documents stuck in INGESTING and retries pending DELETING ones. */
@Component
public class DocumentSweeper {
    private static final Logger log = LoggerFactory.getLogger(DocumentSweeper.class);
    private final DocumentRepository repo;
    private final DocumentService service;
    private final NexusProperties props;

    public DocumentSweeper(DocumentRepository repo, DocumentService service, NexusProperties props) {
        this.repo = repo;
        this.service = service;
        this.props = props;
    }

    @Scheduled(fixedDelayString = "${nexus.sweeper.interval-ms:60000}", initialDelayString = "${nexus.sweeper.interval-ms:60000}")
    public void sweep() {
        try {
            Instant now = Instant.now();
            Instant cutoff = now.minus(Duration.ofMinutes(props.sweeper().stuckIngestingMinutes()));
            int n = repo.failStuckIngesting(cutoff, "Ingestion timed out. Use Reindex to try again.", now);
            if (n > 0) log.warn("Marked {} stuck INGESTING document(s) FAILED", n);
        } catch (RuntimeException e) {
            log.error("Stuck-ingestion sweep failed", e);
        }
        for (Document d : repo.findByStatus(DocumentStatus.DELETING)) {
            try {
                service.completeDeletion(d.getId());
            } catch (RuntimeException e) {
                log.error("Retry of deletion for document {} failed", d.getId(), e);
            }
        }
    }
}
