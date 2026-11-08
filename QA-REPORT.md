# PM AI ES · Implementation audit, 8 November 2026

**Chat upgrade verification is recorded in CHAT-UPGRADE.md.** This table records the earlier foundation audit.

**Release decision: laptop acceptance build.** Business use and live deployment remain unverified. The original 25-section scope is included in REQUIREMENTS.md. This report separates executable component evidence, fixture coverage, source inspection and outstanding end-to-end checks.

## Executed in this environment

| Check | Result |
|---|---|
| Python unit and mock-adapter suite | 42 passed. Ran python -m unittest discover -s tests -v. |
| Production React and offline adapter type check | Passed TypeScript --noEmit. |
| Production frontend bundling | Built dist/index.html, app.js and app.css using esbuild. |
| Real HTTP client with loopback fixture | Passed tests/client.mjs for request paths, JSON submission and error propagation. The responding server was a fixture. |
| Offline demonstration | Passed tests/demo.mjs for login, project creation/isolation, notes, reports, disconnected integrations and logout. |
| Syntax and packaging prerequisites | Python compileall, Bash syntax and Compose YAML service structure passed. |
| FastAPI, PostgreSQL, Docker | Could not execute. Docker command absent, FastAPI import unavailable and dependency installation returned no downloadable matching package in this environment. |
| Company service authentication and browser end-to-end | No authorised service credentials, database server or browser executable available. No company records were modified. |

## Verification table

“Fully Implemented and Tested” applies only to the specific feature in that row. “Implemented but Not Tested” means the integrated acceptance path was not executed, even where related unit checks passed. For database-backed screens, UI/field/handler/endpoint/persistence wiring was reviewed in source. Database mutations, refresh/restart, live permissions, rendered interactions and real provider success remain unverified unless separately evidenced below.

