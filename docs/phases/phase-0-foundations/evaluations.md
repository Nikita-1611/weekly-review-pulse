# Phase 0 Evaluations

## Exit Criteria Verification

1. **CLI Commands**: Running `uv run pulse --help` must print the CLI application banner and list all registered subcommands (`ingest`, `cluster`, `summarize`, `render`, `publish`, `run`, `init-db`).
2. **Database Initialization**: Running `uv run pulse init-db` must successfully create the `pulse.db` file (or path defined by `PULSE_DB_PATH`) and establish the exact schemas for `products`, `reviews`, `review_embeddings`, `runs`, and `themes`, including the `sqlite-vec` virtual table.
3. **CI/CD Pipeline**: The `.github/workflows/ci.yml` must execute successfully on an empty repository structure. It must pass:
    - `ruff` linting
    - `mypy` type checking
    - `pytest` for smoke tests.
