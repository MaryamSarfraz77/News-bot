"""
Formats a clean, boxed summary of a cron pipeline run for the terminal —
used instead of letting CrewAI's raw verbose agent-reasoning log
("Thought:/Action:/Observation:...") hit stdout. Agent/crew verbose is
turned off (see config/agents.yaml, src/crew.py); this is what prints
in its place.

Consumes the dict returned by src.crew.run_pipeline_cron().
"""

import datetime


def print_cron_summary(result: dict) -> None:
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    topics_str = ", ".join(result.get("topics", []))

    def fmt_count(value, label):
        if value is None:
            return f"⚠ unknown ({label})"
        return f"✅ ({value} {label})"

    width = 42
    line = "=" * width
    print(line)
    print(" WIRE DESK — SCHEDULED RUN")
    print(f" {now}")
    print(line)
    print(f" Topics:              {topics_str}")
    print(f" Articles found:      {result.get('articles_found', 0)}")
    print(f" Summaries made:      {result.get('summaries_made', 0)}")
    print(f" Posted to Slack:     {fmt_count(result.get('slack_posted'), 'messages')}")
    print(f" Logged to Sheet:     {fmt_count(result.get('sheets_logged'), 'rows')}")
    print(f" Duration:            {result.get('duration_seconds', 0):.1f}s")
    print(line)
