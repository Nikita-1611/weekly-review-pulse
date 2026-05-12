# Detailed Implementation Plan - Weekly Product Review Pulse

## Project Folder & File Structure
```text
Lip3/
├── .env                          # Environment variables (MCP_SERVER_URL, GROQ_API_KEY, etc.)
├── .gitignore                    # Protects credentials.json, token.json, .env
├── config.yaml                   # Product configuration (App Store IDs, Doc IDs, emails)
├── requirements.txt              # Root dependencies (ML, scraping, MCP SDK)
├── run_pulse.py                  # Master orchestrator
├── google_mcp_servers.py         # Local MCP server (for development)
├── MCP_Server/                   # Deployed MCP server (Render)
│   ├── google_mcp_servers.py     # FastMCP server with SSE transport
│   ├── requirements.txt          # Server-only dependencies
│   └── README.md
├── phases/
│   ├── phase0-foundations/
│   │   └── agent/
│   │       ├── config.py
│   │       ├── logger.py
│   │       ├── storage.py
│   │       └── helpers.py
│   ├── phase1-ingestion-storage/
│   │   ├── ingestion/
│   │   │   ├── app_store_fetcher.py
│   │   │   ├── play_store_scraper.py
│   │   │   ├── pii_scrubber.py
│   │   │   └── cleaner.py
│   │   └── storage/
│   │       └── db.py
│   ├── phase2-reasoning/
│   │   └── reasoning/
│   │       ├── embedder.py
│   │       ├── clusterer.py
│   │       ├── synthesizer.py
│   │       └── quote_validator.py
│   ├── phase3-mcp-delivery/
│   │   └── delivery/
│   │       ├── mcp_client.py         # SSE client connecting to Render
│   │       ├── renderer.py
│   │       └── mocks/
│   │           ├── docs_mock_server.py
│   │           └── gmail_mock_server.py
│   ├── phase4-idempotency/
│   │   └── orchestrator/
│   │       ├── state_manager.py
│   │       └── audit_logger.py
│   └── phase5-scheduler/
│       └── scheduler/
│           └── cron_config.py
└── docs/
    ├── architecture.md
    ├── implementationPlan.md
    ├── evaluations.md
    └── edgeCases.md
```

## Exact Dependencies (`requirements.txt`)

**Root (Pipeline):**
```text
requests==2.31.0
playwright==1.42.0
spacy==3.7.4
sentence-transformers==2.5.1
umap-learn==0.5.5
hdbscan==0.8.33
langchain==0.1.13
mcp
pyyaml==6.0.1
langdetect==1.0.9
emoji==2.11.0
python-dotenv
```

**MCP Server (`MCP_Server/requirements.txt`):**
```text
fastmcp
google-api-python-client
google-auth-httplib2
google-auth-oauthlib
requests
```

---

## Phase 1: Ingestion + PII Scrubbing
**Objective:** Fetch raw reviews, scrub PII, and persist to SQLite.

**Exact Files to Create:**
- `storage/db.py`: Initializes SQLite schemas (reviews, run_state).
- `ingestion/app_store_fetcher.py`: iTunes RSS integration parsing `updated` field.
- `ingestion/play_store_scraper.py`: Playwright-based scraper.
- `ingestion/pii_scrubber.py`: Applies Regex (emails, +91/10-digit phone) and spaCy NER (`en_core_web_sm`).

**Tasks:**
1. Setup local SQLite database.
2. Implement fetchers for App Store (RSS) and Play Store (Playwright).
3. Implement PII scrubber.

**Edge Cases & Handling:**
- *Empty review sets (no reviews in window):* **Skip** clustering/LLM, **Alert** via Gmail ("No new reviews for this window"), mark state as completed.
- *Network timeouts during Play Store scraping:* **Retry** 3 times with exponential backoff. If it still fails, **Fail Fast** and log error to `run_state`.
- *App Store RSS returning malformed JSON:* **Fail Fast** and log error to `run_state`.

**Exit Criteria:**
Successfully ingest, scrub, and save reviews for all products in `config.yaml` to SQLite without duplicates or PII.

---

## Phase 2: Embedding + Clustering + LLM Summarization
**Objective:** Cluster reviews and extract themes, quotes, and actionable insights.

**Exact Files to Create:**
- `reasoning/embedder.py`: Handles `BAAI/bge-small-en-v1.5` embeddings.
- `reasoning/clusterer.py`: Implements UMAP + HDBSCAN.
- `reasoning/synthesizer.py`: LangChain LLM prompts.
- `reasoning/quote_validator.py`: Exact-match substring validation.

