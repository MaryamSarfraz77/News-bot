# Setup Guide — Wire Desk (AI News Automation Bot)

This covers every connection: Gemini, SerperDev, Slack, Google Sheets,
running the pipeline locally, pushing to GitHub, and deploying the
scheduled backend to Vercel.

---

## Part 1 — Get Your API Keys

### 1.1 Gemini API Key (LLM for summarization + agent reasoning)
1. Go to https://aistudio.google.com/apikey and sign in with a Google account.
2. **Create API Key** (no credit card required for the free tier).
3. Copy it → you'll paste it as `GEMINI_API_KEY`.

### 1.2 SerperDev API Key (news search)
1. Go to https://serper.dev and sign up.
2. Your API key shows on the dashboard homepage.
3. Copy it → `SERPER_API_KEY`.

---

## Part 2 — Slack: Private Channel + Webhook

1. Create (or pick) a **private channel**, e.g. `#news-updates`.
2. Go to https://api.slack.com/apps → **Create New App**.
3. On the template screen, choose **Blank app** (not "AI agent" or
   "Starter app" — those add features you don't need).
4. Name it (e.g. "News Bot"), pick your workspace → **Create App**.
5. In the left sidebar, click **Incoming Webhooks** → toggle **On**.
6. Click **Add New Webhook to Workspace** → select your **private
   channel** → **Allow**.
7. Copy the Webhook URL (`https://hooks.slack.com/services/...`) →
   `SLACK_WEBHOOK_URL`.

**If you hit "can't add more apps" (10-app free limit):** either
remove an unused app from **Settings & administration → Manage apps**,
or create a fresh free workspace just for this project at
https://slack.com/get-started#/createnew and repeat the steps there.

**Important:** if this webhook is regenerated or the channel is
deleted/renamed, it breaks silently — you'll only notice when a post
fails.

---

## Part 3 — Google Sheets: Service Account Setup

### 3.1 Google Cloud project + APIs
1. Go to https://console.cloud.google.com → **New Project**.
2. Give it a name (e.g. `news-bot`) → **Create**. (The quota notice
   about "10 projects remaining" is informational, not an error —
   just click Create.)
3. Once created, search for **Google Sheets API** → **Enable**.
4. Search for **Google Drive API** → **Enable** (gspread needs this too).

### 3.2 Create the service account
1. **IAM & Admin → Service Accounts → Create Service Account**.
2. Name it (e.g. `news-bot-service-account`) → **Create and Continue** → **Done**.
3. Click into it → **Keys** tab → **Add Key → Create New Key → JSON → Create**.
4. A `.json` file downloads — this is your credentials file.

### 3.3 Share your Sheet with the service account
1. Open the downloaded JSON file in any text editor. Copy the
   `client_email` value (looks like
   `news-bot-service-account@news-bot-505011.iam.gserviceaccount.com`).
2. Go to https://sheets.google.com → **Blank spreadsheet**. Any new
   empty sheet works — it doesn't need to be special.
3. Rename it (e.g. "News Bot Log"). In row 1, add headers: `Date`,
   `Headline`, `Summary`, `Source URL`.
4. Click **Share** (top-right) → paste the `client_email` → set
   permission to **Editor** → **Send**.
5. Copy the Sheet ID from the URL:
   `https://docs.google.com/spreadsheets/d/`**`THIS_PART`**`/edit`
   → `GOOGLE_SHEET_ID`.

### 3.4 Place the credentials file (local runs only)
Rename the downloaded file to `google_service_account.json` and move
it into `news-bot/credentials/google_service_account.json` (already
gitignored).

---

## Part 4 — Run It Locally (step by step)

### 4.1 Install dependencies
```bash
cd news-bot
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4.2 Configure environment variables
```bash
cp .env.example .env
```
Fill in `GEMINI_API_KEY`, `SERPER_API_KEY`, `SLACK_WEBHOOK_URL`,
`GOOGLE_SHEET_ID`, and leave `GOOGLE_SERVICE_ACCOUNT_FILE` as the
default (it already points at `credentials/google_service_account.json`).
Set `NEWS_TOPICS` to whatever default topics you'd like, e.g.
`AI,Technology,Finance` — this is what the scheduled run uses.

### 4.3 Place the Google service account file
Confirm `credentials/google_service_account.json` (from Part 3.4) is
in place:
```bash
ls credentials/google_service_account.json
```

### 4.4 Run the pipeline once
```bash
python local_main.py
```

### 4.5 Verify it worked — checklist
Go through these in order; each confirms one piece before you move to
the next:

1. **Terminal output** — you should see a clean boxed summary like:
   ```
   ==========================================
    WIRE DESK — SCHEDULED RUN
    2026-08-11 09:00 UTC
   ==========================================
    Topics:              AI, Technology, Finance
    Articles found:      12
    Summaries made:      8
    Posted to Slack:     ✅ (8 messages)
    Logged to Sheet:     ✅ (8 rows)
    Duration:            14.2s
   ==========================================
   ```
   If instead you see CrewAI's raw `Thought:/Action:/Observation:` log
   spam, `verbose` is `true` somewhere — check every agent in
   `config/agents.yaml` is `verbose: false`.
2. **No exceptions / non-zero exit** — the command should finish
   cleanly. If it errors, see Troubleshooting below.
3. **Slack** — open the private channel; you should see one message
   per summarized article (headline + summary + link).
4. **Google Sheet** — open the sheet; new rows should appear with
   Date, Headline, Summary, Source URL.
5. **Counts line up** — "Summaries made" in the terminal should match
   the number of new Slack messages and new Sheet rows (barring any
   publish failures, which `format_utils.py` would flag as `⚠ unknown`).

Optional — test a single topic instead of the full `NEWS_TOPICS` list:
```bash
python local_main.py "AI in finance"
```
This prints structured JSON instead of the boxed summary (it's the
on-demand code path, still useful for isolating one topic).

**Troubleshooting:**
- `ERROR: SERPER_API_KEY is not set` → check `.env` is filled in and
  you're running from the `news-bot/` directory.
- Slack silent failure → re-check the webhook URL and that it's
  scoped to the right private channel.
- Google Sheets `PermissionError` / 403 → Sheet wasn't shared with the
  service account's `client_email`, or Sheets/Drive API isn't enabled.
- `pip install` failing on Windows with a Rust/Cargo compile error →
  this comes from a dependency (`tiktoken`, via `litellm`) needing a
  pre-built wheel. Fix: `pip install --only-binary=:all: -r requirements.txt`.
  Use Python 3.11 or 3.12 if that still fails — newer Python versions
  sometimes lack pre-built wheels.
- Gemini rate-limit errors → far less likely than under Groq's old
  6,000 tokens/minute free-tier cap, but `NewsFetcherTool` still
  hard-caps results at 5 per topic as a safety margin. If it still
  happens, wait ~20 seconds and retry, or test with one topic at a time.

---

## Part 5 — Push to GitHub

### 5.1 Initialize and push
```bash
git init
git add .
git commit -m "Initial commit: Wire Desk news bot (backend only)"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```
(`.env`, `venv/`, `__pycache__/`, and the real service account JSON
are all gitignored — double check with `git status` before committing
that none of them are staged.)

### 5.2 Add GitHub repo secrets (for the scheduled trigger)
These are separate from Vercel's env vars — GitHub Actions only needs
enough to call your deployed endpoint, not the pipeline's own keys.

Go to your repo → **Settings → Secrets and variables → Actions → New
repository secret**, and add:

| Secret name | Value |
|---|---|
| `VERCEL_APP_URL` | `https://<your-project>.vercel.app` (set this after Part 6.4) |
| `CRON_SECRET` | same random string you'll set as `CRON_SECRET` on Vercel |

You can add `VERCEL_APP_URL` after you have a live deployment — the
workflow just won't run successfully until both secrets exist.

---

## Part 6 — Deploy to Vercel

### 6.1 Import into Vercel
1. Go to https://vercel.com/new and import your GitHub repo.
2. Vercel has no framework to auto-detect now (no `package.json`) —
   it'll fall back to "Other". That's fine: it still auto-detects the
   Python function at `api/run.py` via `requirements.txt` at the repo
   root. Leave the root directory as-is.

### 6.2 Add environment variables in Vercel
**Settings → Environment Variables:**

| Key | Value |
|---|---|
| `GEMINI_API_KEY` | your Gemini key |
| `GEMINI_MODEL` | `gemini-3.1-flash-lite` |
| `SERPER_API_KEY` | your Serper key |
| `NEWS_TOPICS` | e.g. `AI,Technology,Finance` |
| `SLACK_WEBHOOK_URL` | your Slack webhook URL |
| `GOOGLE_SHEET_ID` | your Sheet ID |
| `GOOGLE_SHEET_WORKSHEET_NAME` | `Sheet1` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | entire contents of the service account JSON, as one line |
| `CRON_SECRET` | same random string you put in GitHub secrets |

**On Vercel, do not use `GOOGLE_SERVICE_ACCOUNT_FILE`** — there's no
persistent filesystem. `GOOGLE_SERVICE_ACCOUNT_JSON` is what the code
checks first.

To get the JSON as one line:
```bash
python -c "import json; print(json.dumps(json.load(open('credentials/google_service_account.json'))))"
```

### 6.3 Deploy
Click **Deploy**. Your app will be live at:
```
https://<your-project>.vercel.app
```
The only endpoint is `/api/run` (GET).

### 6.4 Wire up the GitHub Actions secret
Now that you have the live URL, go back to your repo's Actions
secrets (Part 5.2) and set `VERCEL_APP_URL` to it.

### 6.5 Test the deployed endpoint manually
```bash
curl -H "x-cron-secret: <your CRON_SECRET>" "https://<your-project>.vercel.app/api/run"
```
You should get back `{"status": "success", "result": {...}}`, and see
new Slack messages + Sheet rows.

### 6.6 Test the scheduled trigger manually
In GitHub: repo → **Actions** tab → **Run News Pipeline (Scheduled)**
→ **Run workflow** (this uses the `workflow_dispatch` trigger, so you
don't have to wait for the real 6-hour schedule). Confirm the run goes
green, and Slack/Sheets update again.

From here it runs automatically every 6 hours — no further action
needed. GitHub may delay a scheduled run by a few minutes under load;
that's normal.

---

## Summary Checklist

- [ ] Gemini + SerperDev keys obtained
- [ ] Slack: blank app created, private channel, Incoming Webhook added
- [ ] Google Cloud project with Sheets API + Drive API enabled
- [ ] Service account created, JSON key downloaded, Sheet shared with it as Editor
- [ ] `.env` filled in locally; `credentials/google_service_account.json` present
- [ ] `pip install -r requirements.txt` succeeds
- [ ] `python local_main.py` runs locally, prints the boxed summary (not raw agent logs)
- [ ] Slack gets new messages, Sheet gets new rows after the local run
- [ ] Pushed to GitHub (`.env` / credentials confirmed NOT committed)
- [ ] GitHub repo secrets `VERCEL_APP_URL` and `CRON_SECRET` set
- [ ] Deployed to Vercel with all env vars set (using `GOOGLE_SERVICE_ACCOUNT_JSON`, not the file path)
- [ ] `curl -H "x-cron-secret: ..." .../api/run` works on the live URL
- [ ] Manual GitHub Actions run (`workflow_dispatch`) succeeds and updates Slack/Sheets
