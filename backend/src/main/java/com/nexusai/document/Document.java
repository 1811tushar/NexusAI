package com.nexusai.document;

import com.nexusai.user.User;
import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "documents")
@Getter @Setter @NoArgsConstructor
public class Document {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false) @JoinColumn(name = "uploaded_by", nullable = false)
    private User uploadedBy;
    /** Read-only mirror of uploaded_by so background threads never touch the lazy association. */
    @Column(name = "uploaded_by", insertable = false, updatable = false)
    private Long uploadedById;
    @Column(nullable = false, length = 255)
    private String title;
    @Column(name = "original_filename", nullable = false, length = 255)
    private String originalFilename;
    @Enumerated(EnumType.STRING) @Column(name = "source_type", nullable = false, length = 8)
    private SourceType sourceType;
    @Column(name = "mime_type", length = 100)
    private String mimeType;
    @Column(name = "size_bytes", nullable = false)
    private long sizeBytes;
    @Column(name = "storage_key", nullable = false, length = 255)
    private String storageKey;
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 12)
    private DocumentStatus status = DocumentStatus.UPLOADED;
    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;
    @Column(name = "page_count")
    private Integer pageCount;
    @Column(name = "chunk_count")
    private Integer chunkCount;
    @JdbcTypeCode(SqlTypes.CHAR)
    @Column(name = "content_hash", nullable = false, unique = true, length = 64, columnDefinition = "bpchar")
    private String contentHash;
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;
    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;
    @Column(name = "ingested_at")
    private Instant ingestedAt;

    @PrePersist void onCreate() { Instant n = Instant.now(); createdAt = n; updatedAt = n; }
    @PreUpdate void onUpdate() { updatedAt = Instant.now(); }
}
