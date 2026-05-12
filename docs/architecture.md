# Weekly Product Review Pulse - System Architecture

## 1. System Overview
The Weekly Product Review Pulse is an automated system designed to extract, analyze, and summarize public app store reviews for selected fintech products. By leveraging the Model Context Protocol (MCP), the system securely delegates document and email operations to a custom-built MCP server deployed on Render (`https://weekly-review-pulse.onrender.com`), keeping the core reasoning agent stateless and decoupled from Google Workspace OAuth secrets. The MCP client connects to the remote server via SSE (Server-Sent Events) transport.

## 2. Configuration & Invocation
The system relies on a centralized configuration file to manage product metadata, and a CLI for execution.

### 2.1 Config File Schema (`config.yaml`)
```yaml
products:
  - id: "groww"
    name: "Groww"
    app_store_id: "1404871703"
    play_store_package: "com.nextbillion.groww"
    google_doc_id: "1abcdefghijklmnopqrstuvwxyz12345"
    stakeholder_emails:
      - "product-team@example.com"
  - id: "indmoney"
    name: "INDMoney"
    app_store_id: "1454616202"
    play_store_package: "com.indwealth.app"
    google_doc_id: "1zyxwvutsrqponmlkjihgfedcba54321"
    stakeholder_emails:
      - "leadership@example.com"
```

### 2.2 CLI Command Structure
- Scheduled Run: `python run_pulse.py --product groww` (Defaults to current week minus 1)
- Backfill Run: `python run_pulse.py --product groww --iso-week 2026-W30`

## 3. Core Modules & Flow

### 3.1 Ingestion Module (Data Retrieval)
Responsible for fetching reviews from public sources.
- **Apple App Store Fetcher:** Ingests reviews via the iTunes RSS feed. Exact URL format: `https://itunes.apple.com/rss/customerreviews/page=1/id={app_store_id}/sortby=mostrecent/json`. The rolling window (8-12 weeks) is applied by filtering on the `updated` field in the response to ignore older reviews.
- **Google Play Store Scraper:** Uses a web scraper (e.g., Playwright).
- **PII Scrubbing:** Sanitizes incoming text before processing using the following rules:

  | PII Type | Method | Pattern / Model |
  | :--- | :--- | :--- |
  | Email Addresses | Regex | `[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}` |
  | Phone Numbers | Regex | `(?:\+91[\-\s]?)?[0-9]{10}` |
  | Person Names | NER Fallback | spaCy NER (`en_core_web_sm` model) |

### 3.2 Reasoning & Analysis Engine
Processes the raw reviews to discover actionable insights.
- **Embedding Layer:** Converts reviews into vectors using `BAAI/bge-small-en-v1.5`.
- **Clustering Pipeline (UMAP + HDBSCAN):**
  - **UMAP Hyperparameters:**
    - `n_neighbors=15`: Balances local and global structure, keeping micro-themes distinct.
    - `n_components=5`: Optimal dimensionality reduction for HDBSCAN density clustering without losing variance.
    - `metric='cosine'`: Best suited for text embeddings.
  - **HDBSCAN Hyperparameters:**
    - `min_cluster_size=10`: Ensures themes are statistically significant (noise reduction).
    - `min_samples=5`: Allows slightly complex cluster shapes while preventing single-review outliers from forming clusters.
    - `cluster_selection_epsilon=0.1`: Helps merge highly similar micro-clusters.
- **LLM Summarization & Extraction:** Uses `ChatGroq` with the `llama-3.3-70b-versatile` model to name themes, extract verbatim quotes, and propose actionable product ideas.
- **Quote Validation Guardrail:** Strict exact-match substring validation against the original sanitized review text. Retries up to 2 times before falling back to a placeholder.

### 3.3 SQLite Storage Schemas
```sql
CREATE TABLE reviews (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    store TEXT NOT NULL, -- 'app_store' or 'play_store'
    review_date TEXT NOT NULL,
    rating INTEGER,
    raw_text TEXT,
    scrubbed_text TEXT,
    cluster_id INTEGER,
    ingestion_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE run_state (
    run_id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL,
    iso_week TEXT NOT NULL, -- e.g., '2026-W34'
    status TEXT NOT NULL, -- 'started', 'ingested', 'clustered', 'doc_appended', 'email_sent', 'failed'
    doc_heading_id TEXT,
    email_message_id TEXT,
    error_log TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(product_id, iso_week)
);
```

## 4. MCP Integration (Human-Visible Delivery)

The MCP server is a custom-built **FastMCP** application deployed on **Render** at `https://weekly-review-pulse.onrender.com`. It exposes two tools via **SSE (Server-Sent Events)** transport. The MCP server URL is configured via the `MCP_SERVER_URL` environment variable in `.env`.

### 4.1 Google Docs MCP Tool
- **Tool:** `write_report`
- **Transport:** SSE (`/sse` endpoint)
- **Input Schema:**
  ```json
  {
    "doc_id": "string (from config.yaml)",
    "title": "string (e.g. 'Week 34, 2026 Pulse')",
    "content": "string (Markdown report body)"
  }
  ```
