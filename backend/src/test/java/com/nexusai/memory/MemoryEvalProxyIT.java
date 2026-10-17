package com.nexusai.memory;

import static com.github.tomakehurst.wiremock.client.WireMock.*;

import com.nexusai.common.IntegrationTestBase;
import com.nexusai.user.Role;
import org.junit.jupiter.api.Test;

/** BE-ME-01 / BE-EV-01: memory calls always carry the AUTHENTICATED user id; eval data is proxied for admins. */
class MemoryEvalProxyIT extends IntegrationTestBase {

    @Test
    void listForwardsTheAuthenticatedUserIdAndQuery() {
        AI.stubFor(get(urlPathEqualTo("/internal/memories")).willReturn(okJson("""
                {"items":[{"id":4,"summary":"Q2 revenue fell","sourceInvestigationId":9,"importance":0.7,"createdAt":"2026-05-01T10:00:00Z","lastAccessedAt":null}],
                 "page":0,"size":20,"totalItems":1,"totalPages":1}""")));
        Session s = sessionFor(Role.ANALYST);
        web.get().uri("/api/memories?q=revenue&userId=999").header("Authorization", bearer(s)).exchange().expectStatus().isOk().expectBody()
                .jsonPath("$.data.items[0].summary").isEqualTo("Q2 revenue fell").jsonPath("$.data.items[0].sourceInvestigationId").isEqualTo(9);
        AI.verify(getRequestedFor(urlPathEqualTo("/internal/memories")).withQueryParam("userId", equalTo(String.valueOf(s.user().getId())))
                .withQueryParam("q", equalTo("revenue")).withHeader("X-Internal-API-Key", equalTo(INTERNAL_KEY)));
        AI.verify(0, getRequestedFor(urlPathEqualTo("/internal/memories")).withQueryParam("userId", equalTo("999")));   // a client-supplied id is ignored
    }

    @Test
    void deleteOneScopesToTheUserAndReportsMissingAs404() {
        AI.stubFor(delete(urlPathEqualTo("/internal/memories/4")).willReturn(okJson("{\"deleted\":1}")));
        AI.stubFor(delete(urlPathEqualTo("/internal/memories/5")).willReturn(okJson("{\"deleted\":0}")));
        Session s = sessionFor(Role.ANALYST);
        web.delete().uri("/api/memories/4").header("Authorization", bearer(s)).exchange().expectStatus().isNoContent();
        web.delete().uri("/api/memories/5").header("Authorization", bearer(s)).exchange().expectStatus().isNotFound();
        AI.verify(deleteRequestedFor(urlPathEqualTo("/internal/memories/4")).withQueryParam("userId", equalTo(String.valueOf(s.user().getId()))));
    }

    @Test
    void forgetEverythingOnlyForTheCaller() {
        AI.stubFor(delete(urlPathEqualTo("/internal/memories")).willReturn(okJson("{\"deleted\":3}")));
        Session s = sessionFor(Role.APPROVER);
        web.delete().uri("/api/memories").header("Authorization", bearer(s)).exchange().expectStatus().isNoContent();
        AI.verify(deleteRequestedFor(urlPathEqualTo("/internal/memories")).withQueryParam("userId", equalTo(String.valueOf(s.user().getId()))));
    }

    @Test
    void evalRunsAreProxiedForAdminsWithTheV21Shape() {
        AI.stubFor(get(urlPathEqualTo("/internal/eval/runs")).willReturn(okJson("""
                [{"id":1,"createdAt":"2026-09-01T10:00:00Z","variant":"fixed+vector","system":"AGENT_NO_VERIFIER","questionCount":40,
                  "metrics":{"answerCorrectness":0.8,"groundedClaimsShare":0.9,"hallucinationRate":0.05,"avgLatencyMs":9000,"avgTokens":12000,
                             "approvalGateCompliance":1.0,"retrievalHitRate":0.77,"citationValidity":0.95,"guardrailBlockRate":null,"failureRecoveryRate":0.8},"extra":"ignored"}]""")));
        AI.stubFor(get(urlPathEqualTo("/internal/eval/runs/1")).willReturn(okJson("""
                {"id":1,"createdAt":"2026-09-01T10:00:00Z","variant":null,"system":"AGENT","questionCount":1,
                 "metrics":{"answerCorrectness":1,"groundedClaimsShare":1,"hallucinationRate":0,"avgLatencyMs":1,"avgTokens":1},
                 "results":[{"questionId":"q1","category":"MISSING_DATA","question":"?","expectedFacts":["x"],"answer":"a","correct":true,"groundedShare":1,"hallucinated":false,"latencyMs":5}]}""")));
        Session admin = sessionFor(Role.ADMIN);
        web.get().uri("/api/eval/runs").header("Authorization", bearer(admin)).exchange().expectStatus().isOk().expectBody()
                .jsonPath("$.data[0].system").isEqualTo("AGENT_NO_VERIFIER").jsonPath("$.data[0].metrics.retrievalHitRate").isEqualTo(0.77)
                .jsonPath("$.data[0].metrics.guardrailBlockRate").isEmpty();
        web.get().uri("/api/eval/runs/1").header("Authorization", bearer(admin)).exchange().expectBody().jsonPath("$.data.results[0].category").isEqualTo("MISSING_DATA");
    }

    @Test
    void aiOutageIsReportedAsAvailabilityError() {
        AI.stubFor(get(urlPathEqualTo("/internal/memories")).willReturn(aResponse().withStatus(503)));
        web.get().uri("/api/memories").header("Authorization", bearer(sessionFor(Role.ANALYST))).exchange().expectStatus().isEqualTo(503)
                .expectBody().jsonPath("$.error.code").isEqualTo("AI_SERVICE_UNAVAILABLE");
    }
}
