"""
Local entry point. Loads environment variables from .env and runs the
news pipeline once.

Usage:
    python main.py                 # cron mode — uses NEWS_TOPICS from .env
    python main.py "AI in finance" # on-demand mode — single topic, structured output
"""

import sys
import json

from dotenv import load_dotenv

load_dotenv()

from src.crew import run_pipeline_cron, run_pipeline_topic  # noqa: E402
from src.utils.format_utils import print_cron_summary  # noqa: E402


if __name__ == "__main__":
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
        print(f"\n=== ON-DEMAND RUN: '{topic}' ===\n")
        output = run_pipeline_topic(topic)
        print(json.dumps(output, indent=2))
    else:
        output = run_pipeline_cron()
        print_cron_summary(output)
