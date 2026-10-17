package com.nexusai.audit;

import jakarta.persistence.*;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Entity
@Table(name = "audit_log")
@Getter @Setter @NoArgsConstructor
public class AuditLog {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    @Column(name = "user_id")
    private Long userId;
    @Column(nullable = false, length = 50)
    private String action;
    @Column(length = 30)
    private String entity;
    @Column(name = "entity_id", length = 50)
    private String entityId;
    @Column(length = 45)
    private String ip;
    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @PrePersist void onCreate() { createdAt = Instant.now(); }
}
