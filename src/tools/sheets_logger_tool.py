"""
Custom CrewAI tool: SheetsLoggerTool

Parses the summarized news text (format produced by the Summarizer
task) and appends one row per story into a Google Sheet using a
service account, via gspread. Fields: Date, Headline, Summary, Source URL.
"""

import json
import os
from datetime import date
from typing import Type

import gspread
from crewai.tools import BaseTool
from google.oauth2.service_account import Credentials
from pydantic import BaseModel, Field

from src.utils.parser import parse_news_items

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class SheetsLoggerInput(BaseModel):
    formatted_news_text: str = Field(
        ...,
        description=(
            "The summarized news text to log. Expected to contain "
            "'Headline:', 'Summary:', and 'Source URL:' lines per item."
        ),
    )


def _get_credentials() -> Credentials:
    """
    Supports two ways of providing the service account key:
    - GOOGLE_SERVICE_ACCOUNT_JSON: the raw JSON string (used on Vercel)
    - GOOGLE_SERVICE_ACCOUNT_FILE: a path to the JSON key file (local dev)
    """
    json_str = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if json_str:
        info = json.loads(json_str)
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    file_path = os.getenv(
        "GOOGLE_SERVICE_ACCOUNT_FILE", "credentials/google_service_account.json"
    )
    return Credentials.from_service_account_file(file_path, scopes=SCOPES)


class SheetsLoggerTool(BaseTool):
    name: str = "SheetsLoggerTool"
    description: str = (
        "Logs summarized news items into Google Sheets. Appends one row "
        "per story with Date, Headline, Summary, and Source URL."
    )
    args_schema: Type[BaseModel] = SheetsLoggerInput

    def _run(self, formatted_news_text: str) -> str:
        sheet_id = os.getenv("GOOGLE_SHEET_ID")
        worksheet_name = os.getenv("GOOGLE_SHEET_WORKSHEET_NAME", "Sheet1")
        if not sheet_id:
            return "ERROR: GOOGLE_SHEET_ID is not set in the environment."

        try:
            creds = _get_credentials()
            client = gspread.authorize(creds)
            sheet = client.open_by_key(sheet_id)
            worksheet = sheet.worksheet(worksheet_name)
        except Exception as exc:  # noqa: BLE001
            return f"ERROR connecting to Google Sheets: {exc}"

        items = parse_news_items(formatted_news_text)
        print("========== SHEETS DEBUG ==========")
        print(f"Parsed items: {len(items)}")
        for i, item in enumerate(items, start=1):
            print(f"ITEM {i}:")
            print(f"  Headline: {item['headline']}")
            print(f"  URL: {item['url']}")
            
        print("===================================")
        
        if not items:
            return "No parseable news items found to log."

        today = date.today().isoformat()
        rows = [
            [today, item["headline"], item["summary"], item["url"]] for item in items
        ]

        try:
            worksheet.append_rows(rows, value_input_option="USER_ENTERED")
        except Exception as exc:  # noqa: BLE001
            return f"ERROR appending rows to Google Sheets: {exc}"

        return f"Logged {len(rows)} row(s) to Google Sheets."
