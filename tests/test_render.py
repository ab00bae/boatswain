"""Rendering — the numbers must survive the trip to markdown intact."""

from __future__ import annotations

from boatswain.aggregate import summarise
from boatswain.render import to_markdown
from tests.conftest import NOW, make_item


def markdown_for(items):
    return to_markdown(summarise(items, repo="ab00bae/demo", now=NOW))


def test_the_repository_is_in_the_heading():
    assert "# Sprint report — ab00bae/demo" in markdown_for([])


def test_counts_appear_in_the_table():
    markdown = markdown_for([make_item(1), make_item(2)])

    assert "| Issues opened | 2 |" in markdown


def test_stale_issues_get_their_own_section():
    markdown = markdown_for(
        [make_item(1, created_days_ago=60, updated_days_ago=40, title="Old thing")]
    )

    assert "## Stale issues" in markdown
    assert "Old thing" in markdown


def test_no_stale_issues_says_so_rather_than_showing_an_empty_table():
    markdown = markdown_for([make_item(1, updated_days_ago=0)])

    assert "None — every open issue saw activity." in markdown


def test_backlog_direction_is_spelled_out():
    markdown = markdown_for([make_item(1), make_item(2)])

    assert "backlog grew" in markdown


def test_merge_rate_is_omitted_when_undefined():
    """A repository with no decided pull requests should not show 0%."""
    markdown = markdown_for([make_item(1, is_pull_request=True)])

    assert "Merge rate" not in markdown


def test_merge_rate_is_shown_as_a_percentage():
    markdown = markdown_for(
        [
            make_item(1, is_pull_request=True, closed_days_ago=1, merged=True),
            make_item(2, is_pull_request=True, closed_days_ago=1, merged=False),
        ]
    )

    assert "| Merge rate | 50% |" in markdown


def test_non_ascii_titles_survive():
    """GitHub titles carry emoji; they must not be mangled or crash the render."""
    markdown = markdown_for(
        [make_item(1, created_days_ago=60, updated_days_ago=40, title="🚀 Roadmap → v2")]
    )

    assert "🚀 Roadmap → v2" in markdown


def test_markdown_tables_are_well_formed():
    """Every row in the metrics table must have the same column count."""
    markdown = markdown_for([make_item(1)])
    rows = [
        line for line in markdown.splitlines()
        if line.startswith("|") and "---" not in line
    ]

    assert rows
    assert all(row.count("|") == 3 for row in rows)
