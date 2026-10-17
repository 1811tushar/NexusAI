package com.nexusai.investigation;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.security.CurrentUser;
import jakarta.validation.Valid;
import java.nio.charset.StandardCharsets;
import java.util.List;
import org.springframework.http.CacheControl;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequestMapping("/api/investigations")
public class InvestigationController {
    private final InvestigationService service;
    private final InvestigationStreamService stream;
    private final ReportExportService export;

    public InvestigationController(InvestigationService service, InvestigationStreamService stream, ReportExportService export) {
        this.service = service;
        this.stream = stream;
        this.export = export;
    }

    @PostMapping
    public ResponseEntity<ApiResponse<InvestigationDTO>> start(@RequestBody StartInvestigationRequestDTO req) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResponse.ok(service.start(req, CurrentUser.require())));
    }

    @GetMapping
    public ApiResponse<PagedResponseDTO<InvestigationDTO>> list(@RequestParam(required = false) InvestigationStatus status, @RequestParam(required = false) String q,
                                                                @RequestParam(defaultValue = "false") boolean mine, @RequestParam(defaultValue = "0") int page,
                                                                @RequestParam(defaultValue = "20") int size, @RequestParam(required = false) String sort) {
        return ApiResponse.ok(service.list(status, q, mine, page, size, sort, CurrentUser.require()));
    }

    @GetMapping("/{id}")
    public ApiResponse<InvestigationDetailDTO> get(@PathVariable long id) { return ApiResponse.ok(service.get(id, CurrentUser.require())); }

    @GetMapping("/{id}/steps")
    public ApiResponse<List<AgentStepDTO>> steps(@PathVariable long id) { return ApiResponse.ok(service.steps(id, CurrentUser.require())); }

    /**
     * SSE. Not declared with produces= so that error responses (404...) can still be written as the JSON envelope even when the client sent
     * Accept: text/event-stream. Resume point: Last-Event-ID header, else ?after=seq.
     */
    @GetMapping("/{id}/stream")
    public ResponseEntity<SseEmitter> stream(@PathVariable long id, @RequestHeader(value = "Last-Event-ID", required = false) String lastEventId,
                                             @RequestParam(required = false) Integer after) {
        int from = parse(lastEventId, after == null ? 0 : after);
        SseEmitter emitter = stream.open(id, from, CurrentUser.require());
        return ResponseEntity.ok().contentType(MediaType.TEXT_EVENT_STREAM)
                .cacheControl(CacheControl.noCache()).header("X-Accel-Buffering", "no").header("Connection", "keep-alive").body(emitter);
    }

    @PostMapping("/{id}/cancel")
    public ResponseEntity<Void> cancel(@PathVariable long id) {
        service.cancel(id, CurrentUser.require());
        return ResponseEntity.noContent().build();
    }

    @GetMapping("/{id}/report.md")
    public ResponseEntity<byte[]> reportMarkdown(@PathVariable long id) {
        byte[] body = export.render(id, CurrentUser.require()).getBytes(StandardCharsets.UTF_8);
        return ResponseEntity.ok().contentType(new MediaType("text", "markdown", StandardCharsets.UTF_8))
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.builder("attachment").filename("investigation-" + id + "-report.md").build().toString())
                .header("X-Content-Type-Options", "nosniff").body(body);
    }

    @PostMapping("/{id}/feedback")
    public ResponseEntity<Void> feedback(@PathVariable long id, @Valid @RequestBody FeedbackRequestDTO req) {
        service.feedback(id, req, CurrentUser.require());
        return ResponseEntity.noContent().build();
    }

    private static int parse(String header, int fallback) {
        if (header == null || header.isBlank()) return fallback;
        try { return Integer.parseInt(header.trim()); } catch (NumberFormatException e) { return fallback; }
    }
}
