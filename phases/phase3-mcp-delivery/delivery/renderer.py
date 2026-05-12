from typing import List, Dict

def render_markdown_narrative(product_name: str, iso_week: str, insights: List[Dict], max_themes: int = 3) -> str:
    """
    Renders the LLM insights into a clean Markdown narrative for Google Docs.
    Only highlights the top `max_themes` themes (sorted by review count) for a focused weekly note.
    """
    lines = [
        f"# Weekly Product Review Pulse: {product_name}",
        f"**Week:** {iso_week}",
        "---",
        ""
    ]
    
    if not insights or (len(insights) == 1 and insights[0].get("theme_name") == "No Significant Themes"):
        lines.append("## No Significant Themes")
        lines.append("Reviews were too scattered or sparse this week; no significant themes formed.")
        return "\n".join(lines)

    # Sort by review count (largest clusters first) and take top N
    sorted_insights = sorted(insights, key=lambda x: x.get('review_count', 0), reverse=True)
    top_insights = sorted_insights[:max_themes]

    lines.append(f"*Showing top {len(top_insights)} themes out of {len(insights)} identified.*")
    lines.append("")
        
    for idx, insight in enumerate(top_insights, 1):
        theme = insight.get('theme_name', 'Unknown Theme')
        quote = insight.get('quote', '(No exact representative quote found)')
        action = insight.get('action_idea', 'N/A')
        count = insight.get('review_count', '?')
        
        lines.extend([
            f"## {idx}. {theme} ({count} reviews)",
            f"> \"{quote}\"",
            "",
            f"**Actionable Idea:** {action}",
            ""
        ])
        
    return "\n".join(lines)

def render_email_body(product_name: str, iso_week: str, doc_url: str) -> str:
    """
    Renders the HTML email body to send to stakeholders.
    """
    return f"""
    <html>
        <body>
            <h2>Weekly Product Review Pulse: {product_name} ({iso_week})</h2>
            <p>The weekly review pulse analysis for <strong>{product_name}</strong> is complete.</p>
            <p>You can view the full insights, themes, and actionable ideas in the weekly tracker document:</p>
            <p><a href="{doc_url}">View Pulse Document</a></p>
            <br/>
            <p><em>This is an automated message from the Pulse Agent.</em></p>
        </body>
    </html>
    """
