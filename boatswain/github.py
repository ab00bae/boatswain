"""GitHub REST access.

The only module that touches the network. Everything it returns is a plain
`Item`, so nothing downstream depends on the shape of a GitHub payload — and
the tests never need a live token.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from boatswain.models import Item

API_ROOT = "https://api.github.com"
PAGE_SIZE = 100
# GitHub refuses requests without one, and it identifies the client in logs.
USER_AGENT = "boatswain/0.1"


class GitHubError(Exception):
    """A request failed in a way the user can act on."""


def resolve_token(explicit: str | None = None) -> str | None:
    """Find a token: the flag, then the environment, then the gh CLI.

    Falling back to `gh auth token` means anyone who has already signed in with
    the GitHub CLI needs no extra setup.
    """
    if explicit:
        return explicit

    for variable in ("GITHUB_TOKEN", "GH_TOKEN"):
        if token := os.environ.get(variable):
            return token

    try:
        finished = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    token = finished.stdout.strip()
    return token or None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def to_item(payload: dict[str, Any]) -> Item:
    """Convert one API record. GitHub returns pull requests from /issues too."""
    pull_request = payload.get("pull_request")

    return Item(
        number=payload["number"],
        title=payload.get("title", ""),
        author=(payload.get("user") or {}).get("login", "unknown"),
        is_pull_request=pull_request is not None,
        created_at=_parse_time(payload["created_at"]),
        updated_at=_parse_time(payload.get("updated_at")) or _parse_time(payload["created_at"]),
        closed_at=_parse_time(payload.get("closed_at")),
        # Only present on pull requests, and null on ones that were closed
        # without being merged.
        merged_at=_parse_time((pull_request or {}).get("merged_at")),
        labels=tuple(
            label["name"] if isinstance(label, dict) else str(label)
            for label in payload.get("labels", [])
        ),
    )


class GitHubClient:
    def __init__(self, token: str | None = None, timeout: float = 30.0) -> None:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        self._client = httpx.Client(headers=headers, timeout=timeout)

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    def _paginate(self, url: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []

        while url:
            response = self._client.get(url, params=params)
            self._raise_for_status(response, url)
            collected.extend(response.json())

            # The Link header carries the next page; params are already baked
            # into that URL, so they must not be sent again.
            url = response.links.get("next", {}).get("url", "")
            params = {}

        return collected

    @staticmethod
    def _raise_for_status(response: httpx.Response, url: str) -> None:
        if response.is_success:
            return

        if response.status_code == 404:
            raise GitHubError(
                f"Repository not found, or the token cannot see it: {url}"
            )
        if response.status_code in (401, 403):
            if response.headers.get("X-RateLimit-Remaining") == "0":
                raise GitHubError(
                    "GitHub rate limit exhausted. Supply a token with --token, "
                    "set GITHUB_TOKEN, or wait for the limit to reset."
                )
            raise GitHubError(
                "GitHub rejected the credentials. Set GITHUB_TOKEN, pass "
                "--token, or run 'gh auth login'."
            )

        raise GitHubError(f"GitHub returned {response.status_code} for {url}")

    def fetch_items(self, repo: str, since: datetime) -> list[Item]:
        """Everything needed for a report on `repo` over the window from `since`.

        Two requests, not one. The `since` filter matches on *updated* time, so
        a single filtered call would silently omit open issues that nobody has
        touched — exactly the ones a staleness report exists to surface. So:
        every open item, plus everything closed inside the window.
        """
        url = f"{API_ROOT}/repos/{repo}/issues"
        base = {"per_page": PAGE_SIZE, "sort": "updated", "direction": "desc"}

        payloads = self._paginate(url, {**base, "state": "open"})
        payloads += self._paginate(
            url, {**base, "state": "closed", "since": since.isoformat()}
        )

        # Open and closed are disjoint, but dedupe by number regardless so a
        # race between the two calls cannot double-count an item.
        unique = {payload["number"]: payload for payload in payloads}
        return [to_item(payload) for payload in unique.values()]


def load_fixture(path: str | Path) -> list[Item]:
    """Read items from a saved JSON payload instead of calling the API.

    Lets the demo run with no token and no network, and keeps its output
    identical on every machine.
    """
    payloads = json.loads(Path(path).read_text(encoding="utf-8"))
    return [to_item(payload) for payload in payloads]
