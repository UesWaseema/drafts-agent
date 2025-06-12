from bs4 import BeautifulSoup
import re

def extract_waiver_percentage(text: str) -> int:
    """
    Return the first percent that appears within ±60 characters of the
    keywords waiver / fee waiver / APC waiver / discount. 0 if none.
    """
    if not isinstance(text, str):
        return 0

    plain = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)

    # pattern 1: “20 % … waiver/discount …”
    for m in re.finditer(r'(\d{1,3}(?:\.\d+)?)\s*%', plain):
        num, a, b = m.group(1), m.start(), m.end()
        ctx = plain[max(0, a-60):min(len(plain), b+60)].lower()
        if re.search(r'\b(waiver|discount|fee waiver|apc waiver)\b', ctx):
            return int(round(float(num)))

    # pattern 2: “waiver/discount of 15 %”
    m2 = re.search(r'\b(?:waiver|discount)\s*(?:of\s*)?(\d{1,3}(?:\.\d+)?)\s*%', plain, re.I)
    if m2:
        return int(round(float(m2.group(1))))

    return 0
