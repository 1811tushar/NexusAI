package com.nexusai.investigation;

import static org.assertj.core.api.Assertions.assertThat;

import com.nexusai.user.Role;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;

/** BE-IV-05, SEC-01: analysts see only their own investigations (foreign id = 404); approvers and admins see all. */
class VisibilityIT extends RunTestSupport {

    @Test
    void foreignInvestigationLooksMissingToAnalystsButVisibleToApproverAndAdmin() {
        stubInvestigate(happyBody());
        Session owner = sessionFor(Role.ANALYST);
        Session other = sessionFor(Role.ANALYST);
        long id = startRun(owner);
        awaitStatus(id, "COMPLETED");
        String base = "/api/investigations/" + id;

        for (String suffix : new String[] {"", "/steps", "/report.md", "/stream"}) {
            web.get().uri(base + suffix).header("Authorization", bearer(other)).exchange().expectStatus().isNotFound();
            web.get().uri(base + suffix).header("Authorization", bearer(owner)).exchange().expectStatus().isOk();
            web.get().uri(base + suffix).header("Authorization", bearer(sessionFor(Role.APPROVER))).exchange().expectStatus().isOk();
            web.get().uri(base + suffix).header("Authorization", bearer(sessionFor(Role.ADMIN))).exchange().expectStatus().isOk();
        }
        web.post().uri(base + "/feedback").header("Authorization", bearer(other)).contentType(MediaType.APPLICATION_JSON).bodyValue(Map.of("rating", 1))
                .exchange().expectStatus().isNotFound();
        // visible but not the owner: an approver/admin cannot leave feedback for someone else's report
        web.post().uri(base + "/feedback").header("Authorization", bearer(sessionFor(Role.ADMIN))).contentType(MediaType.APPLICATION_JSON).bodyValue(Map.of("rating", 1))
                .exchange().expectStatus().isForbidden();
    }

    @Test
    void listsAreScopedAndMineFiltersApproversAndAdmins() {
        stubInvestigate(doneFrame("COMPLETED"));
        Session a1 = sessionFor(Role.ANALYST);
        Session a2 = sessionFor(Role.ANALYST);
        Session admin = sessionFor(Role.ADMIN);
        awaitStatus(startRun(a1), "COMPLETED");
        awaitStatus(startRun(a2), "COMPLETED");
        awaitStatus(startRun(admin), "COMPLETED");

        total(a1, "", 1);
        total(a2, "?mine=false", 1);                    // an analyst cannot widen the scope
        total(sessionFor(Role.APPROVER), "", 3);
        total(admin, "", 3);
        total(admin, "?mine=true", 1);
        total(admin, "?q=revenue", 3);
        total(admin, "?q=nothing-like-this", 0);
        total(admin, "?status=FAILED", 0);
        web.get().uri("/api/investigations?sort=password,asc").header("Authorization", bearer(admin)).exchange().expectStatus().isBadRequest();
    }

    private void total(Session s, String query, int expected) {
        web.get().uri("/api/investigations" + query).header("Authorization", bearer(s)).exchange().expectStatus().isOk()
                .expectBody().jsonPath("$.data.totalItems").isEqualTo(expected);
    }

    @Test
    void dashboardAndActionLogAreRoleScoped() {
        stubInvestigate(happyBody());
        Session owner = sessionFor(Role.ANALYST);
        Session other = sessionFor(Role.ANALYST);
        awaitStatus(startRun(owner), "COMPLETED");

        web.get().uri("/api/dashboard/summary").header("Authorization", bearer(owner)).exchange().expectBody()
                .jsonPath("$.data.investigationsByStatus.COMPLETED").isEqualTo(1).jsonPath("$.data.investigationsByStatus.REFUSED").isEqualTo(0)
                .jsonPath("$.data.avgConfidence30d").isEqualTo(0.82).jsonPath("$.data.recent.length()").isEqualTo(1).jsonPath("$.data.documentsReady").isEqualTo(0);
        web.get().uri("/api/dashboard/summary").header("Authorization", bearer(other)).exchange().expectBody()
                .jsonPath("$.data.investigationsByStatus.COMPLETED").isEqualTo(0).jsonPath("$.data.avgConfidence30d").isEmpty().jsonPath("$.data.recent.length()").isEqualTo(0);
        web.get().uri("/api/dashboard/summary").header("Authorization", bearer(sessionFor(Role.APPROVER))).exchange().expectBody()
                .jsonPath("$.data.investigationsByStatus.COMPLETED").isEqualTo(1);

        web.get().uri("/api/actions").header("Authorization", bearer(owner)).exchange().expectBody().jsonPath("$.data.totalItems").isEqualTo(1);
        web.get().uri("/api/actions").header("Authorization", bearer(other)).exchange().expectBody().jsonPath("$.data.totalItems").isEqualTo(0);
        web.get().uri("/api/actions").header("Authorization", bearer(sessionFor(Role.APPROVER))).exchange().expectBody().jsonPath("$.data.totalItems").isEqualTo(1);
    }

    @Test
    void feedbackAndReportExport() {
        stubInvestigate(happyBody());
        Session owner = sessionFor(Role.ANALYST);
        long id = startRun(owner);
        awaitStatus(id, "COMPLETED");
        String md = web.get().uri("/api/investigations/" + id + "/report.md").header("Authorization", bearer(owner)).exchange().expectStatus().isOk()
                .expectHeader().contentTypeCompatibleWith("text/markdown").expectHeader().value("Content-Disposition", v -> assertThat(v).contains("investigation-" + id + "-report.md"))
                .expectBody(String.class).returnResult().getResponseBody();
        assertThat(md).contains("# Report").contains("## Claims and verification").contains("UNSUPPORTED").contains("[key claim]").contains("simulated");

        web.post().uri("/api/investigations/" + id + "/feedback").header("Authorization", bearer(owner)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("rating", 3)).exchange().expectStatus().isBadRequest();
        web.post().uri("/api/investigations/" + id + "/feedback").header("Authorization", bearer(owner)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("rating", -1, "comment", "Missed the supplier note")).exchange().expectStatus().isNoContent();
        assertThat(jdbc.queryForObject("select feedback_rating from investigations where id = ?", Integer.class, id)).isEqualTo(-1);
        web.get().uri("/api/investigations/" + id).header("Authorization", bearer(owner)).exchange().expectBody().jsonPath("$.data.feedbackRating").isEqualTo(-1);
    }

    @Test
    void reportIsNotAvailableUntilReady() {
        Session owner = sessionFor(Role.ANALYST);
        long id = jdbc.queryForObject("insert into investigations(user_id, question, status, thread_id) values (?, 'Why did revenue fall?', 'RUNNING', gen_random_uuid()) returning id",
                Long.class, owner.user().getId());
        web.get().uri("/api/investigations/" + id + "/report.md").header("Authorization", bearer(owner)).exchange().expectStatus().isEqualTo(409);
        web.post().uri("/api/investigations/" + id + "/feedback").header("Authorization", bearer(owner)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("rating", 1)).exchange().expectStatus().isEqualTo(409);
    }
}
