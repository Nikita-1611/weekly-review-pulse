import asyncio
import json
import os
from typing import Dict, List, Optional
from mcp import ClientSession
from mcp.client.sse import sse_client
from agent.logger import get_logger
from dotenv import load_dotenv

load_dotenv()

# Read MCP server URL from environment
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "https://weekly-review-pulse.onrender.com/sse")

from agent.helpers import with_retries

@with_retries(max_retries=3, base_delay=2.0, exceptions=(Exception,))
async def call_docs_mcp(doc_id: str, anchor_text: str, content_markdown: str, run_id: str) -> Optional[str]:
    """
    Calls the Google Docs MCP server to append a section via SSE.
    """
    logger = get_logger(run_id)
    
    try:
        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "write_report", 
                    arguments={
                        "doc_id": doc_id,
                        "title": anchor_text,
                        "content": content_markdown
                    }
                )
                if result and result.content:
                    data = json.loads(result.content[0].text)
                    if data.get("status") == "success":
                        return data.get("heading_id")
        return None
    except Exception as e:
        logger.error(f"Failed to call Docs MCP: {e}")
        # Re-raise so the retry decorator can catch it
        raise

@with_retries(max_retries=3, base_delay=2.0, exceptions=(Exception,))
async def call_gmail_mcp(to_emails: List[str], subject: str, body_html: str, run_id: str) -> Optional[str]:
    """
    Calls the Gmail MCP server to send an email via SSE.
    """
    logger = get_logger(run_id)
    
    try:
        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "send_stakeholder_email", 
                    arguments={
                        "to_emails": to_emails,
                        "subject": subject,
                        "body_html": body_html
                    }
                )
                if result and result.content:
                    data = json.loads(result.content[0].text)
                    if data.get("status") == "success":
                        return data.get("message_id")
        return None
    except Exception as e:
        logger.error(f"Failed to call Gmail MCP: {e}")
        # Re-raise so the retry decorator can catch it
        raise

def check_doc_section_exists(doc_id: str, anchor_text: str, run_id: str) -> bool:
    """
    Checks if a section exists using Docs MCP.
    """
    # For the real server, we return False to always attempt a write.
    return False

def publish_insights(doc_id: str, anchor_text: str, markdown_report: str, emails: List[str], html_body: str, run_id: str, skip_docs: bool = False) -> Dict[str, str]:
    """
    Synchronous wrapper to call both MCP servers via SSE.
    """
    logger = get_logger(run_id)
    
    heading_id = "skipped_docs"
    # 1. Append to Docs
    if not skip_docs:
        heading_id = asyncio.run(call_docs_mcp(doc_id, anchor_text, markdown_report, run_id))
        if not heading_id:
            logger.error("Publishing failed at Google Docs step.")
            return {"status": "failed", "step": "docs", "error": "Could not update Google Doc. Check your Doc ID and permissions."}
        
    # 2. Send Email
    message_id = asyncio.run(call_gmail_mcp(emails, "Weekly Product Pulse Ready", html_body, run_id))
    if not message_id:
        logger.error("Publishing failed at Gmail step.")
        return {"status": "failed", "step": "gmail", "error": "Could not send email. Check your stakeholder email list."}
        
    return {
        "status": "success",
        "heading_id": heading_id,
        "message_id": message_id
    }
