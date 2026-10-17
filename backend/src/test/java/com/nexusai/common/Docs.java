package com.nexusai.common;

import java.nio.charset.StandardCharsets;
import java.util.UUID;

/** Tiny valid-looking files for upload tests. Each call yields unique content (the knowledge base rejects duplicates). */
public final class Docs {
    private Docs() { }
    public static byte[] pdf() { return ("%PDF-1.4\n% " + UUID.randomUUID() + "\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF").getBytes(StandardCharsets.US_ASCII); }
    public static byte[] text() { return ("Quarterly notes " + UUID.randomUUID() + "\n").getBytes(StandardCharsets.UTF_8); }
    public static byte[] fakeDocx() {
        byte[] head = {0x50, 0x4B, 0x03, 0x04};
        byte[] body = ("[Content_Types].xml word/document.xml " + UUID.randomUUID()).getBytes(StandardCharsets.US_ASCII);
        byte[] out = new byte[head.length + body.length];
        System.arraycopy(head, 0, out, 0, head.length);
        System.arraycopy(body, 0, out, head.length, body.length);
        return out;
    }
}
