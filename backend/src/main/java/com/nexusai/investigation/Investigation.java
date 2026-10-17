package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.DynamicUpdate;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/**
 * JSON columns are always REPLACED with a fresh node (never mutated in place) so Hibernate's dirty check sees the change.
 * last_seq is read-only here: it is only ever advanced by InvestigationEventPersister through an atomic UPDATE ... RETURNING.
 */
@Entity
@Table(name = "investigations")
@DynamicUpdate
@Getter @Setter @NoArgsConstructor
public class Investigation {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "user_id", nullable = false)
    private Long userId;
    @Column(nullable = false, columnDefinition = "text")
    private String question;
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 18)
    private InvestigationStatus status = InvestigationStatus.RUNNING;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable = false, columnDefinition = "jsonb")
    private JsonNode options;
    @Column(name = "thread_id", nullable = false, unique = true)
    private UUID threadId;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable = false, columnDefinition = "jsonb")
    private JsonNode plan;
    @Column(name = "report_markdown", columnDefinition = "text")
    private String reportMarkdown;
    @Column(columnDefinition = "text")
    private String summary;
    @Column(columnDefinition = "numeric(4,3)")
    private Double confidence;
    @Column(name = "loops_used", nullable = false)
    private int loopsUsed;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable = false, columnDefinition = "jsonb")
    private JsonNode recommendations;
    @JdbcTypeCode(SqlTypes.JSON) @Column(columnDefinition = "jsonb")
    private JsonNode usage;
    @Column(name = "latency_ms")
    private Integer latencyMs;
    @Column(name = "error_message", columnDefinition = "text")
    private String errorMessage;
    @Column(name = "feedback_rating")
    private Short feedbackRating;
    @Column(name = "feedback_comment", columnDefinition = "text")
    private String feedbackComment;
    @Column(name = "last_seq", nullable = false, insertable = false, updatable = false)
    private int lastSeq;
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;
    @Column(name = "completed_at")
    private Instant completedAt;

    @PrePersist void onCreate() { if (createdAt == null) createdAt = Instant.now(); }
}
