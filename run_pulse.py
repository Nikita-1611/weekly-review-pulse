import sys
import os
from dotenv import load_dotenv

# Load root .env file explicitly on startup
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(dotenv_path=os.path.join(ROOT_DIR, ".env"), override=True)

import argparse
from pathlib import Path
import datetime
from zoneinfo import ZoneInfo

# 1. Stitch project together by adding phase folders to sys.path
ROOT_DIR = Path(__file__).resolve().parent
PHASES_DIR = ROOT_DIR / "phases"

# Add all phase directories as top-level search paths
sys.path.insert(0, str(PHASES_DIR / "phase0-foundations"))
sys.path.insert(0, str(PHASES_DIR / "phase1-ingestion-storage"))
sys.path.insert(0, str(PHASES_DIR / "phase2-reasoning"))
sys.path.insert(0, str(PHASES_DIR / "phase3-mcp-delivery"))
sys.path.insert(0, str(PHASES_DIR / "phase4-idempotency"))

# Now we can import real logic from across the different phase folders
from agent.storage import init_db, save_reviews, get_reviews_to_embed, save_embeddings, update_review_clusters, get_clustered_reviews, save_themes, get_themes
from agent.logger import setup_logging, get_logger
from agent.helpers import WindowHelper, generate_run_id
from agent.config import yaml_settings

# Real Logic Imports (Stitched from different folders)
from orchestrator.state_manager import StateManager
from orchestrator.audit_logger import audit_step
from ingestion.app_store_fetcher import fetch_app_store_reviews
from ingestion.play_store_scraper import scrape_play_store_reviews
from reasoning.embedder import embed_reviews
from reasoning.clusterer import cluster_embeddings
from reasoning.synthesizer import synthesize_insights
from delivery.renderer import render_markdown_narrative, render_email_body
from delivery.mcp_client import publish_insights


# ─── Phase 5: Config Validation ─────────────────────────────────────────
def validate_config():
    """Validates config.yaml has all required fields. Fails fast if missing."""
    errors = []
    
    if not yaml_settings.products:
        errors.append("config.yaml: 'products' list is empty. At least one product must be defined.")
    
    for p in yaml_settings.products:
        prefix = f"config.yaml -> product '{p.id}'"
        if not p.app_store_id:
            errors.append(f"{prefix}: missing 'app_store_id'")
        if not p.play_store_package:
            errors.append(f"{prefix}: missing 'play_store_package'")
        if not p.google_doc_id or p.google_doc_id == "<PLACEHOLDER_DOC_ID>":
            errors.append(f"{prefix}: missing or placeholder 'google_doc_id'")
        if not p.stakeholder_emails or p.stakeholder_emails == ["<PLACEHOLDER_EMAIL>"]:
            errors.append(f"{prefix}: missing or placeholder 'stakeholder_emails'")
    
    if errors:
        print("\n[ERROR] Configuration Validation Failed:")
        for e in errors:
            print(f"   - {e}")
        print("\nPlease fix config.yaml before running the pipeline.")
        sys.exit(1)
    
    print("[OK] Config validation passed.")


def validate_iso_week(iso_week: str):
    """Validates ISO week format and rejects future weeks. Fails fast."""
    # Format check
    if not WindowHelper.validate_iso_week(iso_week):
        print(f"\n[ERROR] Invalid ISO week format: '{iso_week}'")
        print("   Expected format: YYYY-WNN (e.g., 2026-W18)")
        sys.exit(1)
    
    # Future week check
    year = int(iso_week[:4])
    week = int(iso_week[6:])
    
    ist_now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    current_year, current_week, _ = ist_now.isocalendar()
    
    if year > current_year or (year == current_year and week > current_week):
        print(f"\n[ERROR] Future ISO week rejected: '{iso_week}'")
        print(f"   Current week is {current_year}-W{current_week:02d}. Cannot run for a future week.")
        sys.exit(1)
    
    print(f"[OK] ISO week validated: {iso_week}")

