package com.nexusai.eval;

import com.nexusai.ai.AiServiceClient;
import java.util.List;
import org.springframework.stereotype.Service;

/** BE-EV-01: ADMIN-only read access to stored evaluation runs (runs are started from the CLI, never from the UI). */
@Service
public class EvalService {
    private final AiServiceClient ai;
    public EvalService(AiServiceClient ai) { this.ai = ai; }
    public List<EvalRunDTO> runs() { return ai.evalRuns(); }
    public EvalRunDetailDTO run(long id) { return ai.evalRun(id); }
}
