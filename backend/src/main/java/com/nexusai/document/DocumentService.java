package com.nexusai.document;

import com.nexusai.ai.AiServiceClient;
import com.nexusai.ai.AiSearchRequest;
import com.nexusai.audit.AuditAction;
import com.nexusai.audit.AuditService;
import com.nexusai.common.config.NexusProperties;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.common.security.RequestIdFilter;
import com.nexusai.common.storage.FileStorage;
import com.nexusai.common.util.PageUtil;
import com.nexusai.user.Role;
import com.nexusai.user.UserRepository;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.EnumSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import org.springframework.web.multipart.MultipartFile;

/**
 * Document rules (contract 4.2 + section 2). Documents are organisation-wide knowledge: everyone may read, ADMIN/ANALYST may
 * upload, ANALYST may delete/reindex only their own, ADMIN any, APPROVER nothing but read. Methods that mix DB and I/O are
 * deliberately NOT @Transactional; each DB step uses the TransactionTemplate so no connection is held during AI/disk calls.
 */
@Service
public class DocumentService {
    private static final Logger log = LoggerFactory.getLogger(DocumentService.class);
    private static final Set<String> SORTABLE = Set.of("createdAt", "title", "sizeBytes", "status", "sourceType", "ingestedAt");
    private static final int MAX_SEARCH_K = 20;

    private final DocumentRepository repo;
    private final UserRepository users;
    private final FileStorage storage;
    private final AiServiceClient ai;
    private final ApplicationEventPublisher events;
    private final AuditService audit;
    private final NexusProperties props;
    private final TransactionTemplate tx;

    public DocumentService(DocumentRepository repo, UserRepository users, FileStorage storage, AiServiceClient ai,
                           ApplicationEventPublisher events, AuditService audit, NexusProperties props, TransactionTemplate tx) {
        this.repo = repo;
        this.users = users;
        this.storage = storage;
        this.ai = ai;
        this.events = events;
        this.audit = audit;
        this.props = props;
        this.tx = tx;
    }

    // ---------------- upload ----------------

    public DocumentDTO upload(MultipartFile file, AuthenticatedUser actor) {
        requireUploader(actor);
        if (file == null) throw new ValidationFailedException("Missing file", Map.of("file", "is required"));
        if (repo.count() >= props.upload().maxDocsTotal()) {
            throw new QuotaExceededException("The knowledge base is full (" + props.upload().maxDocsTotal() + " documents)");
        }
        byte[] bytes;
        try {
            bytes = file.getBytes();
        } catch (java.io.IOException e) {
            throw new ValidationFailedException("The file could not be read", Map.of("file", "unreadable"));
        }
        long maxBytes = (long) props.upload().maxMb() * 1024 * 1024;
        DocumentFileValidator.Validated v = DocumentFileValidator.validate(file.getOriginalFilename(), file.getContentType(), bytes, maxBytes);

        String hash = sha256(bytes);
        repo.findByContentHash(hash).ifPresent(d -> { throw duplicate(d.getId()); });

        String key = storage.store(bytes);
        try {
            DocumentDTO dto = tx.execute(status -> {
                Document d = new Document();
                d.setUploadedBy(users.findById(actor.id()).orElseThrow(() -> new UnauthenticatedException("Account no longer exists")));
                d.setTitle(v.title());
                d.setOriginalFilename(v.safeFilename());
                d.setSourceType(v.type());
                d.setMimeType(v.type().canonicalMime());
                d.setSizeBytes(bytes.length);
                d.setStorageKey(key);
                d.setContentHash(hash);
                d.setStatus(DocumentStatus.UPLOADED);
                repo.saveAndFlush(d);
                events.publishEvent(new DocumentIngestionRequested(d.getId(), RequestIdFilter.currentOrNew()));
                return DocumentDTO.from(d);
            });
            audit.record(actor.id(), AuditAction.DOCUMENT_UPLOAD, "DOCUMENT", String.valueOf(dto.id()));
            return dto;
        } catch (DataIntegrityViolationException e) {      // lost a race on the unique content hash
            storage.delete(key);
            Document existing = repo.findByContentHash(hash).orElseThrow(() -> e);
            throw duplicate(existing.getId());
        } catch (RuntimeException e) {
            storage.delete(key);
            throw e;
        }
    }

    // ---------------- read ----------------

    public PagedResponseDTO<DocumentDTO> list(String q, DocumentStatus status, SourceType type, int page, int size, String sort) {
        Pageable pageable = PageUtil.of(page, size, sort, SORTABLE, "createdAt", Sort.Direction.DESC);
        return tx.execute(s -> {
            Page<Document> result = repo.findAll(DocumentSpecs.filter(q, status, type), pageable);
            return PagedResponseDTO.from(result, DocumentDTO::from);
        });
    }

    public DocumentDTO get(long id) {
        return tx.execute(s -> DocumentDTO.from(load(id)));
    }

