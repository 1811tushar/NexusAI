package com.nexusai.auth;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.security.CurrentUser;
import com.nexusai.user.UserDTO;
import com.nexusai.user.UserService;
import jakarta.validation.Valid;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/auth")
public class AuthController {
    private final AuthService auth;
    private final UserService users;
    private final RefreshCookieFactory cookies;

    public AuthController(AuthService auth, UserService users, RefreshCookieFactory cookies) {
        this.auth = auth;
        this.users = users;
        this.cookies = cookies;
    }

    @PostMapping("/register")
    public ResponseEntity<ApiResponse<AuthResponseDTO>> register(@Valid @RequestBody RegisterRequestDTO req,
                                                                 @RequestHeader(value = "User-Agent", required = false) String ua) {
        return withCookie(auth.register(req, ua));
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<AuthResponseDTO>> login(@Valid @RequestBody LoginRequestDTO req,
                                                              @RequestHeader(value = "User-Agent", required = false) String ua) {
        return withCookie(auth.login(req, ua));
    }

    @PostMapping("/refresh")
    public ResponseEntity<ApiResponse<AuthResponseDTO>> refresh(@CookieValue(name = RefreshCookieFactory.NAME, required = false) String refresh,
                                                                @RequestHeader(value = "User-Agent", required = false) String ua) {
        return withCookie(auth.refresh(refresh, ua));
    }

    @PostMapping("/logout")
    public ResponseEntity<ApiResponse<Void>> logout(@CookieValue(name = RefreshCookieFactory.NAME, required = false) String refresh) {
        auth.logout(refresh);
        return ResponseEntity.ok().header(HttpHeaders.SET_COOKIE, cookies.clear().toString()).body(ApiResponse.ok(null));
    }

    @GetMapping("/me")
    public ApiResponse<UserDTO> me() { return ApiResponse.ok(users.me(CurrentUser.id())); }

    private ResponseEntity<ApiResponse<AuthResponseDTO>> withCookie(AuthResult r) {
        return ResponseEntity.ok().header(HttpHeaders.SET_COOKIE, cookies.issue(r.refreshToken()).toString()).body(ApiResponse.ok(r.body()));
    }
}
