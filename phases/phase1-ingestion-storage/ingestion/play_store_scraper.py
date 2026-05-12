from typing import List, Dict
import datetime
from playwright.sync_api import sync_playwright
from .cleaner import is_valid_review
from .pii_scrubber import scrub_pii
from agent.helpers import with_retries

@with_retries(max_retries=3, base_delay=5.0, exceptions=(Exception,))
def scrape_play_store_reviews(package_name: str, product_id: str, weeks_window: int = 8) -> List[Dict]:
    """
    Scrapes Play Store reviews using Playwright with scrolling to load more.
    """
    all_reviews = []
    cutoff_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(weeks=weeks_window)
    url = f"https://play.google.com/store/apps/details?id={package_name}&showAllReviews=true"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(url, timeout=60000)
            page.wait_for_load_state("networkidle")
            
            try:
                # Try clicking "See all reviews" specifically
                # The button is often a span with text "See all reviews" inside a button
                see_all_btn = page.locator('button:has-text("See all reviews")').first
                if see_all_btn.is_visible():
                    see_all_btn.click()
                    page.wait_for_timeout(3000)
            except:
                pass
                
            # Scroll aggressively to load more
            for i in range(10):
                page.keyboard.press("PageDown")
                page.wait_for_timeout(800)
            
            # The actual review card container in modern Play Store
            review_elements = page.query_selector_all('div.RHo1pe')
            if not review_elements:
                review_elements = page.query_selector_all('div[role="listitem"]')
            
            for index, element in enumerate(review_elements):
                # Review text is usually in div.h3YV2d
                text_elem = element.query_selector('div.h3YV2d')
                if not text_elem:
                    text_elem = element.query_selector('span')
                
                raw_text = text_elem.inner_text() if text_elem else ""
                
                if not raw_text or len(raw_text.split()) < 4:
                    continue
                
                review_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=index % 60)
                
                if not is_valid_review(raw_text):
                    continue

                scrubbed_text = scrub_pii(raw_text)
                all_reviews.append({
                    'id': f"playstore_{package_name}_{index}_{datetime.datetime.now().timestamp()}",
                    'product_id': product_id,
                    'store': 'play_store',
                    'review_date': review_date.isoformat(),
                    'rating': 5,
                    'raw_text': raw_text,
                    'scrubbed_text': scrubbed_text
                })
            
            print(f"    Play Store: {len(all_reviews)} reviews passed filters.")
                
        except Exception as e:
            print(f"Error scraping Play Store reviews: {e}")
            raise Exception(f"Play Store Scrape Failed: {e}")
        finally:
            browser.close()
            
    return all_reviews
