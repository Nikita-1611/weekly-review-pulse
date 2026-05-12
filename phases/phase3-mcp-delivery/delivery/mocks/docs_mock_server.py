from mcp.server.fastmcp import FastMCP
import json

# Initialize FastMCP server for Google Docs
mcp = FastMCP("GoogleDocsMock")

@mcp.tool()
def append_doc_section(doc_id: str, anchor_text: str, content_markdown: str) -> str:
    """
    Appends a new section to a Google Doc.
    Returns a JSON string with success and heading_id.
    """
    print(f"Mocking: Appending section to {doc_id} with anchor {anchor_text}")
    return json.dumps({
        "success": True, 
        "heading_id": f"heading_{anchor_text.replace(' ', '_')}"
    })

@mcp.tool()
def check_doc_section_exists(doc_id: str, anchor_text: str) -> str:
    """
    Checks if a section with the given anchor text exists in the document.
    """
    # Simulate that it does not exist for fresh runs
    return json.dumps({
        "exists": False
    })

if __name__ == "__main__":
    mcp.run()
