"""Command line interface."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated

import typer

from boatswain import __version__, render
from boatswain.aggregate import summarise
from boatswain.github import GitHubClient, GitHubError, load_fixture, resolve_token

app = typer.Typer(
    help="Sprint status reports from GitHub issues and pull requests.",
    no_args_is_help=True,
    add_completion=False,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"boatswain {__version__}")
        raise typer.Exit()


def _force_utf8_output() -> None:
    """Make the output streams able to carry the characters GitHub returns.

    On Windows a redirected stdout defaults to cp1252, which cannot encode the
    emoji and arrows that appear routinely in issue titles. Without this the
    tool works interactively and then crashes the moment anyone pipes it to a
    file — the exact thing a report generator is for.
    """
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                # A stream that refuses reconfiguration is not worth failing on.
                pass


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version, is_eager=True,
                     help="Show the version and exit."),
    ] = False,
) -> None:
    _force_utf8_output()


@app.command()
def report(
    repo: Annotated[
        str, typer.Option("--repo", "-r", help="Repository as owner/name.")
    ],
    sprint_days: Annotated[
        int, typer.Option("--sprint-days", "-d", min=1,
                          help="Length of the reporting window in days.")
    ] = 14,
    stale_days: Annotated[
        int, typer.Option("--stale-days", min=1,
                          help="Idle days before an open issue counts as stale.")
    ] = 14,
    out: Annotated[
        Path | None, typer.Option("--out", "-o", help="Write markdown to this file.")
    ] = None,
    token: Annotated[
        str | None, typer.Option("--token", help="GitHub token. Defaults to "
                                 "GITHUB_TOKEN, then the gh CLI.")
    ] = None,
    fixture: Annotated[
        Path | None,
        typer.Option("--fixture", help="Read a saved JSON payload instead of "
                     "calling the API. Used by the demo so it needs no network."),
    ] = None,
    as_of: Annotated[
        str | None,
        typer.Option("--now", help="Treat this ISO-8601 instant as the present, "
                     "to reproduce a report for a past sprint."),
    ] = None,
) -> None:
    """Summarise recent issue and pull request activity for a repository."""
    if as_of is None:
        now = datetime.now(timezone.utc)
    else:
        try:
            now = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        except ValueError as exc:
            render.console.print(
                f"[red]--now is not an ISO-8601 timestamp:[/red] {as_of!r}"
            )
            raise typer.Exit(code=2) from exc
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

    if fixture is not None:
        if not fixture.exists():
            render.console.print(f"[red]Fixture not found:[/red] {fixture}")
            raise typer.Exit(code=2)
        items = load_fixture(fixture)
    else:
        resolved = resolve_token(token)
        if resolved is None:
            render.console.print(
                "[yellow]No GitHub token found.[/yellow] Proceeding unauthenticated; "
                "expect a low rate limit on public repositories."
            )
        try:
            with GitHubClient(resolved) as client:
                items = client.fetch_items(
                    repo, since=now - timedelta(days=sprint_days)
                )
        except GitHubError as exc:
            render.console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1) from exc

    summary = summarise(
        items, repo=repo, now=now, sprint_days=sprint_days, stale_days=stale_days
    )

    render.to_terminal(summary)

    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render.to_markdown(summary), encoding="utf-8")
        render.console.print(f"[green]Wrote[/green] {out}\n")


if __name__ == "__main__":
    app()
