package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import java.util.Optional;
import org.springframework.stereotype.Service;

/** Persist-then-publish: the event is committed by the persister first, so viewers can always recover it from the database. */
@Service
public class InvestigationEventService {
    private final InvestigationEventPersister persister;
    private final StreamHub hub;

    public InvestigationEventService(InvestigationEventPersister persister, StreamHub hub) {
        this.persister = persister;
        this.hub = hub;
    }

    public Optional<PersistedEvent> emit(long investigationId, String type, JsonNode payload) {
        Optional<PersistedEvent> p = persister.persist(investigationId, type, payload);
        p.ifPresent(e -> publish(investigationId, e));
        return p;
    }

    public void publish(long investigationId, PersistedEvent e) {
        hub.publish(investigationId, new StreamHub.Event(e.seq(), e.type(), e.payload().toString()));
    }

    /** report_delta: sent to connected viewers only, never stored, no sequence number. */
    public void publishLive(long investigationId, String type, JsonNode payload) {
        hub.publish(investigationId, new StreamHub.Event(-1, type, payload.toString()));
    }
}
