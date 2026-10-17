package com.nexusai.document;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.security.CurrentUser;
import org.springframework.core.io.InputStreamResource;
import org.springframework.http.CacheControl;
import org.springframework.http.ContentDisposition;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.multipart.MultipartFile;

import java.nio.charset.StandardCharsets;

@RestController
@RequestMapping("/api/documents")
public class DocumentController {
    private final DocumentService service;
    public DocumentController(DocumentService service) { this.service = service; }

    @PostMapping(consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
    public ResponseEntity<ApiResponse<DocumentDTO>> upload(@RequestParam("file") MultipartFile file) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResponse.ok(service.upload(file, CurrentUser.require())));
    }

    @GetMapping
    public ApiResponse<PagedResponseDTO<DocumentDTO>> list(@RequestParam(required = false) String q,
                                                           @RequestParam(required = false) DocumentStatus status,
                                                           @RequestParam(required = false) SourceType sourceType,
                                                           @RequestParam(defaultValue = "0") int page,
                                                           @RequestParam(defaultValue = "20") int size,
                                                           @RequestParam(required = false) String sort) {
        return ApiResponse.ok(service.list(q, status, sourceType, page, size, sort));
    }

    @GetMapping("/{id}")
    public ApiResponse<DocumentDTO> get(@PathVariable long id) { return ApiResponse.ok(service.get(id)); }

    @GetMapping("/{id}/chunks")
    public ApiResponse<PagedResponseDTO<ChunkDTO>> chunks(@PathVariable long id, @RequestParam(defaultValue = "0") int page,
                                                          @RequestParam(defaultValue = "50") int size) {
        return ApiResponse.ok(service.chunks(id, page, size));
    }

    /** Original bytes with safe headers: fixed content type, forced download, no sniffing. Not wrapped in the envelope. */
    @GetMapping("/{id}/file")
    public ResponseEntity<InputStreamResource> file(@PathVariable long id) {
        DocumentService.DownloadedFile f = service.download(id);
        return ResponseEntity.ok()
                .contentType(MediaType.parseMediaType(f.mimeType()))
                .contentLength(f.size())
                .header(HttpHeaders.CONTENT_DISPOSITION, ContentDisposition.builder("attachment").filename(f.filename(), StandardCharsets.UTF_8).build().toString())
                .header("X-Content-Type-Options", "nosniff")
                .cacheControl(CacheControl.noStore().cachePrivate())
                .body(new InputStreamResource(f.stream()));
    }

    @PostMapping("/{id}/reindex")
    public ResponseEntity<ApiResponse<DocumentDTO>> reindex(@PathVariable long id) {
        return ResponseEntity.status(HttpStatus.ACCEPTED).body(ApiResponse.ok(service.reindex(id, CurrentUser.require())));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable long id) {
        service.delete(id, CurrentUser.require());
        return ResponseEntity.noContent().build();
    }
}
