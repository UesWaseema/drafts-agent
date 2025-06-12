import re
from functools import lru_cache

_SPAM_WORDS = {
    "free","money","urgent","sex","viagra","casino","loan","guarantee",
    "winner","discount","offer","save","earn","investment","income",
    "work from home","mortgage","pre-approved","warning","password",
}

@lru_cache(maxsize=4096)
def spam_word_hit(word: str) -> bool:
    w = word.lower()
    return w in _SPAM_WORDS
