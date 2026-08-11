"""
Custom CrewAI tool: NewsFetcherTool

Calls the SerperDev "news" search endpoint directly via `requests`,
giving us full control over the query (topic, result count) instead of
relying on a prebuilt/black-box search tool.

results_per_topic is hard-capped regardless of what the agent
requests — this keeps the downstream summarizer LLM call small enough
to stay under Groq's free-tier tokens-per-minute limit.
"""

import os
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

MAX_RESULTS_PER_TOPIC = 5


class NewsFetcherInput(BaseModel):
    topics: str = Field(
        ...,
        description=(
            "Comma-separated list of topics to search news for, "
            "e.g. 'AI,Technology,Finance'."
        ),
    )
    results_per_topic: int = Field(
        default=3,
        description="How many headlines to fetch per topic (max 5).",
    )


class NewsFetcherTool(BaseTool):
    name: str = "NewsFetcherTool"
    description: str = (
        "Fetches the latest trending news headlines for one or more topics "
        "using the SerperDev News Search API. Returns headline, snippet, "
        "source URL, and topic for each result. results_per_topic is "
        "capped at 5 regardless of the value requested."
    )
    args_schema: Type[BaseModel] = NewsFetcherInput

    def _run(self, topics: str, results_per_topic: int = 3) -> str:
        results_per_topic = max(1, min(results_per_topic, MAX_RESULTS_PER_TOPIC))

        api_key = os.getenv("SERPER_API_KEY")
        if not api_key:
            return "ERROR: SERPER_API_KEY is not set in the environment."

        topic_list = [t.strip() for t in topics.split(",") if t.strip()]
        if not topic_list:
            return "ERROR: No valid topics provided."

        all_results = []
        endpoint = "https://google.serper.dev/news"
        headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}

        for topic in topic_list:
            payload = {"q": topic, "num": results_per_topic}
            try:
                resp = requests.post(
                    endpoint, headers=headers, json=payload, timeout=15
                )
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as exc:
                all_results.append(f"[{topic}] ERROR fetching news: {exc}")
                continue

            articles = data.get("news", [])[:results_per_topic]
            if not articles:
                all_results.append(f"[{topic}] No news found.")
                continue

            for item in articles:
                headline = item.get("title", "Untitled")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                all_results.append(
                    f"Topic: {topic}\n"
                    f"Headline: {headline}\n"
                    f"Snippet: {snippet}\n"
                    f"Source URL: {link}\n"
                    "---"
                )

        return "\n".join(all_results) if all_results else "No news found."
