package com.nexusai.investigation;

import jakarta.persistence.LockModeType;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

public interface InvestigationRepository extends JpaRepository<Investigation, Long>, JpaSpecificationExecutor<Investigation> {
    Optional<Investigation> findByThreadId(UUID threadId);
    long countByUserIdAndStatus(Long userId, InvestigationStatus status);
    List<Investigation> findByStatus(InvestigationStatus status);
    List<Investigation> findTop10ByOrderByCreatedAtDesc();
    List<Investigation> findTop10ByUserIdOrderByCreatedAtDesc(Long userId);

    /** Row lock that serialises every event, decision and cancel for one investigation. */
    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("select i from Investigation i where i.id = :id")
    Optional<Investigation> findByIdForUpdate(@Param("id") Long id);

    /** Compare-and-set on the status: exactly one concurrent caller gets 1. */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Investigation i set i.status = :to where i.id = :id and i.status = :from")
    int transition(@Param("id") Long id, @Param("from") InvestigationStatus from, @Param("to") InvestigationStatus to);

    @Query("select i.status, count(i) from Investigation i group by i.status")
    List<Object[]> countByStatusAll();

    @Query("select i.status, count(i) from Investigation i where i.userId = :uid group by i.status")
    List<Object[]> countByStatusForUser(@Param("uid") Long userId);

    @Query("select avg(i.confidence) from Investigation i where i.createdAt >= :since and i.confidence is not null")
    Double avgConfidenceSince(@Param("since") Instant since);

    @Query("select avg(i.confidence) from Investigation i where i.userId = :uid and i.createdAt >= :since and i.confidence is not null")
    Double avgConfidenceSinceForUser(@Param("uid") Long userId, @Param("since") Instant since);
}
