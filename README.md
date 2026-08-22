# Information Radar

Information Radar is a personal, topic-agnostic early-signal detector. It ranks acceleration and cross-source confirmation above raw popularity, then stores and delivers a concise daily digest.

The repository now contains the Phase 2 core journey and Phase 3 V1 adapters. It runs with Python's standard library only.

## Quick start

```bash
cd /Users/tim_hong/Documents/ChatGPT/InformationRadar
PYTHONPATH=src python3 -m radar.cli --db data/radar.db serve
```

Open <http://127.0.0.1:4173>.

The development server seeds deterministic demo data for `ai_tools` and `housing` when the database is empty. The UI uses the API when available and falls back to local fixtures when opened as a static file.

## Commands

```bash
# Seed deterministic data for a topic
PYTHONPATH=src python3 -m radar.cli demo ai_tools
PYTHONPATH=src python3 -m radar.cli demo housing

# Run collection, scoring, digest persistence; add --deliver for Telegram/Hermes
PYTHONPATH=src python3 -m radar.cli run ai_tools --since 1d
PYTHONPATH=src python3 -m radar.cli run housing --since 7d --deliver

# Print the latest stored digest
PYTHONPATH=src python3 -m radar.cli digest ai_tools

# Run once or keep the daily 07:00 Asia/Taipei scheduler alive
PYTHONPATH=src python3 -m radar.cli schedule ai_tools --once
PYTHONPATH=src python3 -m radar.cli schedule ai_tools --hour 7 --minute 0 --deliver
```

## Architecture

```text
Scheduler / CLI
      ↓
Topic Plugin → Collectors → RawSignal normalization
      ↓
SQLite → Entity resolution → metric snapshots
      ↓
Momentum + acceleration + cross-source scoring
      ↓
Digest persistence → Telegram / Hermes adapters
      ↓
Local dashboard API + web UI
```

Topic-specific policy lives in `src/radar/topics.py`. The default registry includes `ai_tools`, `housing`, and `test_topic` to prove extensibility. The core pipeline does not branch on AI-tool-specific logic.

Collectors:

- GitHub public repository search with optional token
- Hacker News Algolia search
- Reddit configurable subreddit adapter
- Product Hunt GraphQL adapter, optional token
- X recent-search adapter, optional bearer token
- RSS/Atom official-source adapter

Each collector records `SUCCESS`, `PARTIAL`, `FAILED`, `RATE_LIMITED`, or `AUTH_REQUIRED` independently. Optional failures do not stop the digest pipeline.

## Configuration and secrets

Copy `.env.example` into your deployment environment. Do not commit real tokens. Telegram and Hermes delivery are skipped cleanly until their environment variables are configured.

When the local server is running, the gear icon opens Web Settings. You can save provider and delivery credentials, see only masked/configured status, verify read-only provider connectivity, and explicitly send a Telegram/Hermes delivery test. Web-saved values are stored in the local SQLite `app_settings` table and take precedence over environment variables; blank secret fields keep the existing value.

The Docker example binds the dashboard to `127.0.0.1:4173` on the host. Put it behind the user's private access layer when deploying to a NAS; do not expose the port publicly.

The settings API is intentionally local-only and does not include a multi-user authentication layer in V1. Keep the bind address private and do not publish `/api/settings` to the Internet.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
node --check src/web/app.js
```

The golden fixture covers popular-but-stable, small-fast, cross-source, duplicate, and noise cases. The critical assertion is that acceleration can beat absolute popularity.

## Delivery boundaries

Local implementation and fixture/API smoke tests are verified. Live GitHub/HN/Reddit/Product Hunt/X credentials, Telegram delivery, Hermes routing, and production deployment still require the configured environment and a live run.
