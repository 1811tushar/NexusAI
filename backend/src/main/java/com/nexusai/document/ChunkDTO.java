package com.nexusai.document;

public record ChunkDTO(Long id, int chunkIndex, Integer page, String section, String content) { }
