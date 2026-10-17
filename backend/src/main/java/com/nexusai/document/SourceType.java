package com.nexusai.document;

import java.util.Optional;
import java.util.Set;

public enum SourceType {
    PDF("pdf", "application/pdf", Set.of("application/pdf")),
    DOCX("docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            Set.of("application/vnd.openxmlformats-officedocument.wordprocessingml.document")),
    TXT("txt", "text/plain", Set.of("text/plain")),
    MD("md", "text/markdown", Set.of("text/markdown", "text/x-markdown", "text/plain", "application/octet-stream"));

    private final String extension;
    private final String canonicalMime;
    private final Set<String> acceptedContentTypes;

    SourceType(String extension, String canonicalMime, Set<String> accepted) {
        this.extension = extension;
        this.canonicalMime = canonicalMime;
        this.acceptedContentTypes = accepted;
    }
    public String extension() { return extension; }
    /** The mime type we store and serve; never the client-supplied one. */
    public String canonicalMime() { return canonicalMime; }
    public boolean accepts(String contentType) { return acceptedContentTypes.contains(contentType); }

    public static Optional<SourceType> fromExtension(String ext) {
        for (SourceType t : values()) if (t.extension.equals(ext)) return Optional.of(t);
        return Optional.empty();
    }
}
