"""
Gemini-powered HTML formatter for CFP drafts.
Put this file next to your other `agent_*.py` helpers.
"""

from __future__ import annotations
import re, textwrap, unicodedata
from typing import Tuple

from crewai import Agent, Task, Crew, Process
from common import gpt4o_llm   
# ── 1. System / back-story prompt ───────────────────────────────────
HTML_SYSTEM_PROMPT = """
You are an expert HTML formatter.

HARD RULES
1. Never add or rewrite content—re-format exactly what the user gives you.
2. If the draft already has headings, keep them. Otherwise apply the
   Template-One headings (Introduction, Scope, Types of Articles, Metrics,
   Bibliography, Closing Note, signature block).
3. Use only these tags: <p>, <ul>, <li>, <strong>, <em>, <u>, <a>.
4. Convert every full URL (http / https) and every e-mail address into a
   clickable link; do NOT shorten or rename.
5. Bold the journal name + ISSN the first time they appear. Bold the words
   “Fee Waiver” and the waiver date if present.
6. Signature / Closing block:  
   • Detect the final greeting line (e.g. “Warm Regards,” “Kind regards,”  
     “Sincerely,” etc.).  
   • Wrap that line and every following line in **one <p>** element and
     separate each printed line with <br> tags, e.g.:

     <p>Warm Regards,<br>
        {{sender_name}}<br>
        Editorial Office<br>
        {{journal_name}}<br>
        616 Corporate Way, Suite 2-6158<br>
        Valley Cottage, NY 10989<br>
        United States<br>
        Email: <a href="mailto:sender@journal.org">sender@journal.org</a></p>

   • Do not alter the text—just wrap and preserve it.
7. Output **pure HTML, nothing else** – no <html>, <head>, <body>, no “Sure,
   here is the HTML:” prose, no markdown fences.
8. Side headings – wrap in <p> tags only, and never use ALL CAPS.
"""

"""
Gemini-powered HTML + plain-text formatter for CFP drafts  – final version
Put this file next to your other `agent_*.py` helpers.
"""

        # your CustomLiteLLM wrapper (Gemini 2.5)

# ────────────────────────────────────────────────────────────────
# 0.  Domain → application helper
# ────────────────────────────────────────────────────────────────
INTERSPIRE_DOMAINS = {"CFP10", "CFP12", "CFP9", "CFP4", "CFP2"}
MAILWIZZ_DOMAINS   = {"NCFP9", "NCFP10", "NCFP11", "NCFP12"}

def which_app(domain_code: str) -> str:
    if domain_code in INTERSPIRE_DOMAINS:
        return "interspire"
    if domain_code in MAILWIZZ_DOMAINS:
        return "mailwizz"
    raise ValueError(f"Unknown domain code: {domain_code!r}")

# ────────────────────────────────────────────────────────────────
# 1.  Header / footer templates
# ────────────────────────────────────────────────────────────────
INT_HEADER = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>Research</title></head>
<body><table border="0" align="center" style="width: 600px; margin-left: auto; margin-right: auto;"><tbody><tr><td>
<p>Dear Dr. %%First Name%%,</p>
"""
INT_FOOTER = """</td></tr></tbody></table></body></html>"""

MW_HEADER_TMPL = """<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta http-equiv="Content-Type" content="text/html; charset=iso-8859-1" />
<title>{journal_shortname}</title>
<link id="dark-mode-custom-link" rel="stylesheet" type="text/css" />
<link id="dark-mode-general-link" rel="stylesheet" type="text/css" />
<style id="dark-mode-custom-style" lang="en" type="text/css"></style>
<style id="dark-mode-native-style" lang="en" type="text/css"></style>
<style id="dark-mode-native-sheet" lang="en" type="text/css"></style>
</head>
<body data-gr-ext-disabled="forever" data-gr-ext-installed="" data-new-gr-c-s-check-loaded="14.1240.0" data-new-gr-c-s-loaded="14.1240.0">
<table align="left" border="0" style="width: 620px; margin-left: auto; margin-right: auto;"><tbody><tr>
<td style="font-family:Lucida Sans Unicode,Lucida Grande,sans-serif;">
<p>Dear Dr. [NAME],</p>
"""

MW_FOOTER = """<p>If you prefer not to receive further updates, you can <a href="[DIRECT_UNSUBSCRIBE_URL]">Unsubscribe</a>.</p>
</td></tr></tbody></table></body></html>"""

def wrap_with_template(body_html: str, domain_code: str, journal_shortname: str) -> str:
    if which_app(domain_code) == "interspire":
        return INT_HEADER + body_html + INT_FOOTER
    return MW_HEADER_TMPL.format(journal_shortname=journal_shortname) + body_html + MW_FOOTER

# ────────────────────────────────────────────────────────────────
# 2.  System prompt & agent
# ────────────────────────────────────────────────────────────────
HTML_SYSTEM_PROMPT = """
You are an expert HTML formatter.
(Hard rules 1-7 unchanged; header/footer handled outside)"""

gemini_html_agent = Agent(
    role="HTML Formatter",
    goal="Return pure, production-ready HTML e-mail bodies.",
    backstory=HTML_SYSTEM_PROMPT,
    llm=gpt4o_llm,
    verbose=False,
    allow_delegation=False,
)

HTML_TEMPLATE = """
# Convert this CFP e-mail to production-ready HTML
## Requirements
* Use inline CSS or very light styles – it must render cleanly in email clients.
* Preserve **all headings, paragraphs, and bullet structure** exactly.
* Do **not** invent new copy.
* Replace line-breaks with <br> where appropriate.
* Return only the HTML string – no markdown fences, no commentary.

