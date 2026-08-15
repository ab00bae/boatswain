"""The API layer, exercised against a mock transport — never the live API."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from boatswain.github import (
    GitHubClient,
    GitHubError,
    load_fixture,
    resolve_token,
    to_item,
)
from tests.conftest import api_payload

SINCE = datetime(2026, 8, 1, tzinfo=timezone.utc)


def client_returning(handler) -> GitHubClient:
    """A client wired to a mock transport instead of the network."""
    client = GitHubClient(token="test-token")
    client._client = httpx.Client(
        transport=httpx.MockTransport(handler),
        headers=client._client.headers,
    )
    return client


class TestPayloadConversion:
    def test_an_issue_is_not_marked_as_a_pull_request(self):
        item = to_item(api_payload(1))

        assert item.is_pull_request is False

    def test_a_pull_request_is_detected_by_its_pull_request_key(self):
        item = to_item(api_payload(1, pull_request=True))

        assert item.is_pull_request is True

    def test_merged_at_is_read_from_the_nested_object(self):
        item = to_item(
            api_payload(1, pull_request=True, merged_at="2026-08-11T00:00:00Z")
        )

        assert item.is_merged is True

    def test_a_pull_request_closed_without_merging_has_no_merge_time(self):
        item = to_item(api_payload(1, pull_request=True, merged_at=None))

        assert item.is_merged is False

    def test_timestamps_are_timezone_aware(self):
        item = to_item(api_payload(1))

        assert item.created_at.tzinfo is not None

    def test_labels_are_flattened_to_names(self):
        item = to_item(api_payload(1))

        assert item.labels == ("bug",)

    def test_a_missing_author_does_not_crash(self):
        payload = api_payload(1)
        payload["user"] = None

        assert to_item(payload).author == "unknown"


class TestFetching:
    def test_open_and_closed_are_both_requested(self):
        seen_states = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen_states.append(request.url.params.get("state"))
            return httpx.Response(200, json=[])

        with client_returning(handler) as client:
            client.fetch_items("ab00bae/demo", since=SINCE)

        assert sorted(seen_states) == ["closed", "open"]

    def test_the_closed_request_is_bounded_by_since(self):
        """Fetching every closed issue ever would be slow and pointless."""
        params = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.params.get("state") == "closed":
                params.update(dict(request.url.params))
            return httpx.Response(200, json=[])

        with client_returning(handler) as client:
            client.fetch_items("ab00bae/demo", since=SINCE)

        assert "since" in params

    def test_the_open_request_is_not_bounded_by_since(self):
        """`since` filters on updated time, so it would hide the stale backlog."""
        params = {}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.params.get("state") == "open":
                params.update(dict(request.url.params))
            return httpx.Response(200, json=[])

        with client_returning(handler) as client:
            client.fetch_items("ab00bae/demo", since=SINCE)

        assert "since" not in params

    def test_pages_are_followed(self):
        calls = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            calls["n"] += 1
            if calls["n"] == 1:
                return httpx.Response(
                    200,
                    json=[api_payload(1)],
                    headers={
                        "Link": '<https://api.github.com/next-page>; rel="next"'
                    },
                )
            return httpx.Response(200, json=[api_payload(2)])

        with client_returning(handler) as client:
            items = client.fetch_items("ab00bae/demo", since=SINCE)

        assert {item.number for item in items} == {1, 2}

    def test_items_are_deduplicated_by_number(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=[api_payload(7)])

        with client_returning(handler) as client:
            items = client.fetch_items("ab00bae/demo", since=SINCE)

        assert len(items) == 1


class TestErrors:
    def test_missing_repository_is_reported_clearly(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"message": "Not Found"})

        with client_returning(handler) as client:
            with pytest.raises(GitHubError, match="not found"):
                client.fetch_items("ab00bae/nope", since=SINCE)

    def test_exhausted_rate_limit_says_so(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(403, headers={"X-RateLimit-Remaining": "0"})

        with client_returning(handler) as client:
            with pytest.raises(GitHubError, match="rate limit"):
                client.fetch_items("ab00bae/demo", since=SINCE)

    def test_bad_credentials_are_distinguished_from_rate_limiting(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, headers={"X-RateLimit-Remaining": "4999"})

        with client_returning(handler) as client:
            with pytest.raises(GitHubError, match="credentials"):
                client.fetch_items("ab00bae/demo", since=SINCE)

    def test_other_failures_include_the_status_code(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        with client_returning(handler) as client:
            with pytest.raises(GitHubError, match="500"):
                client.fetch_items("ab00bae/demo", since=SINCE)


class TestTokenResolution:
    def test_an_explicit_token_wins(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "from-env")

        assert resolve_token("explicit") == "explicit"

    def test_the_environment_is_used_next(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "from-env")

        assert resolve_token(None) == "from-env"

    def test_gh_token_is_also_accepted(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "from-gh-env")

        assert resolve_token(None) == "from-gh-env"


class TestFixtures:
    def test_a_saved_payload_loads_without_network(self, tmp_path):
        path = tmp_path / "items.json"
        path.write_text(json.dumps([api_payload(1), api_payload(2)]), encoding="utf-8")

        items = load_fixture(path)

        assert [item.number for item in items] == [1, 2]
