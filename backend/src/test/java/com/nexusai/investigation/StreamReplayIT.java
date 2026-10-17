package com.nexusai.investigation;

import static org.assertj.core.api.Assertions.assertThat;

import com.nexusai.user.Role;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.CompletableFuture;
import org.junit.jupiter.api.Test;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.MediaType;
import org.springframework.http.codec.ServerSentEvent;
import org.springframework.test.web.reactive.server.WebTestClient;

/** BE-IV-03: replay from Last-Event-ID / ?after, late joiners, many viewers, headers, auth before streaming. */
class StreamReplayIT extends RunTestSupport {

    private WebTestClient viewer() { return web.mutate().responseTimeout(Duration.ofSeconds(40)).build(); }

    private List<ServerSentEvent<String>> read(Session s, long id, String query, String lastEventId) {
        var req = viewer().get().uri("/api/investigations/" + id + "/stream" + query).header("Authorization", bearer(s)).accept(MediaType.TEXT_EVENT_STREAM);
        if (lastEventId != null) req = req.header("Last-Event-ID", lastEventId);
        return req.exchange().expectStatus().isOk()
                .returnResult(new ParameterizedTypeReference<ServerSentEvent<String>>() { }).getResponseBody().collectList().block(Duration.ofSeconds(40));
    }

    private static List<Integer> ids(List<ServerSentEvent<String>> events) {
        return events.stream().filter(e -> e.id() != null).map(e -> Integer.parseInt(e.id())).toList();
    }

    private long completedRun(Session s) {
        stubInvestigate(happyBody());
        long id = startRun(s);
        awaitStatus(id, "COMPLETED");
        return id;
    }

    @Test
    void replayFromTheStartIsCompleteContiguousAndClosesAfterDone() {
        Session s = sessionFor(Role.ANALYST);
        long id = completedRun(s);
        List<ServerSentEvent<String>> events = read(s, id, "", null);
        int total = count("select count(*) from agent_steps where investigation_id = ?", id);
        assertThat(ids(events)).hasSize(total).isEqualTo(java.util.stream.IntStream.rangeClosed(1, total).boxed().toList());
        assertThat(events.get(events.size() - 1).event()).isEqualTo("done");
        assertThat(events.stream().map(ServerSentEvent::event)).doesNotContain("report_delta");       // live-only, never replayed
    }

    @Test
    void lastEventIdAndAfterResumeWithoutDuplicatesOrGaps() {
        Session s = sessionFor(Role.ANALYST);
        long id = completedRun(s);
        int total = count("select count(*) from agent_steps where investigation_id = ?", id);
        assertThat(ids(read(s, id, "", "5"))).isEqualTo(java.util.stream.IntStream.rangeClosed(6, total).boxed().toList());
        assertThat(ids(read(s, id, "?after=" + (total - 2), null))).containsExactly(total - 1, total);
        assertThat(read(s, id, "?after=" + total, null)).isEmpty();                                   // nothing missed: closes immediately
        assertThat(ids(read(s, id, "?after=3", "10")).get(0)).isEqualTo(11);                         // the header wins over ?after
    }

    @Test
    void twoViewersAndALateJoinerSeeTheSameOrderedStreamWhileTheRunIsLive() throws Exception {
        stubInvestigateSlow(happyBody(), 5000);
        Session s = sessionFor(Role.ANALYST);
        long id = startRun(s);
        CompletableFuture<List<ServerSentEvent<String>>> v1 = CompletableFuture.supplyAsync(() -> read(s, id, "", null));
        CompletableFuture<List<ServerSentEvent<String>>> v2 = CompletableFuture.supplyAsync(() -> read(sessionFor(Role.ADMIN), id, "", null));
        Thread.sleep(2500);                                                                            // mid-run
        CompletableFuture<List<ServerSentEvent<String>>> late = CompletableFuture.supplyAsync(() -> read(sessionFor(Role.APPROVER), id, "", null));

        List<ServerSentEvent<String>> a = v1.get(45, java.util.concurrent.TimeUnit.SECONDS);
        List<ServerSentEvent<String>> b = v2.get(45, java.util.concurrent.TimeUnit.SECONDS);
        List<ServerSentEvent<String>> c = late.get(45, java.util.concurrent.TimeUnit.SECONDS);
        awaitStatus(id, "COMPLETED");
        int total = count("select count(*) from agent_steps where investigation_id = ?", id);
        List<Integer> expected = java.util.stream.IntStream.rangeClosed(1, total).boxed().toList();
        assertThat(ids(a)).isEqualTo(expected);
        assertThat(ids(b)).isEqualTo(expected);
        assertThat(ids(c)).isEqualTo(expected);                                                        // the late joiner got replay + live, no gap, no duplicate
        assertThat(a.stream().filter(e -> "report_delta".equals(e.event())).count()).isEqualTo(2);    // live viewers also receive the unnumbered deltas
        assertThat(a.get(a.size() - 1).event()).isEqualTo("done");
    }

