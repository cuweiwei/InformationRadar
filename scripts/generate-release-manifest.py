#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path


COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
IMAGE_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$", re.IGNORECASE)


def main():
    parser = argparse.ArgumentParser(description="Generate the AI Home Platform release contract")
    parser.add_argument("--commit", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--compose", default="compose.prod.yml")
    parser.add_argument("--output", default="release-manifest.json")
    args = parser.parse_args()

    if not COMMIT_SHA_PATTERN.fullmatch(args.commit):
        parser.error("--commit must be a full 40-character Git SHA")
    if not IMAGE_DIGEST_PATTERN.fullmatch(args.image_digest):
        parser.error("--image-digest must be an immutable sha256 digest")

    compose_path = Path(args.compose)
    manifest = {
        "schemaVersion": 1,
        "serviceId": "information-radar",
        "repository": "cuweiwei/InformationRadar",
        "commitSha": args.commit,
        "imageDigest": args.image_digest,
        "composePath": "compose.prod.yml",
        "composeSha256": hashlib.sha256(compose_path.read_bytes()).hexdigest(),
        "deploymentProjectId": "information-radar",
        "health": {"path": "/health", "readinessPath": "/health/ready"},
    }
    Path(args.output).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
