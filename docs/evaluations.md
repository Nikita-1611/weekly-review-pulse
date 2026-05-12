# Phase-wise Evaluations

## Phase 1: Ingestion + PII Scrubbing
- **Data Completeness:** Verify the `app_store_fetcher.py` and `play_store_scraper.py` pull reviews spanning exactly the configured 8-12 week window by asserting the boundaries of the `updated` or `date` fields.
- **Empty Set Handling:** Provide a mocked empty response from the sources and ensure the system correctly skips downstream phases and successfully triggers the "No new reviews" alert email.
- **PII Scrubbing Accuracy:** Run a synthetic dataset containing emails, 10-digit Indian phone numbers (+91 variations), and full names through `pii_scrubber.py` to ensure 100% precision without false positives (e.g., product names should not be scrubbed).
- **Database Integrity:** Validate that the `storage/db.py` SQLite tables accurately enforce primary keys and product constraints.

## Phase 2: Embedding + Clustering + LLM Summarization
- **Clustering Quality:** Calculate the Silhouette score for `clusterer.py` outputs. Ensure the noise ratio is within acceptable bounds. Test the edge case where 100% of reviews are noise to verify the system gracefully skips synthesis.
- **Quote Extraction Accuracy:** Run unit tests specifically targeting `quote_validator.py`. Force the LLM to output modified text and verify that the exact-match substring logic successfully rejects the quote, tests the 2-retry mechanism, and correctly falls back to the placeholder string.
- **Theme Relevance:** Manually inspect the outputs of `synthesizer.py` for 5 distinct test runs to ensure generated themes are actionable and logically derived from the clusters.

## Phase 3: MCP Integration for Docs and Gmail
- **Real MCP Server Validation:** The custom-built FastMCP server is deployed on Render (`https://weekly-review-pulse.onrender.com`) using SSE transport. The `mcp_client.py` connects to the remote `/sse` endpoint (configured via `MCP_SERVER_URL` in `.env`) and calls `write_report` and `send_stakeholder_email` tools.
- **Mocked MCP Validation (Development):** Local FastMCP mock servers (`docs_mock_server.py`, `gmail_mock_server.py`) return malformed payloads (e.g., missing `heading_id` or `message_id`) to verify that the client catches errors and correctly fails fast.
- **Delivery Success:** Confirm that the Google Docs section is appended correctly using the specific anchor format, and that the Gmail notification accurately routes the user directly to the report.

## Phase 4: Idempotency, Delivery Orchestration & Audit Logging
- **MCP Delivery Validation:** Verify that `state_manager.py` correctly triggers `mcp_client.py` to connect to the deployed MCP server on Render (`https://weekly-review-pulse.onrender.com/sse`) via SSE and successfully:
  - Calls `write_report` to push the weekly report to Google Docs.
  - Calls `send_stakeholder_email` to send Gmail notifications to stakeholders.
- **Idempotency Recovery:** Manually force failures by exiting the process midway through each phase. Restart the CLI and verify that `state_manager.py` correctly reads `run_state` and resumes the pipeline exactly where it left off, preventing duplicate Google API calls or re-ingestions.
- **Partial Delivery Resumption:** Simulate a scenario where the Google Doc was updated (`doc_appended`) but the email was not sent. Verify that on the next run, only the Gmail MCP call is made — skipping the Docs step entirely.

## Phase 5: Scheduler + CLI Backfill
- **Config Validation:** Intentionally corrupt `config.yaml` (e.g., remove `google_doc_id`) and verify that `run_pulse.py` fails immediately upon startup.
- **CLI Guardrails:** Attempt to run `run_pulse.py --iso-week <future_week>` and assert that the system rejects the command instantly.
- **Cron Verification:** Validate that `scheduler/cron_config.py` correctly triggers the script on Monday at 8:00 AM IST.

## Production Validation Results
- **Data Volume:** Successfully ingested 242 real reviews for Groww (222 from App Store, 20 from Play Store) using a 12-week rolling window.
- **Clustering:** UMAP + HDBSCAN correctly identified 2 distinct themes from the review corpus.
- **LLM Model:** Confirmed `llama-3.3-70b-versatile` via Groq API produces actionable theme summaries with validated quotes.
- **MCP Server:** Deployed on Render at `https://weekly-review-pulse.onrender.com` with SSE transport. Server responds correctly on `/sse` endpoint.
- **Idempotency:** Verified that clearing `runs` table and re-running the pipeline correctly resumes from the appropriate phase.
