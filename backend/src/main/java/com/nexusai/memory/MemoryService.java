package com.nexusai.memory;

import com.nexusai.ai.AiServiceClient;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.exception.ResourceNotFoundException;
import org.springframework.stereotype.Service;

/** BE-ME-01: memories live in Python (ai.memories); Spring only proxies, always with the AUTHENTICATED user id, never one from the request. */
@Service
public class MemoryService {
    private final AiServiceClient ai;
    public MemoryService(AiServiceClient ai) { this.ai = ai; }

    public PagedResponseDTO<MemoryDTO> list(long userId, String q, int page, int size) {
        return ai.listMemories(userId, q, Math.max(page, 0), Math.min(Math.max(size, 1), 100));
    }

    public void delete(long userId, long memoryId) {
        if (ai.deleteMemory(userId, memoryId) == 0) throw new ResourceNotFoundException("Memory not found");
    }

    public void deleteAll(long userId) { ai.deleteAllMemories(userId); }

    /** For future user deletion: removes memories and checkpoints of the user in the AI service. */
    public void purgeUser(long userId) { ai.purgeUser(userId); }
}
