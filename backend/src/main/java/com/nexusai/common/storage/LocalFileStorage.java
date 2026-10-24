package com.nexusai.common.storage;

import com.nexusai.common.config.NexusProperties;
import java.io.IOException;
import java.io.InputStream;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.NoSuchFileException;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/** Keys look like "ab/ab12...(32 hex)": random, never derived from user input, and re-validated on every access (no path traversal). */
@Component
public class LocalFileStorage implements FileStorage {
    private static final Pattern KEY = Pattern.compile("^[0-9a-f]{2}/[0-9a-f]{32}$");
    private final Path root;

    @Autowired // two constructors exist (this one for Spring, the Path one for tests): Spring needs to be told which to use
    public LocalFileStorage(NexusProperties props) {
        this(Path.of(props.upload().dir()));
    }

    public LocalFileStorage(Path root) {
        this.root = root.toAbsolutePath().normalize();
        try {
            Files.createDirectories(this.root);
        } catch (IOException e) {
            throw new UncheckedIOException("Cannot create upload directory", e);
        }
    }

    @Override
    public String store(byte[] content) {
        String id = UUID.randomUUID().toString().replace("-", "");
        String key = id.substring(0, 2) + "/" + id;
        Path target = resolve(key);
        try {
            Files.createDirectories(target.getParent());
            Path tmp = Files.createTempFile(target.getParent(), ".upload-", ".tmp");
            Files.write(tmp, content);
            Files.move(tmp, target, StandardCopyOption.ATOMIC_MOVE);
            return key;
        } catch (IOException e) {
            throw new UncheckedIOException("Could not store file", e);
        }
    }

    @Override
    public InputStream open(String key) {
        try {
            return Files.newInputStream(resolve(key));
        } catch (IOException e) {
            throw new UncheckedIOException("Could not open file", e);
        }
    }

    @Override
    public byte[] read(String key) {
        try {
            return Files.readAllBytes(resolve(key));
        } catch (IOException e) {
            throw new UncheckedIOException("Could not read file", e);
        }
    }

    @Override
    public boolean exists(String key) { return Files.isRegularFile(resolve(key)); }

    @Override
    public void delete(String key) {
        try {
            Files.deleteIfExists(resolve(key));
        } catch (NoSuchFileException ignored) {
            // already gone
        } catch (IOException e) {
            throw new UncheckedIOException("Could not delete file", e);
        }
    }

    private Path resolve(String key) {
        if (key == null || !KEY.matcher(key).matches()) throw new IllegalArgumentException("Invalid storage key");
        Path p = root.resolve(key).normalize();
        if (!p.startsWith(root)) throw new IllegalArgumentException("Invalid storage key");
        return p;
    }
}