**Tasks:**
1. Generate embeddings for scrubbed reviews.
2. Apply UMAP + HDBSCAN clustering.
3. Synthesize themes, actions, and verbatim quotes.
4. Validate quotes against source texts.

**Edge Cases & Handling:**
- *All reviews fall into HDBSCAN noise (no clusters formed):* **Skip** LLM synthesis. Proceed to Doc append, but generate narrative stating: "Reviews were too scattered; no significant themes formed this week."
- *LLM returning quotes that fail validation after 2 retries:* **Drop** the hallucinated quote. Replace with a placeholder: "(No exact representative quote found)". Do not fail the entire cluster.

**Exit Criteria:**
Output a structured dictionary of verified themes, actions, and exact-match quotes ready for rendering.

---

## Phase 3: MCP Integration for Docs and Gmail
**Objective:** Deliver insights via a custom-built MCP server deployed on Render.

**Exact Files Created:**
- `delivery/mcp_client.py`: SSE-based client that connects to `MCP_SERVER_URL` from `.env` and calls `write_report` and `send_stakeholder_email` tools.
- `delivery/renderer.py`: Converts theme data into Markdown and HTML report formats.
- `delivery/mocks/docs_mock_server.py`: FastMCP-based mock for local development.
- `delivery/mocks/gmail_mock_server.py`: FastMCP-based mock for local development.
- `MCP_Server/google_mcp_servers.py`: **Real MCP server** deployed on Render with SSE transport, using Google OAuth2 for Docs and Gmail API access.

**MCP Server Details:**
- **URL:** `https://weekly-review-pulse.onrender.com/sse`
- **Transport:** SSE (Server-Sent Events)
- **Tools:** `write_report` (Google Docs), `send_stakeholder_email` (Gmail)
- **Authentication:** Google OAuth2 via `credentials.json` / `token.json` (excluded from Git)

**Tasks:**
1. Render markdown narrative.
2. Connect to deployed MCP server via SSE and call `write_report` tool.
3. Call `send_stakeholder_email` tool with deep-link to the Google Doc.

**Edge Cases & Handling:**
- *MCP server returning success but with empty `heading_id` or `message_id`:* **Fail Fast**. Update `run_state` to failed.
- *Render cold start delay:* SSE client waits for the server to respond.

**Exit Criteria:**
Verified updates in the target Google Doc and successfully received summary emails via the deployed Render MCP server.

---

## Phase 4: Idempotency, Delivery Orchestration & Audit Logging
**Objective:** Orchestrate the actual delivery of insights to Google Docs and Gmail via the deployed MCP server on Render. Guarantee safe, repeatable runs without duplication.

Phase 4 is the **brain** that decides when and how to call the MCP server. It uses the `run_state` table to track progress and resume from the last successful step.

**Delivery Flow:**
```
run_pulse.py (orchestrator)
    ↓
state_manager.py (checks run_state)
    ↓ if status == 'clustered'
mcp_client.py → SSE → https://weekly-review-pulse.onrender.com/sse
    ↓                           ↓
    ↓                    write_report() → Google Docs API
    ↓ updates run_state to 'doc_appended'
    ↓
mcp_client.py → SSE → https://weekly-review-pulse.onrender.com/sse
                              ↓
                       send_stakeholder_email() → Gmail API
    ↓ updates run_state to 'email_sent'
```

**Exact Files Created:**
- `orchestrator/state_manager.py`: Handles the preflight decision logic based on `run_state`. Determines whether to call `write_report` (Google Docs) and/or `send_stakeholder_email` (Gmail) via the MCP server.
- `orchestrator/audit_logger.py`: Logs step-by-step progress to SQLite.

**Tasks:**
1. Check `run_state` for the current `(product_id, iso_week)`.
2. If not yet delivered, call `mcp_client.py` to connect to the Render MCP server via SSE and push the report to Google Docs using `write_report`.
3. Update `run_state` to `doc_appended` and save the `heading_id`.
4. Call `mcp_client.py` again to send a stakeholder notification email via `send_stakeholder_email`.
5. Update `run_state` to `email_sent` and save the `message_id`.

**Edge Cases & Handling:**
- *Run already completed (`email_sent`):* **Abort** immediately. No duplicate API calls.
- *Partial delivery (doc appended but email not sent):* **Resume** from Gmail step only. Skips Google Docs.
- *MCP server returns error:* Mark `run_state` as `failed`. Next run will retry from the failed step.

# Weekly Product Review Pulse: Full System Integration

