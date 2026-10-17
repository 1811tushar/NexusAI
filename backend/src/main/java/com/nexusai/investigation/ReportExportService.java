package com.nexusai.investigation;

import com.nexusai.approval.ApprovalDTO;
import com.nexusai.approval.ActionLogDTO;
import com.nexusai.common.exception.InvalidStateException;
import com.nexusai.common.security.AuthenticatedUser;
import java.util.List;
import org.springframework.stereotype.Service;

/** report.md: the report plus claims with verification status, evidence index and the approval/action outcomes (contract 4.3). */
@Service
public class ReportExportService {
    private final InvestigationService investigations;
    private final InvestigationMapper mapper;

    public ReportExportService(InvestigationService investigations, InvestigationMapper mapper) {
        this.investigations = investigations;
        this.mapper = mapper;
    }

    public String render(long id, AuthenticatedUser actor) {
        Investigation inv = investigations.requireVisible(id, actor);
        if (inv.getReportMarkdown() == null) throw new InvalidStateException("The report is not ready yet");
        InvestigationDetailDTO d = mapper.toDetail(inv);
        StringBuilder sb = new StringBuilder();
        sb.append("# Investigation ").append(d.id()).append("\n\n");
        sb.append("**Question:** ").append(oneLine(d.question())).append("\n\n");
        sb.append("- Status: ").append(d.status()).append('\n');
        if (d.confidence() != null) sb.append("- Overall confidence: ").append(String.format(java.util.Locale.ROOT, "%.0f%%", d.confidence() * 100)).append('\n');
        sb.append("- Loops used: ").append(d.loopsUsed()).append('\n');
        sb.append("- Owner: ").append(d.owner().displayName()).append("\n\n---\n\n");
        sb.append(d.reportMarkdown().strip()).append("\n\n---\n\n");

        sb.append("## Claims and verification\n\n");
        if (d.claims().isEmpty()) sb.append("_No claims were recorded._\n\n");
        for (ClaimDTO c : d.claims()) {
            sb.append("- **").append(c.status()).append("** (").append(String.format(java.util.Locale.ROOT, "%.0f%%", c.confidence() * 100)).append(')')
              .append(c.isKey() ? " [key claim]" : "").append(": ").append(oneLine(c.text()));
            if (!c.evidenceKeys().isEmpty()) sb.append(" — evidence: ").append(String.join(", ", c.evidenceKeys()));
            sb.append('\n');
        }
        sb.append("\n## Evidence\n\n");
        if (d.evidence().isEmpty()) sb.append("_No evidence was recorded._\n\n");
        for (EvidenceDTO e : d.evidence()) {
            sb.append("- `").append(e.evidenceKey()).append("` [").append(e.kind()).append("] ").append(oneLine(e.title())).append('\n');
        }
        sb.append("\n## Approvals and actions\n\n");
        List<ApprovalDTO> aps = d.approvals();
        if (aps.isEmpty() && d.actions().isEmpty()) sb.append("_No actions were proposed._\n\n");
        for (ApprovalDTO a : aps) {
            sb.append("- Approval for **").append(oneLine(a.title())).append("** (").append(a.actionType()).append(", ").append(a.risk()).append("): ").append(a.status());
            if (a.decidedBy() != null) sb.append(" by ").append(a.decidedBy().displayName());
            if (a.comment() != null && !a.comment().isBlank()) sb.append(" — ").append(oneLine(a.comment()));
            sb.append('\n');
        }
        for (ActionLogDTO l : d.actions()) {
            sb.append("- Action ").append(l.actionType()).append(": ").append(l.status()).append(l.automatic() ? " (automatic)" : "").append(" — ").append(oneLine(l.note())).append('\n');
        }
        sb.append("\n_Actions are simulated; no external system was changed._\n");
        return sb.toString();
    }

    private static String oneLine(String s) { return s == null ? "" : s.replaceAll("\\s+", " ").trim(); }
}
