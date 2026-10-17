# Hero scenario

**Question:** "Why did Q2 revenue decline compared to Q1, and what should management investigate?"

**Data:** the AI stream generates, deterministically, `ai-service/app/evals/seed/V7__seed_business_data.sql` (four regions, three categories, about twelve products, monthly sales/marketing/customer metrics Jan 2025 to Sep 2026) and a matching document corpus. The planted story lives in `seed/story.md`: a primary cause, a secondary cause, a seasonal red herring and a growing region. **The truth is defined there, not here.**

**Load for a local demo:** Flyway applies V6 and V7 when the backend starts (the integration step places V7 in `backend/src/main/resources/db/migration/`). Upload the corpus files from `ai-service/app/evals/corpus/` through the Documents page.

**Expected journey:** plan, document retrieval and read-only SQL, statistics (period comparison, contribution analysis), discrete claims, verification and citation validation, confidence check with a bounded loop, report with verified findings and an explicit unverified/limitations section, a proposed catalogue action, approval pause if the action is HIGH risk, approver decision, simulated execution recorded, final report reflects the decision.

**Acceptance for the demo:** every number in the report traces to an evidence card; at least one claim is shown as unsupported or contradicted if the data warrants it; no HIGH-risk action is recorded as executed before an APPROVE.
