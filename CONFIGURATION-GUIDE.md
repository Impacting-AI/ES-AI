# Configure PM AI ES

Sign in as **Super Admin** or **CEO**. Use **Agent settings** in the sidebar or the tabs under **Agents**. First select **General** and set the time zone, language and operating mode. **Analyse** permits questions and health checks. **Draft** adds planning. **Approved actions** also permits reviewed external actions. Save the settings.

| Service | What to enter | How to verify |
|---|---|---|
| OpenAI, Anthropic or Gemini | In **AI model**, choose the provider, enter its API key and a text-generation model ID available to that account. Set guidance, maximum output tokens, retrieved passages, message history and hourly limit. Temperature is optional. Set a fallback provider/model if needed and configure its key. | Click **Test Model** for that provider, inspect the result, then **Save Configuration**. The test makes a small billable generation request. Ask a question about an approved source and verify the saved answer and references. |
| Cost settings | Enter conservative input/output rates per million tokens for the model and fallback. Set a monthly USD cap. A zero cap disables monthly budget enforcement. | Monitoring shows estimated costs and unresolved reservations. Compare with provider billing. Setup probes are excluded. |
| Jira Cloud | In **Integrations → Jira**, enter the existing site URL, account email and compatible site API token. Optionally set the default project key, polling interval and status mapping. | Test and save. Discover projects, issue types, statuses, link types, assignable accounts, boards and permissions. Under **Team & delivery**, bind the intended Jira project and optional board. |
| Slack | Install an authorised Slack app in the intended workspace. Enter its bot token and expected workspace ID under **Integrations → Slack**. Configure history import, polling and optional reviewed Jira notifications. | Test the workspace identity and save. Discover channels and users. Add the bot to the intended channel. Under **Team & delivery**, bind that channel and enter each approved employee's user ID. |
| Email | Use **Integrations → Email**. Enter the Resend API key and verified sender address. | Test and save. The test lists domains and may fail with a sending-only key. A provider receipt means the message was accepted. Check the recipient inbox separately. |
| Reports | In the project **Reports** tab choose daily, weekly or off. Set local hour, time zone, weekday, audience, report heading and suggested recipient. | With the worker running, the rule generates a draft for the previous complete day or seven days. Review the content and recipient, queue the saved revision, then approve it in **Agents → Automation**. |
| Employees and permissions | Create the login with the terminal admin command. Use **Permissions** to grant a role, agent access and membership. Add name, role, skills, net hours per day and Jira/Slack IDs in the project team. | Sign in as that user. Verify access to an assigned project and denial on a different project. Employee and Read-Only roles view project data. |
| PostgreSQL and encryption | For Docker, the launcher generates DB_PASSWORD and ENCRYPTION_KEY once. PUBLIC_ORIGIN must match the exact browser origin. | Readiness is available at /api/health. After restart, check the same project and test an existing connection. Preserve the original encryption key. |

## Model generation settings

Enter the exact model ID accepted by the selected text-generation API. The model list is optional. Blank temperature, top-p, reasoning effort and output limits use provider defaults where available. Anthropic Messages requires an output limit. A monthly budget also requires an explicit output limit for cost reservations. A context window of zero delegates the limit to the provider. A positive value budgets the evidence and history sent with the question.

Use a JSON object for additional generation options in the provider's native spelling. For example, Gemini accepts generation settings inside its generationConfig object, so enter the inner fields directly. Use the dedicated fields for output tokens and sampling. Fallback can inherit those fields or use separate values. Each model has its own custom parameters.

**Test Model** sends a short billable generation request with the draft settings. A successful request verifies that combination on that account. Full context capacity is only checked against model metadata when the provider exposes it. Changing the settings or credential invalidates the previous verification.

## First approved publication

1. Use a test project in the existing Jira workspace and a private test Slack channel. Confirm the employee account IDs in the project roster.
2. Upload a scope and approve the source. Generate a plan, edit it and approve it internally. Bind Jira to the local project. Choose **Prepare Jira backlog for review**.
3. Review each draft under **Agents → Automation**. Publish the parent and prerequisites first. The portal uses confirmed remote keys for child issues. Review estimates, acceptance criteria and dates. Dependency ordering in PM AI ES does not itself create Jira link records. Use a reviewed **Jira relationship** action for those.
4. A new Jira project requires a permitted project template and lead account. A board requires an existing authorised filter ID. A Slack channel is created private. Creation and linking are separate actions. Use confirmed channel IDs and roster mappings for invitations.
5. Sync from **Team & delivery**. Check issue or channel IDs in Jira or Slack with the expected user. Open **Reports**, generate an internal draft and send one reviewed test email to yourself. Record those IDs, the report range and receipt time in your acceptance notes.

## Troubleshooting

- **Connection test fails.** Check the displayed category, workspace, selected model and provider billing. Saved settings can be unverified. Retest after changing the selected model or rotating keys.
- **Issue type or field rejected.** Inspect metadata for this Jira project. The board workflow and required custom fields depend on the selected Jira project. Custom field publication needs additional mapping.
- **Slack cannot read history or invite users.** Check bot membership and the app's granted scopes. The UI lists the read capabilities. Channel creation, invitations and notifications need their corresponding permissions.
- **No scheduled report appears.** Confirm the worker is running, the schedule is enabled, the local execution hour has passed and the rule owner's project access is current. Inspect worker logs.
- **An action needs reconciliation.** Look up the exact remote project, channel or email receipt before taking further action. A timeout may occur after the provider accepted a write. The build retains this state and blocks automatic redispatch.
- **Revoke a key.** Use **Revoke** on the relevant connection. To rotate it, enter the replacement, test and save it. Changing an agent configuration invalidates earlier unexecuted action drafts.
