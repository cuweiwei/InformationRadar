import time
from datetime import datetime
from zoneinfo import ZoneInfo


def run_scheduler(pipeline, topic_id, hour=7, minute=0, deliver=False, once=False, timezone_name="Asia/Taipei"):
    timezone = ZoneInfo(timezone_name)
    if once:
        return pipeline.run(topic_id, deliver=deliver)
    last_run_date = None
    while True:
        now = datetime.now(timezone)
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if now >= scheduled and last_run_date != now.date():
            pipeline.run(topic_id, deliver=deliver)
            last_run_date = now.date()
        sleep_seconds = 30 if now >= scheduled else max(1, min(60, int((scheduled - now).total_seconds())))
        time.sleep(sleep_seconds)
