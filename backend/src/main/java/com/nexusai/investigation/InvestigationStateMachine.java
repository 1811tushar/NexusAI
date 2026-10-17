package com.nexusai.investigation;

import static com.nexusai.investigation.InvestigationStatus.*;

import com.nexusai.common.exception.InvalidStateException;
import java.util.EnumMap;
import java.util.Map;
import java.util.Set;

/** Contract section 7. Terminal states have no outgoing transitions; REFUSED is reachable only from RUNNING (via done.status=REFUSED). */
public final class InvestigationStateMachine {
    private static final Map<InvestigationStatus, Set<InvestigationStatus>> ALLOWED = new EnumMap<>(InvestigationStatus.class);
    static {
        ALLOWED.put(RUNNING, Set.of(AWAITING_APPROVAL, COMPLETED, FAILED, CANCELLED, REFUSED));
        ALLOWED.put(AWAITING_APPROVAL, Set.of(RUNNING, FAILED, CANCELLED));
        ALLOWED.put(COMPLETED, Set.of());
        ALLOWED.put(FAILED, Set.of());
        ALLOWED.put(CANCELLED, Set.of());
        ALLOWED.put(REFUSED, Set.of());
    }
    private InvestigationStateMachine() { }

    public static boolean canTransition(InvestigationStatus from, InvestigationStatus to) { return ALLOWED.get(from).contains(to); }

    public static void require(InvestigationStatus from, InvestigationStatus to) {
        if (!canTransition(from, to)) throw new InvalidStateException("Invalid investigation transition " + from + " -> " + to);
    }

    public static boolean canCancel(InvestigationStatus s) { return canTransition(s, CANCELLED); }
}
