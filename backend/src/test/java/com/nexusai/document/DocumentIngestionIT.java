package com.nexusai.document;

import static com.github.tomakehurst.wiremock.client.WireMock.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.awaitility.Awaitility.await;

import com.fasterxml.jackson.databind.JsonNode;
import com.github.tomakehurst.wiremock.http.Fault;
import com.nexusai.common.Docs;
import com.nexusai.common.IntegrationTestBase;
import com.nexusai.user.Role;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.test.web.reactive.server.WebTestClient;
import org.springframework.web.reactive.function.BodyInserters;

/** BE-DC-01..04: upload validation, async ingestion, duplicates, deletion (incl. AI down), permissions, sweeper. */
class DocumentIngestionIT extends IntegrationTestBase {
    @Autowired DocumentSweeper sweeper;

    private WebTestClient.ResponseSpec upload(Session s, String filename, String contentType, byte[] bytes) {
        MultipartBodyBuilder mb = new MultipartBodyBuilder();
        mb.part("file", new ByteArrayResource(bytes) {
            @Override public String getFilename() { return filename; }
        }, MediaType.parseMediaType(contentType)).filename(filename);
        return web.post().uri("/api/documents").header("Authorization", bearer(s))
                .contentType(MediaType.MULTIPART_FORM_DATA).body(BodyInserters.fromMultipartData(mb.build())).exchange();
    }

    private long uploadPdf(Session s) {
        JsonNode n = upload(s, "report.pdf", "application/pdf", Docs.pdf()).expectStatus().isAccepted()
                .expectBody(JsonNode.class).returnResult().getResponseBody();
        return n.at("/data/id").asLong();
    }

    private String status(long id) {
        return jdbc.query("select status from documents where id = ?", rs -> rs.next() ? rs.getString(1) : null, id);
    }

    @Test
    void uploadIsAcceptedThenBecomesReady() {
        stubIngestOk(3, 12);
        Session analyst = sessionFor(Role.ANALYST);
        JsonNode n = upload(analyst, "Q2 Report.pdf", "application/pdf", Docs.pdf()).expectStatus().isAccepted()
                .expectBody(JsonNode.class).returnResult().getResponseBody();
        assertThat(n.at("/data/status").asText()).isEqualTo("UPLOADED");
        assertThat(n.at("/data/title").asText()).isEqualTo("Q2 Report");
        long id = n.at("/data/id").asLong();

        await().atMost(10, TimeUnit.SECONDS).until(() -> "READY".equals(status(id)));
        web.get().uri("/api/documents/" + id).header("Authorization", bearer(analyst)).exchange().expectStatus().isOk()
                .expectBody().jsonPath("$.data.pageCount").isEqualTo(3).jsonPath("$.data.chunkCount").isEqualTo(12);
        AI.verify(postRequestedFor(urlEqualTo("/internal/ingest")).withHeader("X-Internal-API-Key", equalTo(INTERNAL_KEY))
                .withHeader("X-Request-Id", matching("[0-9a-f-]{36}")));
    }

    @Test
    void aiRejectionBecomesFailedWithReasonAndReindexRecovers() {
        stubIngestRejected("PDF is encrypted");
        Session analyst = sessionFor(Role.ANALYST);
        long id = uploadPdf(analyst);
        await().atMost(10, TimeUnit.SECONDS).until(() -> "FAILED".equals(status(id)));
        assertThat(jdbc.queryForObject("select error_message from documents where id = ?", String.class, id)).contains("encrypted");

        AI.resetAll();
        stubIngestOk(1, 2);
        web.post().uri("/api/documents/" + id + "/reindex").header("Authorization", bearer(analyst)).exchange().expectStatus().isAccepted();
        await().atMost(10, TimeUnit.SECONDS).until(() -> "READY".equals(status(id)));
    }

