# Information Radar

Information Radar is a personal, topic-agnostic early-signal detector. It ranks acceleration and cross-source confirmation above raw popularity, then stores and delivers a concise daily digest.

The repository now contains the Phase 2 core journey and Phase 3 V1 adapters. It runs with Python's standard library only.

## Quick start

```bash
cd /Users/tim_hong/Documents/ChatGPT/InformationRadar
PYTHONPATH=src python3 -m radar.cli --db data/radar.db serve
```

Open <http://127.0.0.1:8787>.

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

# Create a consistent SQLite backup
PYTHONPATH=src python3 -m radar.cli --db data/radar.db backup backups/radar-manual.db
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

The production Docker image is built by GitHub Actions and published to GHCR. Synology runs `radar-web` continuously and starts `radar-job` from Task Scheduler at 07:00 Asia/Taipei. The host port is bound to `127.0.0.1:8789` because `8787` is already used by the Hermes linebot; the container still listens on `8787`. Use a private Tailscale or NAS access layer and do not expose the port publicly.

Each pushed release builds only `linux/amd64` from a digest-pinned Python base, applies available OS and packaging fixes, publishes BuildKit provenance and an SBOM, and scans the pushed digest with Trivy. Any fixable HIGH or CRITICAL OS/library CVE blocks release evidence; findings without an upstream fixed version are excluded from the blocking set rather than being represented as remediated. Only after that gate passes does CI upload `release-manifest.json` in the deterministic `aihome-release-<commit SHA>` workflow artifact. The manifest binds the source commit, published image digest, source production Compose checksum, deployment project, and health paths without committing a post-build digest back to the same commit. `compose.prod.yml` uses one required `IMAGE_DIGEST` placeholder for both services; AI Home Platform verifies the source checksum before materializing the selected immutable digest. Every third-party workflow action is pinned to a full commit SHA.

`GET /health/ops` is the read-only AI Home Platform evidence endpoint. It reports only validated `AIHP_RELEASE_COMMIT` / `AIHP_IMAGE_DIGEST` coordinates, live database/schema readiness, and explicit backup, restore-test, and runtime-secret adapter status. The existing SQLite backup command is reported as `local_only`; manual restore guidance and environment/local settings are not presented as verified platform adapters.

Optional LLM enrichment uses an OpenAI-compatible `LLM_API_URL`, `LLM_API_KEY`, and `LLM_MODEL`. If these are absent or unavailable, deterministic Radar summaries and scores remain active.

## NAS deployment

The production directory is `/volume1/docker/information-radar`. Keep `RADAR_IMAGE` in `image.env` pinned to a GHCR digest. The guarded deployment script backs up SQLite, recreates only the web service, checks `/health/ready`, and restores the previous image reference on failure:

```bash
/volume1/docker/information-radar/scripts/nas-deploy.sh \
  ghcr.io/cuweiwei/information-radar@sha256:<digest>
```

Configure Synology Task Scheduler with `/volume1/docker/information-radar/scripts/run-radar-job.sh` at 07:00 and `/volume1/docker/information-radar/scripts/backup-radar.sh` at 06:45. The job is idempotent for collection and digest persistence; delivery records prevent normal duplicate sends. A network timeout after Telegram accepted a message remains an ambiguous delivery and must be reconciled before forcing a retry.

The settings API is intentionally local-only and does not include a multi-user authentication layer in V1. Keep the bind address private and do not publish `/api/settings` to the Internet.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
node --check src/web/app.js
```

The golden fixture covers popular-but-stable, small-fast, cross-source, duplicate, and noise cases. The critical assertion is that acceleration can beat absolute popularity.

## Delivery boundaries

Local implementation and fixture/API smoke tests are verified by CI. Live GitHub/HN/Reddit/Product Hunt/X credentials, Telegram delivery, Hermes routing, GHCR publication, NAS deployment, and private-access verification require the configured environment and a live run.
