# Application architecture

React forms use web/api.ts to call the same-origin FastAPI service. API dependencies resolve the session, agent access, platform role and project membership. PostgreSQL stores the authorised project evidence, memberships, source versions, passages, policy versions, usage and receipts. Integration credentials and authenticator seeds are encrypted with the installation key.

The PM agent routes explicit health and planning commands to deterministic access checks. It uses the selected AI provider for interpretation and drafting. Excerpts, external activity and conversation history enter the model as data. External publication takes a separate, reviewed API action. Each approval is associated with the target and policy revision. Publishing a child work item depends on confirmed prerequisites. The worker imports bounded activity, records digests and generates due report drafts.

An alternate, network-disabled API adapter builds the sample HTML preview from the same React components. The production build only imports the live HTTP client. See QA-REPORT.md for coverage and KNOWN-LIMITATIONS.md for the operational boundary.