| ID | Module | Feature | Implementation Status | Test Result | Evidence | Remaining Issue |
|---|---|---|---|---|---|---|
| 01 | Foundation | Single PM agent, shared auth and registry | Implemented but Not Tested | React build | app.py, agent_api.py, Agent.tsx | Exercise registry after login |
| 02 | Foundation | Future department agents and cross-agent flows | Missing | Scope review | REQUIREMENTS.md §2/22 | Subsequent phase |
| 03 | Authentication | Password hash and authenticator algorithm | Fully Implemented and Tested | Pass | test_password, test_totp_published_vector | Primitive verification only |
| 04 | Authentication | Login, secure session, logout, replay/rate limits, reset | Implemented but Not Tested | Source reviewed | app.py, admin.py, smoke.py | API, MFA replay and recovery on laptop |
| 05 | Permissions | Role/tool decision rules and paused mode | Fully Implemented and Tested | Pass | test_roles, test_all_modes_enforce_pause, test_tools_off | Project membership enforced separately |
| 06 | Permissions | Membership, data isolation, archived access, grant and revoke | Implemented but Not Tested | Test written | app.py member, agent_api.py assign, smoke.py | Real multi-user PostgreSQL execution |
| 07 | Dashboard | Project totals, approvals, overdue counts and upcoming dates | Partially Implemented | Compiled | main.tsx, app.py projects | Dedicated attention summary and unified automation-health view incomplete |
| 08 | Projects | Create, edit, open, profile, dates, department context | Implemented but Not Tested | HTTP payload fixture passed | main.tsx, app.py Project, smoke.py | Durable CRUD and refresh |
| 09 | Projects | Delete by name confirmation | Partially Implemented | Source reviewed | app.py archive_project | Archival only; no permanent purge |
| 10 | Documents | Upload by project, original filename, ID, metadata, rename and download | Implemented but Not Tested | Smoke scenario written | app.py upload, add_source, Metadata | Upload/download byte comparison and restart |
| 11 | Documents | Size limits before parsing streaming requests | Fully Implemented and Tested | Pass | test_chunk_limit, test_replay | Deployment-level resource load test outstanding |
| 12 | Documents | PDF extraction, structured text chunking, unsupported originals | Partially Implemented | Chunk overlap passed | domain.py, app.py upload, test_overlap | OCR, malicious files and PDF resource exhaustion verification |
| 13 | Storage | Secure project-specific storage, retention and backup | Partially Implemented | Source reviewed | schema.sql sources, SETUP-GUIDE.md | PostgreSQL byte storage; object storage and tested recovery outstanding |
| 14 | Knowledge | Scoped lexical RAG ranking and superseded exclusion | Fully Implemented and Tested | Pass for ranking | test_authority, test_overlap | Database isolation and citation accuracy separate |
| 15 | Knowledge | Source approval, evidence IDs, authority and chronology | Partially Implemented | Ranking rule passed | app.py evidence, source approval, smoke.py | Requirement-level change ledger and conflict adjudication |
| 16 | Chat | Response OFF saves notes, Response ON uses actual configured provider | Implemented but Not Tested | Fixture HTTP submissions passed | app.py message/ask, tests/client.mjs | Real answer and database readback |
| 17 | Chat | Conversation history, citation navigation, import and deduplication | Partially Implemented | Import rules passed | imports.py, test_import_provenance, chat_imports | Structured JSON only; verify restore and historical conflict handling |
| 18 | Project expertise | Project guidance and technical profile included in model requests | Implemented but Not Tested | Source reviewed | app.py Project, ask, web/main.tsx | Qualitative relevance validation |
| 19 | AI settings | Provider, primary/fallback IDs, guidance, temperature, token/context limits | Implemented but Not Tested | Validation and mocked adapters passed | test_agent.py, Connections.tsx, agent_store.py | Persist settings and check selected model in live run |
| 20 | AI settings | Test/save, status fingerprint, capability listing, error/rotation/revocation | Implemented but Not Tested | Selected mock tests passed | test_connections.py, connections_api.py | Real encrypted write/read/restart/rotate |
| 21 | AI settings | Genuine GPT, Claude and Gemini generation | Blocked by External Credentials or Permissions | No live calls | models.py, tests/live_acceptance.py | Authorised billable account and model access for each |
| 22 | AI governance | Cost estimates, limits, fallback and monitoring | Partially Implemented | Budget and fallback rule tests passed | test_budget, test_fallback_same_service_probed, app.py ask | Validate concurrent reservation, incomplete usage and probe costs |
| 23 | Planning | Approved scope analysis, milestones, deliverables and acceptance criteria | Partially Implemented | Prompt and source gate inspected | app.py plan; main.tsx Project plan | Model quality and oversize scope handling need verification |
| 24 | Backlog | Hierarchy, parent types, prerequisites, cycle and roster validation | Fully Implemented and Tested | Pass for graph rules | backlog.py; test_order, test_reject_bad_graphs | Real Jira metadata and writes separate |
| 25 | Backlog | Approved plan to Epic/Story/Task/Subtask drafts with effort and due date | Implemented but Not Tested | Graph tests passed; handlers inspected | agent_api.py backlog and decide | Persist, review and publish mapped parents in Jira |
| 26 | Estimation | Working days, dependencies, capacity, target and infeasible graphs | Fully Implemented and Tested | Pass for calculator | test_dependency_weekend_and_target, test_invalid_graphs, test_parallel_capacity | Human sign-off on effort |
| 27 | Estimation | Automatic calendar scheduling from plan, availability and deadlines | Partially Implemented | Calculator exercised separately | domain.py working_schedule, main.tsx Schedule | No holiday, shared multi-project capacity or automatic calendar-to-backlog transfer |
| 28 | Team | Name, role, skills, capacity, confirmed Jira/Slack mappings | Implemented but Not Tested | Source reviewed | activity.py Staff, agent_api.py check_roster | Test assigned/unassigned IDs with actual members |
| 29 | Jira setup | Existing workspace, auth, options, board association, status and permission mapping | Blocked by External Credentials or Permissions | Paginated discovery fixture passed | discovery.py, test_jira_options_page | Existing Eleven Steeds workspace permission check |
| 30 | Jira publish | Project and board creation, hierarchy, assignee, date, link and receipt | Blocked by External Credentials or Permissions | Issue payload and subtask fixture passed | connectors.py, test_jira_issue_fields, test_subtask_requires_parent | Authorised disposable project, board and remote IDs |
| 31 | Jira configuration | Arbitrary workflow and mandatory custom-field mapping | Partially Implemented | Source reviewed | discovery.py jira_preflight, connectors.py | Discoverable types/statuses; additional required fields not mapped |
| 32 | Slack setup | Bot token, workspace ID, scopes, channel discovery and mapping | Blocked by External Credentials or Permissions | Mismatch and scope fixtures passed | test_workspace_mismatch_stops_discovery, test_slack_credential_scope_failure | Install app, grant permissions and test membership |
| 33 | Slack delivery | Private channel creation, roster invitations and Jira notification | Blocked by External Credentials or Permissions | Notification and workspace fixtures passed | connectors.py, test_approved_notification_endpoint | Verify receipt, channel type, invited members and message in Slack |
| 34 | Slack setup | Web OAuth installation flow | Missing | Source reviewed | Connections.tsx | Requires preinstalled bot token |
| 35 | Sync | Manual and scheduled Jira/Slack recent activity imports and comments | Partially Implemented | Read-path inspection | activity.py, worker.py, Delivery.tsx | One recent page; replies, attachments, worklogs, older history incomplete |
| 36 | Monitoring | Issue evidence, overdue and blocked detection, health digest | Partially Implemented | Pass for risk rules | test_evidence_risks, test_health, agent_policy.py | Live freshness and coverage; QA completion evidence requires human verification |
| 37 | Reports | Daily and weekly schedule window, timezone and day boundary | Fully Implemented and Tested | Pass for schedule rules | test_weekly_window, test_off_and_zone | Scheduler persistence and restart separate |
| 38 | Reports | Draft generation by date and audience, editing and revision conflict | Implemented but Not Tested | Redaction passed; API scenario written | report_text.py, reporting.py, tests/smoke.py | Real database date filtering, review and revision |
| 39 | Reports | Worker generation, recipient, heading, deduplication, closed periods | Partially Implemented | Window tests passed | worker.py, reporting.py, report_occurrences | One rule per project; run worker and verify duplicate suppression |
| 40 | Reports | Client redaction, avoidance of claimed verification | Fully Implemented and Tested | Pass for renderer fixture | test_report_redaction_and_period | User must review client content and selected evidence |
| 41 | Email | Sender, recipient, preview, approval, Resend dispatch/receipt | Blocked by External Credentials or Permissions | Idempotency header fixture passed | connectors.py, test_email_idempotency | Verified domain, provider receipt and inbox delivery |
| 42 | Email | Multiple providers, unattended preapproved delivery and flexible templates | Partially Implemented | Source reviewed | Reports.tsx, ReportRule.tsx, reporting.py | Resend, editable body and heading, per-message human approval |
| 43 | Approvals | Proposal, destination, reviewed payload, scope baseline, reject and publish | Implemented but Not Tested | API path inspection | agent_api.py decide, Agent.tsx | Actual concurrency, stale scope and post-dispatch failure |
| 44 | Approvals | Revision instructions and regeneration for every external action | Partially Implemented | Source reviewed | app.py plans, agent_api.py actions | Plan edits supported; general all-action regeneration lacks full flow |
| 45 | Feedback | Attach to output, categorise, count recurrences and propose guidance | Implemented but Not Tested | Recommendation text unit passed | review_rules.py, app.py feedback, ImprovementReview.tsx | Exercise SQL and UI across two projects |
| 46 | Feedback | Human evaluation, approve, reject, version guard and rollback | Partially Implemented | Smoke scenario written | app.py review and rollback_improvement | No automated before/after quality scoring |
| 47 | Settings | Agent identity, language, users, mode, time zone, permissions and configuration history | Implemented but Not Tested | Policy validation passed | agent_policy.py, agent_store.py, Agent.tsx | Persist, restore and access-control execution |
| 48 | Settings | Global project defaults, service escalation, notifications and central employee profiles | Partially Implemented | Source reviewed | agent_policy.py, activity.py | Policies, team mappings and reviewed Slack notifications cover subset |
| 49 | Secrets | Server-side encrypted keys, UI masking, revoke, rate and origin checks | Implemented but Not Tested | Redacted failure fixtures passed | db.py, connections_api.py, transport.py, app.py | Inspect browser/network/logs against live backend |
| 50 | Security | External text treated as data, no LLM tool authority, bounded inputs | Partially Implemented | Source reviewed; body-limit tests passed | models.py POLICY, app.py, agent_api.py | No adversarial model/authorization end-to-end evaluation |
| 51 | Reliability | Migrations, transactional writes, restart persistence and backup | Implemented but Not Tested | Smoke/restart harness written | schema.sql, migrate.py, tests/check-stack.sh | Run against real PostgreSQL including an upgrade and restore |
| 52 | Reliability | Audit history, run errors, polling retry and duplicate-action guard | Partially Implemented | Source reviewed | agent_actions indexes, worker.py, agent_runs | Simulate crash and lost response; ambiguous-write reconciliation is manual |
| 53 | Preview | Responsive React screens, sample data, network-disconnected interaction | Partially Implemented | Build and demo adapter passed | demo/build.mjs, tests/demo.mjs, web/style.css | Browser/mobile rendering and full keyboard workflow |
| 54 | Deployment | Docker build, manual startup, local bootstrap, initial admin, stop/restart | Implemented but Not Tested | Shell and YAML passed | Dockerfile, compose.yaml, Start.command | Build images and run macOS/Windows/Linux acceptance |
| 55 | Deployment | GitHub publishing and hosted cloud instance | Missing | No deployment performed | REQUIREMENTS.md §23 | Separate repository, cloud project and approval |
| 56 | Acceptance | A: create, upload, rename, import and isolate | Implemented but Not Tested | Fixture import; smoke written | tests/smoke.py, tests/live_acceptance.py | Run with PostgreSQL and a second user |
| 57 | Acceptance | B: chat modes, genuine answer, history and changing authority | Blocked by External Credentials or Permissions | Rules and adapter fixture passed | test_domain.py, live_acceptance.py | Model account and real database |
| 58 | Acceptance | C: approved scope to achievable scheduled plan | Partially Implemented | Graph, capacity and date units passed | test_audit.py, test_domain.py | Live generation plus manager effort/deadline review |
| 59 | Acceptance | D: review and publish to company Jira/Slack | Blocked by External Credentials or Permissions | Selected payloads mocked | connectors.py, CONFIGURATION-GUIDE.md | Remote write IDs, employee assignment and invitation |
| 60 | Acceptance | E: import activity, flag risk, draft, approve and deliver report | Blocked by External Credentials or Permissions | Risk, report and email fixtures passed | test_audit.py, test_agent.py | Connected services, worker and test inbox |
| 61 | Acceptance | F: feedback to proposed instruction, approval and rollback | Implemented but Not Tested | Unit rule pass; API fixture written | tests/test_audit.py, tests/smoke.py | Real permission, evaluation and rollback test |