## Input (plain-text)
{plain_email}

## Output
"""

# ────────────────────────────────────────────────────────────────
# 3.  Sanitiser for Gemini quirks
# ────────────────────────────────────────────────────────────────
def html_output_sanitizer(raw_html: str) -> str:
    m = re.search(r"<p\b[^>]*>(?!`)", raw_html)
    if m:
        return raw_html[m.start():].strip()
    first = raw_html.find("<")
    return raw_html[first:].strip() if first != -1 else raw_html.strip()

# ────────────────────────────────────────────────────────────────
# 4.  Convert plain-text → HTML  (CrewAI wrapper, version-agnostic)
# ────────────────────────────────────────────────────────────────
def convert_draft_to_html(plain_email: str,
                          domain_code: str,
                          journal_shortname: str) -> Tuple[str, dict]:
    html_task = Task(
        name="Gemini HTML Conversion",
        description=HTML_TEMPLATE.format(plain_email=plain_email),
        agent=gemini_html_agent,
        expected_output="Pure HTML string – no prose, no fences.",
        llm_options={"use_tools": False},
    )
    crew   = Crew([gemini_html_agent], [html_task], verbose=False, process=Process.sequential)
    result = crew.kickoff()

    core_body = getattr(result, "output", str(result))
    usage     = getattr(result, "usage", {})
    clean_body = html_output_sanitizer(core_body)
    final_html = wrap_with_template(clean_body, domain_code, journal_shortname)
    return final_html, usage

# ────────────────────────────────────────────────────────────────
# 5.  Cleaning helpers  (salutation, markup, bullets, smart wrap)
# ────────────────────────────────────────────────────────────────
_SALUTATION_RE = re.compile(r"^\s*(dear|hi|hello|greetings)\b.*?,?\s*$", re.I)
BULLET_PATTERN = re.compile(r"""^[\s>]*(?:[\u2022\u25AA\u25CF\u25E6\u25B6\u25C6\u2043•■▪►]|[?\-*+]\s)""", re.VERBOSE)
MARKUP_PATTERNS = [
    (re.compile(r"\*\*(.+?)\*\*"), r"\1"),
    (re.compile(r"\*(.+?)\*"),     r"\1"),
    (re.compile(r"`(.+?)`"),       r"\1"),
    (re.compile(r"</?[^>]+>"),     r""),
    (re.compile(r"__([^_]+)__"),   r"\1"),
    (re.compile(r"_([^_]+)_"),     r"\1"),
]
_URL_RE = re.compile(r"https?://\S+", re.I)

def _strip_salutation(txt: str) -> str:
    lines = txt.lstrip().splitlines()
    if lines and _SALUTATION_RE.match(lines[0]):
        lines.pop(0)
    return "\n".join(lines).lstrip()

def _strip_markup(txt: str) -> str:
    for pat, repl in MARKUP_PATTERNS:
        txt = pat.sub(repl, txt)
    return txt

def _normalize_bullets(line: str) -> str:
    return BULLET_PATTERN.sub("- ", line)

def _smart_wrap_line(line: str, width: int = 72) -> list[str]:
    if len(line) <= width:
        return [line]

    words, wrapped, current = line.split(), [], []

    def flush():
        if current:
            wrapped.append(" ".join(current)); current.clear()

    for w in words:
        is_url = bool(_URL_RE.fullmatch(w))
        if is_url and len(w) > width:
            flush(); wrapped.append(w); continue

        new_len = len(" ".join(current)) + (1 if current else 0) + len(w)
        if new_len > width:
            flush()
        current.append(w)
        if is_url:
            flush()
    flush()
    return wrapped

def _wrap_preserve_breaks(text: str, width: int = 72) -> str:
    return "\n".join(
        ln if _URL_RE.fullmatch(ln) else "\n".join(_smart_wrap_line(ln, width))
        for ln in text.splitlines()
    )

def sanitize_body(body_txt: str) -> str:
    body = _strip_markup(body_txt)
    lines = [_normalize_bullets(unicodedata.normalize("NFKC", ln)) for ln in body.splitlines()]
    return _wrap_preserve_breaks("\n".join(lines), width=72)

# ────────────────────────────────────────────────────────────────
# 6.  Plain-text builder  (Interspire header/footer + clean body)
# ────────────────────────────────────────────────────────────────
INT_PLAIN_HEADER = (
    "Your email client cannot read this email.\n"
    "To view it online, please go here: %%webversion%%\n\n"
    "Dear Dr. %%First Name%%,\n"
)
INT_PLAIN_FOOTER = "\n\n\n\n\n\n\n\nTo stop receiving these emails:%%unsubscribelink%%"

def build_final_plaintext(body_txt: str, domain_code: str) -> str:
    body_clean = sanitize_body(_strip_salutation(body_txt).rstrip())
    if which_app(domain_code) == "interspire":
        return f"{INT_PLAIN_HEADER}\n{body_clean}{INT_PLAIN_FOOTER}"
    return body_clean
