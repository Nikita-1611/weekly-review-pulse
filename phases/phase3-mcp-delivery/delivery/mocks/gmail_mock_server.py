from mcp.server.fastmcp import FastMCP
import json

# Initialize FastMCP server for Gmail
mcp = FastMCP("GmailMock")

@mcp.tool()
def send_email(to: list[str], subject: str, body_html: str, is_draft: bool = True) -> str:
    """
    Sends an email or creates a draft.
    Returns a JSON string with success and message_id.
    """
    print(f"Mocking: Sending email to {to} with subject: {subject}")
    return json.dumps({
        "success": True, 
        "message_id": f"msg_mock_{subject.replace(' ', '_')}"
    })

if __name__ == "__main__":
    mcp.run()
