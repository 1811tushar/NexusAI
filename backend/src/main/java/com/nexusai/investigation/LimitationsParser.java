package com.nexusai.investigation;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Extracts the "Limitations and failures" section of the report (contract v2.1: the report must carry it). Bullet and numbered
 * items become one entry each; a plain paragraph becomes a single entry. If report_ready carries a `limitations` array, that wins.
 */
public final class LimitationsParser {
    private static final Pattern HEADING = Pattern.compile("^\\s{0,3}#{1,6}\\s*(.+?)\\s*#*\\s*$");
    private static final Pattern BULLET = Pattern.compile("^\\s*(?:[-*+]|\\d+[.)])\\s+(.*)$");
    private LimitationsParser() { }

    public static List<String> parse(String markdown) {
        List<String> out = new ArrayList<>();
        if (markdown == null) return out;
        boolean inSection = false;
        StringBuilder paragraph = new StringBuilder();
        for (String line : markdown.split("\\R")) {
            Matcher h = HEADING.matcher(line);
            if (h.matches()) {
                if (inSection) break;
                String title = h.group(1).toLowerCase().replace("*", "").replace("_", "").trim();
                inSection = title.startsWith("limitations");
                continue;
            }
            if (!inSection) continue;
            Matcher b = BULLET.matcher(line);
            if (b.matches()) {
                flush(paragraph, out);
                if (!b.group(1).isBlank()) out.add(strip(b.group(1)));
            } else if (line.isBlank()) {
                flush(paragraph, out);
            } else {
                if (paragraph.length() > 0) paragraph.append(' ');
                paragraph.append(line.trim());
            }
        }
        flush(paragraph, out);
        return out;
    }

    private static void flush(StringBuilder p, List<String> out) {
        if (p.length() > 0) { out.add(strip(p.toString())); p.setLength(0); }
    }

    private static String strip(String s) { return s.trim().replace("**", ""); }
}
