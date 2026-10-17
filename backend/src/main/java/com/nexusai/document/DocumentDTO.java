package com.nexusai.document;

import java.time.Instant;

public record DocumentDTO(Long id, String title, String originalFilename, SourceType sourceType, String mimeType, long sizeBytes,
                          DocumentStatus status, String errorMessage, Integer pageCount, Integer chunkCount, Uploader uploadedBy,
                          Instant createdAt, Instant ingestedAt) {
    public record Uploader(Long id, String displayName) { }

    /** Call inside a transaction (the uploader association is lazy). */
    public static DocumentDTO from(Document d) {
        return new DocumentDTO(d.getId(), d.getTitle(), d.getOriginalFilename(), d.getSourceType(), d.getMimeType(), d.getSizeBytes(),
                d.getStatus(), d.getErrorMessage(), d.getPageCount(), d.getChunkCount(),
                new Uploader(d.getUploadedBy().getId(), d.getUploadedBy().getDisplayName()), d.getCreatedAt(), d.getIngestedAt());
    }
}
