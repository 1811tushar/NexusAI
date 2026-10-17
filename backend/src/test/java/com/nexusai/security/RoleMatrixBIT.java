package com.nexusai.security;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.junit.jupiter.params.provider.Arguments.arguments;

import com.nexusai.common.IntegrationTestBase;
import com.nexusai.user.Role;
import java.util.stream.Stream;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;

/** SEC-01: matrix for every endpoint Backend B owns. Expected status for: anonymous, ANALYST, APPROVER, ADMIN. */
class RoleMatrixBIT extends IntegrationTestBase {
    private static final String SHORT = "{\"question\":\"short\"}";
    private static final String DECISION = "{\"decision\":\"APPROVE\"}";
    private static final String RATING = "{\"rating\":1}";

    static Stream<Arguments> matrix() {
        return Stream.of(
                arguments(HttpMethod.POST, "/api/investigations", SHORT, 401, 400, 403, 400),
                arguments(HttpMethod.GET, "/api/investigations", null, 401, 200, 200, 200),
                arguments(HttpMethod.GET, "/api/investigations/999999", null, 401, 404, 404, 404),
                arguments(HttpMethod.GET, "/api/investigations/999999/steps", null, 401, 404, 404, 404),
                arguments(HttpMethod.GET, "/api/investigations/999999/stream", null, 401, 404, 404, 404),
                arguments(HttpMethod.GET, "/api/investigations/999999/report.md", null, 401, 404, 404, 404),
                arguments(HttpMethod.POST, "/api/investigations/999999/cancel", null, 401, 404, 403, 404),
                arguments(HttpMethod.POST, "/api/investigations/999999/feedback", RATING, 401, 404, 404, 404),
                arguments(HttpMethod.GET, "/api/dashboard/summary", null, 401, 200, 200, 200),
                arguments(HttpMethod.GET, "/api/approvals", null, 401, 200, 200, 200),
                arguments(HttpMethod.GET, "/api/approvals/pending-count", null, 401, 200, 200, 200),
                arguments(HttpMethod.GET, "/api/approvals/999999", null, 401, 404, 404, 404),
                arguments(HttpMethod.POST, "/api/approvals/999999/decision", DECISION, 401, 403, 404, 404),
                arguments(HttpMethod.GET, "/api/actions", null, 401, 200, 200, 200),
                arguments(HttpMethod.GET, "/api/memories", null, 401, 200, 200, 200),
                arguments(HttpMethod.DELETE, "/api/memories", null, 401, 204, 204, 204),
                arguments(HttpMethod.DELETE, "/api/memories/5", null, 401, 204, 204, 204),
                arguments(HttpMethod.GET, "/api/eval/runs", null, 401, 403, 403, 200),
                arguments(HttpMethod.GET, "/api/eval/runs/1", null, 401, 403, 403, 200));
    }

    @ParameterizedTest(name = "{0} {1}")
    @MethodSource("matrix")
    void endpointHonoursRoleMatrix(HttpMethod method, String uri, String body, int anon, int analyst, int approver, int admin) {
        AI.stubFor(get(urlPathEqualTo("/internal/memories")).willReturn(okJson("{\"items\":[],\"page\":0,\"size\":20,\"totalItems\":0,\"totalPages\":0}")));
        AI.stubFor(delete(urlPathMatching("/internal/memories(/\\d+)?")).willReturn(okJson("{\"deleted\":1}")));
        AI.stubFor(get(urlPathEqualTo("/internal/eval/runs")).willReturn(okJson("[]")));
        AI.stubFor(get(urlPathMatching("/internal/eval/runs/\\d+")).willReturn(okJson("{\"id\":1,\"system\":\"AGENT\",\"questionCount\":0,\"results\":[]}")));
        check(method, uri, body, null, anon);
        check(method, uri, body, Role.ANALYST, analyst);
        check(method, uri, body, Role.APPROVER, approver);
        check(method, uri, body, Role.ADMIN, admin);
    }

    private void check(HttpMethod method, String uri, String body, Role role, int expected) {
        var spec = web.method(method).uri(uri);
        if (role != null) spec = spec.header("Authorization", bearer(sessionFor(role)));
        if (body != null) spec.contentType(MediaType.APPLICATION_JSON).bodyValue(body).exchange().expectStatus().isEqualTo(expected);
        else spec.exchange().expectStatus().isEqualTo(expected);
    }
}
