package com.nexusai.investigation;

import static com.nexusai.investigation.InvestigationStatus.*;
import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.nexusai.common.exception.InvalidStateException;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

/** BE-PL-10: JUnit coverage of the contract section 7 state machine (incl. REFUSED). */
class InvestigationStateMachineTest {
    @Test void legalTransitions() {
        assertThat(InvestigationStateMachine.canTransition(RUNNING, AWAITING_APPROVAL)).isTrue();
        assertThat(InvestigationStateMachine.canTransition(AWAITING_APPROVAL, RUNNING)).isTrue();
        for (InvestigationStatus t : new InvestigationStatus[] {COMPLETED, FAILED, CANCELLED, REFUSED}) {
            assertThat(InvestigationStateMachine.canTransition(RUNNING, t)).as("RUNNING -> " + t).isTrue();
        }
        assertThat(InvestigationStateMachine.canTransition(AWAITING_APPROVAL, FAILED)).isTrue();
        assertThat(InvestigationStateMachine.canTransition(AWAITING_APPROVAL, CANCELLED)).isTrue();
    }

    @Test void awaitingApprovalCannotCompleteOrBeRefusedDirectly() {
        assertThat(InvestigationStateMachine.canTransition(AWAITING_APPROVAL, COMPLETED)).isFalse();
        assertThat(InvestigationStateMachine.canTransition(AWAITING_APPROVAL, REFUSED)).isFalse();
    }

    @ParameterizedTest
    @EnumSource(value = InvestigationStatus.class, names = {"COMPLETED", "FAILED", "CANCELLED", "REFUSED"})
    void terminalStatesHaveNoExit(InvestigationStatus terminal) {
        assertThat(terminal.isTerminal()).isTrue();
        for (InvestigationStatus to : InvestigationStatus.values()) {
            assertThat(InvestigationStateMachine.canTransition(terminal, to)).as(terminal + " -> " + to).isFalse();
            assertThatThrownBy(() -> InvestigationStateMachine.require(terminal, to)).isInstanceOf(InvalidStateException.class);
        }
        assertThat(InvestigationStateMachine.canCancel(terminal)).isFalse();
    }

    @Test void onlyRunningAndWaitingRunsAreCancellable() {
        assertThat(InvestigationStateMachine.canCancel(RUNNING)).isTrue();
        assertThat(InvestigationStateMachine.canCancel(AWAITING_APPROVAL)).isTrue();
        assertThat(RUNNING.isTerminal()).isFalse();
        assertThat(AWAITING_APPROVAL.isTerminal()).isFalse();
    }
}
