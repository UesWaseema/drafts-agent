import json, litellm
from config import OPENROUTER_API_KEY, LLAMA_MODEL

_SYSTEM = (
    "You are an expert **marketing editor for academic-journal newsletters and loyalty-program mailers**. "
    "You will receive one JSON block containing:\n"
    "  • subject      – email subject line\n"
    "  • body_text    – plain-text body\n"
    "  • body_html    – HTML body (same content, richer markup)\n"
    "  • metadata.*   – misc. fields such as campaign_name, draft_type, sent_date\n\n"

    "Task 1 – scenario:  Read the draft and assign a SHORT label (≤ 10 words) "
    "that captures its main purpose. Possible patterns include, but are not limited to: "
    "Data-driven research showcase, Early-bird APC waiver deadline, Loyalty-program invitation, "
    "Impact-factor announcement, Final reminder: call for papers, Fee-waiver + loyalty combo.\n\n"

    "Task 2 – subject fit:  Judge whether the subject line fits that scenario. "
    "Return **subject_fit** as true/false and explain why in ≤ 2 concise sentences.\n\n"

    "Task 3 – improvement:  If the fit is poor, suggest *one* concrete tweak; "
    "otherwise return \"OK\".\n\n"

    "Respond **ONLY** with a minified JSON object using **exactly** these keys:\n"
    "{"
    "\"scenario\": <string>, "
    "\"subject_fit\": <true|false>, "
    "\"subject_reasoning\": <string>, "
    "\"improvement\": <string>"
    "} "
    "— no extra keys, no markdown, no commentary."
)


def analyse(draft: dict) -> dict:
    payload = json.dumps({
        "subject": draft["subject"],
        "body_text": draft["textbody"],
        "body_html": draft["htmlbody"]
    })
    response = litellm.completion(
        provider="openrouter",
        model=LLAMA_MODEL,
        api_base="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
        extra_body={"provider": {"only": ["groq"]}},
        temperature=0.2,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user",   "content": payload}
        ]
    )
    raw = response["choices"][0]["message"]["content"]
    return json.loads(raw)
