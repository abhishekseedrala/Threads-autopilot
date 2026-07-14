"""
refresh_token.py
Threads long-lived tokens last ~60 days. This runs weekly, exchanges the
current token for a fresh 60-day one, and writes it back into the repo's
GitHub Secrets using the GitHub CLI (needs a GH_PAT secret with repo scope).
Result: the system literally never expires.
"""
import json
import os
import subprocess
import urllib.parse
import urllib.request

TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
REPO = os.environ["GITHUB_REPOSITORY"]  # provided automatically by Actions


def refresh():
    qs = urllib.parse.urlencode({
        "grant_type": "th_refresh_token",
        "access_token": TOKEN,
    })
    url = f"https://graph.threads.net/refresh_access_token?{qs}"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read())
    return data["access_token"], data.get("expires_in")


def main():
    new_token, expires_in = refresh()
    days = int(expires_in) // 86400 if expires_in else "?"
    print(f"Got fresh token, valid ~{days} days. Updating repo secret...")
    subprocess.run(
        ["gh", "secret", "set", "THREADS_ACCESS_TOKEN",
         "--repo", REPO, "--body", new_token],
        check=True,
        env={**os.environ, "GH_TOKEN": os.environ["GH_PAT"]},
    )
    print("Secret updated. System is immortal for another cycle.")


if __name__ == "__main__":
    main()