@audit_step("Ingestion", "ingested")
def step_ingestion(prod_config, product_id, run_id=None):
    print("--- Phase 1: Ingesting reviews from stores... ---")
    reviews = []
    window = yaml_settings.rolling_window_weeks
    if prod_config.app_store_id:
        reviews.extend(fetch_app_store_reviews(prod_config.app_store_id, product_id, weeks_window=window))
    if prod_config.play_store_package:
        reviews.extend(scrape_play_store_reviews(prod_config.play_store_package, product_id, weeks_window=window))
    
    save_reviews(reviews)
    print(f"    Done. Ingested {len(reviews)} reviews.")
    return reviews

@audit_step("Clustering", "clustered")
def step_clustering(product_id, run_id=None):
    print("--- Phase 2: Embedding and Clustering reviews... ---")
    to_embed = get_reviews_to_embed(product_id)
    if to_embed:
        # Use scrubbed_text if available, fallback to raw_text
        texts = [r.get('scrubbed_text') or r.get('raw_text') for r in to_embed]
        embeddings = embed_reviews(texts)
        save_embeddings([(r['id'], e) for r, e in zip(to_embed, embeddings)])
    
    # Perform clustering
    import numpy as np
    from agent.storage import get_connection, IS_SQLITE, adapt_query
    conn = get_connection()
    if IS_SQLITE:
        cursor = conn.cursor()
        query = adapt_query("""
            SELECT r.id, r.raw_text, e.embedding 
            FROM reviews r 
            JOIN review_embeddings e ON r.id = e.review_id 
            WHERE r.product_id = %s
        """)
        cursor.execute(query, (product_id,))
    else:
        from psycopg2.extras import DictCursor
        cursor = conn.cursor(cursor_factory=DictCursor)
        cursor.execute("""
            SELECT r.id, r.raw_text, e.embedding 
            FROM reviews r 
            JOIN review_embeddings e ON r.id = e.review_id 
            WHERE r.product_id = %s
        """, (product_id,))
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    
    if rows:
        embeddings_arr = np.array([np.frombuffer(row['embedding'], dtype=np.float32) for row in rows])
        reviews_list = [dict(row) for row in rows]
        clusters, all_noise = cluster_embeddings(embeddings_arr, reviews_list)
        
        # Update DB
        update_data = []
        for c_id, r_list in clusters.items():
            for r in r_list:
                update_data.append((c_id, r['id']))
        update_review_clusters(update_data)
    
    print("    Done. Clustering complete.")
    return True

@audit_step("Synthesis & Drafting", "drafted")
def step_synthesis(product_id, iso_week, run_id=None):
    print("--- Phase 3.1: Summarizing insights into Drafts... ---")
    clusters = get_clustered_reviews(product_id)
    # Check if there are any clusters
    all_noise = not any(c_id != -1 for c_id in clusters.keys())
    
    insights = synthesize_insights(clusters, all_noise=all_noise, run_id=run_id)
    save_themes(run_id, insights)
    print("    Done. Themes drafted and saved.")
    return True

@audit_step("Delivery", "email_sent")
def step_publish(prod_config, product_id, iso_week, run_id=None, action=None):
    print("--- Phase 3.2: Publishing approved Drafts to Docs & Email... ---")
    
    insights = get_themes(run_id)
    if not insights:
        print("No insights found for this run. Cannot publish.")
        return {"status": "failed", "error": "No themes found."}
    
    # Rendering
    markdown = render_markdown_narrative(prod_config.name, iso_week, insights)
    html = render_email_body(prod_config.name, iso_week, f"https://docs.google.com/document/d/{prod_config.google_doc_id}", insights)
    
    # Delivery
    skip_docs = (action == 'resume_email')
    result = publish_insights(
        prod_config.google_doc_id, f"Week {iso_week}", markdown,
        prod_config.stakeholder_emails, html, run_id, skip_docs=skip_docs
    )
    
    if result["status"] == "success":
        # Additional state update for headings/messages
        StateManager.update_run_status(
            run_id, 'email_sent', 
            doc_heading_id=result["heading_id"], 
            email_message_id=result["message_id"]
        )
        print(f"--- Pipeline completed successfully for {product_id}! ---")
        return result
    else:
        raise Exception(f"Publishing failed: {result.get('error')}")

