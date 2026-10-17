package com.nexusai.user;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.security.CurrentUser;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/users/me")
public class UserController {
    private final UserService service;
    public UserController(UserService service) { this.service = service; }

    @PatchMapping
    public ApiResponse<UserDTO> update(@Valid @RequestBody UpdateProfileRequestDTO req) {
        return ApiResponse.ok(service.updateProfile(CurrentUser.id(), req.displayName()));
    }

    @PostMapping("/password")
    public ApiResponse<Void> changePassword(@Valid @RequestBody ChangePasswordRequestDTO req) {
        service.changePassword(CurrentUser.require(), req.currentPassword(), req.newPassword());
        return ApiResponse.ok(null);
    }
}
