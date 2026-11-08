# PM AI ES 0.5 · Project knowledge and chat upgrade

## Why a visible document could produce an empty answer

The earlier uploader saved DOCX and XLSX files as originals without extracting their text. A scanned PDF could likewise produce no passages. The previous chat retriever required a keyword match. An approved annex containing a distinctive handover requirement returned zero results for “Summarise my project documents.” The model request then contained no document excerpts. These defects were reproduced or identified in the supplied build. The specific document and running database on the user's laptop were unavailable for diagnosis.

## Install over the existing project

1. Back up the existing PostgreSQL database and retain its matching private .env file. The backup command is in SETUP-GUIDE.md. If developers have modified the application locally, merge the updated source with those changes before starting.
2. Extract the new ZIP into a temporary folder. Copy its PM-AI-ES contents into the existing installation folder. Keep the existing .env, Compose project name and PostgreSQL volume. Running from a different Compose project can open a fresh database.
3. In the existing installation folder run `bash Start.command`. It rebuilds the app and worker, then applies the additive schema updates. Keep the worker running. Existing already-indexed documents retain their passages. Earlier originals with no passages are queued for processing. Earlier project-wide chats remain in **Earlier project chat**.
4. Open http://localhost:8080 and sign in. Check **Documents**. Click **Review** on the file. **Ready** indicates indexed text. Review a failed file's processing message and use **Retry processing** after an applicable correction. Upload an OCR text version for a scanned PDF. Approval is separate from processing.
5. Open **AI PM chat**. The header shows how many project sources are eligible. If **Approved sources only** is enabled under **Agents → Permissions**, approve the relevant document version to make it available. The upgrade uses the existing provider, model and server-side credentials.
6. Start a new chat and ask a question with an answer found only in the uploaded file. Click the source reference and check its excerpt. On a PDF the reference includes the extracted page when known. Earlier indexed documents with blank location metadata can still show their passage text.

## Features in the source

| Area | Behaviour |
|---|---|
| Ingestion | PDF text by page; DOCX paragraphs including table text; XLSX stored cell values; UTF-8 TXT/MD/CSV/JSON. Sources retain original bytes and metadata. Persisted Uploaded, Processing, Ready, Failed and Unsupported states explain availability. |
| Retrieval | Project ID on passage and source; source readiness, approval policy and version authority filters. Lexical ranking includes metadata. Representative passages supply context for broad questions. Explicit historical queries may include labelled superseded excerpts. |
| Citations | Source chips come from exact bracketed IDs in the answer that match supplied excerpts. Open an excerpt or jump to its project passage. A valid reference identifies supplied text; a reviewer must still check whether it supports the model's claim. |
| Chat | New, open, search by title or message, rename and archive; copy, feedback and retry. Edit or regenerate forks a separate chat before the selected user turn and retains the original transcript. |
| Memory | Recent messages, project knowledge and bounded extractive conversation summaries. Relevant earlier turns and summaries from the same user's project chats can supply historical context. New chats are owner-scoped within the project. Existing legacy conversations retain project-level access. |
| Streaming | OpenAI, Anthropic and Gemini stream adapters; frontend parses incremental UTF-8 events, handles errors and supports Stop. Partial replies are not saved as complete answers. Stream parameter rejection before the first output can fall back to buffered generation. |
| Files | Attachments are scoped to a chat unless **Add to project knowledge** is selected. Permanent uploads start as draft evidence. Response OFF records a dated, categorised project note without a generation call. |
| Voice | Browser speech recognition places editable text in the composer. The user submits it explicitly. Browser speech synthesis supplies play/replay, pause/resume and stop. |
| Display | Responsive sidebar and composer, scroll tracking, escaped React text, headings, lists, tables, code blocks, basic syntax colouring and safe HTTP(S) Markdown links. |

## Verification results

| Test | Result and scope |
|---|---|
| Python regression suite | **51 passed.** Includes previous project tests, real text extraction from binary DOCX/PDF/XLSX fixtures, failed/unsupported files, approval filtering, historical selection, long conversation memory and validated citations. |
| Document-to-model HTTP transport | A DOCX carried the unique handover identifier ORCHID-944; another project's document carried FROST-822. The production passage SELECT was run on a SQLite fixture with adapted parameter markers. All three real adapter implementations sent the first project's text to a loopback HTTP fixture and parsed its streamed reply. The other project stayed out of the request. No real provider was contacted. |
| Provider failures | Truncated stream rejected; stream-parameter refusal recovered through buffered text in a fixture. Existing credential-error fixtures passed. |
| React and transport | TypeScript passed. Production React compiled. Server-rendered Markdown/table/code/escaping, fragmented streaming, interrupted streams, credential error display, speech adapter permission-denied/unsupported/transcription and offline chat CRUD tests passed. |
| Docker, PostgreSQL, live providers | The local runtime lacked Docker, PostgreSQL, FastAPI and the PostgreSQL driver. No authorised provider credentials were available. Full-stack upgrade, database persistence and live response quality await the laptop tests below. |
| Browser, audio and concurrency | No interactive browser or microphone was available. Browser visual layout, tactile mobile use, actual transcription/playback, concurrent turns and stop-generation timing need device testing. A provider may bill work already started before cancellation. |

## Laptop acceptance checks

1. Run `bash tests/check-stack.sh` in the project folder. This uses a disposable PostgreSQL volume. Added smoke scenarios cover DOCX ingestion, unique-term search, Response OFF, branching, renaming, project isolation and processing retry.
2. On a disposable installation configured with an authorised provider, run `docker compose exec app python -m tests.live_acceptance`. This creates an internal fixture project, uploads a unique identifier, requires it in a genuine streamed answer, verifies the saved citation and asks a contextual follow-up. Repeat for each required provider. The script reports unconfigured services as skipped.
3. Create two internal projects. Upload different acceptance IDs. Ask about one, inspect the citation, then switch projects and verify the other ID does not appear. Test an outdated scope by approving its replacement. Test a draft with approved-only retrieval enabled.
4. Start two chats in one project. Rename one, search a phrase from its messages, reopen it after refresh and login, and confirm that editing preserves the original branch. Attach a private test file, then try the explicit project knowledge option separately.
5. On the target browser test microphone allow/deny, editable transcription, playback, mobile navigation and stopping a long answer. Stop and restart the stack and verify conversation and document persistence. Keep the same .env and database volume.

## Limits

The system uses bounded lexical retrieval. It has no embedding provider dependency, OCR, image analysis, spreadsheet formula recalculation or full-document PDF layout analysis. Broad answers can sample only the passages that fit the configured budget. PDF and Office documents have file and extraction limits. Approved-only policy excludes conversation-only attachments. Browser speech support and speech processing depend on the device/browser. Offline preview supports sample conversations and notes; genuine model calls and database persistence require the installed application. The bounded extractive summary can omit details in long histories. The current planning workflow's single-pass limit remains in force.

## Changed source

- **Backend:** server/knowledge.py, server/ingest.py, server/chat.py, server/chat_memory.py, server/app.py, server/models.py, server/transport.py, server/schema.sql, server/worker.py.
- **Frontend:** web/ProjectChat.tsx, web/ChatMessage.tsx, web/voice.ts, web/chat.css, web/main.tsx, web/api.ts, demo/api.ts.
- **Tests:** tests/test_knowledge_chat.py, tests/chat-ui.mjs, tests/demo.mjs, tests/smoke.py, tests/live_acceptance.py.
- **Packaging and guidance:** package.json, README.md, QA-REPORT.md, KNOWN-LIMITATIONS.md, this report and rebuilt dist assets.
