📨 Drafts‑Agent

Drafts‑Agent is an automated pipeline that drafts, quality‑checks, converts to HTML, and sends outreach emails for journal Calls‑for‑Papers (CFP).  It is built around a set of composable agents (each a short Python script) orchestrated by Streamlit and the CrewAI framework.

TL;DR – Run python run_pipeline.py to generate, QC and push HTML‑ready drafts to your ESP.  Run streamlit run agent_ranking_ui.py to explore scores and rankings interactively.

✨ Key Features

Module

Purpose

agent_draft_writer.py

GPT‑powered first‑draft generation.

agent_spam_removal.py

Removes buzz‑words & detects policy violations.

agent_qc_analyzer.py

Enforces 300‑450‑word length, style & tone rules.

agent_qc_autofix.py

Attempts automated fixes when QC fails.

agent_html_converter.py / agent_gemini_html.py

Converts the cleaned draft to strict HTML (inline styles only, no CSS files).

agent_ranking.py

Scores emails on past open/CTR data to surface the best variant.

agent_ranking_ui.py

Streamlit dashboard for human review & tie‑breaking.

database_sync_pipeline.py / run_daily_sync.py

Keeps local SQLite & MySQL in sync with your ESP (Interspire/Mailwizz).

draft_agent_interspire_patch.py

Final push: inserts the chosen draft into the ESP campaign.

campaign_stats.py, validate_campaign_stats.py

Pull and validate post‑send metrics.

backfill_sent_date.py

Back‑populate missing sent_date fields.

Additional helpers live in common.py (shared utils), quality_check_rules.py (spam‑word lists, style rules) and interspire_helpers.py (ESP REST helpers).

🗂  Repository Layout

├── agent_*                # Atomic agents (see table above)
├── run_pipeline.py        # End‑to‑end orchestrator
├── run_daily_sync.py      # CRON‑friendly sync job
├── db.py                  # DB connectors (MySQL + SQLite)
├── logs/                  # Rotating *.log files
├── interspire_analysis/   # Jupyter & SQL notebooks for ESP data
├── __pycache__/           # Byte‑code; ignored in .gitignore
├── old/                   # Deprecated scripts kept for reference
├── *.db                   # SQLite data stores (generated at runtime)
└── tests/                 # Smoke tests for ESP connectivity

🚀 Quick‑start

# 1. Clone & step in
$ git clone git@github.com:UesWaseema/drafts-agent.git
$ cd drafts-agent

# 2. Create a virtualenv (Python 3.11+)
$ python -m venv .venv && source .venv/bin/activate

# 3. Install deps
$ pip install -r requirements.txt   # file coming soon; see below

# 4. Add environment variables (example)
$ cp .env.example .env              # then edit

# 5. Launch the pipeline
$ python run_pipeline.py            # runs one full draft cycle

Minimum .env variables

Key

What it’s for

OPENAI_API_KEY

Large‑language‑model calls

ESP_API_KEY

Interspire or Mailwizz API token

MYSQL_DSN

mysql+pymysql://user:pass@host/db

SPAM_WORD_PATH

Optional external list (CSV/JSON)

Tip: The default SQLite databases (journal_data.db, interspire_analysis_results.db) are created automatically; nothing to configure.

🏗  Architecture

flowchart TD
    subgraph Draft Cycle
        A[agent_draft_writer] --> B[agent_spam_removal]
        B --> C{QC passes?}
        C -- yes --> D[agent_html_converter]
        C -- no  --> E[agent_qc_autofix] --> B
    end

    D --> F[agent_ranking]
    F -->|Top variant| G[draft_agent_interspire_patch]
    G --> H[ESP Campaign]

The daily CRON job (run_daily_sync.py) fetches campaign metrics and updates local stores, which feed back into agent_ranking.py.

🧪 Tests

pytest -q

Integration tests (test_interspire.py, test_mailwizz.py) need valid API keys and will hit your ESP sandbox; set CI=1 to skip them.

🗒  Roadmap



🤝 Contributing

Fork + clone.

Create a branch (git switch -c feature/your‑idea).

Commit with conventional commits (feat: …, fix: …).

Push and open a PR.

All commits are auto‑checked by flake8 and pytest in CI.

📜 License

MIT.  See LICENSE (coming soon).

