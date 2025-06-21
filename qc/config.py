import os
from dotenv import load_dotenv

load_dotenv()                # Pulls values from .env into env vars

DB_CFG = dict(
    host=os.getenv("DRAFTS_DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DRAFTS_DB_USER"),
    password=os.getenv("DRAFTS_DB_PASS"),
    db_cfp=os.getenv("INTERSPIRE_DB_NAME"),
    db_agent=os.getenv("DRAFTS_DB_NAME"),
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
LLAMA_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"