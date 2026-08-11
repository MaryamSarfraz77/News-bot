# Wire Desk — AI News Automation Bot

A multi-agent news pipeline built with **CrewAI**, triggered on a schedule
(every 6 hours) and run either locally or via a deployed Vercel function.

The pipeline fetches headlines for a fixed list of topics, summarizes them,
posts the summaries to a private Slack channel, and logs them to Google
Sheets.

## How It Works

Three agents run sequentially, each using a custom tool:

| Agent | Tool | Job |
|---|---|---|
| Researcher | `NewsFetcherTool` | Searches SerperDev for the latest headlines on the given topic(s) |
| Summarizer | `SummarizerTool` | Condenses raw headlines into short, de-duplicated summaries via Gemini |
| Publisher | `SlackBotTool` + `SheetsLoggerTool` | Posts to a private Slack channel and logs rows to Google Sheets |

```
   GitHub Actions ───▶ GET /api/run.py  ───▶ CrewAI pipeline ───▶ Slack + Google Sheets
   (every 6h,             (deployed on          (NEWS_TOPICS
    cron schedule)          Vercel)               from env)
```

GitHub Actions replaces Vercel's built-in Cron here because Vercel's free
Hobby plan only allows once-per-day schedules. The Actions workflow does
nothing but call the already-deployed `/api/run` endpoint — all pipeline
logic still runs inside the Vercel function, not inside CI.

## Tech Stack

- **CrewAI** — multi-agent orchestration
- **Gemini API (3.1 Flash-Lite)** — LLM summarization + agent reasoning
- **SerperDev API** — news search
- **Slack Incoming Webhook** — private channel posting
- **Google Sheets API** (service account + `gspread`) — structured logging
- **Vercel** — hosts the Python function (`api/run.py`)
- **GitHub Actions** — free scheduled trigger, every 6 hours

## Project Structure

```
news-bot/
├── config/agents.yaml        # Agent roles/goals (verbose off — see Notes)
├── config/tasks.yaml         # Task descriptions (rate-limit-capped)
├── src/crew.py               # Crew wiring — run_pipeline_cron()
├── src/tools/                # Custom CrewAI tools
├── src/utils/
│   ├── parser.py             # Shared summarizer-output parser
│   └── format_utils.py       # Prints the boxed terminal summary
├── local_main.py             # Local CLI entry point
├── api/run.py                # Vercel function entry point (GET, multi-topic)
├── .github/workflows/scheduled-run.yml  # 6-hour trigger for api/run.py
└── vercel.json                # Function config (no crons — see Notes)
```

## Setup

See `SETUP_GUIDE.md` for the full walkthrough: local run + verification,
pushing to GitHub, and deploying to Vercel.

Quick start (local):

```bash
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python local_main.py
```

## Environment Variables

See `.env.example` for the full list. At minimum you need: `GEMINI_API_KEY`,
`SERPER_API_KEY`, `SLACK_WEBHOOK_URL`, `GOOGLE_SHEET_ID`, and either
`GOOGLE_SERVICE_ACCOUNT_FILE` (local) or `GOOGLE_SERVICE_ACCOUNT_JSON` (Vercel).

## Notes

- Vercel's **Hobby plan** only supports daily cron schedules, so the
  6-hourly schedule lives in `.github/workflows/scheduled-run.yml`
  instead of `vercel.json`. It just pings the deployed `/api/run`
  endpoint — no separate hosting needed.
- `NewsFetcherTool` caps results at 5 per topic regardless of what's
  requested — Gemini's free-tier headroom is a safety margin, not an
  invitation to raise this without re-checking limits.
- The Slack webhook is created *inside* a private channel, so no bot
  token or channel-invite step is needed.
- Terminal output prints a clean boxed summary instead of CrewAI's raw
  verbose agent-reasoning log — `verbose: false` on every agent in
  `config/agents.yaml` and on the `Crew` in `src/crew.py` (see
  `src/utils/format_utils.py` for the summary formatter).
