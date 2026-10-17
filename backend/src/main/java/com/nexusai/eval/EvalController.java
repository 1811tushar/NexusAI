package com.nexusai.eval;

import com.nexusai.common.dto.ApiResponse;
import java.util.List;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/** ADMIN only: /api/eval/** is restricted in SecurityConfig. */
@RestController
@RequestMapping("/api/eval/runs")
public class EvalController {
    private final EvalService service;
    public EvalController(EvalService service) { this.service = service; }

    @GetMapping
    public ApiResponse<List<EvalRunDTO>> runs() { return ApiResponse.ok(service.runs()); }

    @GetMapping("/{id}")
    public ApiResponse<EvalRunDetailDTO> run(@PathVariable long id) { return ApiResponse.ok(service.run(id)); }
}
