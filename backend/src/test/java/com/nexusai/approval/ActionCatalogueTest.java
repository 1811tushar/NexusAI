package com.nexusai.approval;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import org.junit.jupiter.api.Test;

/** Contract section 8: risk is fixed per type, params are validated. */
class ActionCatalogueTest {
    private final ActionCatalogue c = new ActionCatalogue();
    private final ObjectMapper m = new ObjectMapper();

    private List<String> check(ActionType t, String json) throws Exception { JsonNode n = m.readTree(json); return c.validate(t, n); }

    @Test void riskIsFixedByType() {
        for (ActionType t : new ActionType[] {ActionType.FLAG_FOR_REVIEW, ActionType.CREATE_FOLLOWUP_TASK, ActionType.SAVE_INSIGHT}) assertThat(c.riskOf(t)).isEqualTo(Risk.LOW);
        for (ActionType t : new ActionType[] {ActionType.ADJUST_PRICE, ActionType.PAUSE_CAMPAIGN, ActionType.REALLOCATE_BUDGET}) assertThat(c.riskOf(t)).isEqualTo(Risk.HIGH);
        assertThat(ActionType.values()).hasSize(6);
    }

    @Test void parseRejectsUnknownAndForgedNames() {
        assertThat(c.parse("ADJUST_PRICE")).contains(ActionType.ADJUST_PRICE);
        assertThat(c.parse(" SAVE_INSIGHT ")).contains(ActionType.SAVE_INSIGHT);
        for (String bad : new String[] {null, "", "adjust_price", "DROP_TABLE", "ADJUST_PRICE; --"}) assertThat(c.parse(bad)).isEmpty();
    }

    @Test void validParams() throws Exception {
        assertThat(check(ActionType.FLAG_FOR_REVIEW, "{\"subject\":\"EMEA\",\"reason\":\"drop\"}")).isEmpty();
        assertThat(check(ActionType.CREATE_FOLLOWUP_TASK, "{\"title\":\"t\",\"ownerRole\":\"ANALYST\",\"dueInDays\":7}")).isEmpty();
        assertThat(check(ActionType.SAVE_INSIGHT, "{\"title\":\"t\",\"text\":\"x\"}")).isEmpty();
        assertThat(check(ActionType.ADJUST_PRICE, "{\"productId\":3,\"changePct\":-30}")).isEmpty();
        assertThat(check(ActionType.PAUSE_CAMPAIGN, "{\"regionId\":2,\"channel\":\"email\",\"weeks\":4,\"extra\":1}")).isEmpty();     // extras ignored
        assertThat(check(ActionType.REALLOCATE_BUDGET, "{\"fromRegionId\":1,\"toRegionId\":2,\"amount\":5000.5}")).isEmpty();
    }

    @Test void invalidParams() throws Exception {
        assertThat(check(ActionType.ADJUST_PRICE, "{\"productId\":3,\"changePct\":30.5}")).isNotEmpty();         // |changePct| <= 30
        assertThat(check(ActionType.ADJUST_PRICE, "{\"productId\":3,\"changePct\":\"10\"}")).isNotEmpty();         // wrong type
        assertThat(check(ActionType.ADJUST_PRICE, "{\"changePct\":10}")).isNotEmpty();                             // missing
        assertThat(check(ActionType.ADJUST_PRICE, "{\"productId\":0,\"changePct\":10}")).isNotEmpty();
        assertThat(check(ActionType.PAUSE_CAMPAIGN, "{\"regionId\":2,\"channel\":\"email\",\"weeks\":99}")).isNotEmpty();
        assertThat(check(ActionType.REALLOCATE_BUDGET, "{\"fromRegionId\":2,\"toRegionId\":2,\"amount\":10}")).isNotEmpty();
        assertThat(check(ActionType.REALLOCATE_BUDGET, "{\"fromRegionId\":1,\"toRegionId\":2,\"amount\":-1}")).isNotEmpty();
        assertThat(check(ActionType.CREATE_FOLLOWUP_TASK, "{\"title\":\"t\",\"ownerRole\":\"ROOT\",\"dueInDays\":7}")).isNotEmpty();
        assertThat(check(ActionType.SAVE_INSIGHT, "{\"title\":\"\",\"text\":\"x\"}")).isNotEmpty();
        assertThat(c.validate(ActionType.SAVE_INSIGHT, null)).isNotEmpty();
        assertThat(c.validate(ActionType.SAVE_INSIGHT, m.readTree("[]"))).isNotEmpty();
    }
}