    @Test
    void aiDownDuringIngestionBecomesFailed() {
        AI.stubFor(post(urlEqualTo("/internal/ingest")).willReturn(aResponse().withFault(Fault.CONNECTION_RESET_BY_PEER)));
        long id = uploadPdf(sessionFor(Role.ANALYST));
        await().atMost(10, TimeUnit.SECONDS).until(() -> "FAILED".equals(status(id)));
        assertThat(jdbc.queryForObject("select error_message from documents where id = ?", String.class, id)).contains("unavailable");
    }

    @Test
    void duplicateContentIsRejectedWithExistingId() {
        stubIngestOk(1, 1);
        Session analyst = sessionFor(Role.ANALYST);
        byte[] bytes = Docs.pdf();
        long first = upload(analyst, "a.pdf", "application/pdf", bytes).expectStatus().isAccepted()
                .expectBody(JsonNode.class).returnResult().getResponseBody().at("/data/id").asLong();
        upload(sessionFor(Role.ADMIN), "copy.pdf", "application/pdf", bytes).expectStatus().isEqualTo(409).expectBody()
                .jsonPath("$.error.code").isEqualTo("DUPLICATE_RESOURCE")
                .jsonPath("$.error.details.existingDocumentId").isEqualTo(String.valueOf(first));
    }

    @Test
    void validationRejectsWrongMagicBytesTypeAndEmptyFiles() {
        Session analyst = sessionFor(Role.ANALYST);
        upload(analyst, "fake.pdf", "application/pdf", Docs.text()).expectStatus().isEqualTo(415);                   // text pretending to be PDF
        upload(analyst, "report.pdf", "text/plain", Docs.pdf()).expectStatus().isEqualTo(415);                       // content type mismatch
        upload(analyst, "run.exe", "application/octet-stream", Docs.text()).expectStatus().isEqualTo(415);
        upload(analyst, "empty.txt", "text/plain", new byte[0]).expectStatus().isBadRequest();
        upload(analyst, "../../etc/passwd.txt", "text/plain", Docs.text()).expectStatus().isAccepted();             // path stripped, stored under a random key
        assertThat(jdbc.queryForObject("select original_filename from documents", String.class)).isEqualTo("passwd.txt");
        assertThat(jdbc.queryForObject("select storage_key from documents", String.class)).matches("[0-9a-f]{2}/[0-9a-f]{32}");
    }

    @Test
    void permissionsFollowTheMatrix() {
        stubIngestOk(1, 1);
        Session owner = sessionFor(Role.ANALYST);
        Session otherAnalyst = sessionFor(Role.ANALYST);
        Session approver = sessionFor(Role.APPROVER);
        Session admin = sessionFor(Role.ADMIN);
        long id = uploadPdf(owner);
        await().atMost(10, TimeUnit.SECONDS).until(() -> "READY".equals(status(id)));

        upload(approver, "x.pdf", "application/pdf", Docs.pdf()).expectStatus().isForbidden();
        // everyone can read
        web.get().uri("/api/documents/" + id).header("Authorization", bearer(approver)).exchange().expectStatus().isOk();
        web.delete().uri("/api/documents/" + id).header("Authorization", bearer(approver)).exchange().expectStatus().isForbidden();
        web.delete().uri("/api/documents/" + id).header("Authorization", bearer(otherAnalyst)).exchange().expectStatus().isForbidden();
        web.post().uri("/api/documents/" + id + "/reindex").header("Authorization", bearer(otherAnalyst)).exchange().expectStatus().isForbidden();

        stubDeleteOk();
        web.delete().uri("/api/documents/" + id).header("Authorization", bearer(admin)).exchange().expectStatus().isNoContent();
        assertThat(status(id)).isNull();
    }

    @Test
    void ownerDeleteRemovesRowFileAndVectors() {
        stubIngestOk(1, 1);
        stubDeleteOk();
        Session owner = sessionFor(Role.ANALYST);
        long id = uploadPdf(owner);
        await().atMost(10, TimeUnit.SECONDS).until(() -> "READY".equals(status(id)));
        web.delete().uri("/api/documents/" + id).header("Authorization", bearer(owner)).exchange().expectStatus().isNoContent();
        assertThat(status(id)).isNull();
        AI.verify(deleteRequestedFor(urlEqualTo("/internal/documents/" + id)));
        assertThat(jdbc.queryForObject("select count(*) from audit_log where action = 'DOCUMENT_DELETE'", Integer.class)).isEqualTo(1);
    }

