"""
Vercel serverless entry point for the SCHEDULED pipeline. Vercel Cron
sends a GET request to this endpoint on the schedule defined in
vercel.json, which triggers one run of the full multi-topic pipeline
(topics from the NEWS_TOPICS env var).

This coexists with api/topic.py, which handles on-demand single-topic
requests from the UI. Both call the same underlying crew.
"""

import json
import os
import sys
import traceback
from http.server import BaseHTTPRequestHandler

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.crew import run_pipeline_cron  # noqa: E402


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Optional simple protection: require a secret query param or header
        # so random internet traffic can't trigger paid API calls.
        expected_secret = os.getenv("CRON_SECRET")
        if expected_secret:
            provided = self.headers.get("x-cron-secret") or self._query_param("secret")
            if provided != expected_secret:
                self._respond(401, {"error": "Unauthorized"})
                return

        try:
            # run_pipeline_cron() now returns a structured dict (counts,
            # timing, raw publish confirmation) rather than a plain string.
            result = run_pipeline_cron()
            self._respond(200, {"status": "success", "result": result})
        except Exception as exc:  # noqa: BLE001
            self._respond(
                500,
                {
                    "status": "error",
                    "message": str(exc),
                    "trace": traceback.format_exc(),
                },
            )

    def _query_param(self, key: str):
        from urllib.parse import urlparse, parse_qs

        query = parse_qs(urlparse(self.path).query)
        values = query.get(key)
        return values[0] if values else None

    def _respond(self, status_code: int, payload: dict):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))
