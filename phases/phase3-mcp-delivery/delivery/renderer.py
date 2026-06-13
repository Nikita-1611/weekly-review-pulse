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

def render_email_body(product_name: str, iso_week: str, doc_url: str, insights: List[Dict] = None) -> str:
    """
    Renders a premium HTML email body to send to stakeholders.
    """
    themes_html = ""
    if insights:
        # Filter and show top 3 themes
        sorted_insights = sorted(insights, key=lambda x: x.get('review_count', 0), reverse=True)
        top_insights = sorted_insights[:3]
        
        for idx, insight in enumerate(top_insights, 1):
            theme = insight.get('theme_name', 'Unknown Theme')
            quote = insight.get('quote') or insight.get('representative_quote') or '(No exact representative quote found)'
            count = insight.get('review_count', '?')
            importance = insight.get('importance', 'Medium')
            
            badge_class = "badge-medium"
            if importance in ("High", "Critical"):
                badge_class = "badge-high"
            elif importance == "Low":
                badge_class = "badge-low"
                
            themes_html += f"""
            <div class="theme-item">
                <div class="theme-header">
                    <h4 class="theme-name">{idx}. {theme}</h4>
                    <span class="theme-badge {badge_class}">{importance}</span>
                </div>
                <p class="theme-quote">"{quote}"</p>
                <p class="theme-meta">Mentioned in {count} reviews</p>
            </div>
            """
    else:
        themes_html = "<p style='font-style: italic; color: #64748B; font-size: 14px;'>No significant feedback themes formed for this week's reviews.</p>"

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                background-color: #F8FAFC;
                color: #0F172A;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 30px auto;
                background-color: #FFFFFF;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
                border: 1px solid #E2E8F0;
            }}
            .header {{
                background-color: #00D09C;
                padding: 28px 24px;
                text-align: center;
            }}
            .header h1 {{
                color: #FFFFFF;
                margin: 0;
                font-size: 22px;
                font-weight: 700;
                letter-spacing: -0.5px;
            }}
            .header p {{
                color: #E6FDF9;
                margin: 4px 0 0 0;
                font-size: 13px;
                font-weight: 500;
            }}
            .content {{
                padding: 24px;
            }}
            .welcome {{
                font-size: 14px;
                line-height: 22px;
                color: #334155;
                margin: 0 0 20px 0;
            }}
            .section-title {{
                font-size: 11px;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #64748B;
                margin: 0 0 12px 0;
                border-bottom: 1px solid #F1F5F9;
                padding-bottom: 6px;
            }}
            .theme-item {{
                padding: 14px;
                border: 1px solid #F1F5F9;
                background-color: #F8FAFC;
                border-radius: 12px;
                margin-bottom: 12px;
            }}
            .theme-header {{
                margin-bottom: 6px;
                height: 18px;
            }}
            .theme-name {{
                font-size: 13px;
                font-weight: 700;
                color: #0F172A;
                margin: 0;
                float: left;
            }}
            .theme-badge {{
                font-size: 9px;
                font-weight: 700;
                text-transform: uppercase;
                padding: 2px 8px;
                border-radius: 9999px;
                letter-spacing: 0.5px;
                float: right;
            }}
            .badge-high {{
                background-color: #FEF3C7;
                color: #D97706;
            }}
            .badge-medium {{
                background-color: #EFF6FF;
                color: #2563EB;
            }}
            .badge-low {{
                background-color: #ECFDF5;
                color: #059669;
            }}
            .theme-quote {{
                font-size: 12px;
                font-style: italic;
                color: #475569;
                margin: 12px 0 6px 0;
                line-height: 18px;
                clear: both;
            }}
            .theme-meta {{
                font-size: 10px;
                color: #94A3B8;
                margin: 0;
                font-weight: 500;
            }}
            .cta-container {{
                text-align: center;
                margin: 28px 0 12px 0;
            }}
            .btn {{
                display: inline-block;
                background-color: #00D09C;
                color: #FFFFFF !important;
                text-decoration: none;
                padding: 12px 24px;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 600;
                box-shadow: 0 4px 6px rgba(0, 208, 156, 0.15);
            }}
            .footer {{
                background-color: #F8FAFC;
                padding: 20px;
                text-align: center;
                border-top: 1px solid #F1F5F9;
            }}
            .footer p {{
                font-size: 11px;
                color: #94A3B8;
                margin: 0;
                line-height: 16px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Groww Pulse</h1>
                <p>Weekly Customer Feedback Report • Week {iso_week}</p>
            </div>
            <div class="content">
                <p class="welcome">Hi Team,<br><br>The weekly customer review analysis for <strong>{product_name}</strong> is complete. Here are the top themes identified from recent App Store and Play Store feedback:</p>
                
                <h3 class="section-title">Weekly Themes Preview</h3>
                {themes_html}
                
                <div class="cta-container">
                    <a href="{doc_url}" class="btn" target="_blank">Open Full Google Doc Tracker</a>
                </div>
            </div>
            <div class="footer">
                <p>This is an automated notification from your Groww Pulse pipeline.<br>All review text is scrubbed for PII (names, emails, phone numbers) before processing.</p>
            </div>
        </div>
    </body>
    </html>
    """
