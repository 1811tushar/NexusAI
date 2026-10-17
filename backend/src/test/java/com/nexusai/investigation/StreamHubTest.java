package com.nexusai.investigation;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class StreamHubTest {
    private final StreamHub hub = new StreamHub();

    @Test void publishReachesEverySubscriberOfThatInvestigationOnly() {
        StreamHub.Subscriber a = hub.subscribe(1);
        StreamHub.Subscriber b = hub.subscribe(1);
        StreamHub.Subscriber other = hub.subscribe(2);
        hub.publish(1, new StreamHub.Event(1, "plan", "{}"));
        assertThat(a.queue()).hasSize(1);
        assertThat(b.queue()).hasSize(1);
        assertThat(other.queue()).isEmpty();
        assertThat(hub.viewerCount(1)).isEqualTo(2);
    }

    @Test void unsubscribeStopsDeliveryAndCleansUp() {
        StreamHub.Subscriber a = hub.subscribe(1);
        hub.unsubscribe(1, a);
        hub.publish(1, new StreamHub.Event(1, "plan", "{}"));
        assertThat(a.queue()).isEmpty();
        assertThat(hub.viewerCount(1)).isZero();
    }

    @Test void slowViewerIsFlaggedInsteadOfBlockingThePublisher() {
        StreamHub.Subscriber slow = hub.subscribe(1);
        for (int i = 0; i < StreamHub.QUEUE_CAPACITY + 5; i++) hub.publish(1, new StreamHub.Event(i + 1, "tool_call", "{}"));
        assertThat(slow.overflowed()).isTrue();
        assertThat(slow.queue()).hasSize(StreamHub.QUEUE_CAPACITY);
    }

    @Test void liveOnlyEventsHaveNoSequence() {
        assertThat(new StreamHub.Event(-1, "report_delta", "{}").liveOnly()).isTrue();
        assertThat(new StreamHub.Event(3, "plan", "{}").liveOnly()).isFalse();
    }
}
