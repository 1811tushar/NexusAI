package com.nexusai.investigation;

import java.util.Set;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArraySet;
import java.util.concurrent.LinkedBlockingQueue;
import org.springframework.stereotype.Component;

/**
 * In-memory fan-out of live events to browser viewers. The DATABASE is the source of truth: a viewer replays agent_steps first and
 * only uses this hub for what happens afterwards. Publishing never blocks the run relay: each viewer has a bounded queue and a viewer
 * that cannot keep up is dropped (it reconnects with Last-Event-ID and catches up from the database).
 */
@Component
public class StreamHub {
    public static final int QUEUE_CAPACITY = 2000;

    /** seq < 0 marks a live-only event (report_delta): it has no SSE id and is never replayed. */
    public record Event(int seq, String type, String json) {
        public boolean liveOnly() { return seq < 0; }
    }

    public static final class Subscriber {
        private final BlockingQueue<Event> queue = new LinkedBlockingQueue<>(QUEUE_CAPACITY);
        private volatile boolean overflowed;

        boolean offer(Event e) {
            if (queue.offer(e)) return true;
            overflowed = true;
            return false;
        }
        public BlockingQueue<Event> queue() { return queue; }
        public boolean overflowed() { return overflowed; }
    }

    private final ConcurrentHashMap<Long, Set<Subscriber>> subscribers = new ConcurrentHashMap<>();

    public Subscriber subscribe(long investigationId) {
        Subscriber s = new Subscriber();
        subscribers.computeIfAbsent(investigationId, k -> new CopyOnWriteArraySet<>()).add(s);
        return s;
    }

    public void unsubscribe(long investigationId, Subscriber s) {
        subscribers.computeIfPresent(investigationId, (k, set) -> {
            set.remove(s);
            return set.isEmpty() ? null : set;
        });
    }

    public void publish(long investigationId, Event e) {
        Set<Subscriber> set = subscribers.get(investigationId);
        if (set != null) for (Subscriber s : set) s.offer(e);
    }

    public int viewerCount(long investigationId) {
        Set<Subscriber> set = subscribers.get(investigationId);
        return set == null ? 0 : set.size();
    }
}
