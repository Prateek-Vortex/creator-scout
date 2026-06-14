"""TinyFish Agent listicle-extractor.

This adapter indexes creator metadata extracted from third-party listicles
("Top 12 skincare creators in India" style pages). It does NOT fetch the
linked social profiles — handles are stored as cached metadata only. The
existing compliance layer still blocks any later fetch of Instagram /
TikTok / LinkedIn / Facebook URLs.
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpClient
from creator_scout.discovery.models import Platform
from creator_scout.discovery.normalize import infer_platform_from_url, normalize_handle


GOAL_PROMPT = (
    "Extract every individual creator (person or brand-account) mentioned on this page "
    "and return them as a JSON array. Each item must be a JSON object with these fields:\n"
    "- name: the creator's display name\n"
    "- platform: one of [instagram, tiktok, youtube, x, twitter, twitch]. Skip blog, podcast, "
    "newsletter and general website mentions; we only want social creators.\n"
    "- handle: the username on that platform, without a leading @\n"
    "- profile_url: the full URL to their primary profile on that platform\n"
    "- secondary_accounts: optional list of objects {platform, handle, profile_url} for any "
    "additional platforms they're listed on\n"
    "- niche: a 1-3 word topic label (e.g. 'skincare', 'tech reviewer', 'beauty')\n"
    "- topics: optional list of single-word topic tags\n"
    "- bio: optional one-sentence description from the page\n\n"
    "Critical rules:\n"
    "1. Return ONLY a JSON array. No prose. No markdown fences. No explanation.\n"
    "2. If a creator has no identifiable handle AND no profile_url, skip them.\n"
    "3. If the same person is listed under multiple platforms, use their most prominent "
    "platform as `platform` and put the rest in `secondary_accounts`.\n"
    "4. Do not invent handles. If you can't read the handle from the page, skip that field."
)


class AgentParseError(AdapterError):
    """Raised when the Agent response can't be coerced into creator records."""


_PLATFORM_ALIASES: dict[str, Platform] = {
    "instagram": Platform.INSTAGRAM,
    "ig": Platform.INSTAGRAM,
    "insta": Platform.INSTAGRAM,
    "tiktok": Platform.TIKTOK,
    "tt": Platform.TIKTOK,
    "youtube": Platform.YOUTUBE,
    "yt": Platform.YOUTUBE,
    "x": Platform.X,
    "twitter": Platform.X,
    "twitch": Platform.TWITCH,
}


def _coerce_platform(value: str | None, profile_url: str | None) -> Platform:
    if value:
        platform = _PLATFORM_ALIASES.get(value.strip().lower())
        if platform is not None:
            return platform
    if profile_url:
        return infer_platform_from_url(profile_url)
    return Platform.UNKNOWN


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _parse_agent_result(raw: Any) -> list[dict]:
    """Coerce a free-form Agent `result` field into a list of creator dicts."""
    if raw is None:
        raise AgentParseError("Agent returned no result")

    # The Agent may return the array directly, a dict wrapping it, or a string
    # containing the JSON. Handle each case.
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]

    if isinstance(raw, dict):
        # Direct list keys.
        for key in ("creators", "items", "results", "data"):
            value = raw.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        # TinyFish Agent wraps its payload in {"result": ...} (sometimes
        # repeatedly). Unwrap one level and recurse so nested {"result":
        # "<JSON string>"} or {"result": {"creators": [...]}} both work.
        if "result" in raw:
            return _parse_agent_result(raw["result"])
        # Last resort: if the dict itself looks like a single creator (has
        # name + (handle or profile_url)), wrap it.
        if raw.get("name") and (raw.get("handle") or raw.get("profile_url")):
            return [raw]
        raise AgentParseError(f"Agent dict had no known list key: {list(raw.keys())}")

    if isinstance(raw, str):
        cleaned = _strip_code_fences(raw)
        # Try the cleaned string first; if that fails, slice from first '[' to last ']'.
        for candidate in (cleaned, _slice_json_array(cleaned)):
            if not candidate:
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            return _parse_agent_result(parsed)
        raise AgentParseError("Agent string result was not valid JSON")

    raise AgentParseError(f"Agent result was an unexpected type: {type(raw).__name__}")


def _slice_json_array(text: str) -> str | None:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return None
    return text[start : end + 1]


