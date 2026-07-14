Threads Autopilot 🧵🤖
A fully autonomous Threads posting system. $0/month. Zero human interaction after setup.
AI writes every post → publishes via the official Threads API → reads its own
analytics daily → writes better posts tomorrow. It also refreshes its own access
token and emails you nothing, ever. You just watch it run.
Architecture: GitHub Actions (free cron server) → Gemini/Groq free AI APIs
(writer) → Threads API (publisher) → Insights API (teacher) → back to the writer.
---
Setup (one time, ~2-3 hours)
Step 1 - Create your Meta app (~30 min)
Go to https://developers.facebook.com and log in with the Facebook account
you'll use (create a developer account if prompted).
My Apps → Create App.
When asked for a use case, choose "Access the Threads API".
Name the app anything (e.g. `threads-autopilot`) and create it.
In the app dashboard, open the Threads use case → Settings/Customize and make
sure these permissions are added:
`threads\_basic`
`threads\_content\_publish`
`threads\_manage\_insights`
Under Threads → Roles / Testers (App roles), add your own Threads account
as a Threads Tester.
Open the Threads app on your phone → Settings → Account → Website permissions
→ Invites → accept the tester invite.
Step 2 - Get your long-lived access token (~20 min)
In your Meta app dashboard, find the Threads use case's token generator /
Graph API testing tool and generate a user access token for your Threads
account with the three permissions above.
(Alternative: use the OAuth flow described in Meta's Threads API docs.)
That token is short-lived (1 hour). Exchange it for a long-lived token
(~60 days) by opening this URL in your browser (fill in the two values):
```
   https://graph.threads.net/access\_token
     ?grant\_type=th\_exchange\_token
     \&client\_secret=YOUR\_APP\_SECRET
     \&access\_token=YOUR\_SHORT\_LIVED\_TOKEN
   ```
(App secret is in App settings → Basic.) Copy the `access\_token` from the
response. This is your `THREADS\_ACCESS\_TOKEN`.
Don't worry about the 60-day expiry - the system refreshes it automatically
every Monday, forever.
Step 3 - Get your free AI keys (~10 min)
Gemini (primary): https://aistudio.google.com → Get API key → create key.
Free tier is more than enough for 100 posts/day.
Groq (fallback, optional but recommended): https://console.groq.com →
API Keys → create key.
Step 4 - Create a GitHub Personal Access Token (~5 min)
Needed only so the system can rotate its own Threads token secret.
GitHub → Settings → Developer settings → Personal access tokens →
Fine-grained tokens → Generate new token.
Scope it to the repo you're about to create, with Secrets: Read and write
and Contents: Read and write permission. Copy it.
Step 5 - Create the repo and add secrets (~15 min)
Create a new GitHub repository (public = unlimited free Actions minutes).
Upload everything in this folder to it (or `git push`).
Repo → Settings → Secrets and variables → Actions → add these secrets:
Secret name	Value
`THREADS\_ACCESS\_TOKEN`	long-lived token from Step 2
`GEMINI\_API\_KEY`	from Step 3
`GROQ\_API\_KEY`	from Step 3 (optional)
`GH\_PAT`	from Step 4
Repo → Actions tab → enable workflows if prompted.
Step 6 - Customize and launch (~30 min)
Edit `data/products.json`:
Replace `YOUR\_PRODUCT\_LINK\_HERE` with your real link.
Tweak the product name, promise, and key points to your exact offer.
Adjust the `voice` line - this controls how every post sounds.
Edit `config.json` if you want:
`posts\_per\_day` - start at 15 (see warning below).
`active\_hours\_start/end` - local hours when posting is allowed.
Test it: Actions → Post to Threads → Run workflow → force = true.
Watch the log. Your first AI-written post should appear on Threads in ~30s.
Done. Close the laptop. It runs forever.
---
Scaling to 50-100 posts/day
Two edits:
`config.json` → `"posts\_per\_day": 100`
`.github/workflows/post.yml` → change cron to `'\*/10 \* \* \* \*'`
⚠️ Strong advice: don't launch at 100/day. Threads' ranking algorithm
punishes spammy volume and your per-post engagement will collapse, which feeds
garbage data into the learning loop. Start at 15-20/day, let it learn for 2-3
weeks, scale gradually. The Threads API hard limit is 250 posts/day.
How the learning works
Every post is tagged with its content angle (10 styles: tips, stories,
bold claims, myth-busting, etc.) and posting hour.
Daily, `collect\_insights.py` pulls views/likes/replies/reposts for every post
and computes a weighted score (replies and reposts count most).
The generator uses an epsilon-greedy bandit: 80% of the time it picks from
the best-performing angles, 20% it experiments.
Your top 5 posts ever are injected into the AI prompt as style examples -
the AI literally imitates what your specific audience already proved they love.
A similarity check blocks any post that's too close to the last 120 posts.
Files
```
config.json                     posting schedule + bandit settings
data/products.json              YOUR product info + brand voice (edit this!)
data/performance.json           the learning brain (auto-updated)
data/post\_history.json          everything ever posted (auto-updated)
scripts/generate\_post.py        AI writer (Gemini → Groq fallback)
scripts/post\_thread.py          publisher + smart schedule gate
scripts/collect\_insights.py     daily learning loop
scripts/refresh\_token.py        weekly token self-renewal
scripts/weekly\_report.py        Sunday reports in /reports
.github/workflows/\*.yml         the four cron jobs
```
Troubleshooting
Nothing posts: check Actions logs. Most common: token expired before the
first refresh ran → regenerate token (Step 2) and update the secret.
"Outside active hours / quota reached / gap" in logs: normal - the cron
fires often and the script decides when to actually post.
AI errors: Gemini free tier briefly rate-limited → Groq fallback kicks in
automatically. If both fail, that run skips; next run retries.
