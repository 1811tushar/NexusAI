package com.nexusai.approval;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.mockito.junit.jupiter.MockitoSettings;
import org.mockito.quality.Strictness;

/** BE-AP-02 invariant: a HIGH-risk action is never executed without a stored APPROVE (human decider), whatever the input. */
@ExtendWith(MockitoExtension.class)
@MockitoSettings(strictness = Strictness.LENIENT)
class ActionExecutorTest {
    @Mock ActionLogRepository logs;
    @Mock ApprovalRepository approvals;
    private final ObjectMapper m = new ObjectMapper();
    private ActionExecutor executor;

    @BeforeEach void setUp() {
        executor = new ActionExecutor(logs, approvals, new ActionCatalogue());
        when(logs.save(any())).thenAnswer(i -> { ActionLog l = i.getArgument(0); l.setId(1L); return l; });
        when(logs.findFirstByApprovalIdOrderByIdAsc(any())).thenReturn(Optional.empty());
    }

    private JsonNode json(String s) throws Exception { return m.readTree(s); }

    private Approval approval(ApprovalStatus status, Long decidedBy, String type, String params) throws Exception {
        Approval a = new Approval();
        a.setId(7L);
        a.setInvestigationId(3L);
        a.setActionType(type);
        a.setStatus(status);
        a.setDecidedBy(decidedBy);
        a.setParams(json(params));
        when(approvals.findById(7L)).thenReturn(Optional.of(a));
        return a;
    }

    private static final String PRICE = "{\"productId\":3,\"changePct\":-10}";

    @Test void highRiskIsNeverExecutedAutomatically() throws Exception {
        for (String type : new String[] {"ADJUST_PRICE", "PAUSE_CAMPAIGN", "REALLOCATE_BUDGET"}) {
            assertThatThrownBy(() -> executor.executeAutomatic(3, type, json(PRICE))).isInstanceOf(IllegalStateException.class);
        }
        verify(logs, never()).save(any());
    }

    @Test void approvedActionsRequireAStoredApproveFromAHuman() throws Exception {
        for (ApprovalStatus s : new ApprovalStatus[] {ApprovalStatus.PENDING, ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED}) {
            approval(s, 5L, "ADJUST_PRICE", PRICE);
            assertThatThrownBy(() -> executor.executeApproved(7)).as(s.name()).isInstanceOf(IllegalStateException.class);
        }
        approval(ApprovalStatus.APPROVED, null, "ADJUST_PRICE", PRICE);                          // APPROVED but nobody decided it
        assertThatThrownBy(() -> executor.executeApproved(7)).isInstanceOf(IllegalStateException.class);
        when(approvals.findById(99L)).thenReturn(Optional.empty());
        assertThatThrownBy(() -> executor.executeApproved(99)).isInstanceOf(IllegalStateException.class);
        verify(logs, never()).save(any());
    }

    @Test void approvedHighRiskActionIsExecutedAsSimulation() throws Exception {
        approval(ApprovalStatus.APPROVED, 5L, "ADJUST_PRICE", PRICE);
        ActionLog l = executor.executeApproved(7);
        assertThat(l.getStatus()).isEqualTo(ActionStatus.EXECUTED);
        assertThat(l.isAutomatic()).isFalse();
        assertThat(l.getRisk()).isEqualTo(Risk.HIGH);
        assertThat(l.getApprovalId()).isEqualTo(7L);
        assertThat(l.getNote()).isEqualTo("Simulated execution; no external system was changed.");
    }

    @Test void approvedButInvalidOrUnknownIsFailedNotExecuted() throws Exception {
        approval(ApprovalStatus.APPROVED, 5L, "ADJUST_PRICE", "{\"productId\":3,\"changePct\":99}");
        assertThat(executor.executeApproved(7).getStatus()).isEqualTo(ActionStatus.FAILED);
        approval(ApprovalStatus.APPROVED, 5L, "UNKNOWN", "{}");
        assertThat(executor.executeApproved(7).getStatus()).isEqualTo(ActionStatus.FAILED);
    }

    @Test void executionIsIdempotent() throws Exception {
        approval(ApprovalStatus.APPROVED, 5L, "ADJUST_PRICE", PRICE);
        ActionLog existing = new ActionLog();
        existing.setId(42L);
        when(logs.findFirstByApprovalIdOrderByIdAsc(7L)).thenReturn(Optional.of(existing));
        assertThat(executor.executeApproved(7).getId()).isEqualTo(42L);
        verify(logs, never()).save(any());
    }

    @Test void lowRiskAutomaticExecutionAndFailures() throws Exception {
        assertThat(executor.executeAutomatic(3, "SAVE_INSIGHT", json("{\"title\":\"t\",\"text\":\"x\"}")).getStatus()).isEqualTo(ActionStatus.EXECUTED);
        assertThat(executor.executeAutomatic(3, "SAVE_INSIGHT", json("{\"title\":\"\"}")).getStatus()).isEqualTo(ActionStatus.FAILED);
        ActionLog unknown = executor.executeAutomatic(3, "FORMAT_DISK\u0007", json("{}"));
        assertThat(unknown.getStatus()).isEqualTo(ActionStatus.FAILED);
        assertThat(unknown.getActionType()).isEqualTo("UNKNOWN");
        assertThat(unknown.getRisk()).isEqualTo(Risk.HIGH);
        ArgumentCaptor<ActionLog> cap = ArgumentCaptor.forClass(ActionLog.class);
        verify(logs, org.mockito.Mockito.times(3)).save(cap.capture());
        assertThat(cap.getAllValues()).allSatisfy(l -> assertThat(l.getNote()).endsWith("Simulated execution; no external system was changed."));
    }

    @Test void rejectedAndExpiredAreLoggedNeverExecuted() throws Exception {
        Approval a = approval(ApprovalStatus.REJECTED, 5L, "ADJUST_PRICE", PRICE);
        assertThat(executor.logNotExecuted(a, ActionStatus.REJECTED, "Not executed: rejected.").getStatus()).isEqualTo(ActionStatus.REJECTED);
        assertThat(executor.logNotExecuted(a, ActionStatus.EXPIRED, "Not executed: expired.").getStatus()).isEqualTo(ActionStatus.EXPIRED);
        assertThatThrownBy(() -> executor.logNotExecuted(a, ActionStatus.EXECUTED, "x")).isInstanceOf(IllegalArgumentException.class);
    }
}
