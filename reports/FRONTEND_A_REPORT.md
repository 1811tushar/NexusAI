> Superseded for integration status by REPORT.md. Kept as the Frontend A record.

# Frontend A: report

**Verification status (read first).** The sandbox has no network, so `npm install`, lint, tests, build and Playwright were NOT run.
Only a syntax-level `tsc` parse was possible: it reported zero syntax errors (TS1xxx). Type errors against real library types, failing tests and runtime bugs are still possible.
Run the README commands first and send me the output of whatever fails. Colour contrast (WCAG AA) is designed for but NOT measured. Lighthouse and bundle size NOT measured.

## Built, by checklist ID
| ID | What exists |
|---|---|
| FE-DS-01..05 | tokens.css; light/dark/system theme, no-flash, persisted; risk and verification colours; Public Sans Variable via @fontsource; lucide icons, no emoji |
| FE-DS-06 | Button, IconButton, Input, Textarea, Select (native), Checkbox (native), Switch, Tabs, Dialog, Sheet (Dialog side=right), DropdownMenu, Tooltip, Toast, Badge, Skeleton, Progress, Avatar, Card, Table. Visible focus ring in base CSS |
| FE-DS-07 | ConfidenceGauge, RiskBadge, StatusBadge (REFUSED distinct), ClaimStatusChip, GuardrailChip, EvidenceCard (table + lazy chart), DataTable, CitationChip, MarkdownView. **AgentTimeline and PlanChecklist are Frontend B's** |
| FE-DS-08 / 09 | /dev/ui gallery (dev only); reduced-motion honoured in base CSS |
| FE-SH-01..05 | Shell with role-filtered rail and mobile bottom bar, pending badge; full route table; ProtectedRoute (redirect-back, 403); in-memory token, silent restore, shared refresh; command palette (Ctrl/Cmd+K) |
| FE-SH-06 / 07 | ErrorBoundary with copy details; backend-unreachable banner; 60 s pending poll + approver toast |
| FE-DB-01 | Dashboard: status counts, pending approvals (approver/admin), documents ready, 30-day confidence, recent investigations, quick question box |
| FE-DO-01..05 | Table with sort/filter/search/paging, role-based controls; drag-and-drop multi-upload with client checks and per-file progress; polling only while in progress; FAILED reason + Reindex; delete confirm; viewer with `?chunk=ID` highlight; hybrid library search with highlighted snippets |
| FE-DO-06 | NOT built (PDF page rendering, P1) |
| FE-ME-01 / FE-ST-01 / FE-AD-01 | Memory (search, delete, forget-all typed confirm); Settings (profile, password, theme, role explanation, privacy note, shortcuts); Users admin (list, create, role, enable/disable, server guard messages) |
| Auth | Login, Register (shows "self sign-up off" when the server refuses) |
| FE-ZS-01 / 02, FE-A11-01 / 02, FE-RS-01 | skeleton/empty/error/populated on each page; pending states block duplicate submits; server `details` map to fields; labelled controls, aria-labels, skip link, responsive layout. Not audited with a screen reader |
| FE-A11-03 | `announce()` live region provided; the run-screen milestones themselves are Frontend B's |
| FE-PF-01 | route-level lazy loading, lazy charts. Size not measured |
| FE-Q-01..04 | strict TS, no-`any` lint rule, one HTTP client, MSW mocks for auth, documents, search, memory, admin, dashboard, profile; stubs with TODOs for investigations, approvals, eval. Lint/typecheck/build NOT run |
| FE-Q-05 | Written: httpClient refresh + error mapping, ConfidenceGauge, UploadZone, IngestionStatus + polling rule, role gating, login form. `useInvestigationStream`, approval dialog tests are Frontend B's |
| FE-Q-06 | Playwright (mocks): auth/roles, document upload to READY, failed ingestion + reindex, approver read-only, axe on login and documents. Investigate/approve flow is Frontend B's |
| FE-Q-07 | Markdown sanitised, links `noopener noreferrer`, no tokens in storage |

## Known gaps and risks
- Mock `register` and admin guards are simulated; real server behaviour may differ (the contract has no "registration open" flag, so Register reacts to a 403/404).
- `useSSE`: Last-Event-ID resume relies on @microsoft/fetch-event-source's reconnect behaviour; untested.
- The 20 MB / type checks are duplicated from the contract; keep in sync.
- Upload progress uses XHR (fetch cannot report it).
