package com.nexusai.document;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.nexusai.ai.AiServiceClient;
import com.nexusai.audit.AuditService;
import com.nexusai.common.Docs;
import com.nexusai.common.TestProps;
import com.nexusai.common.exception.*;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.common.storage.FileStorage;
import com.nexusai.user.Role;
import com.nexusai.user.User;
import com.nexusai.user.UserRepository;
import java.util.Optional;
import java.util.UUID;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class DocumentServiceTest {
    @Mock DocumentRepository repo;
    @Mock UserRepository users;
    @Mock FileStorage storage;
    @Mock AiServiceClient ai;
    @Mock ApplicationEventPublisher events;
    @Mock AuditService audit;
    private DocumentService service;

    private static final AuthenticatedUser ANALYST = new AuthenticatedUser(10, Role.ANALYST, UUID.randomUUID());
    private static final AuthenticatedUser OTHER = new AuthenticatedUser(11, Role.ANALYST, UUID.randomUUID());
    private static final AuthenticatedUser APPROVER = new AuthenticatedUser(12, Role.APPROVER, UUID.randomUUID());
    private static final AuthenticatedUser ADMIN = new AuthenticatedUser(13, Role.ADMIN, UUID.randomUUID());

    @BeforeEach void setUp() {
        service = build(500);
        User u = new User();
        u.setId(10L);
        u.setDisplayName("Owner");
        when(users.findById(10L)).thenReturn(Optional.of(u));
        when(repo.saveAndFlush(any())).thenAnswer(i -> { Document d = i.getArgument(0); d.setId(5L); return d; });
        when(storage.store(any())).thenReturn("ab/" + "c".repeat(32));
    }

    private DocumentService build(int maxDocs) {
        return new DocumentService(repo, users, storage, ai, events, audit, TestProps.props(true, maxDocs),
                new TransactionTemplate(mock(PlatformTransactionManager.class)));
    }

    private static MockMultipartFile pdf() { return new MockMultipartFile("file", "Q2.pdf", "application/pdf", Docs.pdf()); }

    private Document doc(long id, long ownerId, DocumentStatus status) {
        User owner = new User();
        owner.setId(ownerId);
        owner.setDisplayName("Owner");
        Document d = new Document();
        d.setId(id);
        d.setUploadedBy(owner);
        d.setStatus(status);
        d.setStorageKey("ab/" + "c".repeat(32));
        d.setSourceType(SourceType.PDF);
        d.setTitle("t");
        when(repo.findWithUploaderById(id)).thenReturn(Optional.of(d));
        when(repo.findById(id)).thenReturn(Optional.of(d));
        return d;
    }

    @Test void approverCannotUpload() {
        assertThatThrownBy(() -> service.upload(pdf(), APPROVER)).isInstanceOf(ForbiddenException.class);
        verify(storage, never()).store(any());
    }

    @Test void totalDocumentCapIsEnforced() {
        when(repo.count()).thenReturn(1L);
        assertThatThrownBy(() -> build(1).upload(pdf(), ANALYST)).isInstanceOf(QuotaExceededException.class);
    }

    @Test void duplicateHashIsRejectedWithExistingIdAndNothingIsStored() {
        Document existing = new Document();
        existing.setId(77L);
        when(repo.findByContentHash(any())).thenReturn(Optional.of(existing));
        assertThatThrownBy(() -> service.upload(pdf(), ANALYST)).isInstanceOfSatisfying(DuplicateResourceException.class,
                e -> assertThat(e.getDetails()).containsEntry("existingDocumentId", "77"));
        verify(storage, never()).store(any());
    }

    @Test void invalidFileIsRejectedBeforeStorage() {
        MockMultipartFile fake = new MockMultipartFile("file", "x.pdf", "application/pdf", Docs.text());
        assertThatThrownBy(() -> service.upload(fake, ANALYST)).isInstanceOf(UnsupportedFileTypeException.class);
        verify(storage, never()).store(any());
    }

    @Test void uploadStoresPublishesIngestionEventAndAudits() {
        DocumentDTO dto = service.upload(pdf(), ANALYST);
        assertThat(dto.status()).isEqualTo(DocumentStatus.UPLOADED);
        assertThat(dto.title()).isEqualTo("Q2");
        assertThat(dto.mimeType()).isEqualTo("application/pdf");
        ArgumentCaptor<Object> ev = ArgumentCaptor.forClass(Object.class);
        verify(events).publishEvent(ev.capture());
        assertThat(ev.getValue()).isInstanceOfSatisfying(DocumentIngestionRequested.class, e -> assertThat(e.documentId()).isEqualTo(5L));
        verify(audit).record(eq(10L), eq("DOCUMENT_UPLOAD"), eq("DOCUMENT"), eq("5"));
    }

    @Test void failedPersistenceRemovesTheStoredFile() {
        when(repo.saveAndFlush(any())).thenThrow(new IllegalStateException("db down"));
        assertThatThrownBy(() -> service.upload(pdf(), ANALYST)).isInstanceOf(IllegalStateException.class);
        verify(storage).delete("ab/" + "c".repeat(32));
    }

    @Test void deleteAndReindexAreOwnerOrAdminOnly() {
        doc(1, 10, DocumentStatus.READY);
        assertThatThrownBy(() -> service.delete(1, OTHER)).isInstanceOf(ForbiddenException.class);
        assertThatThrownBy(() -> service.delete(1, APPROVER)).isInstanceOf(ForbiddenException.class);
        assertThatThrownBy(() -> service.reindex(1, OTHER)).isInstanceOf(ForbiddenException.class);
        assertThatThrownBy(() -> service.reindex(1, APPROVER)).isInstanceOf(ForbiddenException.class);
        verify(repo, never()).transition(anyLong(), any(), any(), any());
    }

    @Test void unknownDocumentIs404() {
        when(repo.findWithUploaderById(404L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> service.delete(404, ADMIN)).isInstanceOf(ResourceNotFoundException.class);
        assertThatThrownBy(() -> service.get(404)).isInstanceOf(ResourceNotFoundException.class);
    }

    @Test void cannotDeleteWhileIngestingOrReindexUnlessReadyOrFailed() {
        doc(2, 10, DocumentStatus.INGESTING);
        assertThatThrownBy(() -> service.delete(2, ANALYST)).isInstanceOf(InvalidStateException.class);
        assertThatThrownBy(() -> service.reindex(2, ANALYST)).isInstanceOf(InvalidStateException.class);
    }

    @Test void adminDeleteMarksDeletingThenRemovesVectorsFileAndRow() {
        Document d = doc(3, 10, DocumentStatus.READY);
        when(repo.transition(eq(3L), any(), eq(DocumentStatus.DELETING), any())).thenAnswer(i -> { d.setStatus(DocumentStatus.DELETING); return 1; });
        service.delete(3, ADMIN);
        verify(ai).deleteDocument(3L);
        verify(storage).delete("ab/" + "c".repeat(32));
        verify(repo).deleteById(3L);
    }

    @Test void whenAiIsDownTheDocumentStaysDeleting() {
        Document d = doc(4, 10, DocumentStatus.DELETING);
        doThrow(new AiServiceUnavailableException("down")).when(ai).deleteDocument(4L);
        assertThat(service.completeDeletion(4)).isFalse();
        verify(storage, never()).delete(any());
        verify(repo, never()).deleteById(anyLong());
        assertThat(d.getStatus()).isEqualTo(DocumentStatus.DELETING);
    }

    @Test void completeDeletionIsNoOpForMissingOrNotDeletingDocuments() {
        when(repo.findById(8L)).thenReturn(Optional.empty());
        assertThat(service.completeDeletion(8)).isTrue();
        doc(9, 10, DocumentStatus.READY);
        assertThat(service.completeDeletion(9)).isFalse();
        verify(ai, never()).deleteDocument(anyLong());
    }

    @Test void chunksOnlyForReadyDocuments() {
        doc(6, 10, DocumentStatus.FAILED);
        assertThatThrownBy(() -> service.chunks(6, 0, 50)).isInstanceOf(InvalidStateException.class);
    }

    @Test void deletingDocumentCannotBeDownloaded() {
        doc(7, 10, DocumentStatus.DELETING);
        assertThatThrownBy(() -> service.download(7)).isInstanceOf(ResourceNotFoundException.class);
    }
}
