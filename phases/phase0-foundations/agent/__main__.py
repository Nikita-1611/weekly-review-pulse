import typer
import sys
import os
from pathlib import Path

# Add external phase folders to sys.path so the CLI can stitch them together
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(BASE_DIR / "phase3-mcp-delivery"))
sys.path.append(str(BASE_DIR / "phase4-idempotency"))

from agent.storage import init_db as _init_db
from agent.logger import get_logger, setup_logging
from agent.helpers import generate_run_id

app = typer.Typer(help="Weekly Product Review Pulse CLI")

@app.command()
def init_db():
    """Initializes the SQLite database with all tables (including vector tables)."""
    setup_logging()
    logger = get_logger("init")
    logger.info("Initializing database...")
    _init_db()
    logger.info("Database initialized successfully.")

@app.command()
def ingest(product: str = typer.Option("all", help="Product ID to ingest")):
    """Ingests reviews from App Store and Play Store."""
    run_id = generate_run_id()
    logger = get_logger(run_id)
    logger.info("Starting ingestion phase...", product=product)

@app.command()
def cluster(product: str = typer.Option("all", help="Product ID to cluster")):
    """Embeds and clusters the ingested reviews."""
    run_id = generate_run_id()
    logger = get_logger(run_id)
    logger.info("Starting clustering phase...", product=product)

@app.command()
def summarize(product: str = typer.Option("all", help="Product ID to summarize")):
    """Extracts themes, actions, and quotes using LLM."""
    run_id = generate_run_id()
    logger = get_logger(run_id)
    logger.info("Starting summarization phase...", product=product)
    
    # Mock cluster data for demonstration
    from agent.reasoning.synthesizer import synthesize_insights
    mock_clusters = {
        0: [{"scrubbed_text": "The app crashes on login every time."}],
        -1: [{"scrubbed_text": "Random noise."}]
    }
    insights = synthesize_insights(mock_clusters, all_noise=False, run_id=run_id)
    logger.info("Insights synthesized.", count=len(insights))
    return insights

@app.command()
def render(product: str = typer.Option("all", help="Product ID to render")):
    """Renders the markdown narrative for the insights."""
    run_id = generate_run_id()
    logger = get_logger(run_id)
    logger.info("Starting rendering phase...", product=product)
    
    from delivery.renderer import render_markdown_narrative, render_email_body
    from agent.helpers import WindowHelper
    
    iso_week = WindowHelper.get_current_iso_week()
    markdown = render_markdown_narrative(product, iso_week, [])
    html = render_email_body(product, iso_week, "http://docs.google.com/mock")
    logger.info("Rendering complete.", md_len=len(markdown))
    return markdown, html

@app.command()
def publish(product: str = typer.Option("all", help="Product ID to publish")):
    """Publishes the insights to Google Docs and sends an email via MCP."""
    run_id = generate_run_id()
    logger = get_logger(run_id)
    logger.info("Starting publish phase...", product=product)
    
    from delivery.mcp_client import publish_insights
    from agent.config import yaml_settings
    
    # Find product config
    prod_config = next((p for p in yaml_settings.products if p.id == product), None)
    if not prod_config:
        logger.error(f"Product {product} not found in config.")
        return
        
    result = publish_insights(
        doc_id=prod_config.google_doc_id,
        anchor_text="Week X",
        markdown_report="Mock Report",
        emails=prod_config.stakeholder_emails,
        html_body="Mock HTML",
        run_id=run_id
    )
    logger.info("Publish result", result=result)

@app.command()
def run(product: str = typer.Option("all", help="Product ID to run full pipeline")):
    """Runs the full E2E pipeline with idempotency and state management."""
    from orchestrator.state_manager import StateManager
    from agent.helpers import WindowHelper
    from agent.config import yaml_settings
    
    products_to_run = [p.id for p in yaml_settings.products] if product == "all" else [product]
    iso_week = WindowHelper.get_current_iso_week()
    
    for prod in products_to_run:
        prod_config = next((p for p in yaml_settings.products if p.id == prod), None)
        if not prod_config:
            print(f"Skipping unknown product: {prod}")
            continue
            
        print(f"--- Starting pipeline for {prod} (Week {iso_week}) ---")
        
        # 1. Preflight Check
        action, status, details = StateManager.preflight_check(
            prod, iso_week, prod_config.google_doc_id, f"Week {iso_week}"
        )
        
        run_id = details["run_id"]
        logger = get_logger(run_id)
        
        if action == 'abort':
            logger.info("Pipeline aborted by orchestrator (already complete).")
            continue
            
        try:
            # 2. Ingest & Cluster (Mocked for now, assuming they succeed)
            if status in ('started', 'failed'):
                logger.info("Executing Ingestion & Clustering...")
                StateManager.update_run_status(run_id, 'clustered')
                status = 'clustered'
                
            # 3. Summarize & Render (Docs Append)
            if status == 'clustered' or action == 'resume_docs':
                logger.info("Executing LLM Summarization & Render...")
                # Call business logic
                from agent.reasoning.synthesizer import synthesize_insights
                from delivery.renderer import render_markdown_narrative, render_email_body
                from delivery.mcp_client import publish_insights
                
                mock_clusters = {0: [{"scrubbed_text": "Mock review"}]}
                insights = synthesize_insights(mock_clusters, all_noise=False, run_id=run_id)
                
                markdown = render_markdown_narrative(prod, iso_week, insights)
                html = render_email_body(prod, iso_week, "http://mock.url")
                
                logger.info("Publishing to Docs & Gmail...")
                result = publish_insights(
                    prod_config.google_doc_id, f"Week {iso_week}", markdown,
                    prod_config.stakeholder_emails, html, run_id
                )
                
                if result["status"] == "success":
                    StateManager.update_run_status(run_id, 'email_sent', doc_heading_id=result["heading_id"], email_message_id=result["message_id"])
                    logger.info("Pipeline completed successfully!")
                else:
                    raise Exception(f"Publishing failed at step: {result.get('step')}")
                    
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            logger.error("Pipeline crashed!", error=str(e))
            StateManager.update_run_status(run_id, "failed", error_log=error_trace)

if __name__ == "__main__":
    app()