def publish_draft(product_id: str, iso_week: str):
    """Entry point for the API to publish an existing drafted run."""
    setup_logging()
    logger = get_logger("root_orchestrator")
    prod_config = next((p for p in yaml_settings.products if p.id == product_id), None)
    
    action, status, details = StateManager.preflight_check(
        product_id, iso_week, prod_config.google_doc_id, f"Week {iso_week}"
    )
    run_id = details["run_id"]
    
    if status == 'drafted' or action == 'resume_publish' or action == 'resume_docs' or action == 'resume_email':
        step_publish(prod_config, product_id, iso_week, run_id=run_id, action=action)
    else:
        print(f"Cannot publish. Status is {status}. Needs to be drafted.")

def run_pipeline(product_id: str, iso_week: str):
    """Orchestrates the full pipeline across all phase folders."""
    setup_logging()
    logger = get_logger("root_orchestrator")
    
    # Load product config
    prod_config = next((p for p in yaml_settings.products if p.id == product_id), None)
    if not prod_config:
        print(f"Error: Product {product_id} not found in config.")
        return

    print(f"\n[Starting Pulse Pipeline for {product_id} (Week {iso_week})]")

    # 1. Orchestrator Preflight (Phase 4)
    action, status, details = StateManager.preflight_check(
        product_id, iso_week, prod_config.google_doc_id, f"Week {iso_week}"
    )
    run_id = details["run_id"]
    
    if action == 'abort':
        logger.info(f"Pipeline already completed for {product_id} {iso_week}. Aborting.")
        print(f"--- Already completed. Skipping. ---")
        return

    try:
        # 2. Execute Steps based on state
        reviews = []
        if status in ('started', 'failed'):
            reviews = step_ingestion(prod_config, product_id, run_id=run_id)
            status = 'ingested'

        if status == 'ingested':
            if len(reviews) == 0:
                logger.info(f"Edge Case: 0 reviews found for {product_id} this week. Skipping clustering and LLM.")
                # Send empty alert via Gmail only
                html_body = f"<h2>Weekly Pulse: {prod_config.name} (Week {iso_week})</h2><p>No new reviews were found for this 12-week window.</p>"
                import asyncio
                from delivery.mcp_client import call_gmail_mcp
                message_id = asyncio.run(call_gmail_mcp(prod_config.stakeholder_emails, f"Weekly Product Pulse: {prod_config.name} (Empty)", html_body, run_id))
                
                StateManager.update_run_status(run_id, 'email_sent', email_message_id=message_id)
                print(f"--- Pipeline completed successfully (No reviews) for {product_id}! ---")
                return

            step_clustering(product_id, run_id=run_id)
            status = 'clustered'

        if status == 'clustered' or action == 'resume_publish' or action == 'resume_docs' or action == 'resume_email':
            if status == 'clustered':
                step_synthesis(product_id, iso_week, run_id=run_id)
                status = 'drafted'
            
            step_publish(prod_config, product_id, iso_week, run_id=run_id, action=action)

    except Exception as e:
        # audit_step decorator already handles the DB logging for the specific step
        # but we catch it here to print a friendly root message
        print(f"FAILED Pipeline execution stopped: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pulse Master Orchestrator")
    parser.add_argument("--product", type=str, default="groww", help="Product ID or 'all' to run all products")
    parser.add_argument("--week", type=str, help="ISO Week (e.g. 2026-W18). Defaults to current week.")
    
    args = parser.parse_args()
    
    # Phase 5: Validate config before anything else
    validate_config()
    
    iso_week = args.week or WindowHelper.get_current_iso_week()
    
    # Phase 5: Validate ISO week (reject future weeks)
    validate_iso_week(iso_week)
    
    init_db()
    
    if args.product == "all":
        for p in yaml_settings.products:
            run_pipeline(p.id, iso_week)
    else:
        # Validate the product exists in config
        valid_ids = [p.id for p in yaml_settings.products]
        if args.product not in valid_ids:
            print(f"\n[ERROR] Unknown product: '{args.product}'")
            print(f"   Available products: {', '.join(valid_ids)}")
            sys.exit(1)
        run_pipeline(args.product, iso_week)