## API inventory

The following is a source-derived route inventory, including administrative, project and external-action surfaces. An endpoint appearing here supplies wiring evidence only.

| Method | Route | Handler | Source line |
|---|---|---|---|
| GET | `/api/projects/{pid}/delivery` | delivery | activity.py:30 |
| POST | `/api/projects/{pid}/team` | staff | activity.py:34 |
| PUT | `/api/projects/{pid}/link` | link | activity.py:41 |
| POST | `/api/projects/{pid}/sync/{service}` | sync | activity.py:66 |
| GET | `/api/projects/{pid}/jira/{issue}/comments` | comments | activity.py:69 |
| GET | `/api/agents` | registry | agent_api.py:37 |
| GET | `/api/agents/pm-ai-es` | detail | agent_api.py:44 |
| PUT | `/api/agents/pm-ai-es/account/{account}` | permission | agent_api.py:58 |
| PUT | `/api/projects/{pid}/membership/{account}` | assign | agent_api.py:70 |
| PUT | `/api/agents/pm-ai-es/settings` | update | agent_api.py:80 |
| POST | `/api/agents/pm-ai-es/versions/{number}/restore` | restore | agent_api.py:86 |
| PUT | `/api/agents/pm-ai-es/credentials/{service}` | rotate | agent_api.py:108 |
| DELETE | `/api/agents/pm-ai-es/credentials/{service}` | revoke | agent_api.py:111 |
| POST | `/api/agents/pm-ai-es/test/{service}` | test_connection | agent_api.py:114 |
| POST | `/api/projects/{pid}/agent` | execute | agent_api.py:123 |
| POST | `/api/projects/{pid}/plans/{plan_id}/backlog` | backlog | agent_api.py:139 |
| GET | `/api/projects/{pid}/actions` | list_actions | agent_api.py:176 |
| POST | `/api/projects/{pid}/actions` | propose | agent_api.py:180 |
| POST | `/api/projects/{pid}/actions/{aid}/{decision}` | decide | agent_api.py:203 |
| GET | `/api/health` | health | app.py:46 |
| GET | `/api/session` | current_session | app.py:99 |
| POST | `/api/login` | login | app.py:130 |
| POST | `/api/logout` | logout | app.py:148 |
| GET | `/api/projects` | projects | app.py:174 |
| POST | `/api/projects` | new_project | app.py:187 |
| PATCH | `/api/projects/{pid}` | edit_project | app.py:198 |
| DELETE | `/api/projects/{pid}` | archive_project | app.py:206 |
| GET | `/api/projects/{pid}/workspace` | workspace | app.py:214 |
| POST | `/api/projects/{pid}/files` | upload | app.py:238 |
| POST | `/api/projects/{pid}/chat-import` | import_chat | app.py:259 |
| PATCH | `/api/projects/{pid}/sources/{sid}` | rename | app.py:280 |
| GET | `/api/projects/{pid}/sources/{sid}` | inspect | app.py:288 |
| POST | `/api/projects/{pid}/sources/{sid}/approve` | approve | app.py:296 |
| POST | `/api/projects/{pid}/messages` | message | app.py:382 |
| GET | `/api/projects/{pid}/search` | search | app.py:405 |
| GET | `/api/settings` | settings | app.py:415 |
| PUT | `/api/settings` | configure | app.py:422 |
| POST | `/api/projects/{pid}/plans` | plan | app.py:431 |
| PUT | `/api/projects/{pid}/plans/{key}` | review | app.py:453 |
| GET | `/api/projects/{pid}/sources/{sid}/original` | original | app.py:468 |
| POST | `/api/projects/{pid}/schedule` | schedule | app.py:490 |
| GET | `/api/projects/{pid}/reports` | report | app.py:496 |
| POST | `/api/projects/{pid}/feedback` | feedback | app.py:513 |
| GET | `/api/projects/{pid}/improvements` | improvements | app.py:526 |
| POST | `/api/projects/{pid}/improvements/{key}` | review | app.py:534 |
| POST | `/api/projects/{pid}/improvements/{key}/rollback` | rollback_improvement | app.py:551 |
| POST | `/api/connections/{service}/{operation}` | configure | connections_api.py:29 |
| GET | `/api/connections/{service}/options/{resource}` | discover | connections_api.py:65 |
| GET | `/api/projects/{pid}/report-rule` | read_rule | reporting.py:59 |
| PUT | `/api/projects/{pid}/report-rule` | write_rule | reporting.py:64 |
| GET | `/api/projects/{pid}/report-drafts` | listing | reporting.py:70 |
| POST | `/api/projects/{pid}/report-drafts` | draft | reporting.py:74 |
| PUT | `/api/projects/{pid}/report-drafts/{key}` | edit | reporting.py:78 |

