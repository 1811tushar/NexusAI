package com.nexusai.investigation;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

/** One row per verification; the API shows the latest row per claim_key. */
@Entity
@Table(name = "claims")
@Getter @Setter @NoArgsConstructor
public class Claim {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "investigation_id", nullable = false)
    private Long investigationId;
    @Column(name = "claim_key", nullable = false, length = 40)
    private String claimKey;
    @Column(name = "text", nullable = false, columnDefinition = "text")
    private String text;
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 12)
    private ClaimStatus status;
    @Column(nullable = false, columnDefinition = "numeric(4,3)")
    private Double confidence;
    @Column(name = "is_key", nullable = false)
    private boolean key;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "evidence_keys", nullable = false, columnDefinition = "jsonb")
    private JsonNode evidenceKeys;
    @Column(name = "loop", nullable = false)
    private int loop;
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist void onCreate() { if (createdAt == null) createdAt = Instant.now(); }
}
