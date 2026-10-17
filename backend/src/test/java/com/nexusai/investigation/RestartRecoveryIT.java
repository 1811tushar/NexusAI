package com.nexusai.investigation;

import static org.assertj.core.api.Assertions.assertThat;

import com.nexusai.user.Role;
import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;

/** BE-IV-06: orphaned RUNNING runs become FAILED at startup, AWAITING_APPROVAL runs are left alone. */
class RestartRecoveryIT extends RunTestSupport {
    @Autowired InvestigationSweeper sweeper;

    private long insert(long userId, String status, String createdAgo) {
        return jdbc.queryForObject("insert into investigations(user_id, question, status, thread_id, created_at) values (?, 'Why did revenue fall?', ?, gen_random_uuid(), now() - ?::interval) returning id",
                Long.class, userId, status, createdAgo);
    }

    @Test
    void orphanedRunningRunsAreFailedAndWaitingRunsAreKept() {
        long uid = createUser(Role.ANALYST).getId();
        long running = insert(uid, "RUNNING", "1 hour");
        long waiting = insert(uid, "AWAITING_APPROVAL", "1 hour");
        long done = insert(uid, "COMPLETED", "1 hour");

        assertThat(sweeper.recoverOrphans(Duration.ZERO)).isEqualTo(1);        // what runs on application start

        assertThat(status(running)).isEqualTo("FAILED");
        assertThat(jdbc.queryForObject("select error_message from investigations where id = ?", String.class, running)).contains("interrupted by a restart");
        assertThat(stepTypes(running)).containsExactly("error");                // viewers of the run get a terminal event
        assertThat(status(waiting)).isEqualTo("AWAITING_APPROVAL");
        assertThat(status(done)).isEqualTo("COMPLETED");
    }

    @Test
    void theGracePeriodProtectsRunsThatWereJustStartedOrResumed() {
        long uid = createUser(Role.ANALYST).getId();
        long fresh = insert(uid, "RUNNING", "10 seconds");
        long stale = insert(uid, "RUNNING", "1 hour");
        assertThat(sweeper.recoverOrphans(Duration.ofMinutes(5))).isEqualTo(1);
        assertThat(status(fresh)).isEqualTo("RUNNING");
        assertThat(status(stale)).isEqualTo("FAILED");
    }

    @Test
    void aRunThatIsReallyBeingRelayedIsNeverSweptAndRestartedRunsCanBeStartedAgain() {
        stubInvestigateSlow(happyBody(), 4000);
        stubCancel();
        Session s = sessionFor(Role.ANALYST);
        long id = startRun(s);
        assertThat(sweeper.recoverOrphans(Duration.ZERO)).isZero();            // a live relay is registered for it
        awaitStatus(id, "COMPLETED");
    }
}