## Next verification, in order

1. Run the disposable stack test. Verify login, negative authorisation, upload, plan review, report edit conflicts, feedback review and persistence after replacing the app and restarting PostgreSQL. Save the actual output.
2. Run the app on the target laptop. Use separate manager and read-only logins and two projects. Record whether each direct API and UI operation respects project membership, including after revocation. Compare downloaded file bytes and metadata before and after restart.
3. Run the operator acceptance tool with each required provider selected in turn. Verify returned model IDs and project citations against the approved source.
4. In a disposable internal Jira project and private Slack channel, verify externally created keys, hierarchy, assignee, channel membership, notifications and second-import deduplication. Test denied permissions with an authorised restricted account.
5. Produce daily and weekly report drafts across a time-zone boundary. Review the recipient, approve one email to a controlled inbox and record provider receipt plus delivery. Interrupt a worker and verify no duplicate publication.
6. Conduct a restore drill and browser walkthrough of A–F. Record evidence and resolve defects before designating the final package.

## Original scope crosswalk

Every original numbered section is mapped below. The cited lines retain the original detailed requirements, examples and acceptance wording. Rows marked partial or missing above remain open.

| Scope section | Requirement source | Audit IDs |
|---|---|---|
| 1. Project Vision | REQUIREMENTS.md line 20 | 01, 02 |
| 2. Unified Platform Architecture | REQUIREMENTS.md line 47 | 01, 02, 13, 54, 55 |
| 3. Admin Login and Main Dashboard | REQUIREMENTS.md line 92 | 03, 04, 05, 06, 07 |
| 4. Project Creation and Management | REQUIREMENTS.md line 130 | 08, 09, 18 |
| 5. Project Documents and Knowledge Base | REQUIREMENTS.md line 175 | 10, 11, 12, 13, 14, 15 |
| 6. Project AI Chat — Response ON/OFF | REQUIREMENTS.md line 238 | 16, 17 |
| 7. Intelligent Project Memory and Historical Understanding | REQUIREMENTS.md line 297 | 14, 15, 16, 17, 43, 44 |
| 8. Automated Project Planning | REQUIREMENTS.md line 342 | 23, 24, 25 |
| 9. Intelligent Task Estimation and Scheduling | REQUIREMENTS.md line 413 | 26, 27 |
| 10. Existing Eleven Steeds Jira Workspace Integration | REQUIREMENTS.md line 451 | 29, 30, 31 |
| 11. Slack Project Automation | REQUIREMENTS.md line 514 | 32, 33, 34, 35 |
| 12. Team Selection and Automatic Assignment | REQUIREMENTS.md line 547 | 24, 25, 28 |
| 13. Project-Specific AI Expertise | REQUIREMENTS.md line 580 | 18, 19, 20, 21 |
| 14. Continuous Project Monitoring | REQUIREMENTS.md line 602 | 35, 36 |
| 15. Automated CEO and Client Reporting | REQUIREMENTS.md line 628 | 37, 38, 39, 40, 41, 42 |
| 16. Human Review Before Publishing | REQUIREMENTS.md line 731 | 30, 33, 43, 44 |
| 17. AI Feedback and Continuous Improvement | REQUIREMENTS.md line 774 | 45, 46 |
| 18. User Interface and Experience | REQUIREMENTS.md line 807 | 07, 53 |
| 19. Central Settings and Integration Management | REQUIREMENTS.md line 856 | 19, 20, 21, 29, 32, 34, 41, 42, 47, 48 |
| 20. Data Model and Storage | REQUIREMENTS.md line 892 | 13, 51, 52 |
| 21. Security and Reliability | REQUIREMENTS.md line 933 | 03, 04, 05, 06, 49, 50, 51, 52 |
| 22. Development Roadmap | REQUIREMENTS.md line 959 | 01, 02, 56, 57, 58, 59, 60, 61 |
| 23. Development, Preview and Deployment | REQUIREMENTS.md line 1031 | 53, 54, 55 |
| 24. Testing and Acceptance Criteria | REQUIREMENTS.md line 1068 | 56, 57, 58, 59, 60, 61 |
| 25. How You Must Work With Me | REQUIREMENTS.md line 1097 | 54, 55, 56, 57, 58, 59, 60, 61 |
