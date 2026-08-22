import argparse
import json
import os
from datetime import datetime, timedelta, timezone

from .demo import demo_signals
from .pipeline import RadarPipeline
from .server import serve
from .scheduler import run_scheduler
from .storage import Storage
from .topics import TopicRegistry


def parse_since(value):
    if not value:
        return datetime.now(timezone.utc) - timedelta(days=1)
    if value.endswith("d"):
        return datetime.now(timezone.utc) - timedelta(days=int(value[:-1]))
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_context(args):
    storage = Storage(args.db)
    registry = TopicRegistry.default()
    return storage, registry, RadarPipeline(storage, registry)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="radar")
    parser.add_argument("--db", default=os.getenv("RADAR_DB", "data/radar.db"))
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="collect, score, build and optionally deliver a digest")
    run.add_argument("topic")
    run.add_argument("--since", default="1d")
    run.add_argument("--deliver", action="store_true")
    run.add_argument("--dry-run", action="store_true")

    demo = sub.add_parser("demo", help="seed deterministic fixture signals")
    demo.add_argument("topic", nargs="?", default="ai_tools")

    digest = sub.add_parser("digest", help="print the latest stored digest")
    digest.add_argument("topic")

    server = sub.add_parser("serve", help="serve the dashboard and local API")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=int, default=4173)
    server.add_argument("--no-demo", action="store_true")

    schedule = sub.add_parser("schedule", help="run the daily scheduler in Asia/Taipei")
    schedule.add_argument("topic")
    schedule.add_argument("--hour", type=int, default=7)
    schedule.add_argument("--minute", type=int, default=0)
    schedule.add_argument("--deliver", action="store_true")
    schedule.add_argument("--once", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "serve":
        return serve(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), args.db, args.host, args.port, not args.no_demo)
    storage, registry, pipeline = build_context(args)
    try:
        if args.command == "demo":
            plugin = registry.get(args.topic)
            pipeline.ingest_signals(plugin, demo_signals(args.topic))
            ranked = pipeline.score_topic(plugin)
            print(json.dumps({"topic": args.topic, "entities": [item.as_dict() for item in ranked]}, ensure_ascii=False, indent=2))
        elif args.command == "run":
            print(json.dumps(pipeline.run(args.topic, parse_since(args.since), deliver=args.deliver, dry_run=args.dry_run), ensure_ascii=False, indent=2))
        elif args.command == "digest":
            result = storage.latest_digest(args.topic)
            print(result["text"] if result else "No digest stored for %s" % args.topic)
        elif args.command == "schedule":
            print(json.dumps(run_scheduler(pipeline, args.topic, args.hour, args.minute, args.deliver, args.once), ensure_ascii=False, indent=2))
    finally:
        storage.close()


if __name__ == "__main__":
    main()
