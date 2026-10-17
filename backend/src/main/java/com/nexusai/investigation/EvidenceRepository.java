package com.nexusai.investigation;

import java.util.List;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface EvidenceRepository extends JpaRepository<Evidence, Long> {
    List<Evidence> findByInvestigationIdOrderByIdAsc(Long investigationId);
    boolean existsByInvestigationIdAndEvidenceKey(Long investigationId, UUID evidenceKey);
}
