from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(slots=True)
class HttpResponse:
    status: int
    body: bytes
    headers: dict[str, str]
    url: str

    def json(self) -> dict:
        return json.loads(self.body.decode("utf-8"))

    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class HttpClient:
    def __init__(self, timeout: int = 20, user_agent: str = "CreatorScoutBot/0.1") -> None:
        self.timeout = timeout
        self.user_agent = user_agent

    def get(self, url: str, headers: dict[str, str] | None = None) -> HttpResponse:
        request = urllib.request.Request(url, headers=self._headers(headers), method="GET")
        return self._open(request)

    def post_json(self, url: str, payload: dict, headers: dict[str, str] | None = None) -> HttpResponse:
        data = json.dumps(payload).encode("utf-8")
        request_headers = {"content-type": "application/json", **self._headers(headers)}
        request = urllib.request.Request(url, data=data, headers=request_headers, method="POST")
        return self._open(request)

    def _headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        return {"user-agent": self.user_agent, **(headers or {})}

    def _open(self, request: urllib.request.Request) -> HttpResponse:
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return HttpResponse(
                    status=response.status,
                    body=response.read(),
                    headers={key.lower(): value for key, value in response.headers.items()},
                    url=response.geturl(),
                )
        except urllib.error.HTTPError as error:
            return HttpResponse(
                status=error.code,
                body=error.read(),
                headers={key.lower(): value for key, value in error.headers.items()},
                url=request.full_url,
            )

