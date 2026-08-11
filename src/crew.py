"""
Defines the AI News Automation Crew: three agents (Researcher,
Summarizer, Publisher) running sequentially, each equipped with the
custom tool(s) it needs.

Two entry points share this same crew:
- run_pipeline_cron()  → used by api/run.py (Vercel Cron). Multiple
  topics from NEWS_TOPICS env var. Returns a structured dict (counts +
  timing + raw confirmation) so callers can print a clean summary
  instead of CrewAI's raw verbose agent-reasoning log.
- run_pipeline_topic()  → used by api/topic.py (on-demand UI request).
  A single user-supplied topic. Returns structured JSON (items list +
  publish status) for the frontend to render as cards.

LLM: Gemini 3.1 Flash-Lite (swapped from Groq — Gemini's free-tier
tokens-per-minute ceiling is far higher, which is what was causing the
429 rate-limit errors under Groq).
"""

import os
import re
import time
import yaml
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai.llm import LLM

from src.tools import (
    NewsFetcherTool,
    SummarizerTool,
    SlackBotTool,
    SheetsLoggerTool,
)
from src.utils.parser import parse_news_items

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_yaml(filename: str) -> dict:
    with open(CONFIG_DIR / filename, "r") as f:
        return yaml.safe_load(f)


def build_crew() -> Crew:
    agents_cfg = _load_yaml("agents.yaml")
    tasks_cfg = _load_yaml("tasks.yaml")

    llm = LLM(
        model=f"gemini/{os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite')}",
        api_key=os.getenv("GEMINI_API_KEY"),
        max_retries=5,
    )

    # max_iter caps how many reasoning (LLM call) rounds a single agent can
    # take on one task before it's forced to give a final answer. These are
    # simple, single/dual-tool tasks, so they should never need many rounds
    # — capping this prevents a confused agent from silently burning through
    # the Gemini free-tier's 15-requests-per-minute quota on retries.
    researcher = Agent(
        config=agents_cfg["researcher"], tools=[NewsFetcherTool()], llm=llm, max_iter=5
    )
    summarizer = Agent(
        config=agents_cfg["summarizer"], tools=[SummarizerTool()], llm=llm, max_iter=5
    )
    publisher = Agent(
        config=agents_cfg["publisher"],
        tools=[SlackBotTool(), SheetsLoggerTool()],
        llm=llm,
        max_iter=6,  # one extra round: it has two tools to call in sequence
    )

    fetch_task = Task(config=tasks_cfg["fetch_news_task"], agent=researcher)
    summarize_task = Task(
        config=tasks_cfg["summarize_news_task"],
        agent=summarizer,
        context=[fetch_task],
    )
    publish_task = Task(
        config=tasks_cfg["publish_news_task"],
        agent=publisher,
        context=[summarize_task],
    )

    return Crew(
        agents=[researcher, summarizer, publisher],
        tasks=[fetch_task, summarize_task, publish_task],
        process=Process.sequential,
        verbose=True,
        # Throttles ALL LLM calls (agent reasoning + tool-triggered calls)
        # across the whole crew to stay under Gemini's free-tier cap of 15
        # requests/minute for gemini-3.1-flash-lite. CrewAI will pause
        # automatically between calls instead of firing them back-to-back
        # and tripping a 429. Kept a few requests under the hard limit as
        # a safety margin — see GEMINI_MODEL / quota notes in README.md.
        max_rpm=10,
    )


def run_pipeline_cron() -> dict:
    """
    Cron entry point: runs the full multi-topic pipeline (topics come
    from the NEWS_TOPICS env var) and returns a structured dict with
    counts, timing, and the publisher's raw confirmation text. Used by
    api/run.py and by main.py to print a clean summary instead of
    CrewAI's raw verbose agent-reasoning log.
    """
    topics_str = os.getenv("NEWS_TOPICS", "AI,Technology")
    topics = [t.strip() for t in topics_str.split(",") if t.strip()]

    start = time.time()
    crew = build_crew()
    result = crew.kickoff(inputs={"topics": topics_str})
    duration = time.time() - start

    tasks_output = getattr(result, "tasks_output", None) or []
    fetch_raw = getattr(tasks_output[0], "raw", "") if len(tasks_output) >= 1 else ""
    summarize_raw = getattr(tasks_output[1], "raw", "") if len(tasks_output) >= 2 else ""
    publish_raw = getattr(tasks_output[2], "raw", "") if len(tasks_output) >= 3 else str(result)

    articles_found = fetch_raw.count("Headline:")
    summaries_made = len(parse_news_items(summarize_raw))

    slack_match = re.search(r"[Pp]osted\s+(\d+)", publish_raw)
    sheets_match = re.search(r"[Ll]ogged\s+(\d+)", publish_raw)
    slack_posted = int(slack_match.group(1)) if slack_match else None
    sheets_logged = int(sheets_match.group(1)) if sheets_match else None

    return {
        "topics": topics,
        "articles_found": articles_found,
        "summaries_made": summaries_made,
        "slack_posted": slack_posted,
        "sheets_logged": sheets_logged,
        "duration_seconds": round(duration, 1),
        "publish_status": publish_raw,
    }


def run_pipeline_topic(topic: str) -> dict:
    """
    On-demand entry point: runs the pipeline for a single user-supplied
    topic. Slack posting and Sheets logging still happen (same as
    cron), but this also returns structured JSON built from the
    summarizer's output, so the frontend can render news cards
    immediately without waiting on/parsing the publisher's free text.
    Used by api/topic.py.
    """
    crew = build_crew()
    result = crew.kickoff(inputs={"topics": topic})

    # crew.kickoff() returns a CrewOutput with per-task outputs in
    # `tasks_output`, in the same order the tasks were defined:
    # [0] fetch_task, [1] summarize_task, [2] publish_task
    tasks_output = getattr(result, "tasks_output", None)

    summarize_raw = ""
    publish_status = str(result)

    if tasks_output and len(tasks_output) >= 2:
        summarize_raw = getattr(tasks_output[1], "raw", "") or ""
    if tasks_output and len(tasks_output) >= 3:
        publish_status = getattr(tasks_output[2], "raw", "") or publish_status

    items = parse_news_items(summarize_raw)

    return {
        "items": items,
        "publish_status": publish_status,
    }