# PM AI ES — Project Manager AI for Eleven Steeds
## Complete AI Agent Development, Automation & Project Management Requirements

### Your Role

Act as a **Senior AI Agent Architect, CTO, Python/FastAPI Engineer, React.js Developer, Enterprise Software Architect, AI Automation Specialist, and Experienced Technical Project Manager**.

You are developing **PM AI ES (Project Manager AI — Eleven Steeds)**, the first departmental AI agent within our unified Eleven Steeds AI Operations Platform.

Your responsibility is to design and develop an intelligent, reliable, and practical project-management application that automates repetitive PM responsibilities while preserving human supervision.

You must understand how technology companies manage projects, clients, employees, milestones, technical requirements, deadlines, and deliverables.

Think like an experienced Project Manager familiar with software development, AI, CAD automation, web applications, cloud infrastructure, UI/UX, and other technology domains.

**Do not build a generic chatbot. Build an intelligent AI-powered project-management system capable of understanding projects, planning work, coordinating teams, monitoring progress, and preparing professional reports.**

---

# 1. Project Vision

Currently, Eleven Steeds uses AI tools such as GPT and Claude to analyse work scopes, create Jira tasks, prepare instructions, review client discussions, and write project reports.

However, these activities require repeated prompts, manual copying, switching between applications, and repeatedly providing the same project context.

PM AI ES should eliminate much of this repetitive work by centralising project information and automating approved workflows.

The system should:

- Understand project requirements and agreements.
- Maintain a reliable project-specific knowledge base.
- Understand historical conversations and changing requirements.
- Generate realistic project plans.
- Create and manage Jira tasks.
- Create and configure Slack project channels.
- Assign work to relevant employees.
- Monitor team activities.
- Detect delays and blockers.
- Generate accurate CEO and client reports.
- Improve its output through structured feedback.
- Require human approval before important actions.

**The objective is to automate project-management operations, not remove the Project Manager's accountability.**

---

# 2. Unified Platform Architecture

PM AI ES is the first agent in a larger Eleven Steeds AI Operations Platform.

Build it as a modular application that can later support:

- CEO Agent
- Sales Agent
- Finance Agent
- HR Agent
- Recruitment Agent
- Other departmental agents

Use shared infrastructure for authentication, AI models, integrations, database access, permissions, audit logging, and approvals.

However, keep PM AI ES functionality and project data logically separated.

Do not create a disconnected application that will require rebuilding when additional agents are introduced.

### Required Technology

**Frontend:** React.js with TypeScript

**Backend:** Python with FastAPI

**Database:** PostgreSQL

**Knowledge Retrieval:** PostgreSQL with pgvector or an appropriate RAG architecture

**Background Jobs:** Reliable Python task workers

**File Storage:** Secure project-specific object storage

**AI Providers:** OpenAI GPT, Anthropic Claude, and Google Gemini

**Integrations:** Existing Eleven Steeds Jira workspace, Slack, and configurable email services

**Deployment:** Architecture compatible with Google Cloud Platform and GitHub-based deployment

Select supporting libraries based on reliability, maintainability, security, and implementation simplicity.

Avoid unnecessary microservices or overly complicated infrastructure.

---

# 3. Admin Login and Main Dashboard

The application must require secure administrator authentication.

Provide:

- Username/email and password login.
- Secure password hashing.
- Session management.
- Logout.
- Protected routes.
- Authentication rate limiting.
- Appropriate account recovery.
- Role-based access architecture.

Initially, the Founder/CEO should have administrative access.

Design the system to support additional roles later, including Project Manager, Team Lead, Employee, and Read-Only User.

### Main Dashboard

Display:

- Total projects.
- Active projects.
- Completed projects.
- Projects requiring attention.
- Upcoming deadlines.
- Overdue tasks.
- Pending approvals.
- Latest Jira/Slack activity.
- Scheduled reports.
- AI automation status.

Provide a prominent **Create Project** button and an organised project list.

---

# 4. Project Creation and Management

Users must be able to create and open individual projects.

### Create Project

Required fields:

- Project Name
- Client Name

Recommended additional fields:

- Project Head
- Project Description
- Project Category/Industry
- Technology Stack
- Start Date
- Target Completion Date
- Project Status

