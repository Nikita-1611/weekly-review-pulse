import emoji
from langdetect import detect, DetectorFactory
from langdetect.lang_detect_exception import LangDetectException

# Ensure consistent results for language detection
DetectorFactory.seed = 0

def is_valid_review(text: str) -> bool:
    """
    Checks if a review meets the cleaning criteria:
    1. Emojis are stripped (handled in ingestion but we don't reject here).
    2. Must be in English.
    3. Must have at least 4 words.
    """
    if not text:
        return False

    # 1. Minimum Word Count (at least 4 words)
    # We strip emojis before counting words to be accurate
    clean_text = emoji.replace_emoji(text, replace='')
    words = clean_text.split()
    if len(words) < 4:
        return False

    # 2. Language Detection (English only)
    try:
        lang = detect(clean_text)
        if lang != 'en':
            return False
    except LangDetectException:
        return False

    return True
