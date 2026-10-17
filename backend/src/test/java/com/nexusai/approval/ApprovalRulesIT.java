package com.nexusai.approval;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.investigation.RunTestSupport;
import com.nexusai.user.Role;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.*;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

/** BE-AP-01..03, BE-IV-04/06, SEC-05: pause/resume, self-approval, roles, race, expiry, forged actions, the HIGH-risk invariant. */
class ApprovalRulesIT extends RunTestSupport {
    @Autowired ApprovalExpiryJob expiryJob;

    private static final String PRICE = highAction("a-high", "ADJUST_PRICE", "{\"productId\":3,\"changePct\":-10}");
    private static final String RESUME_OK = frame("report_ready", "{\"reportMarkdown\":\"# Final\\n\\nDone.\",\"summary\":\"done\",\"recommendations\":[],\"confidence\":0.8}") + doneFrame("COMPLETED");

    private long pausedRun(Session owner, String... actions) {
        stubCancel();
        stubInvestigate(frame("plan", "{\"steps\":[]}") + approvalRequired(actions));
        stubResume(RESUME_OK);
        long id = startRun(owner);
        awaitStatus(id, "AWAITING_APPROVAL");
        return id;
    }

    @Test
    void approvalPausesTheRunThenApproveExecutesSimulatedActionAndResumes() {
        Session analyst = sessionFor(Role.ANALYST);
        Session approver = sessionFor(Role.APPROVER);
        long id = pausedRun(analyst, PRICE);

        long approvalId = approvalIds(id).get(0);
        assertThat(jdbc.queryForMap("select status, risk, action_type, expires_at > now() + interval '6 days' as ttl from approvals where id = ?", approvalId))
                .containsEntry("status", "PENDING").containsEntry("risk", "HIGH").containsEntry("action_type", "ADJUST_PRICE").containsEntry("ttl", true);
        assertThat(count("select count(*) from action_log where investigation_id = ?", id)).isZero();            // nothing ran while waiting
        assertThat(jdbc.queryForObject("select payload->'actions'->0->>'approvalId' from agent_steps where investigation_id = ? and type = 'approval_required'", String.class, id))
                .isEqualTo(String.valueOf(approvalId));
        web.get().uri("/api/approvals/pending-count").header("Authorization", bearer(approver)).exchange().expectBody().jsonPath("$.data.count").isEqualTo(1);
        web.get().uri("/api/investigations/" + id).header("Authorization", bearer(approver)).exchange().expectBody().jsonPath("$.data.pendingApprovals").isEqualTo(1);

        decide(approver, approvalId, "APPROVE", "ok").expectStatus().isOk().expectBody()
                .jsonPath("$.data.status").isEqualTo("APPROVED").jsonPath("$.data.decidedBy.displayName").isEqualTo("APPROVER Tester");
        awaitStatus(id, "COMPLETED");

        assertThat(jdbc.queryForMap("select status, automatic, approval_id, note from action_log where investigation_id = ?", id))
                .containsEntry("status", "EXECUTED").containsEntry("automatic", false).containsEntry("approval_id", approvalId)
                .containsEntry("note", "Simulated execution; no external system was changed.");
        List<String> types = stepTypes(id);
        assertThat(types.indexOf("approval_decided")).isGreaterThan(types.indexOf("approval_required"));
        assertThat(types.indexOf("action_executed")).isGreaterThan(types.indexOf("approval_decided"));
        assertThat(types.indexOf("report_ready")).isGreaterThan(types.indexOf("action_executed"));               // resumed events continue the same seq counter
        assertThat(types.stream().filter("done"::equals)).hasSize(1);
        AI.verify(1, postRequestedFor(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume"))
                .withRequestBody(matchingJsonPath("$.decisions[0].decision", equalTo("APPROVE")))
                .withRequestBody(matchingJsonPath("$.decisions[0].decidedBy", equalTo("APPROVER Tester")))
                .withRequestBody(matchingJsonPath("$.decisions[0].actionKey", equalTo("a-high"))));
        assertThat(count("select count(*) from audit_log where action = 'APPROVAL_DECISION'")).isEqualTo(1);
        web.get().uri("/api/actions").header("Authorization", bearer(analyst)).exchange().expectBody().jsonPath("$.data.totalItems").isEqualTo(1);
    }

    @Test
    void rejectNeedsACommentAndIsNeverExecuted() {
        Session approver = sessionFor(Role.APPROVER);
        long id = pausedRun(sessionFor(Role.ANALYST), PRICE);
        long approvalId = approvalIds(id).get(0);

        decide(approver, approvalId, "REJECT", null).expectStatus().isBadRequest().expectBody().jsonPath("$.error.details.comment").exists();
        decide(approver, approvalId, "REJECT", "   ").expectStatus().isBadRequest();
        assertThat(count("select count(*) from approvals where id = ? and status = 'PENDING'", approvalId)).isEqualTo(1);

        decide(approver, approvalId, "REJECT", "Margins too thin").expectStatus().isOk();
        awaitStatus(id, "COMPLETED");
        assertThat(jdbc.queryForObject("select status from action_log where investigation_id = ?", String.class, id)).isEqualTo("REJECTED");
        assertThat(count("select count(*) from action_log where status = 'EXECUTED'")).isZero();
        AI.verify(postRequestedFor(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume"))
                .withRequestBody(matchingJsonPath("$.decisions[0].decision", equalTo("REJECT"))).withRequestBody(matchingJsonPath("$.decisions[0].comment", equalTo("Margins too thin"))));
    }

    @Test
    void selfApprovalIsForbiddenAndRolesAreChecked() {
        Session admin = sessionFor(Role.ADMIN);                                  // an admin may start runs
        long id = pausedRun(admin, PRICE);
        long approvalId = approvalIds(id).get(0);

        decide(admin, approvalId, "APPROVE", null).expectStatus().isForbidden().expectBody().jsonPath("$.error.code").isEqualTo("SELF_APPROVAL_NOT_ALLOWED");
        decide(sessionFor(Role.ANALYST), approvalId, "APPROVE", null).expectStatus().isForbidden();
        decide(sessionFor(Role.APPROVER), 999999L, "APPROVE", null).expectStatus().isNotFound();
        assertThat(count("select count(*) from approvals where status = 'PENDING'")).isEqualTo(1);
        assertThat(status(id)).isEqualTo("AWAITING_APPROVAL");

        decide(sessionFor(Role.ADMIN), approvalId, "APPROVE", null).expectStatus().isOk();    // a DIFFERENT admin may decide
        awaitStatus(id, "COMPLETED");
    }

    @Test
    void concurrentDecisionsOnTheSameApprovalProduceExactlyOneWinner() throws Exception {
        Session a1 = sessionFor(Role.APPROVER);
        Session a2 = sessionFor(Role.APPROVER);
        long id = pausedRun(sessionFor(Role.ANALYST), PRICE);
        long approvalId = approvalIds(id).get(0);

        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch go = new CountDownLatch(1);
        List<Future<Integer>> results = new ArrayList<>();
        for (Session s : List.of(a1, a2)) {
            results.add(pool.submit(() -> {
                go.await();
                return decide(s, approvalId, "APPROVE", null).returnResult(String.class).getStatus().value();
            }));
        }
        go.countDown();
        List<Integer> codes = new ArrayList<>();
        for (Future<Integer> f : results) codes.add(f.get(20, TimeUnit.SECONDS));
        pool.shutdown();

        assertThat(codes).containsExactlyInAnyOrder(200, 409);
        awaitStatus(id, "COMPLETED");
        assertThat(count("select count(*) from action_log where investigation_id = ? and status = 'EXECUTED'", id)).isEqualTo(1);
        AI.verify(1, postRequestedFor(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume")));
        decide(a1, approvalId, "APPROVE", null).expectStatus().isEqualTo(409).expectBody().jsonPath("$.error.code").isEqualTo("INVALID_STATE");
    }

    @Test
    void runResumesExactlyOnceWhenTwoApproversDecideDifferentApprovalsAtTheSameTime() throws Exception {
        Session a1 = sessionFor(Role.APPROVER);
        Session a2 = sessionFor(Role.APPROVER);
        long id = pausedRun(sessionFor(Role.ANALYST), PRICE, highAction("a-camp", "PAUSE_CAMPAIGN", "{\"regionId\":2,\"channel\":\"email\",\"weeks\":3}"));
        List<Long> ids = approvalIds(id);
        assertThat(ids).hasSize(2);

        ExecutorService pool = Executors.newFixedThreadPool(2);
        CountDownLatch go = new CountDownLatch(1);
        Future<?> f1 = pool.submit(() -> { go.await(); decide(a1, ids.get(0), "APPROVE", null).expectStatus().isOk(); return null; });
        Future<?> f2 = pool.submit(() -> { go.await(); decide(a2, ids.get(1), "REJECT", "no").expectStatus().isOk(); return null; });
        go.countDown();
        f1.get(20, TimeUnit.SECONDS);
        f2.get(20, TimeUnit.SECONDS);
        pool.shutdown();

        awaitStatus(id, "COMPLETED");
        AI.verify(1, postRequestedFor(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume")).withRequestBody(matchingJsonPath("$.decisions.length()", equalTo("2"))));
        assertThat(count("select count(*) from action_log where investigation_id = ?", id)).isEqualTo(2);
        assertThat(count("select count(*) from action_log where investigation_id = ? and status = 'EXECUTED'", id)).isEqualTo(1);
    }

    @Test
    void forgedAndInvalidActionsAreRejectedLoggedFailedAndNeverExecuted() {
        stubInvestigate(approvalRequired(highAction("a-bad1", "DROP_TABLE", "{}"), highAction("a-bad2", "ADJUST_PRICE", "{\"productId\":3,\"changePct\":90}")));
        stubResume(RESUME_OK);
        long id = startRun(sessionFor(Role.ANALYST));
        awaitStatus(id, "COMPLETED");                       // nothing was left PENDING, so the run resumed by itself

        assertThat(count("select count(*) from approvals where investigation_id = ? and status = 'REJECTED' and decided_by is null", id)).isEqualTo(2);
        assertThat(count("select count(*) from action_log where investigation_id = ? and status = 'FAILED'", id)).isEqualTo(2);
        assertThat(count("select count(*) from action_log where status = 'EXECUTED'")).isZero();
        assertThat(jdbc.queryForObject("select action_type from approvals where action_key = 'a-bad1'", String.class)).isEqualTo("UNKNOWN");
        AI.verify(postRequestedFor(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume")).withRequestBody(matchingJsonPath("$.decisions[0].decision", equalTo("REJECT")))
                .withRequestBody(matchingJsonPath("$.decisions[0].decidedBy", equalTo("system"))));
    }

    @Test
    void aHighRiskActionForgedAsLowIsNotExecutedAutomatically() {
        stubInvestigate(frame("action_proposed", """
                {"actionKey":"x1","actionType":"ADJUST_PRICE","risk":"LOW","title":"t","description":"d","params":{"productId":3,"changePct":-5},"rationale":"r","evidenceKeys":[]}""")
                + doneFrame("COMPLETED"));
        long id = startRun(sessionFor(Role.ANALYST));
        awaitStatus(id, "COMPLETED");
        assertThat(count("select count(*) from action_log")).isZero();
        assertThat(stepTypes(id)).doesNotContain("action_executed");
    }

    @Test
    void expiredApprovalsAreExpiredLoggedAndTheRunResumesAsRejected() {
        long id = pausedRun(sessionFor(Role.ANALYST), PRICE);
        long approvalId = approvalIds(id).get(0);
        expiryJob.run();                                                           // not expired yet: nothing happens
        assertThat(status(id)).isEqualTo("AWAITING_APPROVAL");

        jdbc.update("update approvals set expires_at = now() - interval '1 minute' where id = ?", approvalId);
        decide(sessionFor(Role.APPROVER), approvalId, "APPROVE", null).expectStatus().isEqualTo(409);    // expired but not yet swept: cannot be decided
        expiryJob.run();
        awaitStatus(id, "COMPLETED");

        assertThat(jdbc.queryForObject("select status from approvals where id = ?", String.class, approvalId)).isEqualTo("EXPIRED");
        assertThat(jdbc.queryForObject("select status from action_log where investigation_id = ?", String.class, id)).isEqualTo("EXPIRED");
        assertThat(count("select count(*) from action_log where status = 'EXECUTED'")).isZero();
        AI.verify(postRequestedFor(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume"))
                .withRequestBody(matchingJsonPath("$.decisions[0].decision", equalTo("REJECT"))).withRequestBody(matchingJsonPath("$.decisions[0].comment", equalTo("expired"))));
        assertThat(jdbc.queryForObject("select payload->>'decidedBy' from agent_steps where investigation_id = ? and type = 'approval_decided'", String.class, id)).isEqualTo("system");
    }

    @Test
    void cancellingAWaitingRunExpiresItsApprovalsWithoutExecutingAnything() {
        Session owner = sessionFor(Role.ANALYST);
        long id = pausedRun(owner, PRICE);
        long approvalId = approvalIds(id).get(0);
        web.post().uri("/api/investigations/" + id + "/cancel").header("Authorization", bearer(owner)).exchange().expectStatus().isNoContent();
        awaitStatus(id, "CANCELLED");
        assertThat(jdbc.queryForObject("select status from approvals where id = ?", String.class, approvalId)).isEqualTo("EXPIRED");
        assertThat(jdbc.queryForObject("select status from action_log where investigation_id = ?", String.class, id)).isEqualTo("EXPIRED");
        decide(sessionFor(Role.APPROVER), approvalId, "APPROVE", null).expectStatus().isEqualTo(409);
        AI.verify(0, postRequestedFor(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume")));
    }

    @Test
    void approvalVisibilityIsScopedByRole() {
        Session owner = sessionFor(Role.ANALYST);
        Session other = sessionFor(Role.ANALYST);
        long id = pausedRun(owner, PRICE);
        long approvalId = approvalIds(id).get(0);
        web.get().uri("/api/approvals/" + approvalId).header("Authorization", bearer(owner)).exchange().expectStatus().isOk();
        web.get().uri("/api/approvals/" + approvalId).header("Authorization", bearer(other)).exchange().expectStatus().isNotFound();
        web.get().uri("/api/approvals?status=PENDING").header("Authorization", bearer(other)).exchange().expectBody().jsonPath("$.data.totalItems").isEqualTo(0);
        web.get().uri("/api/approvals?status=PENDING").header("Authorization", bearer(owner)).exchange().expectBody().jsonPath("$.data.totalItems").isEqualTo(1);
        web.get().uri("/api/approvals?status=PENDING").header("Authorization", bearer(sessionFor(Role.APPROVER))).exchange().expectBody().jsonPath("$.data.totalItems").isEqualTo(1);
        web.get().uri("/api/approvals/pending-count").header("Authorization", bearer(other)).exchange().expectBody().jsonPath("$.data.count").isEqualTo(0);
        web.get().uri("/api/approvals/pending-count").header("Authorization", bearer(owner)).exchange().expectBody().jsonPath("$.data.count").isEqualTo(1);
    }
}
