package com.nexusai.approval;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

@Entity
@Table(name = "action_log")
@Getter @Setter @NoArgsConstructor
public class ActionLog {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "investigation_id", nullable = false)
    private Long investigationId;
    @Column(name = "approval_id")
    private Long approvalId;
    @Column(name = "action_type", nullable = false, length = 24)
    private String actionType;
    @JdbcTypeCode(SqlTypes.JSON) @Column(nullable = false, columnDefinition = "jsonb")
    private JsonNode params;
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 4)
    private Risk risk;
    @Enumerated(EnumType.STRING) @Column(nullable = false, length = 10)
    private ActionStatus status;
    @Column(nullable = false)
    private boolean automatic;
    @Column(nullable = false, columnDefinition = "text")
    private String note;
    @Column(name = "executed_at", nullable = false, updatable = false)
    private Instant executedAt;

    @PrePersist void onCreate() { if (executedAt == null) executedAt = Instant.now(); }
}
