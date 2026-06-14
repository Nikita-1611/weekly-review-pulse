---
title: Weekly Review Pulse
emoji: 📈
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
---

# 📈 Weekly Review Pulse

**An automated AI-powered product review aggregator and clustering engine that transforms raw user feedback into actionable weekly digests.**

---

## 🔍 The Problem
Product teams at fast-growing companies receive hundreds of app store reviews every week. Reading every single comment on the Google Play Store and Apple App Store is time-consuming and manual. Critical user complaints—like a new payment bug, app crashes on specific devices, or account access errors—easily get buried under generic reviews. 

Teams need a way to **instantly see what matters most** without manual parsing, so they can prioritize bugs and ship fixes faster.

---

## 💡 The Solution
**Weekly Review Pulse** automates the entire feedback lifecycle:
1. **Aggregates:** Scrapes Play Store and App Store reviews for configured apps (like Groww) on a weekly schedule.
2. **Scrubs & Cleans:** Scrubs Personal Identifiable Information (PII) from user text to ensure compliance and privacy.
3. **Clusters using AI:** Leverages a Large Language Model (LLM) to categorize issues into semantic feedback themes (e.g., *"Peak-Time Trading Lag"*, *"Delayed Deposit Processing"*).
4. **Prioritizes:** Ranks themes by severity (Critical, High, Medium, Low) and highlights representative user quotes.
5. **Delivers:** Automatically writes a weekly digest directly to a Google Doc and emails a beautifully formatted HTML report to stakeholders using Gmail.
6. **Showcases:** Exposes a gorgeous local/web dashboard to track runs, inspect review clusters, and trigger/publish digests manually.

---

## ✨ Key Features
* **Semantic Feedback Themes:** Clusters related reviews together so you can see the volume and severity of specific issues.
* **Ratings & Sentiment Overview:** Visualizes store ratings and tracks the weekly pulse of user sentiment.
* **Representative Quotes:** Extracts actual user quotes for each theme so developers can read first-hand issue descriptions.
* **Auto-Generated Google Docs & Emails:** Seamlessly writes structured summaries to Google Docs and sends HTML emails via Gmail.
* **Interactive Dashboard:** Allows product managers to review historical pipeline runs, preview reports in the browser, and publish digests on demand.
* **Automated Weekly Runs:** A scheduled pipeline runs every Monday morning without human intervention.

---

## 🏗️ How It Works

The project is built around a decoupled architecture split into three main components:

1. **Hugging Face Space (Dashboard & API):** Hosts the interactive dashboard and FastAPI bridge backend. Users can check historical logs, preview drafts, and trigger manual runs.
2. **Render (Model Context Protocol Host):** Hosts a custom **FastMCP** server that manages authentication and execution of the Google Workspace tools (Gmail/Docs APIs). Keeping this server remote keeps the core pipeline stateless and secures OAuth secrets.
3. **GitHub Actions (Pipeline Runner):** Executes the weekly automation pipeline (data fetching, LLM clustering, database synchronization) via a cron schedule.

### Architecture Diagram
```mermaid
graph TD
    subgraph GitHub_Actions [GitHub Actions (Weekly Runner)]
        Pipeline[run_pulse.py Pipeline]
    end

    subgraph Hugging_Face [Hugging Face Space (Dashboard)]
        UI[Interactive HTML Dashboard]
        API[FastAPI Backend]
    end

    subgraph Render [Render (MCP Hosting)]
        MCP[FastMCP Google Workspace Server]
    end

    subgraph External_Services [External Services]
        Supabase[(Supabase PostgreSQL)]
        Groq[Groq API - Llama LLM]
        Google[Google Docs & Gmail APIs]
    end

    %% Flow connections
    Pipeline -->|Read/Write Data| Supabase
    Pipeline -->|Analyze & Cluster| Groq
    Pipeline -->|SSE Call Tools| MCP
    MCP -->|Write Doc / Send Email| Google
    
    API -->|Fetch Reviews & Runs| Supabase
    UI <--> API
    API -->|Trigger Pipeline Runs| Pipeline
```

---

## 🛠️ Tech Stack
* **Backend Framework:** FastAPI (Python)
* **Model Context Protocol (MCP):** FastMCP (SSE Transport)
* **AI Engine:** Groq API (Llama-3 models)
* **Database:** Supabase (PostgreSQL) / SQLite (Fallback)
* **APIs:** Google Workspace APIs (Docs & Gmail via Google Client Libraries)
* **Data Gathering:** Apple iTunes RSS feed & custom Google Play Store scraping
* **Deployment & CI/CD:** Hugging Face Spaces (Docker), Render, GitHub Actions

---

## 🧠 What I Learned & Key Challenges
* **Decoupled Architecture with MCP:** Setting up the Model Context Protocol (MCP) server on Render allowed the ingestion pipeline to remain stateless. Instead of handling complex OAuth authorization files inside ephemeral Docker environments or GitHub Actions runners, the client securely calls remote tools over SSE (Server-Sent Events).
* **Secure Secret Rotation:** Handled secure rotation of Google OAuth Client credentials and active user tokens. Completely purged exposed tokens from the repository's Git history and migrated to environment-variable-based secret loading.
* **Semantic Analysis at Scale:** Fine-tuning LLM prompts to reliably classify and cluster unstructured app store comments, extract exact quotes, and rate issue severity without hallucinating details.

---

## ⚙️ Setup & Environment Variables

To run the pipeline and dashboard locally, configure the following environment variables in a `.env` file in the root directory:

```bash
# LLM Provider Configuration
GROQ_API_KEY=your_groq_api_key

# Database Connection (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres:[PASSWORD]@[HOST]:[PORT]/postgres

# Google Workspace Integration (Omit to run in mock/local mode)
GOOGLE_CREDENTIALS_JSON={"installed": {...}}
GOOGLE_TOKEN_JSON={"token": "...", "refresh_token": "...", ...}

# Remote MCP Server endpoint
MCP_SERVER_URL=https://weekly-review-pulse.onrender.com/sse
```

### Running Locally
1. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Start the API & Dashboard:**
   ```bash
   python run_server.py
   ```
   Open your browser at `http://localhost:8000` to view the dashboard.
