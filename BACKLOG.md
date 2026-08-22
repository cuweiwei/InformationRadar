# Information Radar Backlog

## Completed in Phase 2 + Phase 3 implementation

- [x] Topic registry with AI Tools, Housing, and test topic
- [x] SQLite persistence for signals, entities, snapshots, scores, digests, runs, and deliveries
- [x] GitHub and Hacker News collectors
- [x] Reddit, Product Hunt, X, and RSS optional adapters
- [x] Deterministic entity resolution with confidence boundaries
- [x] Momentum, acceleration, novelty, cross-source, relevance, source quality, and saturation scoring
- [x] Lifecycle statuses and explainable evidence
- [x] Daily digest payload and human-readable text
- [x] Telegram and Hermes delivery adapters with graceful configuration failure
- [x] 07:00 Asia/Taipei scheduler and manual CLI run
- [x] API-backed dashboard with AI Tools/Housing topic switching
- [x] Web settings for provider credentials, masked status, connection verification, and explicit delivery tests
- [x] Golden fixture and unit/integration tests

## Follow-up hardening

- [ ] Add provider-recorded fixtures for every live collector and rate-limit contract tests
- [ ] Add authenticated Product Hunt/X live smoke tests in CI secrets environment
- [ ] Add review UI for low-confidence entity merges and alias correction
- [ ] Add persistent score history chart to the entity detail view
- [ ] Add configurable topic YAML loading and configuration management UI
- [x] Add production Telegram/Hermes client verification and deployment runbook
- [x] Production container image, GHCR workflow, NAS web/job split, health checks, backup and rollback
- [x] Optional OpenAI-compatible LLM enrichment with fail-open delivery
- [ ] Add manual mainstream-awareness timestamp and lead-time measurement
