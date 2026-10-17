package com.nexusai.ai;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.common.TestProps;
import com.nexusai.common.exception.*;
import java.net.ConnectException;
import java.util.concurrent.TimeoutException;
import org.junit.jupiter.api.Test;
import org.springframework.web.reactive.function.client.WebClient;

/** Error mapping and retry classification of the AI client (BE-PL-04). The HTTP paths are covered by the ITs against WireMock. */
class AiServiceClientTest {
    private final AiServiceClient client = new AiServiceClient(WebClient.create(), TestProps.props(), new ObjectMapper(),
            new com.nexusai.common.metrics.NexusMetrics(new io.micrometer.core.instrument.simple.SimpleMeterRegistry()));

    private static AiServiceClient.UpstreamHttpException http(int status, String body) { return new AiServiceClient.UpstreamHttpException(status, body); }

    @Test void rateLimitMapsToLlmRateLimited() { assertThat(client.map(http(429, ""), false)).isInstanceOf(LlmRateLimitedException.class); }

    @Test void serverErrorsMapToUnavailable() {
        assertThat(client.map(http(500, ""), false)).isInstanceOf(AiServiceUnavailableException.class);
        assertThat(client.map(http(503, ""), true)).isInstanceOf(AiServiceUnavailableException.class);
    }

    @Test void ingestRejectionCarriesTheReasonFromTheDetailField() {
        RuntimeException e = client.map(http(422, "{\"detail\":\"PDF is encrypted\"}"), true);
        assertThat(e).isInstanceOf(IngestionFailedException.class).hasMessage("PDF is encrypted");
    }

    @Test void ingestRejectionWithUnusableBodyFallsBackToGenericReason() {
        assertThat(client.map(http(422, "<html>boom</html>"), true)).isInstanceOf(IngestionFailedException.class).hasMessage("The document could not be processed");
        assertThat(client.map(http(400, ""), true)).isInstanceOf(IngestionFailedException.class);
    }

    @Test void longReasonsAreTruncated() {
        String body = "{\"detail\":\"" + "x".repeat(2000) + "\"}";
        assertThat(client.map(http(422, body), true).getMessage()).hasSize(500);
    }

    @Test void clientErrorsOutsideIngestAreNotReportedAsIngestionFailures() {
        assertThat(client.map(http(422, "{\"detail\":\"x\"}"), false)).isInstanceOf(AiServiceUnavailableException.class);
        assertThat(client.map(http(404, ""), false)).isInstanceOf(ResourceNotFoundException.class);
    }

    @Test void timeoutsAndConnectionFailuresMapToUnavailable() {
        assertThat(client.map(new TimeoutException(), false)).isInstanceOf(AiServiceUnavailableException.class);
        assertThat(client.map(new ConnectException("refused"), false)).isInstanceOf(AiServiceUnavailableException.class);
    }

    @Test void onlyTransientFailuresAreRetried() {
        assertThat(AiServiceClient.isTransient(http(503, ""))).isTrue();
        assertThat(AiServiceClient.isTransient(new ConnectException("x"))).isTrue();
        assertThat(AiServiceClient.isTransient(http(422, ""))).isFalse();
        assertThat(AiServiceClient.isTransient(http(429, ""))).isFalse();
        assertThat(AiServiceClient.isTransient(new TimeoutException())).isFalse();
    }
}