    @Test
    void streamHeadersAndEarlyAuthorisation() {
        Session owner = sessionFor(Role.ANALYST);
        long id = completedRun(owner);
        viewer().get().uri("/api/investigations/" + id + "/stream").header("Authorization", bearer(owner)).accept(MediaType.TEXT_EVENT_STREAM).exchange()
                .expectStatus().isOk().expectHeader().contentTypeCompatibleWith(MediaType.TEXT_EVENT_STREAM)
                .expectHeader().value("Cache-Control", v -> assertThat(v).contains("no-cache")).expectHeader().valueEquals("X-Accel-Buffering", "no");
        // a foreign id is a JSON 404 even though the client asked for an event stream; no stream is opened
        web.get().uri("/api/investigations/" + id + "/stream").header("Authorization", bearer(sessionFor(Role.ANALYST))).accept(MediaType.TEXT_EVENT_STREAM)
                .exchange().expectStatus().isNotFound().expectBody().jsonPath("$.error.code").isEqualTo("NOT_FOUND");
        web.get().uri("/api/investigations/" + id + "/stream").accept(MediaType.TEXT_EVENT_STREAM).exchange().expectStatus().isUnauthorized();
    }

    @Test
    void anIdleStreamIsKeptAliveWithPingComments() {
        // a run waiting for approval produces no events: the viewer must still receive ': ping' heartbeats (1 s in tests, 15 s in production)
        stubInvestigate(frame("plan", "{\"steps\":[]}") + approvalRequired(highAction("a1", "ADJUST_PRICE", "{\"productId\":3,\"changePct\":-10}")));
        Session s = sessionFor(Role.ANALYST);
        long id = startRun(s);
        awaitStatus(id, "AWAITING_APPROVAL");
        List<ServerSentEvent<String>> events = viewer().get().uri("/api/investigations/" + id + "/stream").header("Authorization", bearer(s))
                .accept(MediaType.TEXT_EVENT_STREAM).exchange().expectStatus().isOk()
                .returnResult(new ParameterizedTypeReference<ServerSentEvent<String>>() { }).getResponseBody()
                .take(Duration.ofSeconds(4)).collectList().block(Duration.ofSeconds(20));
        assertThat(events.stream().filter(e -> e.id() != null).count()).isEqualTo(count("select count(*) from agent_steps where investigation_id = ?", id));
        assertThat(events.stream().anyMatch(e -> e.comment() != null && e.comment().contains("ping"))).isTrue();
        assertThat(events.stream().map(ServerSentEvent::event)).doesNotContain("done");     // still waiting: the stream stays open
    }

    @Test
    void stepsEndpointReturnsTheFullPersistedTrace() {
        Session s = sessionFor(Role.ANALYST);
        long id = completedRun(s);
        int total = count("select count(*) from agent_steps where investigation_id = ?", id);
        web.get().uri("/api/investigations/" + id + "/steps").header("Authorization", bearer(s)).exchange().expectBody()
                .jsonPath("$.data.length()").isEqualTo(total).jsonPath("$.data[0].type").isEqualTo("run_started").jsonPath("$.data[0].seq").isEqualTo(1);
    }
}
