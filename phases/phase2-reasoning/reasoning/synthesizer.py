import os
from typing import List, Dict
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from reasoning.quote_validator import validate_quote
from agent.config import env_settings
from agent.logger import get_logger

# Define Structured Output
response_schemas = [
    ResponseSchema(name="theme_name", description="A short, catchy name for the theme (e.g., 'App Crashes on Login')"),
    ResponseSchema(name="action_idea", description="One specific, actionable recommendation for the product team."),
    ResponseSchema(name="quote", description="One representative verbatim quote from the reviews.")
]
output_parser = StructuredOutputParser.from_response_schemas(response_schemas)
format_instructions = output_parser.get_format_instructions()

def _call_llm_for_theme(cluster_reviews: List[Dict], run_id: str, is_retry: bool = False) -> Dict:
    """
    Invokes Groq via LangChain to extract insights from a cluster of reviews.
    """
    logger = get_logger(run_id)
    
    if not env_settings.groq_api_key:
        logger.warning("GROQ_API_KEY not set. Falling back to dummy response.")
        return {
            "theme_name": "Mock Theme",
            "action_idea": "Mock Action",
            "quote": "Mock Quote"
        }

    # Combine reviews into a single blob (limit to 40 to avoid 6000 TPM limit on free tiers)
    text_blob = "\n".join([f"- {r.get('raw_text', '')}" for r in cluster_reviews[:40]])
    
    chat = ChatGroq(
        groq_api_key=env_settings.groq_api_key,
        model_name="llama-3.1-8b-instant",
        temperature=0.1
    )

    prompt = ChatPromptTemplate.from_template(
        template="""
        You are a product management analyst. Analyze the following user reviews and identify the core theme.
        
        {format_instructions}
        
        {retry_instruction}
        
        Reviews:
        {text_blob}
        """
    )
    
    retry_instruction = "CRITICAL: The 'quote' field MUST be an EXACT SUBSTRING of one of the provided reviews." if is_retry else ""
    
    messages = prompt.format_messages(
        text_blob=text_blob,
        format_instructions=format_instructions,
        retry_instruction=retry_instruction
    )
    
    try:
        response = chat.invoke(messages)
        return output_parser.parse(response.content)
    except Exception as e:
        logger.error(f"LLM Synthesis failed: {e}")
        raise # Fail the pipeline instead of saving junk data

def synthesize_insights(clusters: Dict[int, List[Dict]], all_noise: bool, run_id: str) -> List[Dict]:
    """
    Iterates over clusters and uses LLM to generate insights.
    Handles the edge cases for noise and quote hallucination.
    """
    logger = get_logger(run_id)
    
    # Edge case: All reviews fall into HDBSCAN noise
    if all_noise:
        logger.info("Edge Case: All reviews classified as noise. Skipping LLM synthesis.")
        return [{
            "cluster_id": -1,
            "theme_name": "No Significant Themes",
            "action_idea": "Monitor for new feedback patterns.",
            "quote": "Reviews were too scattered to form distinct themes this week."
        }]
        
    insights = []
    
    # Only process non-noise clusters
    target_clusters = {k: v for k, v in clusters.items() if k != -1}
    
    if not target_clusters:
        return synthesize_insights({}, True, run_id) # Fallback to noise handling

    for cluster_id, reviews in target_clusters.items():
        logger.info(f"Synthesizing theme for cluster {cluster_id} ({len(reviews)} reviews)...")
        
        # Attempt LLM Extraction
        llm_output = _call_llm_for_theme(reviews, run_id, is_retry=False)
        quote = llm_output.get("quote", "")
        
        # Quote Validation Guardrail
        # Note: validate_quote should check if 'quote' is a substring of any 'raw_text' in 'reviews'
        is_valid = validate_quote(quote, reviews)
        retries = 0
        
        while not is_valid and retries < 2:
            logger.warning(f"Quote validation failed for cluster {cluster_id}. Retrying... ({retries+1}/2)")
            llm_output = _call_llm_for_theme(reviews, run_id, is_retry=True)
            quote = llm_output.get("quote", "")
            is_valid = validate_quote(quote, reviews)
            retries += 1
            
        if not is_valid:
            logger.error(f"LLM failed to extract valid quote for cluster {cluster_id}. Dropping quote.")
            llm_output["quote"] = "(No exact representative quote found)"
            
        llm_output["cluster_id"] = cluster_id
        llm_output["review_count"] = len(reviews)
        insights.append(llm_output)
        
    return insights
