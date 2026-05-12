import re
import spacy

# Ensure the spaCy model is downloaded
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    import subprocess
    import sys
    print("Downloading spaCy en_core_web_sm model...")
    subprocess.run([sys.executable, "-m", "spacy", "download", "en_core_web_sm"], check=True)
    nlp = spacy.load("en_core_web_sm")

# Patterns
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
PHONE_REGEX = re.compile(r'(?:\+91[\-\s]?)?[0-9]{10}')

# Allowlist of common fintech terms to NOT scrub even if detected as PERSON by spaCy
ALLOWLIST = {
    "groww", "indmoney", "kuvera", "powerup", "wealth monitor",
    "upi", "sip", "mutual fund", "kyc", "mf", "nfo", "fd"
}

def scrub_pii(text: str) -> str:
    """Removes emails, phone numbers, and Person entities from text."""
    if not text:
        return text
    
    # 1. Regex scrub
    text = EMAIL_REGEX.sub("[EMAIL]", text)
    text = PHONE_REGEX.sub("[PHONE]", text)
    
    # 2. NER fallback for Person names
    doc = nlp(text)
    scrubbed_tokens = []
    
    for token in doc:
        if token.ent_type_ == "PERSON" and token.text.lower() not in ALLOWLIST:
            scrubbed_tokens.append("[PERSON]")
        else:
            scrubbed_tokens.append(token.text_with_ws)
            
    # Re-assemble string
    # spaCy text_with_ws preserves trailing spaces, so just join without space
    scrubbed_text = "".join(scrubbed_tokens)
    return scrubbed_text.strip()
