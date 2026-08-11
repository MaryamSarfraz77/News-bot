"""
Vercel serverless entry point for the scheduled news pipeline.

This endpoint handles GET requests and triggers one run of the
full multi-topic news pipeline.
"""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs


# Add the project root to Python's import path
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from src.crew import run_pipeline_cron


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        # Optional protection using CRON_SECRET
        expected_secret = os.getenv("CRON_SECRET")

        if expected_secret:
            provided = (
                self.headers.get("x-cron-secret")
                or self._query_param("secret")
            )

            if provided != expected_secret:
                self._respond(401, {"error": "Unauthorized"})
                return

        try:
            # Run the news pipeline
            result = run_pipeline_cron()

            self._respond(
                200,
                {
                    "status": "success",
                    "result": result,
                },
            )

        except Exception as exc:
            self._respond(
                500,
                {
                    "status": "error",
                    "message": str(exc),
                    "trace": traceback.format_exc(),
                },
            )

    def _query_param(self, key: str):
        query = parse_qs(urlparse(self.path).query)
        values = query.get(key)

        return values[0] if values else None

    def _respond(self, status_code: int, payload: dict):
        self.send_response(status_code)

        self.send_header(
            "Content-Type",
            "application/json"
        )

        self.end_headers()

        self.wfile.write(
            json.dumps(payload).encode("utf-8")
        )