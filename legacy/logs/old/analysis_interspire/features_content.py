import pandas as pd
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
import tldextract

def intro_word_count(series: pd.Series) -> pd.Series:
    """
    Counts words in the introductory part of the email (first 100 words after stripping HTML).
    """
    def _count(body: str) -> int:
        if not body:
            return 0
        # Strip HTML tags first
        plain_text = BeautifulSoup(body, "lxml").get_text(" ")
        # Split on whitespace and take first 100 words
        words = plain_text.split()
        return min(len(words), 100)

    return series.fillna("").apply(_count).astype("int8")

def has_html_bullets(series: pd.Series) -> pd.Series:
    import re
    from bs4 import BeautifulSoup

    def _detect(body: str) -> int:
        if not body:
            return 0
        soup = BeautifulSoup(body, "lxml")
        # True if any <ul>, <ol>, or <li>
        if soup.find_all(["ul", "ol", "li"]):
            return 1
        plain = soup.get_text(" ")
        # Fallback: unicode bullet • or "* " / "- " at line starts
        if "•" in plain or re.search(r"(?m)^\s*[*-]\s+", plain):
            return 1
        return 0

    return series.fillna("").apply(_detect).astype("int8")

def external_domain_count(series: pd.Series) -> pd.Series:
    import re, tldextract
    href_re = re.compile(r"https?://[A-Za-z0-9._~:/?#@!$&'()*+,;=%-]+", re.I)

    def _count(body: str) -> int:
        if not body:
            return 0
        urls = href_re.findall(body)
        roots = {tldextract.extract(u).registered_domain for u in urls if u}
        roots.discard("")   # safety
        return len(roots)

    return series.fillna("").apply(_count).astype("int8")

def single_cta(series: pd.Series) -> pd.Series:
    from bs4 import BeautifulSoup

    def _calc(body: str) -> int:
        if not body:
            return 0
        soup = BeautifulSoup(body, "lxml")
        anchors = [
            a for a in soup.find_all("a", href=True)
            if not any(x in a["href"].lower() for x in ("unsubscribe", "webversion", "mailto"))
        ]
        return 1 if len(anchors) == 1 else 0

    return series.fillna("").apply(_calc).astype("int8")

if __name__ == "__main__":
    # Example usage for testing
    test_bodies = pd.Series([
        "<p>Hello world.</p><br>More text.",
        "<p>First para.</p><p>Second para.</p>",
        "Plain text line 1\nPlain text line 2",
        "No breaks here, just a long text.",
        "<ul><li>Item 1</li></ul>",
        "<a href='http://example.com'>Link 1</a>",
        "<a href='http://example.com'>Link 1</a><a href='http://anothersite.com'>Link 2</a>",
        "<a href='mailto:test@example.com'>Email</a>",
        "<a href='http://sub.example.com/path'>Subdomain Link</a>",
        "<a href='http://example.com/path'>Link 1</a><a href='http://example.com/anotherpath'>Link 2</a>", # Same domain
        "<a href='invalid-url'>Invalid</a>"
    ])

    print("Intro Word Count:")
    print(intro_word_count(test_bodies))
    print("\nHas HTML Bullets:")
    print(has_html_bullets(test_bodies))
    print("\nExternal Domain Count:")
    print(external_domain_count(test_bodies))
    print("\nSingle CTA:")
    print(single_cta(test_bodies))
