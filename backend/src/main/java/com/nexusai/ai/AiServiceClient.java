package com.nexusai.ai;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.nexusai.common.config.NexusProperties;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.exception.*;
import com.nexusai.common.metrics.NexusMetrics;
import com.nexusai.common.security.RequestIdFilter;
import com.nexusai.document.ChunkDTO;
import com.nexusai.eval.EvalRunDTO;
import com.nexusai.eval.EvalRunDetailDTO;
import com.nexusai.memory.MemoryDTO;
import java.util.UUID;
import org.springframework.http.codec.ServerSentEvent;
import reactor.core.publisher.Flux;
import com.nexusai.document.SearchResultDTO;
import java.net.ConnectException;
import java.time.Duration;
import java.util.List;
import java.util.concurrent.TimeoutException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.MediaType;
import org.springframework.http.client.MultipartBodyBuilder;
import org.springframework.stereotype.Component;
import org.springframework.web.reactive.function.BodyInserters;
import org.springframework.web.reactive.function.client.WebClient;
import org.springframework.web.reactive.function.client.WebClientRequestException;
import reactor.core.Exceptions;
import reactor.core.publisher.Mono;
import reactor.util.retry.Retry;

/**
 * The ONLY class that knows the Python AI service exists (BE-PL-04). One method per internal endpoint (contract section 6).
 * Every call forwards X-Request-Id; the internal API key is added by the WebClient. Retries (2x, short backoff) only on
 * idempotent calls and only for transient failures. Backend B adds investigate/resume/cancel/memories/user purge/eval here.
 */
@Component
public class AiServiceClient {
    private static final Logger log = LoggerFactory.getLogger(AiServiceClient.class);

    private final WebClient web;
    private final NexusProperties props;
    private final ObjectMapper mapper;
    private final NexusMetrics metrics;

    public AiServiceClient(WebClient aiWebClient, NexusProperties props, ObjectMapper mapper, NexusMetrics metrics) {
        this.web = aiWebClient;
        this.props = props;
        this.mapper = mapper;
        this.metrics = metrics;
    }

