package com.nexusai.auth;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.nexusai.common.IntegrationTestBase;
import com.nexusai.user.Role;
import com.nexusai.user.User;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseCookie;
import org.springframework.test.web.reactive.server.EntityExchangeResult;
import org.springframework.test.web.reactive.server.WebTestClient;

/** BE-AU-01..04, SEC-02. */
class AuthFlowIT extends IntegrationTestBase {

    private WebTestClient.ResponseSpec post(String uri, Object body) {
        return web.post().uri(uri).contentType(MediaType.APPLICATION_JSON).bodyValue(body).exchange();
    }

    private WebTestClient.ResponseSpec refresh(String cookie) {
        return web.post().uri("/api/auth/refresh").cookie("nx_refresh", cookie == null ? "" : cookie).exchange();
    }

    @Test
    void registerCreatesAnalystAndSetsHardenedCookie() {
        EntityExchangeResult<JsonNode> r = post("/api/auth/register",
                Map.of("email", "New.User@Test.local", "password", "Str0ngPassw0rd", "displayName", "New User"))
                .expectStatus().isOk().expectBody(JsonNode.class).returnResult();
        JsonNode data = r.getResponseBody().get("data");
        assertThat(data.get("user").get("role").asText()).isEqualTo("ANALYST");
        assertThat(data.get("user").get("email").asText()).isEqualTo("new.user@test.local");
        assertThat(data.get("accessToken").asText()).isNotBlank();

        ResponseCookie c = r.getResponseCookies().getFirst("nx_refresh");
        assertThat(c).isNotNull();
        assertThat(c.isHttpOnly()).isTrue();
        assertThat(c.getPath()).isEqualTo("/api/auth");
        assertThat(c.getSameSite()).isEqualTo("Lax");
        // stored hashed, never raw
        assertThat(jdbc.queryForObject("select count(*) from refresh_tokens where token_hash = ?", Integer.class, c.getValue())).isZero();
    }

    @Test
    void registerRejectsDuplicateEmailAndWeakPassword() {
        post("/api/auth/register", Map.of("email", "dup@test.local", "password", "Str0ngPassw0rd", "displayName", "A")).expectStatus().isOk();
        post("/api/auth/register", Map.of("email", "DUP@test.local", "password", "Str0ngPassw0rd", "displayName", "B"))
                .expectStatus().isEqualTo(409).expectBody().jsonPath("$.error.code").isEqualTo("DUPLICATE_RESOURCE");
        post("/api/auth/register", Map.of("email", "weak@test.local", "password", "short1", "displayName", "W"))
                .expectStatus().isBadRequest().expectBody().jsonPath("$.error.code").isEqualTo("VALIDATION_FAILED");
        post("/api/auth/register", Map.of("email", "weak2@test.local", "password", "onlyletterspassword", "displayName", "W"))
                .expectStatus().isBadRequest();
    }

    @Test
    void loginAndMe() {
        Session s = sessionFor(Role.APPROVER);
        web.get().uri("/api/auth/me").header("Authorization", bearer(s)).exchange().expectStatus().isOk()
                .expectBody().jsonPath("$.data.role").isEqualTo("APPROVER").jsonPath("$.success").isEqualTo(true);
        web.get().uri("/api/auth/me").exchange().expectStatus().isUnauthorized()
                .expectBody().jsonPath("$.error.code").isEqualTo("UNAUTHENTICATED");
        web.get().uri("/api/auth/me").header("Authorization", "Bearer garbage").exchange().expectStatus().isUnauthorized();
    }

    @Test
    void everyResponseCarriesContractVersionAndRequestId() {
        web.get().uri("/api/auth/me").exchange().expectHeader().valueEquals("X-Contract-Version", "2.1").expectHeader().exists("X-Request-Id");
    }

    @Test
    void wrongPasswordIsGenericAndUnknownUserIsIndistinguishable() {
        User u = createUser(Role.ANALYST);
        post("/api/auth/login", Map.of("email", u.getEmail(), "password", "wrong-Password1")).expectStatus().isUnauthorized()
                .expectBody().jsonPath("$.error.code").isEqualTo("INVALID_CREDENTIALS");
        post("/api/auth/login", Map.of("email", "nobody@test.local", "password", "wrong-Password1")).expectStatus().isUnauthorized()
                .expectBody().jsonPath("$.error.code").isEqualTo("INVALID_CREDENTIALS");
    }

