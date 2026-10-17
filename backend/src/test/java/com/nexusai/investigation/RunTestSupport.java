package com.nexusai.investigation;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.awaitility.Awaitility.await;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.common.IntegrationTestBase;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;

/** Helpers for tests that need a scripted Python SSE server (WireMock) and a running investigation. */
public abstract class RunTestSupport extends IntegrationTestBase {
    protected static final String QUESTION = "Why did Q2 revenue decline compared to Q1?";
    protected static final String EV_KEY = "11111111-1111-1111-1111-111111111111";

    /** One SSE frame. Newlines inside the JSON are removed so it stays a single data line. */
    protected static String frame(String type, String json) { return "event: " + type + "\ndata: " + json.replaceAll("\\s*\\R\\s*", "") + "\n\n"; }

    protected static String doneFrame(String status) {
        return frame("done", "{\"status\":\"" + status + "\",\"confidence\":0.82,\"loopsUsed\":0,\"usage\":{\"inputTokens\":100,\"outputTokens\":50},\"latencyMs\":1234}");
    }

    protected static String lowAction(String key) {
        return frame("action_proposed", """
                {"actionKey":"%s","actionType":"SAVE_INSIGHT","risk":"LOW","title":"Save insight","description":"d",
                 "params":{"title":"Q2","text":"Revenue fell"},"rationale":"r","evidenceKeys":[]}""".formatted(key));
    }

    protected static String highAction(String key, String type, String paramsJson) {
        return """
                {"actionKey":"%s","actionType":"%s","risk":"HIGH","title":"Adjust","description":"Lower the price",
                 "params":%s,"rationale":"Because","evidenceKeys":["%s"]}""".formatted(key, type, paramsJson, EV_KEY);
    }

    protected static String approvalRequired(String... actionsJson) {
        return frame("approval_required", "{\"actions\":[" + String.join(",", actionsJson) + "]}");
    }

    /** The complete happy path of the hero scenario with one LOW-risk action. */
    protected static String happyBody() {
        return frame("memory_recalled", "{\"items\":[]}")
                + frame("supervisor_routed", "{\"agents\":[\"RESEARCHER\",\"DATA_ANALYST\"],\"reason\":\"both\"}")
                + frame("plan", """
                        {"steps":[{"id":"s1","description":"Compare Q2 vs Q1","agent":"DATA_ANALYST","status":"PENDING"},
                                  {"id":"s2","description":"Read reports","agent":"RESEARCHER","status":"PENDING"}]}""")
                + frame("step_status", "{\"stepId\":\"s1\",\"status\":\"RUNNING\"}")
                + frame("agent_started", "{\"agent\":\"DATA_ANALYST\",\"stepId\":\"s1\"}")
                + frame("tool_call", "{\"callId\":\"c1\",\"agent\":\"DATA_ANALYST\",\"tool\":\"sql_query\",\"args\":{}}")
                + frame("tool_result", "{\"callId\":\"c1\",\"tool\":\"sql_query\",\"ok\":true,\"summary\":\"3 rows\",\"durationMs\":12}")
                + frame("evidence_added", """
                        {"evidence":{"evidenceKey":"%s","kind":"SQL","title":"Revenue by quarter","snippet":"Q1 100, Q2 88",
                         "source":{"sql":"select 1"},"data":{"columns":["q","revenue"],"rows":[["Q1",100],["Q2",88]],"truncated":false},
                         "score":null,"createdAt":"2026-01-01T00:00:00Z"}}""".formatted(EV_KEY))
                + frame("claims_drafted", """
                        {"claims":[{"claimKey":"c-1","text":"Revenue fell 12%%","isKey":true,"evidenceKeys":["%s"]},
                                   {"claimKey":"c-2","text":"A supplier delay hurt sales","isKey":false,"evidenceKeys":[]}]}""".formatted(EV_KEY))
                + frame("claim_verified", "{\"claimKey\":\"c-1\",\"text\":\"Revenue fell 12%\",\"status\":\"VERIFIED\",\"confidence\":0.9,\"evidenceKeys\":[\"" + EV_KEY + "\"],\"reason\":\"matches\"}")
                + frame("claim_verified", "{\"claimKey\":\"c-2\",\"text\":\"A supplier delay hurt sales\",\"status\":\"UNSUPPORTED\",\"confidence\":0.4,\"evidenceKeys\":[],\"reason\":\"none\"}")
                + frame("confidence", "{\"overall\":0.7,\"threshold\":0.7,\"decision\":\"ACCEPT\",\"loop\":0}")
                + lowAction("a-low")
                + frame("report_delta", "{\"text\":\"# Rep\"}")
                + frame("report_delta", "{\"text\":\"ort\"}")
                + frame("report_ready", """
                        {"reportMarkdown":"# Report\\n\\nRevenue fell.\\n\\n## Limitations and failures\\n\\n- Web search was unavailable\\n",
                         "summary":"Revenue fell 12%","recommendations":[{"id":"r1","text":"Save the insight","risk":"LOW","actionKey":"a-low"}],"confidence":0.82}""")
                + frame("memory_saved", "{\"id\":1,\"summary\":\"Q2 revenue fell\"}")
                + doneFrame("COMPLETED");
    }

