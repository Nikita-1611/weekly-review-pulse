#!/bin/bash
# startup.sh — Reconstructs secrets from HF Space environment variables, then launches the app.
# Set these in your HF Space → Settings → Repository secrets:
#   CONFIG_YAML          — full contents of config.yaml
#   GROQ_API_KEY         — your Groq API key
#   DATABASE_URL         — Supabase PostgreSQL connection string
#   MCP_SERVER_URL       — URL of your deployed MCP server (e.g. https://weekly-review-pulse.onrender.com/sse)
#   GOOGLE_TOKEN_JSON    — contents of MCP_Server/token.json (optional, for MCP server auth)

set -e

echo "[startup] Reconstructing secrets from environment variables..."

# Write config.yaml from secret (if provided)
if [ -n "$CONFIG_YAML" ]; then
    echo "$CONFIG_YAML" > config.yaml
    echo "[startup] config.yaml written."
else
    # Fall back to the example config (read-only dashboard mode)
    cp config.example.yaml config.yaml
    echo "[startup] WARNING: CONFIG_YAML secret not set. Using example config (read-only mode)."
fi

# Write .env from individual secrets
{
    echo "PULSE_DB_PATH=${PULSE_DB_PATH:-/home/user/app/data/pulse.db}"
    echo "PULSE_CONFIG_PATH=config.yaml"
    [ -n "$GROQ_API_KEY" ]    && echo "GROQ_API_KEY=$GROQ_API_KEY"
    [ -n "$DATABASE_URL" ]    && echo "DATABASE_URL=$DATABASE_URL"
    [ -n "$MCP_SERVER_URL" ]  && echo "MCP_SERVER_URL=$MCP_SERVER_URL"
} > .env
echo "[startup] .env written."

# Write MCP Server token.json if provided
if [ -n "$GOOGLE_TOKEN_JSON" ]; then
    echo "$GOOGLE_TOKEN_JSON" > MCP_Server/token.json
    echo "[startup] MCP_Server/token.json written."
fi

echo "[startup] Launching server..."
exec python run_server.py
