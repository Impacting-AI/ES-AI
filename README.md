# PM AI ES · Project Manager AI for Eleven Steeds

**Project Chat upgrade 0.5 · laptop acceptance build.** See CHAT-UPGRADE.md for upgrade steps and verification. PM AI ES helps a project manager turn agreed scope into a reviewed plan, prepare Jira and Slack actions, and report progress from imported records. This build includes the local application and an independent offline demonstration. See QA-REPORT.md for executed evidence and KNOWN-LIMITATIONS.md for outstanding work.

## First launch on a Mac

Install and open Docker Desktop. Extract the source ZIP. In Terminal, open the extracted folder containing Start.command and run `bash Start.command`. Choose your admin login and password and open **http://localhost:8080**. The launcher starts the database, backend, frontend and worker. See SETUP-GUIDE.md for the step-by-step walkthrough, restart instructions, manual setup and recovery.

## What you can do

| Screen | Project manager's workflow |
|---|---|
| Dashboard and Projects | Create a project, add client information, set target dates and open its workspace. View approvals and overdue imported issues. Archive a project by confirming its name. |
| Documents and project knowledge | Upload an agreement, rename its display title, add a description and approve its version. Search extracted passages. Import a structured chat export or add a note. |
| AI PM chat | Start and search chats, attach a file, dictate a message, and follow cited passages. Response OFF saves a draft project note. Response ON streams a provider answer using project knowledge and conversation context. |
| Project plan and Schedule | Draft milestones, deliverables, work items and acceptance criteria from approved scope. Review the plan and check dependencies, employee capacity and target dates. |
| Team & delivery | Enter confirmed employees and Jira/Slack IDs. Bind the correct external project and channel. Import recent activity and inspect Jira comments. |
| Agents → Automation | Prepare a Jira backlog, project, board, relationship, Slack channel, invitation, notification or report email. Review the destination and content. Receipt IDs identify remote responses. |
| Reports | Generate an internal or client draft for a date range. Review imported status and overdue issues. Save edits, queue the saved revision for approval, and configure daily or weekly draft generation. |
| Feedback | Link a correction to an output. Inspect repeated categories and proposed project guidance. An authorised administrator can apply or roll back reviewed guidance. |
| Agents → Settings and Monitoring | Choose model, limits, fallback, permissions, integrations, operating hours and access. Inspect configuration versions, calls, estimated cost, failures and digest history. |

## Project layout

`web/` is the React/TypeScript client. `server/app.py` serves FastAPI and the compiled frontend. `server/schema.sql` contains repeatable PostgreSQL migrations. `server/worker.py` runs scheduled jobs. `tests/` contains unit, contract and operator-run acceptance checks. `demo/` supplies the disconnected preview adapter. The production app uses `web/api.ts` and sends same-origin HTTP requests to FastAPI. The demo has no external network access.

Read CONFIGURATION-GUIDE.md before connecting company accounts. The original scope is preserved in REQUIREMENTS.md.
