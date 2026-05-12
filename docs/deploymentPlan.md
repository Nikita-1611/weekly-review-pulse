# Deployment Architecture Plan: Render Dashboard + Supabase

Since your MCP Server is already successfully running on Render and your code is on GitHub, we only need to deploy the **Dashboard / API** and migrate the database to **Supabase**.

## Step 1: Migrate SQLite to Supabase (PostgreSQL)
Our current code is tightly coupled to SQLite (`sqlite3` module, `INSERT OR REPLACE`, `?` parameter bindings, and `sqlite-vec`). We need to update the data layer to support PostgreSQL.

**Actions:**
1.  **Add Dependencies:** Add `psycopg2-binary` to `requirements.txt`.
2.  **Refactor `storage.py` & `state_manager.py`:**
    *   Change the connection logic to connect via `DATABASE_URL` using `psycopg2` instead of `sqlite3`.
    *   Rewrite `?` parameter bindings to `%s` for Postgres.
    *   Rewrite `INSERT OR IGNORE` to `INSERT ... ON CONFLICT DO NOTHING`.
    *   Rewrite `INSERT OR REPLACE` to `INSERT ... ON CONFLICT (...) DO UPDATE ...`.
    *   Replace `sqlite-vec` virtual table creation with standard Postgres `BYTEA` or `pgvector` column types since we only use it for raw storage before passing to Python's HDBSCAN.

> [!WARNING]
> This is a structural change to the data layer. We will test it thoroughly before deploying.

## Step 2: Prepare Dockerfile for the Dashboard
Since the MCP server is remote, we don't need a complex start script. 
1. The existing `Dockerfile` already ends with `CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]`. This is perfect for Render.
2. We will just ensure all necessary packages (like `psycopg2-binary`) are included.

## Step 3: Deployment Checklist for You
Once the code changes are complete, you will need to do the following in your accounts:

1.  **Supabase:** Create a new project, copy the `Transaction` Connection String (starts with `postgresql://`).
2.  **GitHub:** Commit and push the changes.
3.  **Render:** 
    *   Create a New Web Service connected to this repository.
    *   Set the Build Command to use Docker.
    *   Set the following Environment Variables:
        *   `DATABASE_URL` = (Your Supabase string)
        *   `GROQ_API_KEY` = (Your Groq key)
        *   `MCP_SERVER_URL` = (The URL of your existing Render MCP Server, e.g., `https://mcp-server-xyz.onrender.com/sse`)

## Open Questions

> [!IMPORTANT]
> Shall I begin **Step 1** (Migrating the codebase to PostgreSQL/Supabase)?
