import os
import base64
from email.mime.text import MIMEText
from fastmcp import FastMCP
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Define the scopes for Docs and Gmail
SCOPES = [
    'https://www.googleapis.com/auth/documents',
    'https://www.googleapis.com/auth/gmail.send'
]

mcp = FastMCP("GoogleWorkspaceReal")

def get_creds():
    """Handles OAuth2 authentication and token management."""
    creds = None
    # Check current directory and script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = 'token.json' if os.path.exists('token.json') else os.path.join(script_dir, 'token.json')
    creds_path = 'credentials.json' if os.path.exists('credentials.json') else os.path.join(script_dir, 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Use the credentials.json you downloaded
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Missing credentials.json. Checked: {creds_path}")
            
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    return creds

@mcp.tool()
def write_report(doc_id: str, title: str, content: str):
    """Writes the Pulse report to a real Google Doc."""
    try:
        creds = get_creds()
        service = build('docs', 'v1', credentials=creds)
        
        # Prepare the requests to append text to the end of the document
        # Note: We use a simple insertion at the start or append logic
        requests = [
            {
                'insertText': {
                    'location': {'index': 1},
                    'text': f"\n\n--- {title} ---\n{content}\n"
                }
            }
        ]
        
        service.documents().batchUpdate(documentId=doc_id, body={'requests': requests}).execute()
        return {"status": "success", "heading_id": "real_doc_update"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def send_stakeholder_email(to_emails: list, subject: str, body_html: str):
    """Sends a real email to stakeholders using the Gmail API."""
    try:
        creds = get_creds()
        service = build('gmail', 'v1', credentials=creds)
        
        # Create MIME message
        message = MIMEText(body_html, 'html')
        message['to'] = ", ".join(to_emails)
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Send
        service.users().messages().send(userId='me', body={'raw': raw}).execute()
        return {"status": "success", "message_id": "real_email_sent"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    # Use SSE transport for Render (production), stdio for local dev
    port = os.environ.get("PORT")
    if port:
        mcp.run(transport="sse", host="0.0.0.0", port=int(port))
    else:
        mcp.run()
