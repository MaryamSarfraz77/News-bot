"""
Custom CrewAI tool: SummarizerTool

Makes a direct call to the Gemini API (generateContent) to condense
raw news text into a short, structured summary. Built as an explicit
tool (rather than relying on the agent's default LLM) so summarization
logic, prompt, and output shape are all controlled in one place.

Swapped from Groq: Groq's free-tier tokens-per-minute cap (6,000)
was getting exceeded by bundled multi-article summarization calls.
Gemini 3.1 Flash-Lite's free tier gives far more headroom.
"""

import os
from typing import Type

import requests
from crewai.tools import BaseTool
from pydantic import BaseModel, Field

GEMINI_ENDPOINT_TEMPLATE = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)


class SummarizerInput(BaseModel):
    raw_news_text: str = Field(
        ...,
        description=(
            "The raw news items (headline, snippet, source URL, topic) "
            "to summarize, as returned by NewsFetcherTool."
        ),
    )


class SummarizerTool(BaseTool):
    name: str = "SummarizerTool"
    description: str = (
        "Summarizes a block of raw news items into short, clear, "
        "de-duplicated 2-3 sentence summaries, keeping headline, "
        "source URL, and topic attached to each."
    )
    args_schema: Type[BaseModel] = SummarizerInput

    def _run(self, raw_news_text: str) -> str:
        api_key = os.getenv("GEMINI_API_KEY")
        model = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        if not api_key:
            return "ERROR: GEMINI_API_KEY is not set in the environment."

        system_prompt = (
            "You summarize raw news listings. For each unique story, "
            "output exactly this format:\n"
            "Topic: <topic>\nHeadline: <headline>\nSummary: <2-3 sentence summary>\n"
            "Source URL: <url>\n---\n"
            "Merge duplicate stories covering the same event into a single "
            "entry. Do not invent facts not present in the input."
        )

        endpoint = GEMINI_ENDPOINT_TEMPLATE.format(model=model)
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"parts": [{"text": raw_news_text}]}],
            "generationConfig": {"temperature": 0.3},
        }
        headers = {"Content-Type": "application/json"}

        try:
            resp = requests.post(
                endpoint,
                headers=headers,
                params={"key": api_key},
                json=payload,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.RequestException as exc:
            return f"ERROR calling Gemini API: {exc}"
        except (KeyError, IndexError):
            return "ERROR: Unexpected response shape from Gemini API."
