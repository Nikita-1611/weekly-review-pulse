import sys
import os
from pathlib import Path
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import yaml
from typing import List, Optional, Dict
from datetime import datetime


# 1. Stitch project together (same as run_pulse.py)
ROOT_DIR = Path(__file__).resolve().parent
PHASES_DIR = ROOT_DIR / "phases"

sys.path.insert(0, str(PHASES_DIR / "phase0-foundations"))
sys.path.insert(0, str(PHASES_DIR / "phase1-ingestion-storage"))
sys.path.insert(0, str(PHASES_DIR / "phase2-reasoning"))
sys.path.insert(0, str(PHASES_DIR / "phase3-mcp-delivery"))
sys.path.insert(0, str(PHASES_DIR / "phase4-idempotency"))

import run_pulse

from agent.config import yaml_settings
from agent.storage import get_connection, init_db, adapt_query
from agent.helpers import WindowHelper
from run_pulse import run_pipeline

app = FastAPI(title="Pulse API Bridge")

@app.on_event("startup")
def startup_db():
    init_db()
# Enable CORS for the React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the actual origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class Product(BaseModel):
    id: str
    name: str
    app_store_id: Optional[str]
    play_store_package: Optional[str]

class RunStatus(BaseModel):
    run_id: str
    product_id: str
    iso_week: str
    status: str
    updated_at: str

class Review(BaseModel):
    id: str
    product_id: str
    store: str
    rating: int
    text: str
    scrubbed_text: Optional[str]
    cluster_id: Optional[int] = None

# --- Endpoints ---

@app.get("/")
def get_dashboard():
    return FileResponse("pulse_ui_prototype.html")

@app.get("/api/products", response_model=List[Product])
def get_products():
    return [
        Product(
            id=p.id, 
            name=p.name, 
            app_store_id=p.app_store_id, 
            play_store_package=p.play_store_package
        ) for p in yaml_settings.products
    ]

@app.get("/api/reviews", response_model=List[Review])
def get_recent_reviews(product_id: Optional[str] = None, cluster_id: Optional[int] = None, limit: int = 50):
    conn = get_connection()
    query = "SELECT id, product_id, store, rating, raw_text as text, scrubbed_text, cluster_id FROM reviews"
    where_clauses = []
    params = []
    if product_id:
        where_clauses.append("product_id = %s")
        params.append(product_id)
    if cluster_id is not None:
        where_clauses.append("cluster_id = %s")
        params.append(cluster_id)
        
    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += " ORDER BY ingestion_timestamp DESC LIMIT %s"
    params.append(limit)
    
    rows = conn.execute(adapt_query(query), tuple(params)).fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/history", response_model=List[RunStatus])
def get_run_history():
    conn = get_connection()
    rows = conn.execute(adapt_query("SELECT run_id, product_id, iso_week, status, updated_at FROM runs ORDER BY updated_at DESC LIMIT 20")).fetchall()
    conn.close()
    return [dict(row) for row in rows]

@app.get("/api/dashboard/{product_id}")
def get_dashboard_summary(product_id: str):
    conn = get_connection()
    
    # 1. Total Reviews
    total_reviews = conn.execute(adapt_query("SELECT count(*) FROM reviews WHERE product_id = %s"), (product_id,)).fetchone()[0]
    
    # 2. Latest Run
    latest_run = conn.execute(adapt_query("""
        SELECT status, updated_at, iso_week 
        FROM runs 
        WHERE product_id = %s 
        ORDER BY updated_at DESC LIMIT 1
    """), (product_id,)).fetchone()
    
    # 3. Themes (Phase 3 logic)
    # Fetch themes and join with review counts per cluster
    themes_rows = conn.execute(adapt_query("""
        SELECT t.id, t.theme_name, t.quote, t.action_idea, t.cluster_id,
               (SELECT COUNT(*) FROM reviews r WHERE r.cluster_id = t.cluster_id AND r.product_id = %s) as count
        FROM themes t
        WHERE t.run_id = (SELECT run_id FROM runs WHERE product_id = %s ORDER BY updated_at DESC LIMIT 1)
    """), (product_id, product_id)).fetchall()
    
    themes = []
    for row in themes_rows:
        count = row["count"]
        if count > 100:
            importance = "High"
        elif count > 40:
            importance = "Medium"
        else:
            importance = "Low"
            
        themes.append({
            "id": row["id"],
            "theme_name": row["theme_name"],
            "action_idea": row["action_idea"],
            "importance": importance,
            "representative_quote": row["quote"],
            "review_count": count,
            "cluster_id": row["cluster_id"]
        })
    
    # 4. Activity Log
    activity = conn.execute(adapt_query("""
        SELECT status, updated_at 
        FROM runs 
        WHERE product_id = %s 
        ORDER BY updated_at DESC LIMIT 5
    """), (product_id,)).fetchall()
    
    conn.close()
    
    return {
        "total_reviews": total_reviews,
        "latest_run": dict(latest_run) if latest_run else None,
        "themes": [dict(t) for t in themes],
        "activity": [dict(a) for a in activity]
    }

