from typing import List, Dict

def validate_quote(generated_quote: str, cluster_reviews: List[Dict]) -> bool:
    """
    Quote Validation Guardrail: Exact-match substring validation against the 
    original sanitized review text.
    Returns True if the generated quote is found verbatim inside any review in the cluster.
    """
    if not generated_quote:
        return False
        
    # Clean up any potential surrounding quotes the LLM might have added
    cleaned_quote = generated_quote.strip().strip('"').strip("'")
    
    for review in cluster_reviews:
        text = review.get('scrubbed_text', '')
        if cleaned_quote.lower() in text.lower():
            return True
            
    return False
