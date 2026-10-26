package com.nexusai.common;

import com.fasterxml.jackson.databind.JsonNode;
import com.github.tomakehurst.wiremock.WireMockServer;
import com.github.tomakehurst.wiremock.core.WireMockConfiguration;
import com.nexusai.user.Role;
import com.nexusai.user.User;
import com.nexusai.user.UserRepository;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.MediaType;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.DockerImageName;

import static com.github.tomakehurst.wiremock.client.WireMock.*;

/**
 * Shared base for integration tests (Backend B extends it): one Postgres (pgvector image, same as prod/CI) and one scripted AI stub
 * (WireMock) per JVM, a clean user table before each test, and helpers to create users of each role and obtain tokens.
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
public abstract class IntegrationTestBase {
    public static final String INTERNAL_KEY = "test-internal-key";
    public static final String PASSWORD = "Passw0rd-test1";

    protected static final PostgreSQLContainer<?> POSTGRES = new PostgreSQLContainer<>(
            DockerImageName.parse("pgvector/pgvector:pg16").asCompatibleSubstituteFor("postgres"))
            .withDatabaseName("nexusai").withUsername("nexus").withPassword("nexus_test");
    protected static final WireMockServer AI = new WireMockServer(WireMockConfiguration.options().dynamicPort());
    private static final Path UPLOAD_DIR;

    static {
        POSTGRES.start();
        AI.start();
        try {
            UPLOAD_DIR = Files.createTempDirectory("nx-uploads");
        } catch (IOException e) {
            throw new IllegalStateException(e);
        }
    }

    @DynamicPropertySource
    static void properties(DynamicPropertyRegistry r) {
        r.add("spring.datasource.url", POSTGRES::getJdbcUrl);
        r.add("spring.datasource.username", POSTGRES::getUsername);
        r.add("spring.datasource.password", POSTGRES::getPassword);
        r.add("nexus.ai.url", AI::baseUrl);
        r.add("nexus.upload.dir", UPLOAD_DIR::toString);
    }

    @Autowired protected WebTestClient web;
    @Autowired protected UserRepository users;
    @Autowired protected PasswordEncoder encoder;
    @Autowired protected JdbcTemplate jdbc;

    @BeforeEach
    void resetState() {
        jdbc.execute("TRUNCATE TABLE users, audit_log RESTART IDENTITY CASCADE");   // CASCADE clears every table that references users; audit_log has no foreign key to users, so it is listed explicitly
        AI.resetAll();
    }

    // ---- users and tokens ----

    protected User createUser(Role role) {
        User u = new User();
        u.setEmail(role.name().toLowerCase() + "-" + UUID.randomUUID().toString().substring(0, 8) + "@test.local");
        u.setDisplayName(role.name() + " Tester");
        u.setRole(role);
        u.setPasswordHash(encoder.encode(PASSWORD));
        return users.saveAndFlush(u);
    }

    public record Session(User user, String accessToken, String refreshCookie) { }

    protected Session loginAs(User user) {
        var result = web.post().uri("/api/auth/login").contentType(MediaType.APPLICATION_JSON)
                .bodyValue(Map.of("email", user.getEmail(), "password", PASSWORD)).exchange()
                .expectStatus().isOk().expectBody(JsonNode.class).returnResult();
        String token = result.getResponseBody().at("/data/accessToken").asText();
        var cookie = result.getResponseCookies().getFirst("nx_refresh");
        return new Session(user, token, cookie == null ? null : cookie.getValue());
    }

    protected Session sessionFor(Role role) { return loginAs(createUser(role)); }

    protected static String bearer(Session s) { return "Bearer " + s.accessToken(); }

    // ---- AI stub helpers ----

    protected void stubIngestOk(int pages, int chunks) {
        AI.stubFor(post(urlEqualTo("/internal/ingest")).withHeader("X-Internal-API-Key", equalTo(INTERNAL_KEY))
                .willReturn(okJson("{\"documentId\":0,\"pageCount\":" + pages + ",\"chunkCount\":" + chunks + ",\"warnings\":[]}")));
    }

    protected void stubIngestRejected(String detail) {
        AI.stubFor(post(urlEqualTo("/internal/ingest")).willReturn(aResponse().withStatus(422)
                .withHeader("Content-Type", "application/json").withBody("{\"detail\":\"" + detail + "\"}")));
    }

    protected void stubDeleteOk() {
        AI.stubFor(delete(urlPathMatching("/internal/documents/\\d+")).withHeader("X-Internal-API-Key", equalTo(INTERNAL_KEY))
                .willReturn(okJson("{\"deleted\":3}")));
    }

    protected void stubSearch(String jsonArray) {
        AI.stubFor(post(urlEqualTo("/internal/search")).willReturn(okJson(jsonArray)));
    }
}
