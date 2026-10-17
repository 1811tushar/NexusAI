package com.nexusai.document;

import com.nexusai.common.exception.FileTooLargeException;
import com.nexusai.common.exception.UnsupportedFileTypeException;
import com.nexusai.common.exception.ValidationFailedException;
import java.nio.ByteBuffer;
import java.nio.CharBuffer;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CoderResult;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Map;

/** BE-DC-01 / SEC-04: extension AND content type AND magic bytes AND size; filenames are sanitised, never trusted. */
public final class DocumentFileValidator {
    public record Validated(SourceType type, String safeFilename, String title) { }

    private static final byte[] PDF_MAGIC = "%PDF-".getBytes(StandardCharsets.US_ASCII);
    private static final byte[] ZIP_MAGIC = {0x50, 0x4B, 0x03, 0x04};
    private static final byte[] DOCX_MARKER = "word/document.xml".getBytes(StandardCharsets.US_ASCII);

    private DocumentFileValidator() { }

    public static Validated validate(String originalFilename, String contentType, byte[] bytes, long maxBytes) {
        if (bytes == null || bytes.length == 0) throw new ValidationFailedException("The file is empty", Map.of("file", "must not be empty"));
        if (bytes.length > maxBytes) throw new FileTooLargeException("The file is larger than " + (maxBytes / (1024 * 1024)) + " MB");

        String safe = sanitizeFilename(originalFilename);
        int dot = safe.lastIndexOf('.');
        String ext = dot < 0 ? "" : safe.substring(dot + 1).toLowerCase(Locale.ROOT);
        SourceType type = SourceType.fromExtension(ext)
                .orElseThrow(() -> new UnsupportedFileTypeException("Only PDF, DOCX, TXT and MD files are supported"));

        String ct = contentType == null ? "" : contentType.split(";")[0].trim().toLowerCase(Locale.ROOT);
        if (!type.accepts(ct)) throw new UnsupportedFileTypeException("The content type does not match a ." + ext + " file");
        if (!magicMatches(type, bytes)) throw new UnsupportedFileTypeException("The file content does not match a ." + ext + " file");

        String title = dot > 0 ? safe.substring(0, dot) : safe;
        return new Validated(type, safe, title.length() > 255 ? title.substring(0, 255) : title);
    }

    static boolean magicMatches(SourceType type, byte[] b) {
        return switch (type) {
            case PDF -> startsWith(b, PDF_MAGIC);
            case DOCX -> startsWith(b, ZIP_MAGIC) && indexOf(b, DOCX_MARKER) >= 0;
            case TXT, MD -> looksLikeText(b);
        };
    }

    /** Last path segment only, control characters removed, odd characters replaced, capped at 200 chars. */
    public static String sanitizeFilename(String name) {
        String n = name == null ? "" : name;
        n = n.substring(Math.max(n.lastIndexOf('/'), n.lastIndexOf('\\')) + 1);
        n = n.replaceAll("\\p{Cntrl}", "").replaceAll("[^A-Za-z0-9._ \\-]", "_").trim();
        while (n.startsWith(".")) n = n.substring(1);
        if (n.isEmpty()) n = "document";
        return n.length() > 200 ? n.substring(n.length() - 200) : n;
    }

    private static boolean startsWith(byte[] b, byte[] prefix) {
        if (b.length < prefix.length) return false;
        for (int i = 0; i < prefix.length; i++) if (b[i] != prefix[i]) return false;
        return true;
    }

    private static int indexOf(byte[] hay, byte[] needle) {
        outer:
        for (int i = 0; i <= hay.length - needle.length; i++) {
            for (int j = 0; j < needle.length; j++) if (hay[i + j] != needle[j]) continue outer;
            return i;
        }
        return -1;
    }

    /** No NUL bytes and valid UTF-8 in the first 8 KB. */
    private static boolean looksLikeText(byte[] b) {
        int n = Math.min(b.length, 8192);
        for (int i = 0; i < n; i++) if (b[i] == 0) return false;
        CharsetDecoder dec = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT);
        CoderResult r = dec.decode(ByteBuffer.wrap(b, 0, n), CharBuffer.allocate(n + 1), n == b.length);
        return !r.isError();
    }
}
