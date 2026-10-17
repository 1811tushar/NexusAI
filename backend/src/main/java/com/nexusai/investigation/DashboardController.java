package com.nexusai.investigation;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.security.CurrentUser;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/dashboard")
public class DashboardController {
    private final DashboardService service;
    public DashboardController(DashboardService service) { this.service = service; }

    @GetMapping("/summary")
    public ApiResponse<DashboardSummaryDTO> summary() { return ApiResponse.ok(service.summary(CurrentUser.require())); }
}
