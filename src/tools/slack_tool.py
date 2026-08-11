"""
Custom CrewAI tool: SlackBotTool

Posts formatted news updates to a Slack channel using an Incoming
Webhook. The webhook URL is created from *inside* a private channel in
Slack (Slack App -> Incoming Webhooks -> "Add New Webhook to Workspace"
-> select the private channel), so no bot token or channel-join step
is required — the webhook is already scoped to that private channel.
"""

import os
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
from slack_sdk.webhook import WebhookClient


class SlackBotInput(BaseModel):
    formatted_news_text: str = Field(
        ...,
        description=(
            "The final summarized news text to post to Slack. Should "
            "contain headline, summary, and source URL per item."
        ),
    )


class SlackBotTool(BaseTool):
    name: str = "SlackBotTool"
    description: str = (
        "Posts a formatted news update (headline + summary + link) to "
        "the team's private Slack channel via an Incoming Webhook."
    )
    args_schema: Type[BaseModel] = SlackBotInput

    def _run(self, formatted_news_text: str) -> str:
        webhook_url = os.getenv("SLACK_WEBHOOK_URL")
        if not webhook_url:
            return "ERROR: SLACK_WEBHOOK_URL is not set in the environment."

        # Slack blocks have a ~3000 char limit per text block; chunk if needed.
        max_len = 2900
        chunks = [
            formatted_news_text[i : i + max_len]
            for i in range(0, len(formatted_news_text), max_len)
        ] or [formatted_news_text]

        client = WebhookClient(webhook_url)
        posted = 0
        for i, chunk in enumerate(chunks):
            title = ":newspaper: *Latest News Update*" if i == 0 else ""
            text = f"{title}\n{chunk}".strip()
            response = client.send(text=text)
            if response.status_code != 200:
                return (
                    f"ERROR: Slack webhook returned {response.status_code}: "
                    f"{response.body}"
                )
            posted += 1

        return f"Posted {posted} message(s) to Slack successfully."
