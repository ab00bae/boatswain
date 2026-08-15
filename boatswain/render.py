"""Rendering a report, for a terminal or for a file.

Both renderers read the same `Report`, so the markdown written to a file and the
table printed to a terminal can never disagree about the numbers.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from boatswain.models import Item, Report

console = Console()


def _trend(net: int) -> str:
    """Backlog direction. Fewer open issues at the end of a sprint is the win."""
    if net > 0:
        return f"+{net} (backlog grew)"
    if net < 0:
        return f"{net} (backlog shrank)"
    return "0 (unchanged)"


def _title(item: Item, width: int = 48) -> str:
    return item.title if len(item.title) <= width else item.title[: width - 1] + "…"


def to_terminal(report: Report) -> None:
    window = (
        f"{report.window_start:%Y-%m-%d} → {report.generated_at:%Y-%m-%d}"
        f"  ({report.sprint_days} days)"
    )
    console.print(f"\n[bold]{report.repo}[/bold]  [dim]{window}[/dim]")

    table = Table(header_style="bold", show_edge=False, title_style="bold")
    table.add_column("Metric")
    table.add_column("Count", justify="right")

    table.add_row("Issues opened", str(report.issues_opened))
    table.add_row("Issues closed", str(report.issues_closed))
    table.add_row("[dim]Net change[/dim]", f"[dim]{_trend(report.issue_net_change)}[/dim]")
    table.add_row("Issues still open", str(report.issues_open_total))
    table.add_section()
    table.add_row("PRs opened", str(report.prs_opened))
    table.add_row("PRs merged", str(report.prs_merged))
    table.add_row("PRs closed unmerged", str(report.prs_closed_unmerged))
    table.add_row("PRs still open", str(report.prs_open_total))

    if (rate := report.pr_merge_rate) is not None:
        table.add_row("[dim]Merge rate[/dim]", f"[dim]{rate:.0%}[/dim]")

    console.print()
    console.print(table)

    if report.stale_issues:
        stale = Table(
            title=f"Stale — open, untouched for {report.stale_days}+ days",
            title_style="bold yellow",
            header_style="bold",
            show_edge=False,
        )
        stale.add_column("#", justify="right")
        stale.add_column("Title")
        stale.add_column("Idle", justify="right")

        for item in report.stale_issues:
            stale.add_row(
                str(item.number),
                _title(item),
                f"{item.idle_days(report.generated_at)}d",
            )

        console.print()
        console.print(stale)

    if report.top_contributors:
        contributors = ", ".join(
            f"{name} ({count})" for name, count in report.top_contributors
        )
        console.print(f"\n[bold]Most active[/bold]  [dim]{contributors}[/dim]")

    console.print()


def to_markdown(report: Report) -> str:
    lines = [
        f"# Sprint report — {report.repo}",
        "",
        f"**Window:** {report.window_start:%Y-%m-%d} → {report.generated_at:%Y-%m-%d} "
        f"({report.sprint_days} days)",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Issues opened | {report.issues_opened} |",
        f"| Issues closed | {report.issues_closed} |",
        f"| Net change | {_trend(report.issue_net_change)} |",
        f"| Issues still open | {report.issues_open_total} |",
        f"| PRs opened | {report.prs_opened} |",
        f"| PRs merged | {report.prs_merged} |",
        f"| PRs closed unmerged | {report.prs_closed_unmerged} |",
        f"| PRs still open | {report.prs_open_total} |",
    ]

    if (rate := report.pr_merge_rate) is not None:
        lines.append(f"| Merge rate | {rate:.0%} |")

    lines.append("")

    if report.stale_issues:
        lines += [
            f"## Stale issues (open, untouched for {report.stale_days}+ days)",
            "",
            "| # | Title | Idle |",
            "| ---: | --- | ---: |",
        ]
        lines += [
            f"| {item.number} | {item.title} | "
            f"{item.idle_days(report.generated_at)}d |"
            for item in report.stale_issues
        ]
        lines.append("")
    else:
        lines += ["## Stale issues", "", "None — every open issue saw activity.", ""]

    if report.top_contributors:
        lines += ["## Most active", ""]
        lines += [
            f"- {name} — {count} item(s) opened"
            for name, count in report.top_contributors
        ]
        lines.append("")

    return "\n".join(lines)
