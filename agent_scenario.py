# --------------------------------------------------------------
# Scenario + Top-3 Subject selector  (Llama-4 Maverick → Groq)
# --------------------------------------------------------------
import re, json, litellm, os, logging   # ← re included here
logger = logging.getLogger("scenario_agent")

SYSTEM_PROMPT = """
You are an expert academic-marketing analyst.

Task 1 – SCENARIO   (HARD RULES)
• Read the draft email below.
• Output **exactly one clear, descriptive sentence (10–25 words)** that captures the email’s core focus.
  – State whether it is an initial Call-for-Papers invitation or a follow-up reminder, but **do NOT** add the literal prefixes “CFP:” or “OPEN:”.
  – If the draft offers fee relief, append “with waiver” (omit percentages or figures).
  – If a submission cut-off is mentioned, append “with deadline” (omit the exact date).
  – The two sample lines that follow are **illustrative only**—create your own phrasing that meets the rules:
      ▸ “Inviting articles for the concluding 2024 issue with waiver and deadline.”
      ▸ “Friendly follow-up on previous invitation, highlighting waiver and deadline.”
  – Do not exceed one sentence; write in natural prose.

Task 2 – SUBJECT-LINE RANKING
• You will also receive EXACTLY ten candidate subject lines.
• Select the THREE most likely to maximise open-rate **for the scenario you just wrote**.
• Judge on clarity, relevance, curiosity gap, and likelihood of passing academic spam filters.

Return ONLY this JSON (no markdown, code fences, or extra text):

{
  "scenario": "<your single descriptive sentence>",
  "top_subjects": ["<best-subject-1>", "<best-subject-2>", "<best-subject-3>"]
}
"""

def _safe_json_from_llm(text: str) -> dict:
    """
    Return the first {...} JSON object found in the LLM output.
    If nothing parses, return {}.
    """
    # 1) strip code-block fences ```json ... ```
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[^\n]*\n|\n```$", "", text, flags=re.S).strip()

    # 2) naive attempt
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3) fallback: grab first brace-balanced chunk
    m = re.search(r"\{.*\}", text, flags=re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse JSON from LLM output:\n%s", text[:300])
    return {}

def groq_scenario_agent(draft_txt: str, subject_lines: list[str]) -> dict:
    payload = {"draft": draft_txt, "subjects": subject_lines}

    def _call(model_id: str, provider: str | None = None):
        body = {"provider": {"only": [provider]}} if provider else {}
        return litellm.completion(
            model      = model_id,
            api_base   = "https://openrouter.ai/api/v1",
            api_key    = os.environ["OPENROUTER_API_KEY"],
            extra_body = body,
            temperature=0.38,
            max_tokens = 300,
            messages   = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": json.dumps(payload, indent=2)}
            ],
        )

    try:
        resp = _call(
            "meta-llama/llama-4-maverick-17b-128e-instruct",
            provider="groq"
        )
    except Exception:
        logger.exception("Groq call failed, falling back to GPT-4o")
        resp = _call("openai/gpt-4o-2024-05-13")

    raw_out = resp["choices"][0]["message"]["content"]
    return _safe_json_from_llm(raw_out)