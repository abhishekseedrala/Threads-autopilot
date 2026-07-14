"""
collect_insights.py
Runs daily. Pulls Threads insights (views, likes, replies, reposts, quotes)
for recent posts, scores them, and updates performance.json:
  - angle_scores: which content angles work best
  - hour_scores:  which posting hours work best
  - top_posts:    best posts, fed back into tomorrow's AI prompts
This file IS the learning loop.
"""
import json
import urllib.parse
import urllib.request
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HISTORY = json.loads((ROOT / "data/post_history.json").read_text())
PERF = json.loads((ROOT / "data/performance.json").read_text())

TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
API = "https://graph.threads.net/v1.0"
METRICS = "views,likes,replies,reposts,quotes"

# engagement weighting: replies/reposts signal far more than views
WEIGHTS = {"views": 0.001, "likes": 1.0, "replies": 3.0, "reposts": 4.0, "quotes": 4.0}


def fetch_insights(media_id):
    qs = urllib.parse.urlencode({"metric": METRICS, "access_token": TOKEN})
    url = f"{API}/{media_id}/insights?{qs}"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read())
    out = {}
    for item in data.get("data", []):
        vals = item.get("values", [{}])
        out[item["name"]] = vals[0].get("value", 0) if vals else 0
    return out


def score(ins):
    return round(sum(ins.get(k, 0) * w for k, w in WEIGHTS.items()), 3)


def main():
    now = datetime.now(timezone.utc).timestamp()
    updated = 0
    for p in HISTORY["posts"]:
        age_h = (now - p["timestamp"]) / 3600
        # measure posts between 20h and 14 days old (needs time to accumulate signal)
        if age_h < 20 or age_h > 336:
            continue
        try:
            ins = fetch_insights(p["media_id"])
            p["insights"] = ins
            p["score"] = score(ins)
            updated += 1
        except Exception as e:
            print(f"insights failed for {p['media_id']}: {e}")

    scored = [p for p in HISTORY["posts"] if p.get("score") is not None]

    # --- angle scores (rolling average) ---
    angle_scores = {}
    for p in scored:
        a = p["angle"]
        angle_scores.setdefault(a, []).append(p["score"])
    PERF["angle_scores"] = {
        a: {"avg_score": round(sum(v) / len(v), 3), "n": len(v)}
        for a, v in angle_scores.items()
    }

    # --- hour scores ---
    hour_scores = {}
    for p in scored:
        hour_scores.setdefault(str(p["local_hour"]), []).append(p["score"])
    PERF["hour_scores"] = {h: round(sum(v) / len(v), 3) for h, v in hour_scores.items()}

    # --- top posts fed back to the AI ---
    best = sorted(scored, key=lambda x: x["score"], reverse=True)[:5]
    PERF["top_posts"] = [{"text": p["text"], "score": p["score"], "angle": p["angle"]}
                         for p in best]
    PERF["last_updated"] = datetime.now(timezone.utc).isoformat()

    (ROOT / "data/post_history.json").write_text(json.dumps(HISTORY, indent=2))
    (ROOT / "data/performance.json").write_text(json.dumps(PERF, indent=2))
    print(f"Updated insights for {updated} posts. "
          f"Angles tracked: {len(PERF['angle_scores'])}. "
          f"Top post score: {best[0]['score'] if best else 'n/a'}")


if __name__ == "__main__":
    main()