- **Output Schema:**
  ```json
  {
    "status": "success | error",
    "heading_id": "string"
  }
  ```

### 4.2 Gmail MCP Tool
- **Tool:** `send_stakeholder_email`
- **Transport:** SSE (`/sse` endpoint)
- **Input Schema:**
  ```json
  {
    "to_emails": ["string"],
    "subject": "string",
    "body_html": "string"
  }
  ```
- **Output Schema:**
  ```json
  {
    "status": "success | error",
    "message_id": "string"
  }
  ```

### 4.3 MCP Server Deployment
- **Framework:** FastMCP
- **Hosting:** Render (Free Tier)
- **URL:** `https://weekly-review-pulse.onrender.com`
- **Authentication:** Google OAuth2 via `credentials.json` (local) / environment variables (production)
- **Repository Path:** `MCP_Server/`

## 5. Idempotency, Delivery Orchestration & Pre-flight Decision Logic
Phase 4 is the orchestration layer that drives the actual delivery of insights to Google Docs and Gmail via the deployed MCP server (`https://weekly-review-pulse.onrender.com/sse`). It evaluates `run_state` before executing each delivery step, ensuring safe, non-duplicate runs:

1. **Check `run_state` for `(product_id, iso_week)`:**
   - If `status == 'email_sent'`: **Abort** (Run already completed).
   - If `status == 'doc_appended'`: **Resume** at Gmail delivery using stored `doc_heading_id`. Calls `send_stakeholder_email` via MCP SSE.
   - If `status == 'clustered'`: **Resume** at Document Append. Calls `write_report` via MCP SSE to push the report to Google Docs.
   - If `status == 'failed'` or `status == 'started'`: 
     - **Pre-flight Check:** Query the current `run_state` to determine last completed step.
     - Resume from the appropriate phase, calling the MCP server as needed.

**Delivery Flow (Phase 4 → MCP Server):**
```
state_manager.py (Phase 4)
    ↓ checks run_state
mcp_client.py (Phase 3 client)
    ↓ SSE connection
https://weekly-review-pulse.onrender.com/sse
    ↓ Google OAuth2
Google Docs API + Gmail API
```

## 6. End-to-End Orchestration Flow & Error Handling

1. **Initialize Run:** Read config, check idempotency logic (Phase 4).
2. **Data Ingestion:** Fetch from RSS and Scraper (Phase 1).
   - *Error Handling:* Retry 3 times with exponential backoff on HTTP timeouts.
3. **Storage & Scrubbing:** PII removal and insert into `reviews` table (Phase 1). Update state to `ingested`.
4. **Embedding & Clustering:** Generate vectors, run UMAP+HDBSCAN (Phase 2).
5. **LLM Synthesis:** Generate themes, actions, and quotes (Phase 2).
   - *Error Handling:* If quote validation fails, retry LLM extraction up to 2 times. If it still fails, drop the quote or the cluster. Update state to `clustered`.
6. **Google Docs Append (Phase 4 → MCP Server):** Phase 4 orchestrator calls `mcp_client.py` which connects to the Render MCP server via SSE and calls `write_report`.
   - *Error Handling:* Retry 3 times on Google API 5xx errors. Update state to `doc_appended` and save `doc_heading_id`.
7. **Gmail Send (Phase 4 → MCP Server):** Phase 4 orchestrator calls `mcp_client.py` which connects to the Render MCP server via SSE and calls `send_stakeholder_email`.
   - *Error Handling:* Retry 3 times on 5xx errors. Update state to `email_sent` and save `email_message_id`.
8. **Finalize:** Run completed successfully.

## 7. Traceability to Problem Statement
| Requirement | Architecture Component |
| :--- | :--- |
| Ingest App/Play store reviews | Ingestion Module (RSS + Scraper) |
| UMAP+HDBSCAN clustering | Reasoning & Analysis Engine |
| Extract verbatim validated quotes | LLM Summarization + Quote Validation Guardrail |
| Docs/Gmail MCP delivery | Human-Visible Delivery Module |
| Weekly cadence & backfill CLI | CLI Command Structure |
| Idempotent runs | Idempotency & Pre-flight Decision Logic |
| PII Scrubbing | Ingestion Module (Sanitization) |

## 8. Technology Stack
- **Language:** Python 3.12+
- **Machine Learning:** `sentence-transformers` (`BAAI/bge-small-en-v1.5`), `umap-learn`, `hdbscan`
- **LLM:** `ChatGroq` (`llama-3.3-70b-versatile`) via `langchain`
- **Scraping:** `playwright` (Play Store), `requests` (App Store RSS)
- **MCP Integration:** FastMCP (server), MCP Python SDK with SSE transport (client)
- **MCP Hosting:** Render (`https://weekly-review-pulse.onrender.com`)
- **State:** `sqlite3` with `sqlite-vec` for vector storage
- **Google APIs:** `google-api-python-client`, `google-auth-oauthlib`
