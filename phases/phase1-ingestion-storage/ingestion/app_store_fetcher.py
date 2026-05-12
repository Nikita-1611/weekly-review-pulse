import requests
import datetime
from typing import List, Dict
from .cleaner import is_valid_review
from .pii_scrubber import scrub_pii

# URL format defined in Architecture
RSS_URL_TEMPLATE = "https://itunes.apple.com/in/rss/customerreviews/id={app_store_id}/page={page}/sortby=mostrecent/json"

from agent.helpers import with_retries

@with_retries(max_retries=3, base_delay=2.0, exceptions=(requests.exceptions.RequestException,))
def _fetch_page(url: str) -> dict:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()

def fetch_app_store_reviews(app_store_id: str, product_id: str, weeks_window: int = 8) -> List[Dict]:
    """
    Fetches reviews from the App Store RSS feed.
    Paginates through the feed and stops when reviews fall outside the weeks_window.
    """
    all_reviews = []
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(weeks=weeks_window)
    
    # The RSS feed allows up to 10 pages typically
    max_pages = 10 
    
    for page in range(1, max_pages + 1):
        url = RSS_URL_TEMPLATE.format(page=page, app_store_id=app_store_id)
        try:
            data = _fetch_page(url)
        except requests.exceptions.RequestException as e:
            raise Exception(f"App Store Fetch Failed for {app_store_id} (Page {page}): {e}")

        feed = data.get('feed', {})
        entries = feed.get('entry', [])
        if isinstance(entries, dict): entries = [entries]
            
        if not entries:
            break
            
        # The first entry in the feed is often metadata about the app itself.
        # Reviews will have an 'author' field.
        found_older_review = False
        
        for entry in entries:
            if 'author' not in entry:
                continue
                
            # Parse 'updated' field
            updated_str = entry.get('updated', {}).get('label', '')
            if not updated_str:
                continue
                
            try:
                # App store RSS updated format: '2023-10-25T08:15:30-07:00'
                updated_date = datetime.datetime.fromisoformat(updated_str).astimezone(datetime.timezone.utc)
            except ValueError:
                continue
                
            if updated_date < cutoff_date:
                found_older_review = True
                continue
                
            review_id = entry.get('id', {}).get('label', '')
            rating = int(entry.get('im:rating', {}).get('label', '0'))
            raw_text = entry.get('content', {}).get('label', '')
            
            # Apply cleaning filters
            if not is_valid_review(raw_text):
                continue
            
            scrubbed_text = scrub_pii(raw_text)

            review_dict = {
                'id': f"appstore_{review_id}",
                'product_id': product_id,
                'store': 'app_store',
                'review_date': updated_date.isoformat(),
                'rating': rating,
                'raw_text': raw_text,
                'scrubbed_text': scrubbed_text
            }
            all_reviews.append(review_dict)
            
        if found_older_review:
            # We hit the chronological cutoff
            break
            
    return all_reviews