    public PagedResponseDTO<ChunkDTO> chunks(long id, int page, int size) {
        Document d = tx.execute(s -> load(id));
        if (d.getStatus() != DocumentStatus.READY) throw new InvalidStateException("Chunks are only available for documents in READY state");
        return ai.listChunks(id, Math.max(page, 0), Math.min(Math.max(size, 1), PageUtil.MAX_SIZE));
    }

    public record DownloadedFile(String filename, String mimeType, long size, InputStream stream) { }

    public DownloadedFile download(long id) {
        Document d = tx.execute(s -> load(id));
        if (d.getStatus() == DocumentStatus.DELETING) throw new ResourceNotFoundException("Document not found");
        if (!storage.exists(d.getStorageKey())) throw new ResourceNotFoundException("The stored file is missing");
        return new DownloadedFile(d.getOriginalFilename(), d.getSourceType().canonicalMime(), d.getSizeBytes(), storage.open(d.getStorageKey()));
    }

    /** Library search: hybrid retrieval in Python; titles are filled in here and only READY documents are returned. */
    public List<SearchResultDTO> search(String query, String mode, int k) {
        int kk = Math.min(Math.max(k, 1), MAX_SEARCH_K);
        List<SearchResultDTO> raw = ai.search(new AiSearchRequest(query.trim(), mode, kk, null));
        Set<Long> ids = raw.stream().map(SearchResultDTO::documentId).collect(Collectors.toSet());
        Map<Long, Document> docs = tx.execute(s -> repo.findAllById(ids).stream().collect(Collectors.toMap(Document::getId, d -> d)));
        return raw.stream()
                .filter(r -> docs.containsKey(r.documentId()) && docs.get(r.documentId()).getStatus() == DocumentStatus.READY)
                .map(r -> r.withTitle(docs.get(r.documentId()).getTitle()))
                .toList();
    }

    // ---------------- reindex / delete ----------------

    public DocumentDTO reindex(long id, AuthenticatedUser actor) {
        return tx.execute(s -> {
            Document d = load(id);
            requireManage(d, actor);
            if (d.getStatus() != DocumentStatus.READY && d.getStatus() != DocumentStatus.FAILED) {
                throw new InvalidStateException("Only READY or FAILED documents can be reindexed");
            }
            if (!storage.exists(d.getStorageKey())) throw new InvalidStateException("The stored file is missing; upload it again");
            repo.transition(id, EnumSet.of(DocumentStatus.READY, DocumentStatus.FAILED), DocumentStatus.UPLOADED, Instant.now());
            events.publishEvent(new DocumentIngestionRequested(id, RequestIdFilter.currentOrNew()));
            return DocumentDTO.from(repo.findWithUploaderById(id).orElseThrow());
        });
    }

    /** Marks DELETING, then tries the physical removal; if the AI service is down the document stays DELETING for the sweeper. */
    public void delete(long id, AuthenticatedUser actor) {
        tx.executeWithoutResult(s -> {
            Document d = load(id);
            requireManage(d, actor);
            if (d.getStatus() == DocumentStatus.INGESTING) throw new InvalidStateException("The document is being ingested; try again in a moment");
            if (d.getStatus() != DocumentStatus.DELETING) {
                repo.transition(id, EnumSet.of(DocumentStatus.UPLOADED, DocumentStatus.READY, DocumentStatus.FAILED), DocumentStatus.DELETING, Instant.now());
            }
        });
        audit.record(actor.id(), AuditAction.DOCUMENT_DELETE, "DOCUMENT", String.valueOf(id));
        completeDeletion(id);
    }

    /** Also used by DocumentSweeper. @return true when the document is fully gone. */
    public boolean completeDeletion(long id) {
        Document d = repo.findById(id).orElse(null);
        if (d == null) return true;
        if (d.getStatus() != DocumentStatus.DELETING) return false;
        try {
            ai.deleteDocument(id);
        } catch (AiServiceUnavailableException | LlmRateLimitedException e) {
            log.warn("AI service unavailable while deleting document {}; it stays DELETING and will be retried", id);
            return false;
        }
        storage.delete(d.getStorageKey());
        repo.deleteById(id);
        return true;
    }

    // ---------------- rules ----------------

    private Document load(long id) {
        return repo.findWithUploaderById(id).orElseThrow(() -> new ResourceNotFoundException("Document not found"));
    }

    private static void requireUploader(AuthenticatedUser actor) {
        if (actor.role() == Role.APPROVER) throw new ForbiddenException("Approvers cannot upload documents");
    }

    private static void requireManage(Document d, AuthenticatedUser actor) {
        boolean ok = actor.role() == Role.ADMIN || (actor.role() == Role.ANALYST && d.getUploadedBy().getId().equals(actor.id()));
        if (!ok) throw new ForbiddenException("You can only change documents you uploaded");
    }

    private static DuplicateResourceException duplicate(Long existingId) {
        return new DuplicateResourceException("This document has already been uploaded", Map.of("existingDocumentId", String.valueOf(existingId)));
    }

    static String sha256(byte[] bytes) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(bytes));
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException(e);
        }
    }
}
