package com.nexusai.approval;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.DynamicUpdate;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "approvals")
@DynamicUpdate
@Getter @Setter @NoArgsConstructor
public class Approval {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "investigation_id", nullable = false)
    private Long investigationId;
    @Column(name = "action_key", nullable = false, length = 40)
    private String actionKey;
    @Column(name = "action_type", nullable = false, length = 24)
    private String actionType;                 // ActionType name, or UNKNOWN for a rejected forged type
    @Column(nullable = false, length = 255)
    private String title;
    @Column(nullable = false, columnDefinition = "text")
    private String description;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable = false, columnDefinition = "jsonb")
    private JsonNode params;
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 4)
    private Risk risk;
    @Column(nullable = false, columnDefinition = "text")
    private String rationale;
    @JdbcTypeCode(SqlTypes.JSON) @Column(name = "evidence_keys", nullable = false, columnDefinition = "jsonb")
    private JsonNode evidenceKeys;
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 10)
    private ApprovalStatus status = ApprovalStatus.PENDING;
    @Column(name = "requested_at", nullable = false, updatable = false)
    private Instant requestedAt;
    @Column(name = "decided_by")
    private Long decidedBy;
    @Column(name = "decided_at")
    private Instant decidedAt;
    @Column(columnDefinition = "text")
    private String comment;
    @Column(name = "expires_at", nullable = false)
    private Instant expiresAt;

    @PrePersist void onCreate() { if (requestedAt == null) requestedAt = Instant.now(); }
}
