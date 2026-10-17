package com.nexusai.memory;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.security.CurrentUser;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/memories")
public class MemoryController {
    private final MemoryService service;
    public MemoryController(MemoryService service) { this.service = service; }

    @GetMapping
    public ApiResponse<PagedResponseDTO<MemoryDTO>> list(@RequestParam(required = false) String q, @RequestParam(defaultValue = "0") int page,
                                                         @RequestParam(defaultValue = "20") int size) {
        return ApiResponse.ok(service.list(CurrentUser.id(), q, page, size));
    }

    @DeleteMapping("/{id}")
    public ResponseEntity<Void> delete(@PathVariable long id) {
        service.delete(CurrentUser.id(), id);
        return ResponseEntity.noContent().build();
    }

    @DeleteMapping
    public ResponseEntity<Void> deleteAll() {
        service.deleteAll(CurrentUser.id());
        return ResponseEntity.noContent().build();
    }
}
