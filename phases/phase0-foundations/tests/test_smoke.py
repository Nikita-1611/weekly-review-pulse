import os
import sqlite3
from typer.testing import CliRunner
from agent.__main__ import app
from agent.storage import init_db

runner = CliRunner()

def test_cli_help():
    """Smoke test to ensure the CLI loads and prints help."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Weekly Product Review Pulse CLI" in result.stdout
    assert "ingest" in result.stdout
    assert "cluster" in result.stdout

def test_db_initialization(tmp_path):
    """Smoke test to ensure the database initializes with the correct schema."""
    db_file = tmp_path / "test.db"
    
    # Patch the module-level DB_PATH
    import agent.storage
    agent.storage.DB_PATH = str(db_file)
    
    # Run the init-db function
    init_db()
    
    assert db_file.exists()
    
    # Verify tables
    conn = sqlite3.connect(str(db_file))
    conn.enable_load_extension(True)
    import sqlite_vec
    sqlite_vec.load(conn)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    
    assert "products" in tables
    assert "reviews" in tables
    assert "runs" in tables
    assert "themes" in tables
    assert "review_embeddings" in tables
    
    conn.close()
