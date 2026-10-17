package com.nexusai.approval;

import java.util.List;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ActionLogRepository extends JpaRepository<ActionLog, Long> {
    List<ActionLog> findByInvestigationIdOrderByIdAsc(Long investigationId);
    boolean existsByApprovalId(Long approvalId);
    java.util.Optional<ActionLog> findFirstByApprovalIdOrderByIdAsc(Long approvalId);
    long countByInvestigationIdAndStatus(Long investigationId, ActionStatus status);

    @Query(value = "select a from ActionLog a where a.investigationId in (select i.id from Investigation i where i.userId = :uid)",
           countQuery = "select count(a) from ActionLog a where a.investigationId in (select i.id from Investigation i where i.userId = :uid)")
    Page<ActionLog> findForOwner(@Param("uid") Long ownerId, Pageable pageable);
}