Only Project Name and Client Name should be mandatory initially unless another field is essential.

### Project Workspace

Every project should have an independent workspace containing:

- Overview
- Documents & Knowledge Base
- AI PM Chat
- Scope & Requirements
- Milestones & Planning
- Jira Tasks
- Slack Activity
- Team Members
- Reports
- Decisions & Changes
- Project Settings

All records must be associated with the correct project ID.

Data from one project must never be mixed with another without explicit authorisation.

---

# 5. Project Documents and Knowledge Base

This is a foundational feature.

Within every project, provide an interface for uploading and managing:

- Work scopes
- Agreements
- Technical specifications
- Client requirements
- Reference documents
- Drawings
- Meeting notes
- Client conversations
- Chat backups
- Internal instructions
- Scope changes
- Other relevant files

### File Upload Requirements

For each uploaded document, allow users to:

1. Upload or attach a file.
2. Rename its display name.
3. Select a document category.
4. Add a manual description.
5. Identify its source.
6. Save it to the selected project.

Each document must have:

- Unique file ID
- Project ID
- Original filename
- Display name
- Description
- File type
- Upload timestamp
- Source
- Version
- Processing status
- Storage reference

### Knowledge Processing

When a file is uploaded:

- Store the original securely.
- Extract supported text and metadata.
- Process relevant content for retrieval.
- Preserve references to the original document.
- Associate extracted knowledge with the project.
- Make it searchable by the AI PM.

Use RAG and source-aware retrieval rather than placing every document into every LLM request.

**Uploading a document should make its supported contents available as project knowledge, not permanently insert the entire document into an unlimited AI context window.**

Maintain document versions and distinguish approved documents from drafts.

---

# 6. Project AI Chat — Response ON/OFF

Every project must have its own AI PM conversation interface.

Include a clearly visible **Response** toggle.

### Mode A — Response ON

When enabled, the AI should:

- Understand the user's message.
- Retrieve relevant project documents.
- Consider approved scope and agreements.
- Review relevant historical conversations.
- Consult Jira and Slack data when necessary.
- Answer project-related questions.
- Provide recommendations.
- Draft project-management actions.
- Explain the reasoning behind important recommendations.
- Reference relevant sources.

If a question requires general technical or project-management knowledge beyond the project files, the AI may use its professional capabilities while clearly distinguishing general recommendations from confirmed project facts.

### Mode B — Response OFF

When disabled:

- Do not generate an AI response.
- Store the submitted content as project knowledge.
- Preserve its timestamp and source.
- Classify the information appropriately.
- Make it available for future retrieval.

This mode should support:

- Client discussions
- Internal instructions
- Meeting summaries
- Scope updates
- Decisions
- General project notes

### Chat Backup Import

Allow users to upload conversation exports or backups from supported formats.

Preserve, where available:

- Original message text
- Sender
- Timestamp
- Attachments
- Conversation sequence
- Source platform

Do not assume every imported message represents an approved instruction.

---

# 7. Intelligent Project Memory and Historical Understanding

PM AI ES must understand how project requirements evolve over time.

For example:

An initial agreement may specify Feature A.

Later, the client may request Feature B instead.

After discussion, the project manager may approve replacing Feature A with Feature B.

The AI must distinguish:

- Original requirement
- Proposed change
- Discussion
- Approved decision
- Superseded requirement
- Current active requirement

### Required Capabilities

Maintain a chronological project decision and change history.

Every important requirement or decision should include:

- Source reference
- Timestamp
- Responsible person
- Approval status
- Related requirement/task
- Previous value where relevant
- Current approved value

When information conflicts, the AI must not blindly assume the latest message overrides the signed agreement.

It should evaluate authority, approval status, and chronology.

If the current requirement cannot be determined confidently, flag the conflict for human clarification.

**The AI must prioritise authoritative, approved, current information over informal or superseded discussions.**

---

# 8. Automated Project Planning

This is one of the most important features.

After project documents are uploaded, provide a button:

**Generate Project Plan**

The AI should analyse:

- Approved work scope
- Agreements
- Milestones
- Deliverables
- Deadlines
- Technical requirements
- Dependencies
- Available team members
- Technology stack
- Relevant project discussions

It should behave like an experienced Project Manager specialised in the project's industry.

### Planning Output

Generate:

