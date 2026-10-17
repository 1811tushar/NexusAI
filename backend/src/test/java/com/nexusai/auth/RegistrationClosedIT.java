package com.nexusai.auth;

import com.nexusai.common.IntegrationTestBase;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.context.TestPropertySource;

@TestPropertySource(properties = "nexus.registration-open=false")
class RegistrationClosedIT extends IntegrationTestBase {
    @Test
    void registerIsForbiddenWhenClosed() {
        web.post().uri("/api/auth/register").contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("email", "x@test.local", "password", "Str0ngPassw0rd", "displayName", "X"))
                .exchange().expectStatus().isForbidden().expectBody().jsonPath("$.error.code").isEqualTo("FORBIDDEN");
    }
}
