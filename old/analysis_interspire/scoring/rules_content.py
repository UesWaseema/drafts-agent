import pandas as pd
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import tldextract

def calculate_content_scores(html_body: str) -> dict:
    """
    Calculates various scores for the email content based on predefined rules.
    """
    if not isinstance(html_body, str):
        html_body = ""

    soup = BeautifulSoup(html_body, 'html.parser')
    body_plain = soup.get_text()

    # Initialize scores
    intro_score = 0
    bullets_score = 0
    cta_score = 0
    external_domains_score = 0
    structure_score = 0
    html_validation_score = 0
    mobile_friendly_score = 0
    email_content_score = 0

    # 1. Intro Word Count (re-using logic from features_content)
    def _intro_word_count(text):
        if not isinstance(text, str):
            return 0
        clean_text = BeautifulSoup(text, 'html.parser').get_text()
        split_point = -1
        newline_match = re.search(r'\n', clean_text)
        period_space_match = re.search(r'\. ', clean_text)

        if newline_match and period_space_match:
            split_point = min(newline_match.start(), period_space_match.start())
        elif newline_match:
            split_point = newline_match.start()
        elif period_space_match:
            split_point = period_space_match.start()
        
        if split_point != -1:
            intro_text = clean_text[:split_point]
        else:
            intro_text = clean_text
        words = intro_text.split()
        return min(len(words), 40)

    intro_word_count_val = _intro_word_count(html_body)
    if 10 <= intro_word_count_val <= 30: # Example rule for intro score
        intro_score = 20
    elif intro_word_count_val > 0:
        intro_score = 10
    else:
        intro_score = -10

    # 2. Has HTML Bullets (re-using logic from features_content)
    def _has_html_bullets(text):
        if not isinstance(text, str):
            return 0
        soup_bullets = BeautifulSoup(text, 'html.parser')
        if soup_bullets.find_all(['ul', 'ol']):
            return 1
        body_plain_bullets = soup_bullets.get_text()
        if '•' in body_plain_bullets:
            return 1
        return 0

    if _has_html_bullets(html_body) == 1:
        bullets_score = 10

    # 3. Single CTA (re-using logic from features_content)
    def _single_cta(text):
        if not isinstance(text, str):
            return 0
        soup_cta = BeautifulSoup(text, 'html.parser')
        valid_cta_count = 0
        for a_tag in soup_cta.find_all('a', href=True):
            href = a_tag['href']
            if any(keyword in href for keyword in ['unsubscribe', 'webversion', 'mailto:']):
                continue
            valid_cta_count += 1
        return 1 if valid_cta_count == 1 else 0

    if _single_cta(html_body) == 1:
        cta_score = 20
    else:
        cta_score = -10

    # 4. External Domain Count (re-using logic from features_content)
    def _external_domain_count(text):
        if not isinstance(text, str):
            return 0
        soup_domains = BeautifulSoup(text, 'html.parser')
        domains = set()
        for a_tag in soup_domains.find_all('a', href=True):
            href = a_tag['href']
            if not href:
                continue
            if href.startswith('mailto:'):
                continue
            try:
                parsed_uri = urlparse(href)
                if parsed_uri.netloc:
                    extracted = tldextract.extract(parsed_uri.netloc)
                    domain = f"{extracted.domain}.{extracted.suffix}" if extracted.suffix else extracted.domain
                    if domain:
                        domains.add(domain)
            except Exception:
                pass
        return len(domains)

    ext_domain_count_val = _external_domain_count(html_body)
    if ext_domain_count_val <= 2: # Example rule for external domains
        external_domains_score = 15
    elif ext_domain_count_val <= 5:
        external_domains_score = 5
    else:
        external_domains_score = -5

    # 5. HTML Validation Score (simple heuristic)
    html_validation_score_temp = 0
    if soup.find('html') and soup.find('body'):
        html_validation_score_temp += 5
    if not soup.find(style=True): # Check for inline styles
        html_validation_score_temp += 5
    if soup.find('meta', attrs={'name': 'viewport'}):
        html_validation_score_temp += 5
    html_validation_score = min(html_validation_score_temp, 15) # Cap at 15

    # 6. Mobile Friendly Score (simple heuristic)
    # This is a placeholder. Real mobile-friendliness requires more complex analysis.
    if soup.find('meta', attrs={'name': 'viewport'}):
        mobile_friendly_score = 10 # Basic check for viewport meta tag

    # 7. Structure Score (placeholder)
    # This would involve checking for proper heading usage, paragraph breaks, etc.
    # For now, a simple check for presence of some common tags.
    if soup.find('h1') or soup.find('h2') or soup.find('p'):
        structure_score = 10

    # Calculate overall email content score
    email_content_score = (
        intro_score +
        bullets_score +
        cta_score +
        external_domains_score +
        structure_score +
        html_validation_score +
        mobile_friendly_score
    )

    return {
        "intro_score": intro_score,
        "bullets_score": bullets_score,
        "cta_score": cta_score,
        "external_domains_score": external_domains_score,
        "structure_score": structure_score,
        "html_validation_score": html_validation_score,
        "mobile_friendly_score": mobile_friendly_score,
        "email_content_score": email_content_score,
    }

if __name__ == "__main__":
    # Example usage
    test_html_bodies = [
        "<html><head><meta name='viewport' content='width=device-width'></head><body><h1>Welcome</h1><p>This is an intro. More text.</p><ul><li>Item</li></ul><a href='http://example.com'>CTA</a></body></html>",
        "<div>No HTML or body tags. Just text.</div>",
        "<html><body><p style='color:red;'>Inline style.</p><a href='http://spam.com'>Spam</a><a href='mailto:a@b.com'>Email</a></body></html>",
        "<html><body><p>Intro text.</p><a href='http://one.com'>1</a><a href='http://two.com'>2</a><a href='http://three.com'>3</a><a href='http://four.com'>4</a><a href='http://five.com'>5</a><a href='http://six.com'>6</a></body></html>",
        "<html><body><p>Intro text.</p><a href='http://one.com'>1</a></body></html>",
        "<html><body><p>Intro text.</p><a href='http://one.com'>1</a><a href='http://example.com/unsubscribe'>Unsubscribe</a></body></html>",
        "<html><body><p>Intro text.</p></body></html>"
    ]

    for i, html_body in enumerate(test_html_bodies):
        print(f"\n--- Test Case {i+1} ---")
        scores = calculate_content_scores(html_body)
        for k, v in scores.items():
            print(f"{k}: {v}")
