package com.nexusai.user;

import static org.assertj.core.api.Assertions.assertThat;

import com.nexusai.common.IntegrationTestBase;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.reactive.server.WebTestClient;

/** BE-AU-05: admin user management, last-admin and self-protection rules. */
class AdminUserRulesIT extends IntegrationTestBase {

    private WebTestClient.ResponseSpec patch(Session actor, long id, Map<String, Object> body) {
        return web.patch().uri("/api/admin/users/" + id).header("Authorization", bearer(actor)).contentType(MediaType.APPLICATION_JSON)
                .bodyValue(body).exchange();
    }

    @Test
    void adminCreatesUserWhoCanLogInAndDuplicatesAreRejected() {
        Session admin = sessionFor(Role.ADMIN);
        Map<String, Object> body = Map.of("email", "Approver1@test.local", "displayName", "Ann Approver", "role", "APPROVER",
                "temporaryPassword", "Temp0raryPass1");
        web.post().uri("/api/admin/users").header("Authorization", bearer(admin)).contentType(MediaType.APPLICATION_JSON).bodyValue(body)
                .exchange().expectStatus().isOk().expectBody().jsonPath("$.data.role").isEqualTo("APPROVER");
        web.post().uri("/api/admin/users").header("Authorization", bearer(admin)).contentType(MediaType.APPLICATION_JSON).bodyValue(body)
                .exchange().expectStatus().isEqualTo(409);
        web.post().uri("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("email", "approver1@test.local", "password", "Temp0raryPass1")).exchange().expectStatus().isOk();
    }

    @Test
    void listSupportsSearchAndRoleFilter() {
        Session admin = sessionFor(Role.ADMIN);
        createUser(Role.APPROVER);
        web.get().uri("/api/admin/users?role=APPROVER&q=approver").header("Authorization", bearer(admin)).exchange()
                .expectStatus().isOk().expectBody().jsonPath("$.data.totalItems").isEqualTo(1).jsonPath("$.data.items[0].role").isEqualTo("APPROVER");
    }

    @Test
    void adminCannotDemoteOrDisableThemselves() {
        Session admin = sessionFor(Role.ADMIN);
        patch(admin, admin.user().getId(), Map.of("role", "ANALYST")).expectStatus().isForbidden();
        patch(admin, admin.user().getId(), Map.of("enabled", false)).expectStatus().isForbidden();
    }

    @Test
    void lastEnabledAdminCannotBeDemotedByAnotherAdmin() {
        Session a = sessionFor(Role.ADMIN);
        Session b = sessionFor(Role.ADMIN);
        patch(a, b.user().getId(), Map.of("enabled", false)).expectStatus().isOk();       // two enabled admins: allowed; a is now the only one
        // b's access token is still valid for its short lifetime, so b can try to demote a
        patch(b, a.user().getId(), Map.of("role", "ANALYST")).expectStatus().isEqualTo(409)
                .expectBody().jsonPath("$.error.code").isEqualTo("INVALID_STATE");
        assertThat(jdbc.queryForObject("select count(*) from users where role = 'ADMIN' and enabled", Integer.class)).isEqualTo(1);
    }

    @Test
    void disablingAUserRevokesSessionsAndBlocksLogin() {
        Session admin = sessionFor(Role.ADMIN);
        Session victim = sessionFor(Role.ANALYST);
        patch(admin, victim.user().getId(), Map.of("enabled", false)).expectStatus().isOk();
        web.post().uri("/api/auth/refresh").cookie("nx_refresh", victim.refreshCookie()).exchange().expectStatus().isUnauthorized();
        web.post().uri("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("email", victim.user().getEmail(), "password", PASSWORD)).exchange().expectStatus().isUnauthorized();
    }

    @Test
    void emptyPatchAndUnknownUser() {
        Session admin = sessionFor(Role.ADMIN);
        patch(admin, admin.user().getId(), Map.of()).expectStatus().isBadRequest();
        patch(admin, 999999L, Map.of("role", "ANALYST")).expectStatus().isNotFound();
    }
}
