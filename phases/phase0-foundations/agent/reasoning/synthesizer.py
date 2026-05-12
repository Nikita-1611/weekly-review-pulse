import json
from typing import List, Dict
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from agent.reasoning.quote_validator import validate_quote
from agent.config import env_settings
from agent.logger import get_logger

# Pydantic schema for structured LLM output
class InsightSchema(BaseModel):
    theme_name: str = Field(description="A short, descriptive name for the theme.")
    action_idea: str = Field(description="An actionable idea for the product team based on the reviews.")
    quote: str = Field(description="One exact, verbatim quote from the provided reviews that represents the theme.")

def _call_llm_for_theme(cluster_reviews: List[Dict], is_retry: bool = False, run_id: str = "unknown") -> Dict:
    """
    Calls the Groq LLM using LangChain to extract themes, quotes, and propose actions.
    Uses structured output parsing for reliability.
    """
    logger = get_logger(run_id)
    
    if not env_settings.groq_api_key:
        logger.warning("GROQ_API_KEY is not set. Returning mock response.")
        return {
            "theme_name": "Mock Theme (No API Key)",
            "action_idea": "Set GROQ_API_KEY in .env",
            "quote": "Mock quote" if not cluster_reviews else cluster_reviews[0].get("scrubbed_text", "Mock")
        }

    llm = ChatGroq(
        model_name="llama-3.1-8b-instant", # Using 8b for speed, can be upgraded to 70b
        temperature=0.1,
        groq_api_key=env_settings.groq_api_key
    )
    
    # Enforce structured output
    structured_llm = llm.with_structured_output(InsightSchema)
    
    text_blob = "\n".join([f"- {r.get('scrubbed_text', '')}" for r in cluster_reviews])
    
    retry_instruction = "\nCRITICAL: The quote you provide MUST be an EXACT SUBSTRING of the provided text. Do not summarize or alter the quote in any way." if is_retry else ""
    
    prompt = PromptTemplate.from_template("""
    You are a product manager analyzing user reviews.
    Analyze the following user reviews and identify the core theme.
    Provide an actionable idea for the product team.
    Extract one representative verbatim quote exactly as it appears in the text.
    {retry_instruction}
    
    Reviews:
    {text_blob}
    """)
    
    chain = prompt | structured_llm
    
    try:
        result = chain.invoke({
            "text_blob": text_blob,
            "retry_instruction": retry_instruction
        })
        return result.model_dump()
    except Exception as e:
        logger.error(f"Groq LLM call failed: {e}")
        return {
            "theme_name": "Error extracting theme",
            "action_idea": "Investigate LLM failure",
            "quote": "(No exact representative quote found)"
        }

def synthesize_insights(clusters: Dict[int, List[Dict]], all_noise: bool, run_id: str = "unknown") -> List[Dict]:
    """
    Iterates over clusters and uses LLM to generate insights.
    Handles the edge cases for noise and quote hallucination.
    """
    logger = get_logger(run_id)
    
    # Edge case: All reviews fall into HDBSCAN noise
    if all_noise:
        logger.info("Edge Case triggered: All reviews classified as noise. Skipping LLM synthesis.")
        return [{
            "theme_name": "No Significant Themes",
            "action_idea": "N/A",
            "quote": "Reviews were too scattered; no significant themes formed this week."
        }]
        
    insights = []
    
    for cluster_id, reviews in clusters.items():
        if cluster_id == -1:
            continue # Skip the noise cluster
            
        # Attempt LLM Extraction
        llm_output = _call_llm_for_theme(reviews, is_retry=False, run_id=run_id)
        quote = llm_output.get("quote", "")
        
        # Quote Validation Guardrail
        is_valid = validate_quote(quote, reviews)
        retries = 0
        
        while not is_valid and retries < 2:
            logger.warning(f"Quote validation failed for cluster {cluster_id}. Retrying... ({retries+1}/2)")
            llm_output = _call_llm_for_theme(reviews, is_retry=True, run_id=run_id)
            quote = llm_output.get("quote", "")
            is_valid = validate_quote(quote, reviews)
            retries += 1
            
        if not is_valid:
            # Edge Case: LLM returning quotes that fail validation after 2 retries
            logger.warning(f"Edge Case triggered: LLM failed to extract valid quote after 2 retries for cluster {cluster_id}. Dropping quote.")
            llm_output["quote"] = "(No exact representative quote found)"
            
        # Include cluster info
        llm_output["cluster_id"] = cluster_id
        insights.append(llm_output)
        
    return insights
