import pytest
from agent.orchestrator.state_manager import StateManager
from agent.storage import get_connection, init_db

@pytest.fixture(autouse=True)
def setup_db():
    init_db()
    
def test_get_or_create_run():
    # Clean db
    conn = get_connection()
    conn.execute("DELETE FROM runs")
    conn.commit()
    
    # Create new
    run_id, status, details = StateManager.get_or_create_run("groww", "2026-W19")
    assert status == "started"
    assert run_id is not None
    
    # Get existing
    run_id2, status2, details2 = StateManager.get_or_create_run("groww", "2026-W19")
    assert run_id == run_id2
    assert status2 == "started"
    
def test_update_run_status():
    run_id, _, _ = StateManager.get_or_create_run("groww", "2026-W20")
    StateManager.update_run_status(run_id, "clustered")
    
    _, status, _ = StateManager.get_or_create_run("groww", "2026-W20")
    assert status == "clustered"
    
def test_preflight_check_resume(monkeypatch):
    run_id, _, _ = StateManager.get_or_create_run("groww", "2026-W21")
    StateManager.update_run_status(run_id, "doc_appended")
    
    action, status, _ = StateManager.preflight_check("groww", "2026-W21", "mock_doc", "mock_anchor")
    assert action == "resume_email"
    assert status == "doc_appended"
