package com.nexusai.common.storage;

import java.io.InputStream;

/** Abstraction over where uploaded bytes live (local disk now, object storage later). Keys are opaque and random. */
public interface FileStorage {
    /** Stores the bytes under a new random key and returns the key. */
    String store(byte[] content);
    InputStream open(String key);
    byte[] read(String key);
    boolean exists(String key);
    /** Idempotent: deleting a missing key is not an error. */
    void delete(String key);
}
