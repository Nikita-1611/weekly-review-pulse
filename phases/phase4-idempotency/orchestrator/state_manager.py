from typing import Dict, Any, Optional, Tuple
from agent.storage import get_connection, adapt_query
from agent.helpers import generate_run_id
from agent.logger import get_logger
from delivery.mcp_client import check_doc_section_exists

class StateManager:
    """Manages the state and idempotency logic for the pipeline."""

    @staticmethod
    def get_or_create_run(product_id: str, iso_week: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Fetches an existing run state or creates a new one.
        Returns: (run_id, status, details_dict)
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        cursor.execute(adapt_query("SELECT * FROM runs WHERE product_id = %s AND iso_week = %s"), (product_id, iso_week))
        row = cursor.fetchone()
        
        if row:
            run_id = row["run_id"]
            status = row["status"]
            details = {k: row[k] for k in row.keys()}
        else:
            run_id = generate_run_id()
            status = "started"
            details = {"run_id": run_id, "product_id": product_id, "iso_week": iso_week, "status": status}
            
            cursor.execute(adapt_query("""
                INSERT INTO runs (run_id, product_id, iso_week, status)
                VALUES (%s, %s, %s, %s)
            """), (run_id, product_id, iso_week, status))
            conn.commit()
            
        conn.close()
        return run_id, status, details

    @staticmethod
    def update_run_status(run_id: str, status: str, error_log: str = None, 
                          doc_heading_id: str = None, email_message_id: str = None):
        """Updates the status and optional fields of a specific run."""
        conn = get_connection()
        cursor = conn.cursor()
        
        updates = ["status = %s", "updated_at = CURRENT_TIMESTAMP"]
        params = [status]
        
        if error_log is not None:
            updates.append("error_log = %s")
            params.append(error_log)
        if doc_heading_id is not None:
            updates.append("doc_heading_id = %s")
            params.append(doc_heading_id)
        if email_message_id is not None:
            updates.append("email_message_id = %s")
            params.append(email_message_id)
            
        params.append(run_id)
        
        query = adapt_query(f"UPDATE runs SET {', '.join(updates)} WHERE run_id = %s")
        cursor.execute(query, tuple(params))
        conn.commit()
        conn.close()

    @staticmethod
    def preflight_check(product_id: str, iso_week: str, doc_id: str, anchor_text: str) -> Tuple[str, str, Dict[str, Any]]:
        """
        Implements Architecture §5 Decision Logic.
        Returns the action ('resume', 'restart', 'abort') and the state details.
        """
        run_id, status, details = StateManager.get_or_create_run(product_id, iso_week)
        logger = get_logger(run_id)
        
        if status == 'email_sent':
            logger.info("Run already completed. Aborting.", product=product_id, week=iso_week)
            return 'abort', status, details
            
        elif status == 'doc_appended':
            logger.info("Resuming at Email Generation step.", product=product_id, week=iso_week)
            return 'resume_email', status, details

        elif status == 'drafted':
            logger.info("Resuming at Publishing step.", product=product_id, week=iso_week)
            return 'resume_publish', status, details
            
        elif status == 'clustered':
            logger.info("Resuming at Document Append step.", product=product_id, week=iso_week)
            return 'resume_docs', status, details
            
        elif status in ('failed', 'started'):
            # Pre-flight Check: Did the doc actually append before the crash?
            logger.info("Checking MCP for potential silent successes...", product=product_id, week=iso_week)
            
            # This is a network call to the mock MCP to check if anchor text exists
            exists = check_doc_section_exists(doc_id, anchor_text, run_id)
            
            if exists:
                logger.warning("Found existing document section! Resuming at Email Generation.")
                StateManager.update_run_status(run_id, 'doc_appended')
                details['status'] = 'doc_appended'
                return 'resume_email', 'doc_appended', details
            else:
                logger.info("Starting fresh run.", product=product_id, week=iso_week)
                StateManager.update_run_status(run_id, 'started')
                details['status'] = 'started'
                return 'restart', 'started', details
                
        # Fallback
        return 'restart', status, details
