"""Turning a list of items into a report.

Pure functions over `Item` objects — no network, no clock of their own. `now` is
passed in rather than read from the system, which is what lets the tests pin a
date and assert exact counts.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from boatswain.models import Item, Report

# Bots open and close a lot of pull requests; counting them as contributors
# drowns out the humans.
BOT_SUFFIX = "[bot]"


def summarise(
    items: list[Item],
    *,
    repo: str,
    now: datetime,
    sprint_days: int = 14,
    stale_days: int = 14,
    top_n: int = 5,
) -> Report:
    since = now - timedelta(days=sprint_days)

    report = Report(
        repo=repo, generated_at=now, sprint_days=sprint_days, stale_days=stale_days
    )

    issues = [item for item in items if not item.is_pull_request]
    pulls = [item for item in items if item.is_pull_request]

    report.issues_opened = sum(1 for i in issues if i.opened_within(since))
    report.issues_closed = sum(1 for i in issues if i.closed_within(since))
    report.issues_open_total = sum(1 for i in issues if i.is_open)

    report.prs_opened = sum(1 for p in pulls if p.opened_within(since))
    report.prs_merged = sum(1 for p in pulls if p.is_merged and p.closed_within(since))
    report.prs_closed_unmerged = sum(
        1 for p in pulls if p.closed_within(since) and not p.is_merged
    )
    report.prs_open_total = sum(1 for p in pulls if p.is_open)

    # Stale means open and untouched, which is not the same as merely old: an
    # issue commented on yesterday is still alive however long it has existed.
    report.stale_issues = sorted(
        (i for i in issues if i.is_open and i.idle_days(now) >= stale_days),
        key=lambda i: i.updated_at,
    )

    report.oldest_open_issues = sorted(
        (i for i in issues if i.is_open), key=lambda i: i.created_at
    )[:top_n]

    activity = Counter(
        item.author
        for item in items
        if item.opened_within(since) and not item.author.endswith(BOT_SUFFIX)
    )
    report.top_contributors = activity.most_common(top_n)

    return report
