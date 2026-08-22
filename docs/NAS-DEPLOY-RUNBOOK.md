# Information Radar NAS Deploy Runbook

## Scope

The Synology NAS is the production runtime. GitHub Actions builds and publishes the image; the NAS does not build source code. Persistent state is under `/volume1/docker/information-radar/data` and must survive image replacement.

## First-time setup

Create `data`, `config`, `logs`, `backups`, `run`, and `releases`. Copy `.env.example` to `.env`, add provider and delivery values, set permissions to `600`, and create `image.env` with a GHCR digest:

```text
RADAR_IMAGE=ghcr.io/cuweiwei/information-radar@sha256:<digest>
```

The NAS scripts use `/usr/local/bin/docker` through `sudo` by default. For a manual deployment, the owner must run `sudo -v` in their own interactive TTY first. Configure both Synology Task Scheduler entries to run as `root`; a non-interactive scheduler cannot answer a sudo password prompt.

Use Synology Task Scheduler with timezone `Asia/Taipei`:

- 06:45: `scripts/backup-radar.sh`
- 07:00: `scripts/run-radar-job.sh`

## Release

Run the preflight checks locally and confirm the target digest exists in GHCR. On the NAS, run:

```bash
scripts/nas-deploy.sh ghcr.io/cuweiwei/information-radar@sha256:<digest>
```

The script creates an online SQLite backup, saves the previous image reference, updates only `radar-web`, and verifies `/health/ready`. It prints `DEPLOYMENT VERIFIED` only after the health check succeeds.

## Rollback

If readiness fails, the script restores `releases/previous-image.env` and recreates `radar-web`. SQLite is never automatically restored. To restore data, stop the web service, validate the selected backup with `PRAGMA integrity_check`, and perform the restore as an explicit owner-approved operation.

## Acceptance

```bash
curl -fsS http://127.0.0.1:8787/health
curl -fsS http://127.0.0.1:8787/health/ready
docker compose ps
docker compose --profile job run --rm radar-job radar run ai_tools --dry-run
```

Verify the dashboard through the private access path, then run one configured provider check and one Telegram delivery test. Do not treat a green CI workflow as production deployment evidence.
