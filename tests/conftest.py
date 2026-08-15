"""Shared fixtures.

Nothing here touches the network. The GitHub client is exercised against a
mock transport, so the suite runs identically offline and in CI.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from boatswain.models import Item

# A fixed "now" so every count in the tests is exact rather than relative to
# whenever the suite happens to run.
NOW = datetime(2026, 8, 15, 12, 0, 0, tzinfo=timezone.utc)


def days_ago(days: float) -> datetime:
    return NOW - timedelta(days=days)


def make_item(
    number: int = 1,
    *,
    is_pull_request: bool = False,
    created_days_ago: float = 1,
    updated_days_ago: float | None = None,
    closed_days_ago: float | None = None,
    merged: bool = False,
    author: str = "ab00bae",
    title: str = "Something",
) -> Item:
    closed_at = None if closed_days_ago is None else days_ago(closed_days_ago)
    return Item(
        number=number,
        title=title,
        author=author,
        is_pull_request=is_pull_request,
        created_at=days_ago(created_days_ago),
        updated_at=days_ago(
            created_days_ago if updated_days_ago is None else updated_days_ago
        ),
        closed_at=closed_at,
        merged_at=closed_at if (merged and closed_at) else None,
    )


@pytest.fixture
def now() -> datetime:
    return NOW


def api_payload(
    number: int = 1,
    *,
    pull_request: bool = False,
    merged_at: str | None = None,
    closed_at: str | None = None,
    state: str = "open",
    login: str = "ab00bae",
) -> dict:
    """A payload shaped the way the GitHub issues endpoint returns them."""
    payload = {
        "number": number,
        "title": f"Item {number}",
        "state": state,
        "user": {"login": login},
        "created_at": "2026-08-01T00:00:00Z",
        "updated_at": "2026-08-10T00:00:00Z",
        "closed_at": closed_at,
        "labels": [{"name": "bug"}],
    }
    if pull_request:
        payload["pull_request"] = {"merged_at": merged_at}
    return payload