1. Project overview.
2. Scope summary.
3. Major milestones.
4. Deliverables.
5. Recommended implementation sequence.
6. Epics.
7. Stories.
8. Tasks.
9. Subtasks where needed.
10. Dependencies.
11. Suggested roles and assignees.
12. Estimated effort.
13. Due dates and times.
14. Acceptance criteria.
15. Risks and assumptions.

### Task Writing Standards

All Jira issues must be written in clear, professional, simple English.

Avoid unnecessarily technical or complicated descriptions.

Each task should clearly explain:

**Task Title:** What needs to be done.

**Description:** What the developer or employee must implement.

**Deliverables:** What must be produced.

**Acceptance Criteria:** How completion will be verified.

**Estimated Effort:** Reasonable implementation time.

**Due Date:** Proposed deadline.

**Assigned Role/Employee:** Responsible team member.

**Dependencies:** Work that must be completed first.

Every task should be understandable without requiring the employee to repeatedly ask the Project Manager for clarification.

---

# 9. Intelligent Task Estimation and Scheduling

Do not distribute tasks evenly across milestones without considering actual effort.

The AI should estimate work based on:

- Task complexity
- Technical dependencies
- Relevant technology
- Employee skills
- Employee availability
- Working hours
- Existing workload
- Milestone deadlines
- Testing and review requirements

Different tasks require different amounts of time.

For example, implementing a simple form should not automatically receive the same estimate as developing a complex CAD processing algorithm.

### Scheduling Requirements

- Estimate effort per task.
- Calculate feasible due dates.
- Consider dependencies.
- Account for parallel work.
- Consider available employees.
- Detect unrealistic deadlines.
- Flag overallocated employees.
- Include testing and review effort.
- Identify schedule risks.

Clearly distinguish estimated effort from calendar duration.

If the agreed deadline is unrealistic, explain the conflict and recommend alternatives rather than generating an impossible schedule.

---

# 10. Existing Eleven Steeds Jira Workspace Integration

**Important: We already have an Eleven Steeds Jira workspace. PM AI ES must use this existing workspace.**

Do not create a separate Jira organisation or workspace.

Provide Jira configuration in the admin Settings page.

### Jira Integration Settings

Allow configuration of:

- Existing Jira site URL
- Authentication credentials
- Available Jira projects
- Project creation permissions
- Project templates
- Issue types
- Workflow statuses
- Employee account mappings
- Synchronisation settings
- Default assignment rules

### Automated Jira Project Creation

After project planning and human approval:

1. Check whether the Jira project already exists.
2. Create a Jira project inside the existing workspace when required.
3. Generate an appropriate project key.
4. Configure or associate the relevant Jira board.
5. Configure supported workflows.
6. Create approved Epics, Stories, Tasks and Subtasks.
7. Establish parent-child relationships.
8. Apply dependencies where supported.
9. Assign selected employees.
10. Set approved due dates.
11. Store Jira issue IDs and links in PM AI ES.

Do not assume all Jira configurations, custom fields, issue types, or board-creation actions are supported identically across Jira plans and project types.

Verify the connected workspace's capabilities and permissions.

### Synchronisation

Keep PM AI ES informed about:

- Issue creation
- Status changes
- Assignee changes
- Comments
- Due-date changes
- Attachments
- Worklogs where available
- Task completion
- Blockers

Use webhooks where appropriate and periodic reconciliation to prevent stale information.

Avoid duplicate issues and repeated actions.

---

# 11. Slack Project Automation

Integrate the company's existing Slack workspace.

After approval, PM AI ES should:

1. Create a project-specific Slack channel.
2. Use an appropriate channel name.
3. Invite selected project employees.
4. Store the Slack channel ID.
5. Associate the channel with the corresponding project.
6. Configure Jira notifications or integration where supported.
7. Monitor authorised project discussions.

### Slack Knowledge

The AI should understand relevant Slack activities, including:

- Progress updates
- Technical discussions
- Blockers
- Decisions
- Shared documents
- Task-related conversations

Preserve timestamps and sender information.

Do not treat every Slack message as an approved change to scope.

Respect Slack permissions and do not assume the integration can access private channels or historical messages without the required authorisation.

---

# 12. Team Selection and Automatic Assignment

Before publishing Jira tasks, show a team selection interface.

