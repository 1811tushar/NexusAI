package com.nexusai.common;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.nexusai.common.storage.LocalFileStorage;
import java.nio.file.Path;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;

class LocalFileStorageTest {
    @TempDir Path dir;

    @Test void storesReadsAndDeletesWithRandomKeys() {
        LocalFileStorage s = new LocalFileStorage(dir);
        String k1 = s.store("hello".getBytes());
        String k2 = s.store("hello".getBytes());
        assertThat(k1).isNotEqualTo(k2).matches("[0-9a-f]{2}/[0-9a-f]{32}");
        assertThat(s.read(k1)).isEqualTo("hello".getBytes());
        assertThat(s.exists(k1)).isTrue();
        s.delete(k1);
        s.delete(k1);                       // idempotent
        assertThat(s.exists(k1)).isFalse();
    }

    @Test void rejectsPathTraversalKeys() {
        LocalFileStorage s = new LocalFileStorage(dir);
        for (String bad : new String[] {"../etc/passwd", "ab/../../x", "/etc/passwd", "ab/" + "z".repeat(32), "..", ""}) {
            assertThatThrownBy(() -> s.read(bad)).isInstanceOf(IllegalArgumentException.class);
            assertThatThrownBy(() -> s.delete(bad)).isInstanceOf(IllegalArgumentException.class);
        }
    }
}
