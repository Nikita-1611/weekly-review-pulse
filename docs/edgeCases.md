# Edge Cases & Mitigation Strategies

## Phase 1: Ingestion + PII Scrubbing
- **Empty Review Sets:** No reviews found for a product within the configured 8-12 week window.
  - *Mitigation:* **Skip** the clustering and LLM phases. **Alert** stakeholders via Gmail ("No new reviews for this window"), and mark `run_state` as completed.
- **Network Timeouts during Play Store Scraping:** Playwright fails to load the page or times out.
  - *Mitigation:* **Retry** 3 times using exponential backoff. If it still fails, **Fail Fast**, log the error to `run_state`, and abort the run.
- **App Store RSS Returning Malformed JSON:** The API response is unparseable or changes schema.
  - *Mitigation:* **Fail Fast**. Log the parsing error to `run_state` and abort the run to prevent corrupted data ingestion.
- **PII False Positives:** The spaCy NER model redacts non-PII nouns (e.g., product names like "Groww") as `PERSON`.
  - *Mitigation:* Maintain a configuration allowlist of common fintech and product terms to explicitly exclude from redaction prior to running the NER model.

## Phase 2: Embedding + Clustering + LLM Summarization
- **All Reviews Falling into HDBSCAN Noise:** The clustering algorithm finds no dense regions, classifying all reviews as noise (no clusters formed).
  - *Mitigation:* **Skip** LLM synthesis. Proceed to the Doc append phase, but generate a narrative stating: "Reviews were too scattered; no significant themes formed this week."
- **LLM Quote Hallucination:** The LLM returns quotes that fail the exact-match substring validation.
  - *Mitigation:* **Retry** the LLM extraction up to 2 times with a stricter prompt emphasizing "EXACT SUBSTRING MATCH ONLY". If it still fails, **Drop** the quote and replace it with "(No exact representative quote found)" to preserve factual integrity. Do not fail the entire cluster.

## Phase 3: MCP Integration for Docs and Gmail
- **MCP Server Returning Success but Empty IDs:** The MCP server responds with HTTP 200 but is missing the `heading_id` or `message_id` in the payload.
  - *Mitigation:* **Fail Fast**. Treat this as a delivery failure. Update `run_state` to failed to prevent silent failures and ensure the run is retried later.
- **Network Failure during MCP Call:** The system sends the request to the deployed MCP server (`https://weekly-review-pulse.onrender.com/sse`) via SSE, but times out before receiving a response.
  - *Mitigation:* Handled by Phase 4 idempotency. On the next run, the system will check the current `run_state` and resume from the last successful step.
- **Render Free Tier Cold Start:** The MCP server on Render's free tier may spin down after 15 minutes of inactivity, causing the first request to take 50+ seconds.
  - *Mitigation:* The SSE client will wait for the server to wake up. The pipeline's retry logic handles transient timeouts gracefully.

## Phase 4: Idempotency, Delivery Orchestration & Audit Logging
- **Multiple Concurrent Runs:** Two CLI instances are started simultaneously for the exact same product and ISO week.
  - *Mitigation:* **Fail Fast** for the second instance. The SQLite `UNIQUE(product_id, iso_week)` constraint prevents concurrent database insertions in `run_state`.
- **Partial Run Resumption:** A run crashes midway (e.g., after clustering, before delivery).
  - *Mitigation:* The `state_manager.py` pre-flight check will read the current status (e.g., `clustered`) and safely resume execution at the MCP delivery step. It calls `mcp_client.py` which connects to `https://weekly-review-pulse.onrender.com/sse` to push to Google Docs and Gmail, avoiding duplicate ingestion or LLM processing.
- **Google Doc Appended but Email Not Sent:** The `write_report` MCP call succeeds but the process crashes before `send_stakeholder_email`.
  - *Mitigation:* On the next run, `state_manager.py` sees `status == 'doc_appended'` and skips directly to the Gmail step, calling only `send_stakeholder_email` via the MCP server. No duplicate Google Docs writes.
- **MCP Server Unresponsive:** The Render-deployed MCP server is down or experiencing a cold start.
  - *Mitigation:* The SSE client will timeout gracefully. `state_manager.py` marks the run as `failed`. The next scheduled or manual run will retry the delivery step from the last checkpoint.

## Phase 5: Scheduler + CLI Backfill
- **Config.yaml Missing Required Fields:** `app_store_id` or `google_doc_id` is missing.
  - *Mitigation:* **Fail Fast** on initialization. Validate the configuration schema immediately upon startup and throw an error before any network calls are made.
- **CLI Invoked with Invalid or Future ISO Week:** User attempts to backfill a week that hasn't happened yet.
  - *Mitigation:* **Fail Fast** on initialization. The CLI validates the input week against the current system clock and rejects future dates instantly.

## API Quota & Credit Edge Cases
- **Groq LLM Rate Limiting (429 Too Many Requests):** The Groq API enforces per-minute rate limits on the free tier.
  - *Mitigation:* The Groq SDK includes built-in exponential backoff. The pipeline will automatically wait and retry. If credits are fully exhausted, the run will fail at the synthesis step and can be resumed later without re-ingesting data.
- **Google Cloud API Quotas:** Google Docs and Gmail APIs have daily request limits.
  - *Status:* **Non-issue** for this project's scale. The pipeline makes ~2 API calls per week (1 doc write + 1 email send), which is <0.01% of the daily free quota.
- **Render Free Tier Limits:** The deployed MCP server on Render's free tier may experience cold starts and limited uptime.
  - *Mitigation:* The pipeline handles transient timeouts via the idempotency system. Failed delivery steps are retried on the next run.