We have successfully unified the 5-phase pipeline into a single, cohesive orchestration workflow.

## Component Status

| Phase | Description | Status | Key Modules |
| :--- | :--- | :--- | :--- |
| **Phase 0** | Foundations (DB, Logging, Config) | ✅ **Completed** | `storage.py`, `logger.py`, `config.py` |
| **Phase 1** | Ingestion & PII Scrubbing | ✅ **Completed** | `app_store_fetcher.py`, `pii_scrubber.py` |
| **Phase 2** | Reasoning (Embedding & Clustering) | ✅ **Completed** | `embedder.py`, `clusterer.py`, `synthesizer.py` |
| **Phase 3** | Delivery (MCP & Rendering) | ✅ **Production (Render SSE)** | `renderer.py`, `mcp_client.py`, `MCP_Server/` |
| **Phase 4** | Idempotency, Delivery & Audit | ✅ **Production (MCP → Docs + Gmail)** | `state_manager.py`, `audit_logger.py`, `mcp_client.py` |
| **Phase 5** | Scheduler | ✅ **Completed** | `cron_config.py` |

## Unified Orchestration (`run_pulse.py`)

The root `run_pulse.py` acts as the master brain. It manages `sys.path` to allow imports across phase folders without physical merging. It uses a decorator-based audit system to ensure every step is logged and idempotent.

## Final Verification
1. **PII Scrubbing**: Reviews are now automatically scrubbed for Names, Emails, and Phone numbers before being stored/clustered.
2. **LLM Integration**: The synthesizer uses `ChatGroq` (`llama-3.3-70b-versatile`) to generate real insights.
3. **Resumption**: If a run fails (e.g., due to network error), running the script again will automatically resume from the last successful step.
4. **Environment**: IDE warnings have been resolved via root `.env` and `settings.json`.

**Tasks:**
1. Implement `config.yaml` validation.
2. Implement CLI arguments `--product` and `--iso-week`.
3. Setup `cron` for Monday 8:00 AM IST: `0 8 * * 1 TZ=Asia/Kolkata python /path/to/run_pulse.py --product all`

**Edge Cases & Handling:**
- *config.yaml missing required fields:* **Fail Fast** on initialization. Throw an immediate validation error.
- *CLI invoked with invalid or future ISO week:* **Fail Fast** on initialization. Reject the argument before querying databases.

**Exit Criteria:**
Crontab is successfully registered, and the CLI can reliably backfill historical weeks.

---

## Testing Strategy & FastMCP Mocking
1. **Phase 1 Testing:** Use a static HTML snapshot of the Play Store and a cached JSON of the iTunes RSS to run deterministic ingestion and PII validation tests without network calls.
2. **Phase 2 Testing:** Pass a hardcoded array of standard review strings (e.g., "App crashes on login") and assert that they correctly form a single cluster. Provide the quote validator with intentionally modified text to verify the rejection logic.
3. **Phase 3 & 4 Testing:**
   - **Development:** Run local **FastMCP mock servers** (`docs_mock_server.py`, `gmail_mock_server.py`) to simulate the MCP ecosystem.
   - **Production:** Connect to the deployed MCP server on Render (`https://weekly-review-pulse.onrender.com/sse`) via SSE transport. The `MCP_SERVER_URL` in `.env` controls which server the pipeline connects to.
   - Use mocks to test idempotency state recovery (e.g., simulating a successful doc append that the orchestrator missed).

---

## Risk and Mitigation Table

| Risk Area | Specific Threat | Mitigation Strategy |
| :--- | :--- | :--- |
| **Play Store Scraping** | Google blocks the Playwright scraper due to bot detection. | Implement generous randomized delays. If completely blocked, fail gracefully, log to `run_state`, and alert the team to update selectors/headers. |
| **LLM Output** | LLM continuously hallucinates quotes despite strict prompts. | The 2-retry Guardrail mechanism. If it continually fails, drop the quote and output "(No exact representative quote found)" rather than publishing a fake quote. |
| **MCP Server Downtime** | Google Docs or Gmail MCP servers are offline during the Monday run. | `state_manager.py` idempotency ensures the run fails safely. When the cron (or a manual trigger) runs again, it will skip ingestion and immediately resume the MCP calls. |
| **Duplicate Doc Sections** | Network timeouts cause the agent to think the append failed, but it actually succeeded on Google's end. | Pre-flight check queries the Google Docs MCP to search for the specific `anchor_text` (`Week X, 2026 Pulse`) before attempting a fresh append. |