    @Test
    void deleteWhileAiDownStaysDeletingUntilSweeperSucceeds() {
        stubIngestOk(1, 1);
        Session owner = sessionFor(Role.ANALYST);
        long id = uploadPdf(owner);
        await().atMost(10, TimeUnit.SECONDS).until(() -> "READY".equals(status(id)));

        AI.stubFor(delete(urlPathMatching("/internal/documents/\\d+")).willReturn(aResponse().withFault(Fault.CONNECTION_RESET_BY_PEER)));
        web.delete().uri("/api/documents/" + id).header("Authorization", bearer(owner)).exchange().expectStatus().isNoContent();
        assertThat(status(id)).isEqualTo("DELETING");

        sweeper.sweep();                                  // still down: still DELETING
        assertThat(status(id)).isEqualTo("DELETING");

        AI.resetAll();
        stubDeleteOk();
        sweeper.sweep();
        assertThat(status(id)).isNull();
    }

    @Test
    void sweeperFailsDocumentsStuckInIngesting() {
        long uid = createUser(Role.ANALYST).getId();
        jdbc.update("insert into documents(uploaded_by,title,original_filename,source_type,size_bytes,storage_key,status,content_hash,updated_at) "
                + "values(?,?,?,?,?,?,?,?, now() - interval '30 minutes')", uid, "t", "t.pdf", "PDF", 10, "aa/" + "a".repeat(32), "INGESTING", "b".repeat(64));
        sweeper.sweep();
        assertThat(jdbc.queryForObject("select status from documents", String.class)).isEqualTo("FAILED");
    }

    @Test
    void searchProxiesAndFillsTitlesOnlyForReadyDocuments() {
        stubIngestOk(1, 1);
        Session s = sessionFor(Role.APPROVER);
        Session owner = sessionFor(Role.ANALYST);
        long id = uploadPdf(owner);
        await().atMost(10, TimeUnit.SECONDS).until(() -> "READY".equals(status(id)));
        stubSearch("[{\"chunkId\":7,\"documentId\":" + id + ",\"page\":2,\"section\":\"Pricing\",\"snippet\":\"price rise\",\"score\":0.8},"
                + "{\"chunkId\":8,\"documentId\":424242,\"page\":1,\"section\":null,\"snippet\":\"orphan\",\"score\":0.5}]");
        web.get().uri("/api/search?q=price&mode=hybrid&k=5").header("Authorization", bearer(s)).exchange().expectStatus().isOk()
                .expectBody().jsonPath("$.data.length()").isEqualTo(1).jsonPath("$.data[0].documentTitle").isEqualTo("report");
        web.get().uri("/api/search?q={q}", " ").header("Authorization", bearer(s)).exchange().expectStatus().isBadRequest();
    }

    @Test
    void aiDownOnSearchIsReportedAs503() {
        AI.stubFor(post(urlEqualTo("/internal/search")).willReturn(aResponse().withStatus(503)));
        web.get().uri("/api/search?q=price").header("Authorization", bearer(sessionFor(Role.ANALYST))).exchange()
                .expectStatus().isEqualTo(503).expectBody().jsonPath("$.error.code").isEqualTo("AI_SERVICE_UNAVAILABLE");
    }

    @Test
    void downloadUsesSafeHeaders() {
        stubIngestOk(1, 1);
        Session owner = sessionFor(Role.ANALYST);
        long id = uploadPdf(owner);
        web.get().uri("/api/documents/" + id + "/file").header("Authorization", bearer(owner)).exchange().expectStatus().isOk()
                .expectHeader().contentType("application/pdf").expectHeader().valueEquals("X-Content-Type-Options", "nosniff")
                .expectHeader().value("Content-Disposition", v -> assertThat(v).startsWith("attachment"));
    }
}
