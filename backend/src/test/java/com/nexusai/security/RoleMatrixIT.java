package com.nexusai.security;

import com.nexusai.common.IntegrationTestBase;
import com.nexusai.user.Role;
import java.util.stream.Stream;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.Arguments;
import org.junit.jupiter.params.provider.MethodSource;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.web.reactive.function.BodyInserters;

import static org.junit.jupiter.params.provider.Arguments.arguments;

/** SEC-01 / BE-AU-03: matrix-driven 401/403/404 expectations for every endpoint owned by Backend A. null role = no token. */
class RoleMatrixIT extends IntegrationTestBase {

    // method, uri, body (json) or "MULTIPART_EMPTY", then expected status for: anonymous, ANALYST, APPROVER, ADMIN
    static Stream<Arguments> matrix() {
        return Stream.of(
                arguments(HttpMethod.GET, "/api/auth/me", null, 401, 200, 200, 200),
                arguments(HttpMethod.PATCH, "/api/users/me", "{\"displayName\":\"New Name\"}", 401, 200, 200, 200),
                arguments(HttpMethod.GET, "/api/admin/users", null, 401, 403, 403, 200),
                arguments(HttpMethod.POST, "/api/admin/users", "{}", 401, 403, 403, 400),
                arguments(HttpMethod.PATCH, "/api/admin/users/999999", "{\"role\":\"ANALYST\"}", 401, 403, 403, 404),
                arguments(HttpMethod.GET, "/api/eval/runs", null, 401, 403, 403, 200),   // Backend B proxies it; stubbed below
                arguments(HttpMethod.GET, "/api/documents", null, 401, 200, 200, 200),
                arguments(HttpMethod.GET, "/api/documents/999999", null, 401, 404, 404, 404),
                arguments(HttpMethod.GET, "/api/documents/999999/file", null, 401, 404, 404, 404),
                arguments(HttpMethod.GET, "/api/documents/999999/chunks", null, 401, 404, 404, 404),
                arguments(HttpMethod.POST, "/api/documents", "MULTIPART_EMPTY", 401, 400, 403, 400),
                arguments(HttpMethod.POST, "/api/documents/999999/reindex", null, 401, 404, 403, 404),
                arguments(HttpMethod.DELETE, "/api/documents/999999", null, 401, 404, 403, 404),
                arguments(HttpMethod.GET, "/api/search?q=x", null, 401, 200, 200, 200));
    }

    @ParameterizedTest(name = "{0} {1}")
    @MethodSource("matrix")
    void endpointHonoursRoleMatrix(HttpMethod method, String uri, String body, int anon, int analyst, int approver, int admin) {
        stubSearch("[]");
        AI.stubFor(com.github.tomakehurst.wiremock.client.WireMock.get(com.github.tomakehurst.wiremock.client.WireMock.urlPathEqualTo("/internal/eval/runs"))
                .willReturn(com.github.tomakehurst.wiremock.client.WireMock.okJson("[]")));
        check(method, uri, body, null, anon);
        check(method, uri, body, Role.ANALYST, analyst);
        check(method, uri, body, Role.APPROVER, approver);
        check(method, uri, body, Role.ADMIN, admin);
    }

    private void check(HttpMethod method, String uri, String body, Role role, int expected) {
        var spec = web.method(method).uri(uri);
        if (role != null) spec = spec.header("Authorization", bearer(sessionFor(role)));
        if ("MULTIPART_EMPTY".equals(body)) {
            spec.contentType(MediaType.MULTIPART_FORM_DATA).body(BodyInserters.fromMultipartData(new MultipartBodyBuilder().build()))
                    .exchange().expectStatus().isEqualTo(expected);
        } else if (body != null) {
            spec.contentType(MediaType.APPLICATION_JSON).bodyValue(body).exchange().expectStatus().isEqualTo(expected);
        } else {
            spec.exchange().expectStatus().isEqualTo(expected);
        }
    }

    @org.junit.jupiter.api.Test
    void publicEndpointsNeedNoToken() {
        web.get().uri("/actuator/health").exchange().expectStatus().isOk();
        web.post().uri("/api/auth/refresh").exchange().expectStatus().isUnauthorized();   // reachable, but no cookie
        web.post().uri("/api/auth/logout").exchange().expectStatus().isOk();
    }

    @org.junit.jupiter.api.Test
    void unknownRouteIsNotFoundForAuthenticatedAndUnauthorizedOtherwise() {
        web.get().uri("/api/nope").exchange().expectStatus().isUnauthorized();
        web.get().uri("/api/nope").header("Authorization", bearer(sessionFor(Role.ANALYST))).exchange().expectStatus().isNotFound();
    }
}
