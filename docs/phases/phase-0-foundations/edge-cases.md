# Phase 0 Edge Cases

## Configuration Edge Cases
- **Missing `products.yaml`**: `agent/config.py` uses `pydantic`. If the file is missing, the application will raise a validation error or `FileNotFoundError` during startup.
- **Malformed YAML**: `yaml.safe_load()` will raise an exception during parsing.
- **Missing `.env`**: `pydantic-settings` is configured with `extra="ignore"` and uses default values (e.g. `LOG_LEVEL=INFO`) if the file is missing.

## Database Initialization Edge Cases
- **Database Already Exists**: `CREATE TABLE IF NOT EXISTS` is used for all tables, meaning `init-db` is idempotent. Running it multiple times will not drop or truncate existing data.
- **`sqlite-vec` Missing**: If the extension cannot be loaded on the host machine, the application will raise an `sqlite3.OperationalError` immediately upon `init_db`. This enforces the dependency early before any business logic executes.