    /** POST /internal/ingest (multipart meta + file), synchronous, 120 s, NOT retried (not idempotent for the caller's state machine). */
    public AiIngestResponse ingest(AiIngestRequest meta, String filename, byte[] content) {
        MultipartBodyBuilder b = new MultipartBodyBuilder();
        b.part("meta", meta, MediaType.APPLICATION_JSON);
        b.part("file", new ByteArrayResource(content) {
            @Override public String getFilename() { return filename; }
        }).filename(filename).contentType(MediaType.APPLICATION_OCTET_STREAM);
        Mono<AiIngestResponse> call = web.post().uri("/internal/ingest")
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .contentType(MediaType.MULTIPART_FORM_DATA)
                .body(BodyInserters.fromMultipartData(b.build()))
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).bodyToMono(AiIngestResponse.class);
        return execute(call, Duration.ofSeconds(props.ai().ingestTimeoutSec()), false, true);
    }

    /** DELETE /internal/documents/{id}. Idempotent; a 404 from the AI service counts as already deleted. */
    public void deleteDocument(long documentId) {
        Mono<Void> call = web.delete().uri("/internal/documents/{id}", documentId)
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).toBodilessEntity().then();
        try {
            execute(call, defaultTimeout(), true, false);
        } catch (ResourceNotFoundException e) {
            log.debug("AI service had no chunks for document {}", documentId);
        }
    }

    /** GET /internal/documents/{id}/chunks?page=&size= */
    public PagedResponseDTO<ChunkDTO> listChunks(long documentId, int page, int size) {
        Mono<PagedResponseDTO<ChunkDTO>> call = web.get()
                .uri(u -> u.path("/internal/documents/{id}/chunks").queryParam("page", page).queryParam("size", size).build(documentId))
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r))
                .bodyToMono(new ParameterizedTypeReference<PagedResponseDTO<ChunkDTO>>() { });
        return execute(call, defaultTimeout(), true, false);
    }

    /** POST /internal/search (library search; read-only, retried). */
    public List<SearchResultDTO> search(AiSearchRequest req) {
        Mono<List<SearchResultDTO>> call = web.post().uri("/internal/search")
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .contentType(MediaType.APPLICATION_JSON).bodyValue(req)
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r))
                .bodyToMono(new ParameterizedTypeReference<List<SearchResultDTO>>() { });
        List<SearchResultDTO> out = execute(call, defaultTimeout(), true, false);
        return out == null ? List.of() : out;
    }

    /** GET /health (no key needed, sent anyway). */
    public AiHealthResponse health() {
        Mono<AiHealthResponse> call = web.get().uri("/health")
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).bodyToMono(AiHealthResponse.class);
        return execute(call, Duration.ofSeconds(5), false, false);
    }

    // ---- error mapping (shared by Backend B's additions) ----

    /** Marker for a non-2xx response from Python. */
    public static final class UpstreamHttpException extends RuntimeException {
        private final int status;
        private final String body;
        UpstreamHttpException(int status, String body) {
            super("AI service responded with HTTP " + status);
            this.status = status;
            this.body = body;
        }
        public int status() { return status; }
        public String body() { return body; }
    }

    private static Mono<? extends Throwable> toUpstream(org.springframework.web.reactive.function.client.ClientResponse r) {
        int status = r.statusCode().value();
        return r.bodyToMono(String.class).defaultIfEmpty("").map(body -> new UpstreamHttpException(status, body));
    }

    private Duration defaultTimeout() { return Duration.ofSeconds(props.ai().defaultTimeoutSec()); }

    private <T> T execute(Mono<T> call, Duration timeout, boolean retryTransient, boolean ingest) {
        Mono<T> m = call.timeout(timeout);
        if (retryTransient) {
            m = m.retryWhen(Retry.backoff(2, Duration.ofMillis(250)).filter(AiServiceClient::isTransient)
                    .onRetryExhaustedThrow((spec, signal) -> signal.failure()));
        }
        try {
            return m.block();
        } catch (RuntimeException e) {
            throw map(Exceptions.unwrap(e), ingest);
        }
    }

    static boolean isTransient(Throwable t) {
        Throwable c = Exceptions.unwrap(t);
        if (c instanceof UpstreamHttpException u) return u.status() >= 500 && u.status() != 501;
        return c instanceof WebClientRequestException || c instanceof ConnectException;
    }

    /** Maps and counts (nexus.ai.errors by error code); a missing resource is not an error of the service. */
    RuntimeException map(Throwable c, boolean ingest) {
        RuntimeException r = mapInner(c, ingest);
        if (r instanceof BusinessException be && be.getCode() != ErrorCode.NOT_FOUND) metrics.aiError(be.getCode().name());
        return r;
    }

    private RuntimeException mapInner(Throwable c, boolean ingest) {
        if (c instanceof UpstreamHttpException u) {
            int s = u.status();
            if (s == 429) return new LlmRateLimitedException("The AI provider is rate limited. Try again shortly.");
            if (s >= 500) return new AiServiceUnavailableException("AI service error (HTTP " + s + ")");
            if (s == 404) return new ResourceNotFoundException("Resource not found in the AI service");
            if (ingest && (s == 400 || s == 413 || s == 415 || s == 422)) return new IngestionFailedException(reason(u.body()));
            return new AiServiceUnavailableException("Unexpected response from the AI service (HTTP " + s + ")");
        }
        if (c instanceof TimeoutException) return new AiServiceUnavailableException("The AI service timed out");
        if (c instanceof BusinessException be) return be;
        log.warn("AI service call failed: {}", c.toString());
        return new AiServiceUnavailableException("The AI service is unreachable", c);
    }

    /** Extracts a short, human-readable reason from a FastAPI error body ({"detail": "..."}); never echoes huge payloads. */
    String reason(String body) {
        String fallback = "The document could not be processed";
        if (body == null || body.isBlank()) return fallback;
        try {
            JsonNode n = mapper.readTree(body);
            JsonNode d = n.has("detail") ? n.get("detail") : n.get("message");
            if (d != null && d.isTextual() && !d.asText().isBlank()) return truncate(d.asText());
        } catch (Exception ignored) {
            // not JSON
        }
        return fallback;
    }

    private static String truncate(String s) { return s.length() <= 500 ? s : s.substring(0, 500); }
    // =====================================================================================================================
    // BACKEND B ADDITIONS (additive only: Backend A's methods above are unchanged). One method per internal endpoint, contract section 6.
    // =====================================================================================================================

    /** POST /internal/investigate (SSE). Cold Flux: nothing is sent until subscribed. HTTP errors surface as the Flux error. */
    public Flux<AiEvent> investigateStream(AiInvestigateRequest request) {
        return web.post().uri("/internal/investigate")
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .accept(MediaType.TEXT_EVENT_STREAM).contentType(MediaType.APPLICATION_JSON).bodyValue(request)
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r))
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() { })
                .filter(sse -> sse.event() != null && sse.data() != null)
                .map(sse -> new AiEvent(sse.event(), sse.data()));
    }

    /** POST /internal/investigate/{threadId}/resume (SSE) after the approval decisions. */
    public Flux<AiEvent> resumeStream(UUID threadId, AiResumeRequest request) {
        return web.post().uri("/internal/investigate/{threadId}/resume", threadId)
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .accept(MediaType.TEXT_EVENT_STREAM).contentType(MediaType.APPLICATION_JSON).bodyValue(request)
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r))
                .bodyToFlux(new ParameterizedTypeReference<ServerSentEvent<String>>() { })
                .filter(sse -> sse.event() != null && sse.data() != null)
                .map(sse -> new AiEvent(sse.event(), sse.data()));
    }

    /** POST /internal/investigate/{threadId}/cancel -> {cancelled}. */
    public boolean cancel(UUID threadId) {
        Mono<AiCancelResponse> call = web.post().uri("/internal/investigate/{threadId}/cancel", threadId)
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).bodyToMono(AiCancelResponse.class);
        AiCancelResponse r = execute(call, Duration.ofSeconds(10), false, false);
        return r != null && r.cancelled();
    }

    /** GET /internal/memories?userId=&q=&page=&size= (the user id is always the authenticated user's). */
    public PagedResponseDTO<MemoryDTO> listMemories(long userId, String q, int page, int size) {
        Mono<PagedResponseDTO<MemoryDTO>> call = web.get().uri(u -> {
                    var b = u.path("/internal/memories").queryParam("userId", userId).queryParam("page", page).queryParam("size", size);
                    if (q != null && !q.isBlank()) b.queryParam("q", q);
                    return b.build();
                })
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r))
                .bodyToMono(new ParameterizedTypeReference<PagedResponseDTO<MemoryDTO>>() { });
        return execute(call, defaultTimeout(), true, false);
    }

    /** DELETE /internal/memories/{id}?userId= -> {deleted} (0 when the memory is not that user's). */
    public long deleteMemory(long userId, long memoryId) {
        Mono<AiDeletedResponse> call = web.delete().uri(u -> u.path("/internal/memories/{id}").queryParam("userId", userId).build(memoryId))
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).bodyToMono(AiDeletedResponse.class);
        try {
            AiDeletedResponse r = execute(call, defaultTimeout(), true, false);
            return r == null ? 0 : r.deleted();
        } catch (ResourceNotFoundException e) {
            return 0;
        }
    }

    /** DELETE /internal/memories?userId= -> {deleted}. */
    public long deleteAllMemories(long userId) {
        Mono<AiDeletedResponse> call = web.delete().uri(u -> u.path("/internal/memories").queryParam("userId", userId).build())
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).bodyToMono(AiDeletedResponse.class);
        AiDeletedResponse r = execute(call, defaultTimeout(), true, false);
        return r == null ? 0 : r.deleted();
    }

    /** DELETE /internal/users/{userId} -> {memories, checkpoints}. */
    public AiPurgeResponse purgeUser(long userId) {
        Mono<AiPurgeResponse> call = web.delete().uri("/internal/users/{id}", userId)
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).bodyToMono(AiPurgeResponse.class);
        return execute(call, defaultTimeout(), true, false);
    }

    /** GET /internal/eval/runs. */
    public List<EvalRunDTO> evalRuns() {
        Mono<List<EvalRunDTO>> call = web.get().uri("/internal/eval/runs")
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r))
                .bodyToMono(new ParameterizedTypeReference<List<EvalRunDTO>>() { });
        List<EvalRunDTO> out = execute(call, defaultTimeout(), true, false);
        return out == null ? List.of() : out;
    }

    /** GET /internal/eval/runs/{id}. */
    public EvalRunDetailDTO evalRun(long id) {
        Mono<EvalRunDetailDTO> call = web.get().uri("/internal/eval/runs/{id}", id)
                .header(RequestIdFilter.HEADER, RequestIdFilter.currentOrNew())
                .retrieve().onStatus(s -> s.isError(), r -> toUpstream(r)).bodyToMono(EvalRunDetailDTO.class);
        return execute(call, defaultTimeout(), true, false);
    }

    /** Maps a failure of a stream (connection loss, idle timeout, HTTP error) to the contract error so the relay can emit an error event. */
    public BusinessException mapStreamError(Throwable t) {
        RuntimeException e = map(Exceptions.unwrap(t), false);
        return e instanceof BusinessException be ? be : new AiServiceUnavailableException("The AI service failed", e);
    }
}