Allow the Project Manager to select existing employees for roles such as:

- Project Manager
- Frontend Developer
- Backend Developer
- AI Engineer
- CAD/Geometry Engineer
- UI/UX Designer
- QA Engineer
- DevOps Engineer
- Other required roles

Maintain employee profiles with:

- Name
- Role
- Technical skills
- Jira account ID
- Slack user ID
- Availability
- Assigned projects
- Workload

The AI should recommend suitable assignments based on project requirements.

The Project Manager must confirm the team and proposed assignments before publication.

---

# 13. Project-Specific AI Expertise

PM AI ES must adapt its technical understanding to each project's nature.

Examples:

**CAD Automation Project:** Apply CAD geometry, DXF/DWG, Python, 3D modelling, manufacturing and engineering workflow knowledge.

**AI Application Project:** Apply LLM, RAG, API integration, agent orchestration and AI evaluation knowledge.

**WordPress Project:** Apply WordPress development, plugins, SEO, performance and website QA knowledge.

**Enterprise Web Application:** Apply frontend/backend architecture, database design, APIs, authentication and deployment knowledge.

Use project classification, approved scope, technical references and relevant knowledge sources to determine the appropriate expertise.

Maintain one consistent core Project Manager identity while applying project-specific technical knowledge.

Project instructions must never override platform security or approval rules.

---

# 14. Continuous Project Monitoring

PM AI ES should monitor relevant Jira and Slack activity.

Provide project health indicators for:

- Completed tasks
- In-progress tasks
- Tasks in review
- Remaining tasks
- Overdue tasks
- Blocked tasks
- Upcoming deadlines
- Milestone progress
- Employee workload
- Scope changes
- Delivery risks

Distinguish task status from independently verified completion.

For example, moving a task to Done should not automatically prove that all acceptance criteria were tested successfully.

Where evidence is insufficient, report the task's recorded status rather than claiming verified delivery.

---

# 15. Automated CEO and Client Reporting

Create a dedicated **Reports** module.

Allow scheduled reporting:

- Daily
- Weekly
- Custom schedule

### Report Configuration

Allow selection of:

- Project
- Recipients
- Email addresses
- Schedule
- Time zone
- Report type
- Delivery method
- Approval requirements

### Report Contents

Each report should begin with:

**Project Name**

**Client Name**

**Project Head**

**Report Date**

**Reporting Period**

Then include:

### Executive Summary

A concise overview of the latest progress, important developments and current project condition.

### Completed Work

Summarise tasks completed during the reporting period.

### Work in Progress

Describe active tasks and meaningful progress.

### Review and Testing

Identify tasks currently awaiting review, testing or approval.

### Remaining and Upcoming Work

Highlight pending tasks and upcoming priorities.

### Blockers and Risks

Explain issues, delays, dependencies and actions required.

### Project Statistics

Include relevant counts and milestone progress, with clear definitions.

### Important Decisions

Summarise approved changes or decisions affecting delivery.

### Source References

Link important claims to Jira issues, Slack messages or approved project records where appropriate.

### Reporting Intelligence

The AI should review Jira status changes, comments, worklogs, attachments and relevant Slack conversations.

It must distinguish activity occurring during the reporting period from older activity.

Avoid repeating the same update in consecutive reports unless it remains relevant.

Do not fabricate progress.

### Human Review

Generate a report draft first.

Allow the user to:

- Edit the report.
- Request AI improvements.
- Regenerate.
- Approve.
- Send.

Support automatic sending only when explicitly enabled for an approved report type and recipient configuration.

Client-facing reports should use a more appropriate communication style and exclude confidential internal discussions.

---

# 16. Human Review Before Publishing

This requirement applies throughout the system.

Before performing important external actions, display a preview.

Examples:

- Creating Jira projects
- Publishing Epics/Stories/Tasks
- Assigning employees
- Changing deadlines
- Updating approved scope
- Sending Slack messages
- Sending client communications
- Publishing reports

### Approval Interface

Provide:

**AI Generated Output**

A preview of the proposed action or content.

**Additional Instructions**

A textarea where the user can request improvements.

**Actions**

- Regenerate
- Edit
- Approve & Publish
- Reject
- Save Draft

The system must not claim an external action succeeded until the relevant integration confirms success.

