package com.nexusai.investigation;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class LimitationsParserTest {
    @Test void bulletsAreSeparateEntries() {
        String md = "# Report\n\nText\n\n## Limitations and failures\n\n- Web search was unavailable\n- **SQL** timed out twice\n1. numbered item\n\n## Next\n\n- not me\n";
        assertThat(LimitationsParser.parse(md)).containsExactly("Web search was unavailable", "SQL timed out twice", "numbered item");
    }

    @Test void paragraphBecomesOneEntryAndSectionEndsAtNextHeading() {
        assertThat(LimitationsParser.parse("### Limitations\nNo web data\nwas available.\n\n# Appendix\ntext")).containsExactly("No web data was available.");
    }

    @Test void noSectionNullAndEmptyGiveEmpty() {
        assertThat(LimitationsParser.parse("# Report\n\nAll good.")).isEmpty();
        assertThat(LimitationsParser.parse(null)).isEmpty();
        assertThat(LimitationsParser.parse("")).isEmpty();
    }

    @Test void headingMatchIsCaseInsensitive() {
        assertThat(LimitationsParser.parse("## LIMITATIONS AND FAILURES\n- one")).containsExactly("one");
    }
}
