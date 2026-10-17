package com.nexusai.approval;

import com.nexusai.common.dto.ApiResponse;
import com.nexusai.common.dto.PagedResponseDTO;
import com.nexusai.common.security.AuthenticatedUser;
import com.nexusai.common.security.CurrentUser;
import com.nexusai.common.util.PageUtil;
import com.nexusai.user.Role;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Set;

/** Audit view of executed / rejected / expired / failed actions. Analysts see their own investigations' actions, others all. */
@RestController
@RequestMapping("/api/actions")
public class ActionController {
    private final ActionLogRepository logs;
    public ActionController(ActionLogRepository logs) { this.logs = logs; }

    @GetMapping
    public ApiResponse<PagedResponseDTO<ActionLogDTO>> list(@RequestParam(defaultValue = "0") int page, @RequestParam(defaultValue = "20") int size,
                                                            @RequestParam(required = false) String sort) {
        AuthenticatedUser actor = CurrentUser.require();
        Pageable pageable = PageUtil.of(page, size, sort, Set.of("executedAt", "status"), "executedAt", Sort.Direction.DESC);
        Page<ActionLog> result = actor.role() == Role.ANALYST ? logs.findForOwner(actor.id(), pageable) : logs.findAll(pageable);
        return ApiResponse.ok(PagedResponseDTO.from(result, ApprovalMapper::toDto));
    }
}
