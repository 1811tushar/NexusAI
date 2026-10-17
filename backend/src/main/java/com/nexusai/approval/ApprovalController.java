package com.nexusai.approval;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.security.CurrentUser;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/approvals")
public class ApprovalController {
    private final ApprovalService service;
    public ApprovalController(ApprovalService service) { this.service = service; }

    @GetMapping
    public ApiResponse<PagedResponseDTO<ApprovalDTO>> list(@RequestParam(required = false) ApprovalStatus status, @RequestParam(defaultValue = "0") int page,
                                                           @RequestParam(defaultValue = "20") int size, @RequestParam(required = false) String sort) {
        return ApiResponse.ok(service.list(status, page, size, sort, CurrentUser.require()));
    }

    @GetMapping("/pending-count")
    public ApiResponse<CountDTO> pendingCount() { return ApiResponse.ok(new CountDTO(service.pendingCount(CurrentUser.require()))); }

    @GetMapping("/{id}")
    public ApiResponse<ApprovalDTO> get(@PathVariable long id) { return ApiResponse.ok(service.get(id, CurrentUser.require())); }

    @PostMapping("/{id}/decision")
    public ApiResponse<ApprovalDTO> decide(@PathVariable long id, @Valid @RequestBody DecisionRequestDTO req) {
        return ApiResponse.ok(service.decide(id, req, CurrentUser.require()));
    }
}
