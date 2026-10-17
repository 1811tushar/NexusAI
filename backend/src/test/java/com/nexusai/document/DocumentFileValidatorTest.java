package com.nexusai.document;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.nexusai.common.Docs;
import com.nexusai.common.exception.FileTooLargeException;
import com.nexusai.common.exception.UnsupportedFileTypeException;
import com.nexusai.common.exception.ValidationFailedException;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

class DocumentFileValidatorTest {
    private static final long MAX = 20L * 1024 * 1024;

    @Test void acceptsEachSupportedType() {
        assertThat(DocumentFileValidator.validate("a.pdf", "application/pdf", Docs.pdf(), MAX).type()).isEqualTo(SourceType.PDF);
        assertThat(DocumentFileValidator.validate("a.DOCX", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", Docs.fakeDocx(), MAX).type())
                .isEqualTo(SourceType.DOCX);
        assertThat(DocumentFileValidator.validate("a.txt", "text/plain; charset=utf-8", Docs.text(), MAX).type()).isEqualTo(SourceType.TXT);
        assertThat(DocumentFileValidator.validate("a.md", "application/octet-stream", Docs.text(), MAX).type()).isEqualTo(SourceType.MD);
    }

    @Test void rejectsMagicMismatch() {
        assertThatThrownBy(() -> DocumentFileValidator.validate("a.pdf", "application/pdf", Docs.text(), MAX)).isInstanceOf(UnsupportedFileTypeException.class);
        byte[] zipWithoutWord = {0x50, 0x4B, 0x03, 0x04, 1, 2, 3};
        assertThatThrownBy(() -> DocumentFileValidator.validate("a.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", zipWithoutWord, MAX))
                .isInstanceOf(UnsupportedFileTypeException.class);
    }

    @Test void rejectsBinaryMasqueradingAsText() {
        byte[] bin = {'h', 'i', 0, 1, 2};
        assertThatThrownBy(() -> DocumentFileValidator.validate("a.txt", "text/plain", bin, MAX)).isInstanceOf(UnsupportedFileTypeException.class);
        byte[] badUtf8 = {(byte) 0xC3, 0x28, 'a'};
        assertThatThrownBy(() -> DocumentFileValidator.validate("a.txt", "text/plain", badUtf8, MAX)).isInstanceOf(UnsupportedFileTypeException.class);
    }

    @Test void rejectsEmptyOversizedAndUnknownExtension() {
        assertThatThrownBy(() -> DocumentFileValidator.validate("a.txt", "text/plain", new byte[0], MAX)).isInstanceOf(ValidationFailedException.class);
        assertThatThrownBy(() -> DocumentFileValidator.validate("a.txt", "text/plain", "xx".getBytes(StandardCharsets.UTF_8), 1)).isInstanceOf(FileTooLargeException.class);
        assertThatThrownBy(() -> DocumentFileValidator.validate("a.exe", "text/plain", Docs.text(), MAX)).isInstanceOf(UnsupportedFileTypeException.class);
        assertThatThrownBy(() -> DocumentFileValidator.validate("noextension", "text/plain", Docs.text(), MAX)).isInstanceOf(UnsupportedFileTypeException.class);
    }

    @Test void sanitisesFilenames() {
        assertThat(DocumentFileValidator.sanitizeFilename("../../etc/passwd")).isEqualTo("passwd");
        assertThat(DocumentFileValidator.sanitizeFilename("C:\\temp\\bad<name>.pdf")).isEqualTo("bad_name_.pdf");
        assertThat(DocumentFileValidator.sanitizeFilename("..hidden.txt")).isEqualTo("hidden.txt");
        assertThat(DocumentFileValidator.sanitizeFilename("")).isEqualTo("document");
        assertThat(DocumentFileValidator.sanitizeFilename("a".repeat(500) + ".pdf").length()).isLessThanOrEqualTo(200);
    }
}
