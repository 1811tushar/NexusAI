package com.nexusai.investigation;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import com.nexusai.common.Docs;
import com.nexusai.user.Role;
import io.micrometer.core.instrument.MeterRegistry;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.web.reactive.function.BodyInserters;

/** BE-PL-08: run duration, loops, pending approvals, AI errors and ingestion duration are exported as Micrometer meters. */
class MetricsIT extends RunTestSupport {
    @Autowired MeterRegistry registry;

    private double counter(String name, String tag, String value) {
        var c = registry.find(name).tag(tag, value).counter();
        return c == null ? 0 : c.count();
    }

    @Test
    void runMetricsAreRecordedAtTheTerminalEvent() {
        double before = counter("nexus.runs.finished", "status", "COMPLETED");
        stubInvestigate(happyBody());
        awaitStatus(startRun(sessionFor(Role.ANALYST)), "COMPLETED");
        assertThat(counter("nexus.runs.finished", "status", "COMPLETED")).isEqualTo(before + 1);
        assertThat(registry.get("nexus.run.duration").tag("status", "COMPLETED").timer().count()).isGreaterThanOrEqualTo(1);
        assertThat(registry.get("nexus.run.loops").tag("status", "COMPLETED").summary().count()).isGreaterThanOrEqualTo(1);
    }

    @Test
    void failedRunsAreCountedUnderTheirOwnStatus() {
        double before = counter("nexus.runs.finished", "status", "FAILED");
        stubInvestigate(frame("error", "{\"code\":\"INTERNAL_ERROR\",\"message\":\"boom\",\"retryable\":false}"));
        awaitStatus(startRun(sessionFor(Role.ANALYST)), "FAILED");
        assertThat(counter("nexus.runs.finished", "status", "FAILED")).isEqualTo(before + 1);
    }

    @Test
    void pendingApprovalsGaugeFollowsTheDatabase() {
        assertThat(registry.get("nexus.approvals.pending").gauge().value()).isZero();
        stubInvestigate(frame("plan", "{\"steps\":[]}") + approvalRequired(highAction("a1", "ADJUST_PRICE", "{\"productId\":3,\"changePct\":-10}")));
        long id = startRun(sessionFor(Role.ANALYST));
        awaitStatus(id, "AWAITING_APPROVAL");
        assertThat(registry.get("nexus.approvals.pending").gauge().value()).isEqualTo(1.0);
        assertThat(registry.get("nexus.runs.live").gauge().value()).isGreaterThanOrEqualTo(0.0);
    }

    @Test
    void aiErrorsAreCountedByCode() {
        double before = counter("nexus.ai.errors", "code", "AI_SERVICE_UNAVAILABLE");
        AI.stubFor(post(urlEqualTo("/internal/search")).willReturn(aResponse().withStatus(503)));
        web.get().uri("/api/search?q=price").header("Authorization", bearer(sessionFor(Role.ANALYST))).exchange().expectStatus().isEqualTo(503);
        assertThat(counter("nexus.ai.errors", "code", "AI_SERVICE_UNAVAILABLE")).isGreaterThan(before);
    }

    @Test
    void ingestionDurationIsRecordedPerOutcome() {
        stubIngestOk(1, 1);
        Session s = sessionFor(Role.ANALYST);
        MultipartBodyBuilder mb = new MultipartBodyBuilder();
        mb.part("file", new ByteArrayResource(Docs.pdf()) { @Override public String getFilename() { return "m.pdf"; } }, MediaType.APPLICATION_PDF).filename("m.pdf");
        web.post().uri("/api/documents").header("Authorization", bearer(s)).contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(mb.build())).exchange().expectStatus().isAccepted();
        await().atMost(Duration.ofSeconds(10)).until(() -> registry.find("nexus.ingestion.duration").tag("outcome", "READY").timer() != null);
        assertThat(registry.get("nexus.ingestion.duration").tag("outcome", "READY").timer().count()).isGreaterThanOrEqualTo(1);
    }
}
