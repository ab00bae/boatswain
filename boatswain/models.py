"""Domain types.

Deliberately plain: the GitHub payload is converted into these at the edge, so
the aggregation logic never touches a raw API dict and can be tested with
three-line objects instead of API fixtures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Item:
    """An issue or a pull request. GitHub models both as an "issue"."""

    number: int
    title: str
    author: str
    is_pull_request: bool
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    merged_at: datetime | None = None
    labels: tuple[str, ...] = ()

    @property
    def is_open(self) -> bool:
        return self.closed_at is None

    @property
    def is_merged(self) -> bool:
        return self.merged_at is not None

    def opened_within(self, since: datetime) -> bool:
        return self.created_at >= since

    def closed_within(self, since: datetime) -> bool:
        return self.closed_at is not None and self.closed_at >= since

    def idle_days(self, now: datetime) -> int:
        return (now - self.updated_at).days


@dataclass
class Report:
    """Everything the renderers need. No formatting decisions live here."""

    repo: str
    generated_at: datetime
    sprint_days: int
    stale_days: int

    issues_opened: int = 0
    issues_closed: int = 0
    issues_open_total: int = 0

    prs_opened: int = 0
    prs_merged: int = 0
    prs_closed_unmerged: int = 0
    prs_open_total: int = 0

    stale_issues: list[Item] = field(default_factory=list)
    oldest_open_issues: list[Item] = field(default_factory=list)
    top_contributors: list[tuple[str, int]] = field(default_factory=list)

    @property
    def window_start(self) -> datetime:
        return self.generated_at - timedelta(days=self.sprint_days)

    @property
    def issue_net_change(self) -> int:
        """Positive means the backlog grew over the window."""
        return self.issues_opened - self.issues_closed

    @property
    def pr_merge_rate(self) -> float | None:
        """Share of closed PRs that were merged rather than abandoned."""
        decided = self.prs_merged + self.prs_closed_unmerged
        return self.prs_merged / decided if decided else None
