package com.nexusai.document;

import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.data.jpa.repository.EntityGraph;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.transaction.annotation.Transactional;

public interface DocumentRepository extends JpaRepository<Document, Long>, JpaSpecificationExecutor<Document> {
    Optional<Document> findByContentHash(String contentHash);
    long countByStatus(DocumentStatus status);
    List<Document> findByStatus(DocumentStatus status);

    @Override
    @EntityGraph(attributePaths = "uploadedBy")
    Page<Document> findAll(Specification<Document> spec, Pageable pageable);

    @EntityGraph(attributePaths = "uploadedBy")
    Optional<Document> findWithUploaderById(Long id);

    @EntityGraph(attributePaths = "uploadedBy")
    List<Document> findWithUploaderByIdIn(Collection<Long> ids);

    /** Guarded status transition; returns the number of rows changed (0 = someone else got there first). */
    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Document d set d.status = :to, d.errorMessage = null, d.updatedAt = :now where d.id = :id and d.status in :from")
    int transition(@Param("id") Long id, @Param("from") Collection<DocumentStatus> from, @Param("to") DocumentStatus to, @Param("now") Instant now);

    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Document d set d.status = com.nexusai.document.DocumentStatus.READY, d.pageCount = :pages, d.chunkCount = :chunks, "
            + "d.errorMessage = null, d.ingestedAt = :now, d.updatedAt = :now where d.id = :id and d.status = com.nexusai.document.DocumentStatus.INGESTING")
    int markReady(@Param("id") Long id, @Param("pages") Integer pages, @Param("chunks") Integer chunks, @Param("now") Instant now);

    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Document d set d.status = com.nexusai.document.DocumentStatus.FAILED, d.errorMessage = :msg, d.updatedAt = :now "
            + "where d.id = :id and d.status = com.nexusai.document.DocumentStatus.INGESTING")
    int markFailed(@Param("id") Long id, @Param("msg") String message, @Param("now") Instant now);

    @Transactional
    @Modifying(clearAutomatically = true, flushAutomatically = true)
    @Query("update Document d set d.status = com.nexusai.document.DocumentStatus.FAILED, d.errorMessage = :msg, d.updatedAt = :now "
            + "where d.status = com.nexusai.document.DocumentStatus.INGESTING and d.updatedAt < :cutoff")
    int failStuckIngesting(@Param("cutoff") Instant cutoff, @Param("msg") String message, @Param("now") Instant now);
}