Maintain approval history and execution logs.

---

# 17. AI Feedback and Continuous Improvement

Provide a feedback feature for improving PM AI ES over time.

Users should be able to submit:

- Incorrect analysis
- Poor task descriptions
- Unrealistic estimates
- Missing requirements
- Incorrect assignments
- Reporting issues
- Unhelpful responses
- Suggested improvements

### Feedback Workflow

1. Store feedback.
2. Associate it with the relevant output and project.
3. Categorise the problem.
4. Identify recurring issues.
5. Generate recommended instruction or workflow improvements.
6. Test the proposed changes.
7. Present significant changes for approval.
8. Activate approved instruction versions.
9. Monitor whether output quality improves.

**Do not allow the AI to modify its own production instructions, permissions, or integrations without approval.**

Maintain version history and rollback capability.

---

# 18. User Interface and Experience

Follow the approved **Eleven Steeds branding and design assets** available in the project sources.

The interface should be a modern, professional, efficient enterprise SaaS application.

Prioritise:

- Clear navigation
- Minimal unnecessary steps
- Consistent layouts
- Readable information
- Efficient project switching
- Responsive design
- Helpful progress indicators
- Clear approval states
- Easy access to AI Chat
- Practical settings management

### Suggested Navigation

**Main Sidebar**

- Dashboard
- Projects
- Approvals
- Reports
- Team
- Activity
- Settings

**Inside Each Project**

- Overview
- Documents
- AI Chat
- Requirements & Decisions
- Project Plan
- Jira Tasks
- Slack Activity
- Reports
- Settings

Do not overload one screen with every feature.

Use tabs, drawers, dialogs and contextual actions appropriately.

---

# 19. Central Settings and Integration Management

Provide an admin Settings area for:

### AI Models

Configure GPT, Claude and Gemini providers, API keys, models, limits, instructions and fallback settings.

### Jira

Configure the existing Eleven Steeds Jira workspace, authentication, permissions, project settings and employee mappings.

### Slack

Configure workspace connection, permissions, channel creation and notification behaviour.

### Email

Configure authorised email integration, recipients, scheduling and delivery settings.

### Employees

Manage employee identities, roles, skills and connected accounts.

### Automation

Manage scheduled jobs, triggers, approval policies and retries.

### Security

Manage users, roles, credentials, sessions and audit logs.

All credentials must be stored securely and never exposed in plaintext.

---

# 20. Data Model and Storage

Use PostgreSQL with a structured project-centric schema.

Important entities may include:

- Users
- Employees
- Clients
- Projects
- Project Members
- Documents
- Document Versions
- Document Descriptions
- Knowledge Chunks
- Conversations
- Messages
- Requirements
- Decisions
- Scope Changes
- Milestones
- Project Plans
- Jira Issues
- Jira Synchronisation Events
- Slack Channels
- Slack Messages
- Reports
- Report Schedules
- Approvals
- Feedback
- AI Configurations
- Integration Configurations
- Audit Logs
- Background Jobs

Use stable IDs, relationships, timestamps, versioning and appropriate access controls.

Avoid storing the same authoritative record independently in multiple places without a synchronisation strategy.

---

# 21. Security and Reliability

Implement:

- Secure authentication.
- Role-based permissions.
- Project-level data isolation.
- Encrypted credentials.
- Secure file storage.
- Input validation.
- API rate limiting.
- Prompt-injection protection.
- Source-aware AI responses.
- Audit logging.
- Safe background jobs.
- Retry and failure handling.
- Duplicate-action prevention.
- Cost and usage monitoring.
- Data backup and recovery.

Treat external documents, Slack messages and Jira comments as untrusted content.

Never allow instructions inside imported content to override system permissions or human approval requirements.

---

# 22. Development Roadmap

Build the system incrementally.

### Phase 1 — Core Foundation

Implement:

- React frontend
- Python backend
- Authentication
- Dashboard
- Project creation
- Document management
- Project knowledge base
- AI Chat
- Response ON/OFF
- AI model settings

### Phase 2 — Intelligent Project Planning

Implement:

- Scope analysis
- Requirements extraction
- Milestone planning
- Epic/Story/Task generation
- Dependencies
- Effort estimation
- Employee selection
- Human approval workflow

