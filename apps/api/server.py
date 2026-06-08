from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creator_scout.config import load_env  # noqa: E402
from creator_scout.discovery.auth import authenticate_api_key  # noqa: E402
from creator_scout.discovery.service import DiscoveryService  # noqa: E402
from creator_scout.discovery.store import DiscoveryStore  # noqa: E402


load_env()


class ApiHandler(BaseHTTPRequestHandler):
    server_version = "CreatorScoutDiscovery/0.1"

    def _store(self) -> DiscoveryStore:
        return self.server.store  # type: ignore[attr-defined]

    def _service(self) -> DiscoveryService:
        return self.server.service  # type: ignore[attr-defined]

    def _json_body(self) -> dict:
        length = int(self.headers.get("content-length", "0"))
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body)

    def _api_key(self) -> str | None:
        auth = self.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            return auth.split(" ", 1)[1].strip()
        return self.headers.get("x-api-key")

    def _principal(self):
        return authenticate_api_key(self._store(), self._api_key())

    def _send(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: int, message: str) -> None:
        self._send(status, {"error": {"message": message, "status": status}})

    def do_GET(self) -> None:  # noqa: N802
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        principal = self._principal()
        if path == "/health":
            self._send(200, {"ok": True})
            return
        if path == "/v1/usage":
            if principal is None:
                self._send_error(401, "Missing or invalid API key")
                return
            self._send(200, self._service().usage(principal))
            return
        if path == "/v1/outreach/config":
            if principal is None:
                self._send_error(401, "Missing or invalid API key")
                return
            self._send(200, self._service().outreach_config(principal))
            return
        if path.startswith("/v1/campaigns/") and path.endswith("/creators"):
            if principal is None:
                self._send_error(401, "Missing or invalid API key")
                return
            campaign_id = path.split("/")[-2]
            try:
                limit = int(query_params.get("limit", ["50"])[0])
            except ValueError:
                self._send_error(400, "limit must be an integer")
                return
            payload = self._service().list_campaign_creators(campaign_id, principal, limit=limit)
            if payload is None:
                self._send_error(404, "Campaign not found")
                return
            self._send(200, payload)
            return
        if path.startswith("/v1/campaigns/"):
            if principal is None:
                self._send_error(401, "Missing or invalid API key")
                return
            campaign_id = path.rsplit("/", 1)[-1]
            payload = self._service().get_campaign(campaign_id, principal)
            if payload is None:
                self._send_error(404, "Campaign not found")
                return
            self._send(200, payload)
            return
        if path.startswith("/v1/jobs/"):
            if principal is None:
                self._send_error(401, "Missing or invalid API key")
                return
            job_id = path.rsplit("/", 1)[-1]
            payload = self._service().job_status(job_id, principal)
            if payload is None:
                self._send_error(404, "Job not found")
                return
            self._send(200, payload)
            return
        if path.startswith("/v1/brands/"):
            if principal is None:
                self._send_error(401, "Missing or invalid API key")
                return
            brand_id = path.rsplit("/", 1)[-1]
            payload = self._service().get_brand(brand_id, principal)
            if payload is None:
                self._send_error(404, "Brand not found")
                return
            self._send(200, payload)
            return
        if path.startswith("/v1/creators/"):
            if principal is None:
                self._send_error(401, "Missing or invalid API key")
                return
            creator_id = path.rsplit("/", 1)[-1]
            payload = self._service().get_creator(creator_id, principal)
            if payload is None:
                self._send_error(404, "Creator not found")
                return
            self._send(200, payload)
            return
        self._send_error(404, "Route not found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        principal = self._principal()
        try:
            payload = self._json_body()
            if path == "/v1/webhooks/autosend":
                self._send(200, self._service().handle_autosend_webhook(payload))
                return
            if path == "/v1/discovery/search":
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                self._send(200, self._service().search(payload, principal))
                return
            if path == "/v1/brand-scans":
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                self._send(202 if payload.get("enqueue_discovery") else 200, self._service().scan_brand(payload, principal))
                return
            if path == "/v1/campaigns":
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                self._send(202, self._service().create_campaign(payload, principal))
                return
            if path.startswith("/v1/campaigns/") and path.endswith("/outreach/send"):
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                parts = path.strip("/").split("/")
                if (
                    len(parts) != 7
                    or parts[:2] != ["v1", "campaigns"]
                    or parts[3] != "creators"
                    or parts[5:] != ["outreach", "send"]
                ):
                    self._send_error(404, "Route not found")
                    return
                response = self._service().send_campaign_creator_outreach(parts[2], parts[4], payload, principal)
                if response is None:
                    self._send_error(404, "Campaign creator not found")
                    return
                self._send(200, response)
                return
            if path.startswith("/v1/campaigns/") and path.endswith("/shortlist"):
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                campaign_id = path.split("/")[-2]
                response = self._service().build_campaign_shortlist(campaign_id, payload, principal)
                if response is None:
                    self._send_error(404, "Campaign not found")
                    return
                self._send(200, response)
                return
            if path.startswith("/v1/campaigns/") and path.endswith("/export"):
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                campaign_id = path.split("/")[-2]
                response = self._service().export_campaign_shortlist(campaign_id, principal)
                if response is None:
                    self._send_error(404, "Campaign not found")
                    return
                self._send(200, response)
                return
            if path == "/v1/discovery/refresh":
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                self._send(202, self._service().refresh(payload, principal))
                return
            if path == "/v1/discovery/ingest-query":
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                self._send(202, self._service().ingest_query(payload, principal))
                return
            if path.startswith("/v1/jobs/") and path.endswith("/retry"):
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                job_id = path.split("/")[-2]
                response = self._service().retry_job(job_id, principal)
                if response is None:
                    self._send_error(404, "Job not found")
                    return
                self._send(202, response)
                return
            self._send_error(404, "Route not found")
        except PermissionError as error:
            self._send_error(402, str(error))
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON body")
        except ValueError as error:
            self._send_error(400, str(error))

    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        principal = self._principal()
        try:
            payload = self._json_body()
            if path.startswith("/v1/campaigns/") and "/creators/" in path:
                if principal is None:
                    self._send_error(401, "Missing or invalid API key")
                    return
                parts = path.strip("/").split("/")
                if len(parts) != 5 or parts[:2] != ["v1", "campaigns"] or parts[3] != "creators":
                    self._send_error(404, "Route not found")
                    return
                campaign_id = parts[2]
                creator_id = parts[4]
                response = self._service().update_campaign_creator(campaign_id, creator_id, payload, principal)
                if response is None:
                    self._send_error(404, "Campaign creator not found")
                    return
                self._send(200, response)
                return
            self._send_error(404, "Route not found")
        except PermissionError as error:
            self._send_error(402, str(error))
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON body")
        except ValueError as error:
            self._send_error(400, str(error))

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        if os.environ.get("CREATOR_SCOUT_HTTP_LOGS") == "1":
            super().log_message(format, *args)


def create_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), ApiHandler)
    server.store = DiscoveryStore()  # type: ignore[attr-defined]
    server.service = DiscoveryService(server.store)  # type: ignore[attr-defined]
    return server


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    server = create_server(host, port)
    print(f"Creator Scout Discovery API running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