class TinyFishAgentAdapter:
    """Run TinyFish's Agent API against listicle URLs to extract per-creator rows."""

    provider = "tinyfish_agent"

    def __init__(
        self,
        api_key: str,
        http: HttpClient | None = None,
        *,
        base_url: str = "https://agent.tinyfish.ai",
        timeout: float = 180.0,
        poll_interval: float = 3.0,
    ) -> None:
        if not api_key:
            raise AdapterError("TINYFISH_API_KEY is required for TinyFishAgentAdapter")
        self.api_key = api_key
        self.http = http or HttpClient()
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.poll_interval = max(0.5, float(poll_interval))

    @property
    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "content-type": "application/json"}

    def extract_creators(self, listicle_url: str, *, source_title: str | None = None) -> AdapterResult:
        assert_public_fetch_allowed(listicle_url)

        start_response = self.http.post_json(
            f"{self.base_url}/v1/automation/run-async",
            {"url": listicle_url, "goal": GOAL_PROMPT},
            self._headers,
        )
        if start_response.status >= 400:
            raise AdapterError(
                f"TinyFish Agent start error {start_response.status}: {start_response.text()[:300]}"
            )
        start_body = start_response.json()
        run_id = start_body.get("run_id") or start_body.get("id")
        if not run_id:
            raise AdapterError(f"TinyFish Agent start response missing run_id: {start_body}")

        run_body = self._poll(run_id)
        result_payload = run_body.get("result")
        num_of_steps = int(run_body.get("num_of_steps") or 0)

        items = _parse_agent_result(result_payload)
        records = []
        for item in items:
            record = self._record_from_item(item, listicle_url, source_title, run_id, num_of_steps)
            if record is not None:
                records.append(record)

        return AdapterResult(
            records=records,
            provider=self.provider,
            source_url=listicle_url,
            raw={"run_id": run_id, "num_of_steps": num_of_steps},
        )

    def _poll(self, run_id: str) -> dict:
        deadline = time.monotonic() + self.timeout
        last_body: dict[str, Any] = {}
        while True:
            response = self.http.get(f"{self.base_url}/v1/runs/{run_id}", self._headers)
            if response.status >= 400:
                raise AdapterError(
                    f"TinyFish Agent poll error {response.status}: {response.text()[:300]}"
                )
            body = response.json()
            last_body = body
            status = str(body.get("status") or "").upper()
            if status == "COMPLETED":
                return body
            if status in {"FAILED", "ERROR", "CANCELLED"}:
                raise AdapterError(
                    f"TinyFish Agent run {run_id} ended with status={status}: "
                    f"{body.get('error') or body.get('result')}"
                )
            if time.monotonic() > deadline:
                raise AdapterError(
                    f"TinyFish Agent run {run_id} did not finish within {self.timeout:.0f}s "
                    f"(last status={status})"
                )
            time.sleep(self.poll_interval)

    def _record_from_item(
        self,
        item: dict,
        listicle_url: str,
        source_title: str | None,
        run_id: str,
        num_of_steps: int,
    ) -> dict | None:
        name = str(item.get("name") or "").strip()
        primary_handle = normalize_handle(str(item.get("handle") or ""))
        primary_url = str(item.get("profile_url") or "").strip()
        primary_platform = _coerce_platform(item.get("platform"), primary_url or None)

        if primary_platform is Platform.UNKNOWN:
            return None
        if not primary_handle and not primary_url:
            return None
        if not name:
            name = primary_handle or primary_url

        accounts: list[dict] = []
        seen_account_keys: set[tuple[str, str]] = set()

        def _add_account(platform: Platform, handle: str, profile_url: str, bio: str = "") -> None:
            key = (platform.value, (handle or profile_url).lower())
            if key in seen_account_keys:
                return
            seen_account_keys.add(key)
            accounts.append(
                {
                    "platform": platform.value,
                    "handle": handle,
                    "profile_url": profile_url,
                    "bio": bio,
                }
            )

        bio = str(item.get("bio") or "").strip()
        _add_account(primary_platform, primary_handle, primary_url, bio)

        for extra in item.get("secondary_accounts") or []:
            if not isinstance(extra, dict):
                continue
            extra_url = str(extra.get("profile_url") or "").strip()
            extra_platform = _coerce_platform(extra.get("platform"), extra_url or None)
            if extra_platform is Platform.UNKNOWN:
                continue
            extra_handle = normalize_handle(str(extra.get("handle") or ""))
            if not extra_handle and not extra_url:
                continue
            _add_account(extra_platform, extra_handle, extra_url)

        topics_raw = item.get("topics") or []
        topics = [str(topic).strip().lower() for topic in topics_raw if str(topic).strip()]

        record = {
            "display_name": name,
            "primary_niche": str(item.get("niche") or "creator"),
            "summary": bio,
            "topics": topics,
            "accounts": accounts,
            "sources": [
                {
                    "source_url": listicle_url,
                    "source_type": "tinyfish_agent_listicle",
                    "confidence": 0.55,
                    "fields_found": {
                        "agent_run_id": run_id,
                        "list_title": source_title,
                        "num_of_steps": num_of_steps,
                    },
                }
            ],
        }
        return record