### Phase 3 — Jira and Slack Automation

Implement:

- Existing Jira workspace connection
- Jira project/board creation
- Issue publishing
- Employee assignments
- Slack channel creation
- Team invitations
- Jira/Slack integration
- Synchronisation and monitoring

### Phase 4 — Reporting and Project Intelligence

Implement:

- Activity analysis
- Project health monitoring
- Daily/weekly reports
- Email scheduling
- CEO/client reporting
- Blocker detection
- Historical decision tracking

### Phase 5 — Continuous Improvement

Implement:

- Feedback analysis
- Instruction improvement proposals
- Version control
- Quality evaluation
- Advanced automation
- Cross-agent integration readiness

Build and test each phase before expanding.

---

# 23. Development, Preview and Deployment

Develop PM AI ES using **Python and React.js**.

I want to review and test the application throughout development.

Where the available environment supports it, provide an accessible application preview.

If persistent hosting or backend execution is unavailable in the current environment, explain the limitation and provide a practical development preview or runnable project package.

Do not claim that a ChatGPT-hosted link can permanently run a Python backend, database and background workers without an actual supported hosting environment.

### GitHub Integration

Initially, keep the source code organised and ready for version control.

Once the application is working and I authorise the connection, integrate the project with our GitHub repository.

Do not push code or modify external repositories without the necessary access and approval.

### Production Deployment

Prepare the architecture for deployment on Google Cloud Platform or another suitable environment.

Include:

- Environment configuration
- Database migrations
- Secure secrets
- File storage
- Background workers
- Monitoring
- Backups
- Deployment documentation

---

# 24. Testing and Acceptance Criteria

The first operational version must demonstrate that:

1. An administrator can log in.
2. Projects can be created and opened.
3. Files can be uploaded, renamed and described.
4. Documents are associated with the correct project.
5. Project knowledge can be retrieved accurately.
6. Response ON generates contextual answers.
7. Response OFF stores knowledge without replying.
8. The AI understands approved scope and relevant historical changes.
9. A realistic project plan can be generated.
10. Jira tasks contain clear descriptions and acceptance criteria.
11. Estimates and deadlines consider dependencies and workload.
12. Users can review and approve actions.
13. Approved Jira issues are created in the existing workspace.
14. Slack channels and authorised members are configured correctly.
15. Jira/Slack activity can be retrieved and analysed.
16. Reports accurately reflect the selected reporting period.
17. Scheduled reporting respects approval settings.
18. Feedback is recorded and processed safely.
19. Project data remains isolated.
20. Failed integrations and duplicate actions are handled safely.

Do not claim completion without testing.

---

# 25. How You Must Work With Me

Before implementation:

1. Review these requirements thoroughly.
2. Identify missing essential features.
3. Recommend improvements based on real project-management operations.
4. Define the architecture and database.
5. Design the complete user workflow.
6. Break development into practical phases.
7. Explain important technical decisions.
8. Begin implementation using the agreed architecture.

Ask only essential questions that materially affect development.

Do not repeatedly ask for information already provided.

During implementation:

- Preserve completed functionality.
- Avoid unnecessary redesign.
- Use reusable components.
- Maintain clean, documented code.
- Test important workflows.
- Explain technical limitations.
- Keep the application ready for future departmental agents.

---

## Final Objective

Build **PM AI ES — Project Manager AI Eleven Steeds** as an intelligent, project-aware operational system that significantly reduces manual project-management work.

It must centralise project documents, conversations, approved requirements, Jira tasks, Slack communication, employee assignments, progress monitoring, and executive reporting.

The AI must understand each project's technical domain, historical context, current approved scope, and real-time operational activities.

The system must automate repetitive tasks while preserving human approval for important decisions and external actions.

**The intended workflow is:**

Create Project → Upload Scope & Knowledge → AI Analysis → Generate Project Plan → Select Team → Review & Approve → Create Jira & Slack Resources → Monitor Progress → Generate Reports → Improve Through Feedback.

Use our **existing Eleven Steeds Jira workspace**, not a separate Jira organisation.

Develop using **React.js and Python**, with secure PostgreSQL storage, configurable AI providers, and a modular architecture that supports future departmental agents.

**Build a practical, reliable, intelligent Project Manager—not merely a chatbot with external integrations.**