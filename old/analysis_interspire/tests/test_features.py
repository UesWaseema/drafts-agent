import pandas as pd
from analysis_interspire import features_subject as fs
from analysis_interspire import features_content as fc

def test_char_count():
    s = pd.Series(["ABC", "Hello World", ""])
    expected = pd.Series([3, 11, 0])
    pd.testing.assert_series_equal(fs.char_count(s), expected, check_dtype=False)

def test_caps_ratio():
    s = pd.Series(["AbC", "hello", "WORLD", ""])
    expected = pd.Series([66.66666666666666, 0.0, 100.0, 0.0])
    pd.testing.assert_series_equal(fs.caps_ratio(s), expected, check_dtype=False)

def test_has_call_for_papers():
    s = pd.Series([
        "Call for Papers",
        "call for papers",
        "CALL FOR PAPERS",
        "No match",
        "Call   for   Papers",
        "CallforPapers"
    ])
    expected = pd.Series([1, 1, 1, 0, 1, 0])
    pd.testing.assert_series_equal(fs.has_call_for_papers(s), expected, check_dtype=False)

def test_excess_exclaim():
    s = pd.Series(["Hello!", "What??", "No punctuation", "!!!???"])
    expected = pd.Series([1, 2, 0, 6])
    pd.testing.assert_series_equal(fs.excess_exclaim(s), expected, check_dtype=False)

def test_length_bucket():
    s = pd.Series([
        "Short",
        "This is a medium length subject line.",
        "This is a very very very very very very very very very very very very very very very very very very very very very very very very very very very very long subject line."
    ])

def test_intro_word_count():
    s = pd.Series([
        "<h1>Hello world.</h1><br>More text.",
        "<p>First para.</p><p>Second para.</p>",
        "Plain text line 1\nPlain text line 2",
        "No breaks here, just a long text.",
        "Intro text. Another sentence. And more.",
        "Short.\nNew line.",
        "Very long intro text that should be truncated to 40 words. This is a test to see if the function correctly limits the word count. We need to make sure that even if there are many words, only the first 40 are considered for the count. This helps in focusing on the initial part of the email content.",
        ""
    ])
    expected = pd.Series([2, 2, 3, 8, 3, 2, 40, 0])
    pd.testing.assert_series_equal(fc.intro_word_count(s), expected, check_dtype=False)

def test_has_html_bullets():
    s = pd.Series([
        "<ul><li>Item 1</li><li>Item 2</li></ul>",
        "<ol><li>One</li><li>Two</li></ol>",
        "Just plain text with no bullets.",
        "Text with a • bullet point.",
        "Text with multiple • bullet • points.",
        "No HTML but has a bullet •",
        ""
    ])
    expected = pd.Series([1, 1, 0, 1, 1, 1, 0])
    pd.testing.assert_series_equal(fc.has_html_bullets(s), expected, check_dtype=False)

def test_external_domain_count():
    s = pd.Series([
        "<a href='http://example.com'>Link 1</a>",
        "<a href='http://example.com'>Link 1</a><a href='http://anothersite.com'>Link 2</a>",
        "<a href='mailto:test@example.com'>Email</a>",
        "<a href='http://sub.example.com/path'>Subdomain Link</a>",
        "<a href='http://example.com/path'>Link 1</a><a href='http://example.com/anotherpath'>Link 2</a>", # Same domain
        "<a href='invalid-url'>Invalid</a>",
        "<a href=''>Empty href</a>",
        "<a href='//example.com'>Protocol relative</a>",
        "<a href='/relative/path'>Relative path</a>",
        "No links here."
    ])
    expected = pd.Series([1, 2, 0, 1, 1, 0, 0, 1, 0, 0])
    pd.testing.assert_series_equal(fc.external_domain_count(s), expected, check_dtype=False)

def test_single_cta():
    s = pd.Series([
        "<a href='http://example.com'>Link 1</a>",
        "<a href='http://example.com'>Link 1</a><a href='http://anothersite.com'>Link 2</a>",
        "<a href='mailto:test@example.com'>Email</a>",
        "<a href='http://example.com'>Link</a><a href='http://example.com/unsubscribe'>Unsubscribe</a>",
        "<a href='http://example.com/webversion'>Webversion</a><a href='http://example.com/cta'>CTA</a>",
        "No links here.",
        "<a href='http://example.com/cta'>Only CTA</a>",
        "<a href='http://example.com/cta'>CTA</a><a href='mailto:test@example.com'>Email</a>"
    ])
    expected = pd.Series([1, 0, 0, 0, 0, 0, 1, 1]) # The last one should be 1 because mailto is excluded
    pd.testing.assert_series_equal(fc.single_cta(s), expected, check_dtype=False)

def test_html_bullets_unicode():
    html = "<p>Benefits:</p> • Fast<br> • Easy"
    assert fc.has_html_bullets(pd.Series([html]))[0] == 1

def test_external_domain_count():
    body = '<a href="https://siteA.com/x"></a> <a href="https://blog.siteB.org"></a>'
    assert fc.external_domain_count(pd.Series([body]))[0] == 2

def test_single_cta_filters_system_links():
    body = '<a href="https://good.com">Go</a> <a href="%%webversion%%">view</a>'
    assert fc.single_cta(pd.Series([body]))[0] == 1
