package com.nexusai.user;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.security.CurrentUser;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

/** ADMIN only (enforced in SecurityConfig). */
@RestController
@RequestMapping("/api/admin/users")
public class AdminUserController {
    private final UserService service;
    public AdminUserController(UserService service) { this.service = service; }

    @GetMapping
    public ApiResponse<PagedResponseDTO<UserDTO>> list(@RequestParam(required = false) String q, @RequestParam(required = false) Role role,
                                                       @RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size,
                                                       @RequestParam(required = false) String sort) {
        return ApiResponse.ok(service.list(q, role, page, size, sort));
    }

    @PostMapping
    public ApiResponse<UserDTO> create(@Valid @RequestBody CreateUserRequestDTO req) {
        return ApiResponse.ok(service.create(req, CurrentUser.id()));
    }

    @PatchMapping("/{id}")
    public ApiResponse<UserDTO> patch(@PathVariable long id, @RequestBody PatchUserRequestDTO req) {
        return ApiResponse.ok(service.patch(id, req, CurrentUser.id()));
    }
}
