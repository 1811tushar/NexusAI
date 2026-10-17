package com.nexusai.approval;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

public interface ApprovalRepository extends JpaRepository<Approval, Long>, JpaSpecificationExecutor<Approval> {
    List<Approval> findByInvestigationIdOrderByIdAsc(Long investigationId);
    List<Approval> findByInvestigationIdAndStatus(Long investigationId, ApprovalStatus status);
    Optional<Approval> findByInvestigationIdAndActionKey(Long investigationId, String actionKey);
    boolean existsByInvestigationIdAndActionKey(Long investigationId, String actionKey);
    long countByInvestigationIdAndStatus(Long investigationId, ApprovalStatus status);
    long countByStatus(ApprovalStatus status);
    List<Approval> findByStatusAndExpiresAtBefore(ApprovalStatus status, Instant cutoff);

    @Query("select count(a) from Approval a where a.status = com.nexusai.approval.ApprovalStatus.PENDING and a.investigationId in "
            + "(select i.id from Investigation i where i.userId = :uid)")
    long countPendingForOwner(@Param("uid") Long ownerId);

    @Query("select a.investigationId, count(a) from Approval a where a.status = com.nexusai.approval.ApprovalStatus.PENDING "
            + "and a.investigationId in :ids group by a.investigationId")
    List<Object[]> pendingCounts(@Param("ids") List<Long> investigationIds);

    /** Exactly-one-winner decision: only a still-PENDING, not-yet-expired approval can be decided. Returns rows changed. */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Approval a set a.status = :status, a.decidedBy = :by, a.decidedAt = :now, a.comment = :comment "
            + "where a.id = :id and a.status = com.nexusai.approval.ApprovalStatus.PENDING and a.expiresAt > :now")
    int decideIfPending(@Param("id") Long id, @Param("status") ApprovalStatus status, @Param("by") Long decidedBy,
                        @Param("now") Instant now, @Param("comment") String comment);

    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Approval a set a.status = com.nexusai.approval.ApprovalStatus.EXPIRED, a.decidedAt = :now, a.comment = :comment "
            + "where a.id = :id and a.status = com.nexusai.approval.ApprovalStatus.PENDING and a.expiresAt <= :now")
    int expireIfPending(@Param("id") Long id, @Param("now") Instant now, @Param("comment") String comment);

    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Approval a set a.status = com.nexusai.approval.ApprovalStatus.EXPIRED, a.decidedAt = :now, a.comment = :comment "
            + "where a.investigationId = :inv and a.status = com.nexusai.approval.ApprovalStatus.PENDING")
    int expireAllPending(@Param("inv") Long investigationId, @Param("now") Instant now, @Param("comment") String comment);
}