    @Test
    void refreshRotatesAndReuseRevokesTheWholeFamily() {
        Session s = sessionFor(Role.ANALYST);
        EntityExchangeResult<JsonNode> r = refresh(s.refreshCookie()).expectStatus().isOk().expectBody(JsonNode.class).returnResult();
        String rotated = r.getResponseCookies().getFirst("nx_refresh").getValue();
        assertThat(rotated).isNotEqualTo(s.refreshCookie());
        assertThat(r.getResponseBody().at("/data/accessToken").asText()).isNotBlank();

        // replaying the OLD token = theft signal: it fails AND kills the new token of the same family
        refresh(s.refreshCookie()).expectStatus().isUnauthorized();
        // the theft signal itself is audited exactly once ...
        assertThat(jdbc.queryForObject("select count(*) from audit_log where action = 'REFRESH_REUSE_DETECTED'", Integer.class)).isEqualTo(1);
        // ... and the rotated token of the same family is dead too (using it is another rejected attempt, which is audited again)
        refresh(rotated).expectStatus().isUnauthorized();
    }

    @Test
    void logoutRevokesTheSession() {
        Session s = sessionFor(Role.ANALYST);
        web.post().uri("/api/auth/logout").cookie("nx_refresh", s.refreshCookie()).exchange().expectStatus().isOk()
                .expectHeader().value("Set-Cookie", v -> assertThat(v).contains("Max-Age=0"));
        refresh(s.refreshCookie()).expectStatus().isUnauthorized();
    }

    @Test
    void refreshWithoutCookieIsUnauthorized() {
        web.post().uri("/api/auth/refresh").exchange().expectStatus().isUnauthorized();
    }

    @Test
    void fiveFailedLoginsLockTheAccountEvenForTheRightPassword() {
        User u = createUser(Role.ANALYST);
        for (int i = 0; i < 5; i++) {
            post("/api/auth/login", Map.of("email", u.getEmail(), "password", "wrong-Password1")).expectStatus().isUnauthorized();
        }
        post("/api/auth/login", Map.of("email", u.getEmail(), "password", PASSWORD)).expectStatus().isUnauthorized();
        assertThat(jdbc.queryForObject("select locked_until is not null from users where id = ?", Boolean.class, u.getId())).isTrue();
        // lock expiry restores access
        jdbc.update("update users set locked_until = now() - interval '1 minute' where id = ?", u.getId());
        post("/api/auth/login", Map.of("email", u.getEmail(), "password", PASSWORD)).expectStatus().isOk();
    }

    @Test
    void changePasswordKeepsCurrentSessionAndRevokesOthers() {
        User u = createUser(Role.ANALYST);
        Session a = loginAs(u);
        Session b = loginAs(u);
        web.post().uri("/api/users/me/password").header("Authorization", bearer(a)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("currentPassword", "nope-Password1", "newPassword", "An0therPassword")).exchange()
                .expectStatus().isBadRequest();   // 400, not 401: a 401 would trigger the SPA's refresh loop
        web.post().uri("/api/users/me/password").header("Authorization", bearer(a)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("currentPassword", PASSWORD, "newPassword", "An0therPassword")).exchange().expectStatus().isOk();
        refresh(b.refreshCookie()).expectStatus().isUnauthorized();
        refresh(a.refreshCookie()).expectStatus().isOk();
        post("/api/auth/login", Map.of("email", u.getEmail(), "password", "An0therPassword")).expectStatus().isOk();
    }

    @Test
    void authActionsAreAudited() {
        User u = createUser(Role.ANALYST);
        loginAs(u);
        post("/api/auth/login", Map.of("email", u.getEmail(), "password", "bad-Password1"));
        assertThat(jdbc.queryForObject("select count(*) from audit_log where action = 'LOGIN_SUCCESS'", Integer.class)).isEqualTo(1);
        assertThat(jdbc.queryForObject("select count(*) from audit_log where action = 'LOGIN_FAILURE'", Integer.class)).isEqualTo(1);
    }
}