@app.post("/api/trigger/{product_id}")
def trigger_pulse(product_id: str, background_tasks: BackgroundTasks, week: Optional[str] = None):
    # Use local MCP server if set in env, otherwise mcp_client.py defaults to Render
    pass
    
    # Validate product
    valid_ids = [p.id for p in yaml_settings.products]
    if product_id not in valid_ids:
        raise HTTPException(status_code=404, detail="Product not found")
    
    iso_week = week or WindowHelper.get_current_iso_week()
    
    # Run in background
    background_tasks.add_task(run_pipeline, product_id, iso_week)
    
    return {"message": f"Pulse triggered for {product_id} ({iso_week})", "status": "started"}

class ThemeUpdate(BaseModel):
    theme_name: str
    action_idea: str
    quote: str

@app.put("/api/themes/{theme_id}")
def update_theme_endpoint(theme_id: int, theme_update: ThemeUpdate):
    from agent.storage import update_theme
    update_theme(theme_id, theme_update.theme_name, theme_update.action_idea, theme_update.quote)
    return {"status": "success"}

@app.post("/api/publish/{product_id}")
def publish_pulse(product_id: str, background_tasks: BackgroundTasks, week: Optional[str] = None):
    valid_ids = [p.id for p in yaml_settings.products]
    if product_id not in valid_ids:
        raise HTTPException(status_code=404, detail="Product not found")
    
    iso_week = week or WindowHelper.get_current_iso_week()
    from run_pulse import publish_draft
    background_tasks.add_task(publish_draft, product_id, iso_week)
    return {"message": f"Publishing triggered for {product_id} ({iso_week})", "status": "publishing"}

@app.get("/api/email-preview/{product_id}")
def get_email_preview(product_id: str, week: Optional[str] = None):
    valid_ids = [p.id for p in yaml_settings.products]
    if product_id not in valid_ids:
        raise HTTPException(status_code=404, detail="Product not found")
        
    prod_config = next((p for p in yaml_settings.products if p.id == product_id), None)
    iso_week = week or WindowHelper.get_current_iso_week()
    
    # Load actual themes from the database for the preview
    conn = get_connection()
    latest_run = conn.execute(adapt_query("""
        SELECT run_id FROM runs WHERE product_id = %s ORDER BY updated_at DESC LIMIT 1
    """), (product_id,)).fetchone()
    
    insights = []
    if latest_run:
        run_id = latest_run["run_id"]
        # Fetch themes and calculate counts/importance
        themes_rows = conn.execute(adapt_query("""
            SELECT t.theme_name, t.quote, t.action_idea, t.cluster_id,
                   (SELECT COUNT(*) FROM reviews r WHERE r.cluster_id = t.cluster_id AND r.product_id = %s) as count
            FROM themes t
            WHERE t.run_id = %s
        """), (product_id, run_id)).fetchall()
        
        for row in themes_rows:
            count = row["count"]
            if count > 100:
                importance = "High"
            elif count > 40:
                importance = "Medium"
            else:
                importance = "Low"
            insights.append({
                "theme_name": row["theme_name"],
                "quote": row["quote"],
                "action_idea": row["action_idea"],
                "importance": importance,
                "review_count": count
            })
    conn.close()
    
    from delivery.renderer import render_email_body
    from fastapi.responses import HTMLResponse
    
    doc_url = f"https://docs.google.com/document/d/{prod_config.google_doc_id}"
    html_content = render_email_body(prod_config.name, iso_week, doc_url, insights=insights)
    
    return HTMLResponse(content=html_content, status_code=200)

@app.get("/api/health")
def health_check():
    return {"status": "online", "mcp_server": "reachable"} # Mocking MCP check for now

if __name__ == "__main__":
    import uvicorn
    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)
