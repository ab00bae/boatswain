"""The reporting logic, which is where a wrong number would come from."""

from __future__ import annotations

import pytest

from boatswain.aggregate import summarise
from tests.conftest import make_item


def report_for(items, **kwargs):
    from tests.conftest import NOW

    defaults = {"repo": "ab00bae/demo", "now": NOW, "sprint_days": 14,
                "stale_days": 14}
    return summarise(items, **{**defaults, **kwargs})


class TestWindow:
    def test_item_opened_inside_the_window_counts(self):
        report = report_for([make_item(created_days_ago=3)])

        assert report.issues_opened == 1

    def test_item_opened_before_the_window_does_not_count_as_opened(self):
        report = report_for([make_item(created_days_ago=40)])

        assert report.issues_opened == 0

    def test_but_it_still_counts_as_open(self):
        """The backlog total is a snapshot, not a window measurement."""
        report = report_for([make_item(created_days_ago=40)])

        assert report.issues_open_total == 1

    def test_closed_inside_the_window_counts_as_closed(self):
        report = report_for([make_item(created_days_ago=40, closed_days_ago=2)])

        assert report.issues_closed == 1

    def test_closed_before_the_window_does_not(self):
        report = report_for([make_item(created_days_ago=60, closed_days_ago=30)])

        assert report.issues_closed == 0
        assert report.issues_open_total == 0

    def test_window_boundary_is_inclusive(self):
        report = report_for([make_item(created_days_ago=14)], sprint_days=14)

        assert report.issues_opened == 1


class TestIssuesVersusPullRequests:
    def test_pull_requests_are_not_counted_as_issues(self):
        """GitHub returns both from /issues; conflating them inflates every count."""
        report = report_for([make_item(1, is_pull_request=True)])

        assert report.issues_opened == 0
        assert report.prs_opened == 1

    def test_each_is_totalled_separately(self):
        report = report_for(
            [
                make_item(1),
                make_item(2),
                make_item(3, is_pull_request=True),
            ]
        )

        assert report.issues_open_total == 2
        assert report.prs_open_total == 1


class TestPullRequestOutcomes:
    def test_merged_pull_request_counts_as_merged(self):
        report = report_for(
            [make_item(1, is_pull_request=True, closed_days_ago=2, merged=True)]
        )

        assert report.prs_merged == 1
        assert report.prs_closed_unmerged == 0

    def test_closed_without_merging_is_counted_apart(self):
        report = report_for(
            [make_item(1, is_pull_request=True, closed_days_ago=2, merged=False)]
        )

        assert report.prs_merged == 0
        assert report.prs_closed_unmerged == 1

    def test_merge_rate_is_the_share_of_decided_pull_requests(self):
        report = report_for(
            [
                make_item(1, is_pull_request=True, closed_days_ago=1, merged=True),
                make_item(2, is_pull_request=True, closed_days_ago=1, merged=True),
                make_item(3, is_pull_request=True, closed_days_ago=1, merged=False),
                make_item(4, is_pull_request=True),  # still open, not yet decided
            ]
        )

        assert report.pr_merge_rate == pytest.approx(2 / 3)

    def test_merge_rate_is_undefined_when_nothing_closed(self):
        """Zero decided pull requests must not become a 0% merge rate."""
        report = report_for([make_item(1, is_pull_request=True)])

        assert report.pr_merge_rate is None


class TestStaleness:
    def test_untouched_open_issue_is_stale(self):
        report = report_for(
            [make_item(created_days_ago=60, updated_days_ago=30)], stale_days=14
        )

        assert [i.number for i in report.stale_issues] == [1]

    def test_recently_touched_issue_is_not_stale_however_old(self):
        """Age is not staleness — an issue commented on yesterday is alive."""
        report = report_for(
            [make_item(created_days_ago=300, updated_days_ago=1)], stale_days=14
        )

        assert report.stale_issues == []

    def test_closed_issues_are_never_stale(self):
        report = report_for(
            [make_item(created_days_ago=60, updated_days_ago=40, closed_days_ago=1)],
            stale_days=14,
        )

        assert report.stale_issues == []

    def test_stale_threshold_is_honoured(self):
        items = [make_item(1, created_days_ago=60, updated_days_ago=20)]

        assert report_for(items, stale_days=30).stale_issues == []
        assert len(report_for(items, stale_days=14).stale_issues) == 1

    def test_stale_issues_are_listed_most_neglected_first(self):
        report = report_for(
            [
                make_item(1, created_days_ago=60, updated_days_ago=20),
                make_item(2, created_days_ago=60, updated_days_ago=50),
                make_item(3, created_days_ago=60, updated_days_ago=35),
            ],
            stale_days=14,
        )

        assert [i.number for i in report.stale_issues] == [2, 3, 1]


class TestContributors:
    def test_contributors_are_ranked_by_items_opened(self):
        report = report_for(
            [
                make_item(1, author="alice"),
                make_item(2, author="alice"),
                make_item(3, author="bob"),
            ]
        )

        assert report.top_contributors == [("alice", 2), ("bob", 1)]

    def test_bots_are_excluded(self):
        """Dependabot would otherwise top every ranking."""
        report = report_for(
            [
                make_item(1, author="dependabot[bot]"),
                make_item(2, author="dependabot[bot]"),
                make_item(3, author="alice"),
            ]
        )

        assert report.top_contributors == [("alice", 1)]

    def test_only_activity_inside_the_window_counts(self):
        report = report_for(
            [make_item(1, author="alice", created_days_ago=90)]
        )

        assert report.top_contributors == []


class TestNetChange:
    def test_backlog_growth_is_positive(self):
        report = report_for(
            [make_item(1), make_item(2), make_item(3, closed_days_ago=1)]
        )

        assert report.issue_net_change == 2

    def test_backlog_shrink_is_negative(self):
        report = report_for(
            [
                make_item(1, created_days_ago=40, closed_days_ago=1),
                make_item(2, created_days_ago=40, closed_days_ago=2),
            ]
        )

        assert report.issue_net_change == -2


def test_an_empty_repository_produces_a_zeroed_report():
    report = report_for([])

    assert report.issues_opened == 0
    assert report.prs_opened == 0
    assert report.stale_issues == []
    assert report.pr_merge_rate is None
