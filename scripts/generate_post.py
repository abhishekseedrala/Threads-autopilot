"""
generate_post.py  (v3 - NVIDIA DeepSeek edition)
Writes one Threads post using free AI APIs.
Provider chain: Gemini -> Groq -> DeepSeek (NVIDIA-hosted). First success wins.
Learns from performance.json and feeds top posts back into the prompt.
"""
import json
import os
import random
import sys
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / "config.json").read_text())
PRODUCTS = json.loads((ROOT / "data/products.json").read_text())
PERF = json.loads((ROOT / "data/performance.json").read_text())
HISTORY = json.loads((ROOT / "data/post_history.json").read_text())

GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")
GROQ_KEY = os.environ.get("GROQ_API_KEY", "")
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

ANGLE_DESCRIPTIONS = {
    "practical_tip": "Share one concrete, actionable tip about automating social media / saving time as a creator. Teach something real in 3-5 lines.",
    "bold_claim": "Open with a bold, scroll-stopping claim about automation or consistency on Threads, then back it up in 2-3 lines.",
    "mini_story": "Tell a tiny 4-6 line personal story: the pain of manual posting, the moment of automating it, the result. Casual, human.",
    "question_to_audience": "Ask the audience one sharp question about their posting habits / time spent on social media. Add 1-2 lines of context. Invite replies.",
    "myth_buster": "Bust a common myth (e.g. 'automation gets you banned', 'you must post manually to grow'). Correct it with the truth about official APIs.",
    "behind_the_scenes": "Describe what the automation system is doing right now behind the scenes (picking an angle, checking analytics, publishing). Make the reader realize a bot wrote this.",
    "before_after": "Contrast life before automation (hours daily, burnout, inconsistency) vs after (2-3 hr setup, runs forever). Short lines.",
    "listicle_micro": "A micro-list: 3-4 numbered one-line items (tools, steps, mistakes, wins) about hands-free Threads growth.",
    "contrarian_take": "A spicy contrarian opinion about content creation grind culture, defended in 2-3 lines. End with a mic-drop line.",
    "social_proof_demo": "Point out that THIS very post was written and published by the system with zero human touch, and what that proves.",
}


def pick_angle():
    angles = CONFIG["angles"]
    scores = PERF.get("angle_scores", {})
    if not scores or random.random() < CONFIG.get("epsilon", 0.2):
        return random.choice(angles)
    scored = [(a, scores.get(a, {}).get("avg_score", 0)) for a in angles]
    scored.sort(key=lambda x: x[1], reverse=True)
    top = scored[:4]
    weights = [max(s, 0.1) for _, s in top]
    return random.choices([a for a, _ in top], weights=weights, k=1)[0]


def build_prompt(angle):
    p = PRODUCTS["product"]
    include_cta = random.random() < 0.45
    cta = random.choice(p["cta_phrases"]) if include_cta else None

    top_examples = ""
    tops = PERF.get("top_posts", [])[:5]
    if tops:
        joined = "\n---\n".join(t["text"] for t in tops)
        top_examples = (
            "\nHere are this account's TOP PERFORMING recent posts. "
            "Study their style, rhythm and energy and write something that "
            "matches what this audience responds to (but is completely new):\n"
            f"{joined}\n"
        )

    recent = "\n---\n".join(x["text"] for x in HISTORY["posts"][-8:])
    avoid = f"\nDo NOT resemble any of these recent posts:\n{recent}\n" if recent else ""

    rules = "\n".join(f"- {r}" for r in PRODUCTS["hard_rules"])
    cta_line = f'End the post naturally with this CTA: "{cta}"' if cta else \
        "Do NOT include any call-to-action or link mention. Pure value/entertainment post."

    return f"""You write viral Threads posts for this account.

PRODUCT BEING PROMOTED (subtly, never like an ad):
Name: {p['name']}
Promise: {p['promise']}
Audience: {p['audience']}
Key facts you may draw from: {json.dumps(p['key_points'])}

VOICE: {PRODUCTS['voice']}

TODAY'S CONTENT ANGLE: {ANGLE_DESCRIPTIONS[angle]}
{top_examples}{avoid}
HARD RULES:
{rules}
- {cta_line}

Write ONE Threads post now. Output ONLY the post text, nothing else.
No quotation marks around it. No preamble."""


def call_gemini(prompt):
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.0-flash:generateContent?key={GEMINI_KEY}")
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 1.0, "maxOutputTokens": 400},
    }).encode()
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def call_openai_style(prompt, url, key, model):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 1.0,
        "max_tokens": 400,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    })
    with urllib.request.urlopen(req, timeout=90) as r:
        data = json.loads(r.read())
    return data["choices"][0]["message"]["content"].strip()


def generate(prompt):
    errors = []
    if GEMINI_KEY:
        try:
            return call_gemini(prompt), "gemini"
        except Exception as e:
            errors.append(f"gemini: {e}")
    if GROQ_KEY:
        try:
            return call_openai_style(
                prompt, "https://api.groq.com/openai/v1/chat/completions",
                GROQ_KEY, "llama-3.3-70b-versatile"), "groq"
        except Exception as e:
            errors.append(f"groq: {e}")
    if DEEPSEEK_KEY:
        try:
            return call_openai_style(
                prompt, "https://integrate.api.nvidia.com/v1/chat/completions",
                DEEPSEEK_KEY, "deepseek-ai/deepseek-v4-flash"), "deepseek"
        except Exception as e:
            errors.append(f"deepseek: {e}")
    raise RuntimeError("ALL_PROVIDERS_FAILED (v3): " + " | ".join(errors))


def too_similar(text):
    limit = CONFIG.get("no_repeat_similarity", 0.62)
    for old in HISTORY["posts"][-120:]:
        if SequenceMatcher(None, text.lower(), old["text"].lower()).ratio() > limit:
            return True
    return False


def clean(text):
    text = text.strip().strip('"').strip()
    if len(text) > 490:
        text = text[:487].rsplit(" ", 1)[0] + "..."
    return text


def main():
    angle = pick_angle()
    for attempt in range(4):
        prompt = build_prompt(angle)
        text, provider = generate(prompt)
        text = clean(text)
        if text and not too_similar(text):
            out = {"text": text, "angle": angle, "provider": provider}
            (ROOT / "data/next_post.json").write_text(json.dumps(out, indent=2))
            print(f"[{provider} | {angle}] {text}")
            return
        print(f"attempt {attempt+1}: duplicate-ish output, regenerating...")
        angle = random.choice(CONFIG["angles"])
    sys.exit("Could not generate a sufficiently unique post after 4 attempts.")


if __name__ == "__main__":
    main()