    // ---------------- stubs ----------------

    protected void stubInvestigate(String body) {
        AI.stubFor(post(urlEqualTo("/internal/investigate")).withHeader("X-Internal-API-Key", equalTo(INTERNAL_KEY))
                .willReturn(aResponse().withStatus(200).withHeader("Content-Type", "text/event-stream").withBody(body)));
    }

    /** Same, but the body is dribbled out over {@code millis} so the run stays RUNNING for a while. */
    protected void stubInvestigateSlow(String body, int millis) {
        AI.stubFor(post(urlEqualTo("/internal/investigate"))
                .willReturn(aResponse().withStatus(200).withHeader("Content-Type", "text/event-stream").withBody(body).withChunkedDribbleDelay(8, millis)));
    }

    protected void stubResume(String body) {
        AI.stubFor(post(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/resume")).withHeader("X-Internal-API-Key", equalTo(INTERNAL_KEY))
                .willReturn(aResponse().withStatus(200).withHeader("Content-Type", "text/event-stream").withBody(body)));
    }

    protected void stubCancel() {
        AI.stubFor(post(urlPathMatching("/internal/investigate/[0-9a-f-]{36}/cancel")).willReturn(okJson("{\"cancelled\":true}")));
    }

    // ---------------- actions ----------------

    protected long startRun(Session s) { return startRun(s, QUESTION); }

    protected long startRun(Session s, String question) {
        return web.post().uri("/api/investigations").header("Authorization", bearer(s)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("question", question)).exchange().expectStatus().isAccepted()
                .expectBody(JsonNode.class).returnResult().getResponseBody().at("/data/id").asLong();
    }

    protected WebTestClient.ResponseSpec decide(Session s, long approvalId, String decision, String comment) {
        Map<String, Object> body = comment == null ? Map.of("decision", decision) : Map.of("decision", decision, "comment", comment);
        return web.post().uri("/api/approvals/" + approvalId + "/decision").header("Authorization", bearer(s)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body).exchange();
    }

    protected String status(long id) {
        return jdbc.query("select status from investigations where id = ?", rs -> rs.next() ? rs.getString(1) : null, id);
    }

    protected void awaitStatus(long id, String expected) {
        await().atMost(Duration.ofSeconds(25)).pollInterval(Duration.ofMillis(100)).until(() -> expected.equals(status(id)));
    }

    protected List<Long> approvalIds(long investigationId) {
        return jdbc.queryForList("select id from approvals where investigation_id = ? order by id", Long.class, investigationId);
    }

    protected int count(String sql, Object... args) {
        Integer n = jdbc.queryForObject(sql, Integer.class, args);
        return n == null ? 0 : n;
    }

    protected List<String> stepTypes(long id) {
        return jdbc.queryForList("select type from agent_steps where investigation_id = ? order by seq", String.class, id);
    }
}
