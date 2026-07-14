"""
post_thread.py
Publishes the post created by generate_post.py to Threads via the official API.
Two-step publish: create media container -> publish container.
Includes a schedule gate: the workflow cron fires often, but this script decides
whether it's actually time to post, based on posts_per_day and learned best hours.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text())
PERF = json.loads((ROOT / "data/performance.json").read_text())
HISTORY = json.loads((ROOT / "data/post_history.json").read_text())

TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
API = "https://graph.threads.net/v1.0"

# --- timezone helper (no external deps) ---
TZ_OFFSETS = {"Asia/Kolkata": 5.5, "UTC": 0}
offset = TZ_OFFSETS.get(CONFIG.get("timezone", "UTC"), 0)
now_local = datetime.now(timezone.utc) + timedelta(hours=offset)


def should_post_now():
    """Gate: respect active hours, daily quota, and minimum spacing."""
    if os.environ.get("FORCE_POST") == "1":
        return True

    h = now_local.hour
    start, end = CONFIG["active_hours_start"], CONFIG["active_hours_end"]
    if not (start <= h < end):
        print(f"Outside active hours ({h}h local). Skipping.")
        return False

    today = now_local.strftime("%Y-%m-%d")
    todays = [p for p in HISTORY["posts"] if p.get("local_date") == today]
    quota = CONFIG["posts_per_day"]
    if len(todays) >= quota:
        print(f"Daily quota reached ({len(todays)}/{quota}). Skipping.")
        return False

    # minimum spacing so posts spread across the day instead of bunching
    active_minutes = (end - start) * 60
    min_gap = max(active_minutes // quota - 5, 10)
    if todays:
        last = max(p["timestamp"] for p in todays)
        mins_since = (datetime.now(timezone.utc).timestamp() - last) / 60
        if mins_since < min_gap:
            print(f"Only {mins_since:.0f}m since last post (gap {min_gap}m). Skipping.")
            return False

    # learned best hours: if we have hour scores, skip bottom-tier hours 30% of the time
    hs = PERF.get("hour_scores", {})
    if len(hs) >= 8:
        ranked = sorted(hs.items(), key=lambda x: x[1], reverse=True)
        bottom = {int(k) for k, _ in ranked[len(ranked) * 2 // 3:]}
        if h in bottom and (datetime.now().microsecond % 10) < 3:
            print(f"Hour {h} is a low-performer. Deferring to a better slot.")
            return False
    return True


def api_post(path, params):
    params["access_token"] = TOKEN
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(f"{API}{path}", data=data)
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def publish(text):
    container = api_post("/me/threads", {"media_type": "TEXT", "text": text})
    creation_id = container["id"]
    time.sleep(5)  # Meta recommends a short wait before publishing
    result = api_post("/me/threads_publish", {"creation_id": creation_id})
    return result["id"]


def main():
    if not should_post_now():
        return  # clean exit, workflow succeeds, nothing published

    next_file = ROOT / "data/next_post.json"
    if not next_file.exists():
        sys.exit("No generated post found. Run generate_post.py first.")
    post = json.loads(next_file.read_text())

    media_id = publish(post["text"])
    print(f"Published! media_id={media_id}")

    HISTORY["posts"].append({
        "media_id": media_id,
        "text": post["text"],
        "angle": post["angle"],
        "provider": post["provider"],
        "timestamp": datetime.now(timezone.utc).timestamp(),
        "local_date": now_local.strftime("%Y-%m-%d"),
        "local_hour": now_local.hour,
        "insights": None,
    })
    # keep history file from growing forever
    HISTORY["posts"] = HISTORY["posts"][-1000:]
    (ROOT / "data/post_history.json").write_text(json.dumps(HISTORY, indent=2))
    next_file.unlink()


if __name__ == "__main__":
    main()
