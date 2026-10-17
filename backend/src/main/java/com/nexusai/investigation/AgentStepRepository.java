package com.nexusai.investigation;

import java.time.Instant;
import java.util.List;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface AgentStepRepository extends JpaRepository<AgentStep, Long> {
    List<AgentStep> findByInvestigationIdOrderBySeqAsc(Long investigationId);
    List<AgentStep> findByInvestigationIdAndSeqGreaterThanOrderBySeqAsc(Long investigationId, int seq, Pageable page);
    List<AgentStep> findByInvestigationIdAndTypeOrderBySeqAsc(Long investigationId, String type);
    boolean existsByInvestigationIdAndType(Long investigationId, String type);

    @Query("select max(s.createdAt) from AgentStep s where s.investigationId = :id")
    Instant lastActivity(@Param("id") Long investigationId);
}
